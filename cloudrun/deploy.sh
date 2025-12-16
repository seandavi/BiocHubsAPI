#!/usr/bin/env bash
#
# deploy.sh - Deploy BiocHubs API to Google Cloud Run
#
# This script automates the deployment of the BiocHubs API to Google Cloud Run.
# It handles image building, pushing to Artifact Registry, and service deployment.
#
# Usage:
#   ./cloudrun/deploy.sh [OPTIONS]
#
# Options:
#   --skip-build    Skip Docker image build step
#   --tag=TAG       Use specific image tag (default: latest)
#   --help          Show this help message
#
# Environment variables (can be set in .env.cloudrun):
#   GCP_PROJECT_ID         - Google Cloud project ID (required)
#   GCP_REGION             - Cloud Run region (default: us-central1)
#   SERVICE_NAME           - Cloud Run service name (default: biochubs-api)
#   ARTIFACT_REGISTRY_REPO - Artifact Registry repository (default: biochubs)
#   POSTGRES_URI           - PostgreSQL connection string (required)
#   CLOUD_SQL_INSTANCE     - Cloud SQL instance connection name (optional)
#   MIN_INSTANCES          - Minimum instances (default: 0)
#   MAX_INSTANCES          - Maximum instances (default: 10)
#   MEMORY                 - Memory limit (default: 1Gi)
#   CPU                    - CPU limit (default: 1)
#   TIMEOUT                - Request timeout in seconds (default: 300)
#   ALLOW_UNAUTHENTICATED  - Allow public access (default: true)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DEFAULT_REGION="us-central1"
DEFAULT_SERVICE_NAME="biochubs-api"
DEFAULT_ARTIFACT_REPO="biochubs"
DEFAULT_MIN_INSTANCES="0"
DEFAULT_MAX_INSTANCES="10"
DEFAULT_MEMORY="1Gi"
DEFAULT_CPU="1"
DEFAULT_TIMEOUT="300"
DEFAULT_ALLOW_UNAUTH="true"
IMAGE_TAG="latest"
SKIP_BUILD=false

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse command line arguments
for arg in "$@"; do
    case $arg in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --tag=*)
            IMAGE_TAG="${arg#*=}"
            shift
            ;;
        --help)
            grep '^#' "$0" | grep -v '#!/' | sed 's/^# //'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Load environment from .env.cloudrun if it exists
ENV_FILE="$PROJECT_ROOT/.env.cloudrun"
if [ -f "$ENV_FILE" ]; then
    echo -e "${BLUE}Loading configuration from $ENV_FILE${NC}"
    # Export variables from .env.cloudrun, ignoring comments and empty lines
    set -a
    source <(grep -v '^#' "$ENV_FILE" | grep -v '^$')
    set +a
else
    echo -e "${YELLOW}Warning: .env.cloudrun not found. Using environment variables and defaults.${NC}"
fi

# Set variables with defaults
GCP_PROJECT_ID="${GCP_PROJECT_ID:-}"
GCP_REGION="${GCP_REGION:-$DEFAULT_REGION}"
SERVICE_NAME="${SERVICE_NAME:-$DEFAULT_SERVICE_NAME}"
ARTIFACT_REGISTRY_REPO="${ARTIFACT_REGISTRY_REPO:-$DEFAULT_ARTIFACT_REPO}"
MIN_INSTANCES="${MIN_INSTANCES:-$DEFAULT_MIN_INSTANCES}"
MAX_INSTANCES="${MAX_INSTANCES:-$DEFAULT_MAX_INSTANCES}"
MEMORY="${MEMORY:-$DEFAULT_MEMORY}"
CPU="${CPU:-$DEFAULT_CPU}"
TIMEOUT="${TIMEOUT:-$DEFAULT_TIMEOUT}"
ALLOW_UNAUTHENTICATED="${ALLOW_UNAUTHENTICATED:-$DEFAULT_ALLOW_UNAUTH}"
POSTGRES_URI="${POSTGRES_URI:-}"
CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-}"

# Validate required variables
if [ -z "$GCP_PROJECT_ID" ]; then
    echo -e "${RED}Error: GCP_PROJECT_ID is required${NC}"
    echo "Set it in .env.cloudrun or as an environment variable"
    exit 1
fi

if [ -z "$POSTGRES_URI" ]; then
    echo -e "${RED}Error: POSTGRES_URI is required${NC}"
    echo "Set it in .env.cloudrun or as an environment variable"
    exit 1
fi

