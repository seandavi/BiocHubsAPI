# Quick Start Guide - Google Cloud Run

This guide provides the fastest path to deploying BiocHubs API on Google Cloud Run.

## Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed
- [Docker](https://docs.docker.com/get-docker/) installed
- Google Cloud project with billing enabled

## 5-Minute Deployment

### 1. Setup Configuration

```bash
# Copy the template
cp .env.cloudrun.example .env.cloudrun

# Edit with your values (use your favorite editor)
nano .env.cloudrun
```

**Minimal required configuration:**
```bash
GCP_PROJECT_ID=your-project-id
POSTGRES_URI=postgresql://user:password@host:5432/database
```

### 2. Create Cloud SQL Database (Optional but Recommended)

```bash
# Set project
gcloud config set project your-project-id

# Create Cloud SQL instance (takes ~5 minutes)
gcloud sql instances create biochubs-db \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region=us-central1

# Create database
gcloud sql databases create hubs_dev --instance=biochubs-db

# Set password
gcloud sql users set-password postgres \
    --instance=biochubs-db \
    --password=$(openssl rand -base64 32)

# Get connection details
gcloud sql instances describe biochubs-db
```

Update `.env.cloudrun` with Cloud SQL connection string:
```bash
POSTGRES_URI=postgresql://postgres:YOUR_PASSWORD@/hubs_dev?host=/cloudsql/PROJECT:REGION:biochubs-db
CLOUD_SQL_INSTANCE=PROJECT:REGION:biochubs-db
```

### 3. Deploy

```bash
# Make script executable (if needed)
chmod +x cloudrun/deploy.sh

# Deploy!
./cloudrun/deploy.sh
```

The script will:
- ✓ Validate configuration
- ✓ Enable required Google Cloud APIs
- ✓ Create Artifact Registry repository
- ✓ Build Docker image
- ✓ Push to Artifact Registry
- ✓ Deploy to Cloud Run
- ✓ Show service URL

### 4. Initialize Database

```bash
# Get the Cloud SQL connection string from your .env.cloudrun
export POSTGRES_URI="your-connection-string"

# Initialize schema
uv run hubs-api db init
```

### 5. Test

```bash
# Get your service URL (shown at end of deployment)
SERVICE_URL=$(gcloud run services describe biochubs-api \
    --region=us-central1 --format="value(status.url)")

# Test health endpoint
curl $SERVICE_URL/health

# View API documentation
open $SERVICE_URL/docs

# Query resources
curl "$SERVICE_URL/api/v2/resources?limit=5"
```

## Using Justfile (Alternative)

If you have [just](https://github.com/casey/just) installed:

```bash
# Deploy
just cloudrun-deploy

# View logs
just cloudrun-logs

# Get service URL
just cloudrun-url

# Test health
just cloudrun-health
```

## Common Use Cases

### Development/Testing Deployment

```bash
# Use minimal resources
echo "MIN_INSTANCES=0
MAX_INSTANCES=3
MEMORY=512Mi
CPU=1" >> .env.cloudrun

./cloudrun/deploy.sh
```

### Production Deployment

```bash
# Use more resources and keep warm
echo "MIN_INSTANCES=1
MAX_INSTANCES=20
MEMORY=2Gi
CPU=2
ALLOW_UNAUTHENTICATED=false" >> .env.cloudrun

./cloudrun/deploy.sh
```

### Quick Update (Skip Build)

```bash
# If you only changed environment variables
./cloudrun/deploy.sh --skip-build
```

### Deploy Specific Version

```bash
# Tag and deploy
./cloudrun/deploy.sh --tag=v1.0.0
```

## Monitoring

### View Logs

```bash
# Real-time logs
gcloud run services logs tail biochubs-api --region=us-central1

# Recent logs
gcloud run services logs read biochubs-api --region=us-central1 --limit=100
```

### Check Status

```bash
# Service details
gcloud run services describe biochubs-api --region=us-central1

# List all services
gcloud run services list --region=us-central1
```

### Metrics

View in Cloud Console:
```bash
# Open in browser
gcloud run services describe biochubs-api --region=us-central1 \
    --format="value(status.observedGeneration)"
```

Or visit: https://console.cloud.google.com/run

## Troubleshooting

### Deployment fails with "Image not found"

```bash
# Verify Artifact Registry setup
gcloud artifacts repositories list --location=us-central1

# Check Docker authentication
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### Database connection errors

```bash
# Verify Cloud SQL instance
gcloud sql instances describe biochubs-db

# Check connection string format
echo $POSTGRES_URI

# Test from Cloud Shell
gcloud sql connect biochubs-db --user=postgres
```

### Service not responding

```bash
# Check service status
gcloud run services describe biochubs-api --region=us-central1

# View recent logs
gcloud run services logs read biochubs-api --region=us-central1 --limit=50

# Check health endpoint
curl $(gcloud run services describe biochubs-api --region=us-central1 \
    --format="value(status.url)")/health
```

### Need to rollback

```bash
# List revisions
gcloud run revisions list --service=biochubs-api --region=us-central1

# Route traffic to previous revision
gcloud run services update-traffic biochubs-api --region=us-central1 \
    --to-revisions=REVISION-NAME=100
```

## Clean Up

### Delete Service Only

```bash
gcloud run services delete biochubs-api --region=us-central1
```

### Delete Everything

```bash
# Delete service
gcloud run services delete biochubs-api --region=us-central1

# Delete Cloud SQL instance
gcloud sql instances delete biochubs-db

# Delete Artifact Registry images
gcloud artifacts docker images delete \
    us-central1-docker.pkg.dev/PROJECT/biochubs/biochubs-api --delete-tags
```

## Next Steps

- [Full Documentation](README.md) - Detailed configuration and advanced features
- [Cloud Run Best Practices](https://cloud.google.com/run/docs/tips)
- [Cloud SQL Documentation](https://cloud.google.com/sql/docs)
- Setup CI/CD with GitHub Actions
- Configure custom domain
- Enable authentication
- Set up monitoring and alerting

## Cost Estimation

Free tier includes:
- 2 million requests/month
- 360,000 GB-seconds/month
- 180,000 vCPU-seconds/month

Typical costs for moderate usage:
- Cloud Run: $5-20/month
- Cloud SQL (db-f1-micro): $7-10/month
- Artifact Registry: < $1/month

Total: ~$15-30/month for a small to medium deployment.

Use the [Google Cloud Pricing Calculator](https://cloud.google.com/products/calculator) for detailed estimates.