# Construct image URL
IMAGE_URL="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${SERVICE_NAME}:${IMAGE_TAG}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}BiocHubs API - Cloud Run Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Project ID:        $GCP_PROJECT_ID"
echo "  Region:            $GCP_REGION"
echo "  Service Name:      $SERVICE_NAME"
echo "  Image:             $IMAGE_URL"
echo "  Min Instances:     $MIN_INSTANCES"
echo "  Max Instances:     $MAX_INSTANCES"
echo "  Memory:            $MEMORY"
echo "  CPU:               $CPU"
echo "  Timeout:           ${TIMEOUT}s"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set gcloud project
echo -e "${BLUE}Setting gcloud project to $GCP_PROJECT_ID...${NC}"
gcloud config set project "$GCP_PROJECT_ID"

# Enable required APIs
echo -e "${BLUE}Ensuring required APIs are enabled...${NC}"
gcloud services enable run.googleapis.com --quiet
gcloud services enable artifactregistry.googleapis.com --quiet

# Create Artifact Registry repository if it doesn't exist
echo -e "${BLUE}Checking Artifact Registry repository...${NC}"
if ! gcloud artifacts repositories describe "$ARTIFACT_REGISTRY_REPO" --location="$GCP_REGION" &> /dev/null; then
    echo -e "${YELLOW}Creating Artifact Registry repository: $ARTIFACT_REGISTRY_REPO${NC}"
    gcloud artifacts repositories create "$ARTIFACT_REGISTRY_REPO" \
        --repository-format=docker \
        --location="$GCP_REGION" \
        --description="BiocHubs API container images"
else
    echo -e "${GREEN}✓ Artifact Registry repository exists${NC}"
fi

# Configure Docker authentication
echo -e "${BLUE}Configuring Docker authentication for Artifact Registry...${NC}"
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

# Build and push image
if [ "$SKIP_BUILD" = false ]; then
    echo -e "${BLUE}Building Docker image...${NC}"
    cd "$PROJECT_ROOT"
    docker build -t "$IMAGE_URL" .
    
    echo -e "${BLUE}Pushing image to Artifact Registry...${NC}"
    docker push "$IMAGE_URL"
    echo -e "${GREEN}✓ Image pushed successfully${NC}"
else
    echo -e "${YELLOW}Skipping image build (--skip-build specified)${NC}"
fi

# Prepare gcloud run deploy command
DEPLOY_CMD="gcloud run deploy $SERVICE_NAME \
    --image=$IMAGE_URL \
    --platform=managed \
    --region=$GCP_REGION \
    --port=8000 \
    --memory=$MEMORY \
    --cpu=$CPU \
    --min-instances=$MIN_INSTANCES \
    --max-instances=$MAX_INSTANCES \
    --timeout=$TIMEOUT \
    --set-env-vars=POSTGRES_URI=\"$POSTGRES_URI\""

# Add Cloud SQL instance if specified
if [ -n "$CLOUD_SQL_INSTANCE" ]; then
    DEPLOY_CMD="$DEPLOY_CMD --add-cloudsql-instances=$CLOUD_SQL_INSTANCE"
    echo "  Cloud SQL:         $CLOUD_SQL_INSTANCE"
fi

# Add authentication setting
if [ "$ALLOW_UNAUTHENTICATED" = "true" ]; then
    DEPLOY_CMD="$DEPLOY_CMD --allow-unauthenticated"
    echo "  Authentication:    Public (unauthenticated)"
else
    DEPLOY_CMD="$DEPLOY_CMD --no-allow-unauthenticated"
    echo "  Authentication:    Required"
fi

echo ""
echo -e "${BLUE}Deploying to Cloud Run...${NC}"

# Execute deployment
eval "$DEPLOY_CMD"

# Get service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$GCP_REGION" \
    --format="value(status.url)" 2>/dev/null || echo "")

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

if [ -n "$SERVICE_URL" ]; then
    echo ""
    echo -e "${GREEN}Service URL:${NC} $SERVICE_URL"
    echo ""
    echo -e "${GREEN}Test endpoints:${NC}"
    echo "  Health:    $SERVICE_URL/health"
    echo "  API Docs:  $SERVICE_URL/docs"
    echo "  Resources: $SERVICE_URL/api/v2/resources?limit=5"
    echo ""
    echo -e "${YELLOW}Note: If this is a fresh deployment, you need to initialize the database:${NC}"
    echo "  1. Connect to your PostgreSQL instance"
    echo "  2. Run: POSTGRES_URI=\"your-connection-string\" uv run hubs-api db init"
fi

echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "  View logs:         gcloud run services logs tail $SERVICE_NAME --region=$GCP_REGION"
echo "  Update service:    gcloud run services update $SERVICE_NAME --region=$GCP_REGION"
echo "  Delete service:    gcloud run services delete $SERVICE_NAME --region=$GCP_REGION"
echo ""
