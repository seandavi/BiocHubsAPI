# Google Cloud Run Deployment Guide

This directory contains configuration and scripts for deploying the Bioconductor Hubs API to Google Cloud Run.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and configured
- Docker installed (for building images)
- A Google Cloud Project with billing enabled
- Cloud Run API enabled: `gcloud services enable run.googleapis.com`
- Artifact Registry API enabled: `gcloud services enable artifactregistry.googleapis.com`
- A PostgreSQL database (Cloud SQL recommended)

## Quick Start

### 1. Set Up Environment Variables

Copy the example environment file and configure it:

```bash
cp .env.cloudrun.example .env.cloudrun
# Edit .env.cloudrun with your values
```

Required environment variables:
- `GCP_PROJECT_ID`: Your Google Cloud project ID
- `GCP_REGION`: Cloud Run region (e.g., `us-central1`)
- `SERVICE_NAME`: Name for your Cloud Run service (default: `biochubs-api`)
- `POSTGRES_URI`: PostgreSQL connection string
- `ARTIFACT_REGISTRY_REPO`: Artifact Registry repository name (default: `biochubs`)

### 2. Set Up Cloud SQL (Recommended)

Create a Cloud SQL PostgreSQL instance:

```bash
# Create instance
gcloud sql instances create biochubs-db \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region=us-central1

# Create database
gcloud sql databases create hubs_dev --instance=biochubs-db

# Set password for postgres user
gcloud sql users set-password postgres \
    --instance=biochubs-db \
    --password=YOUR_SECURE_PASSWORD
```

Get the instance connection name:
```bash
gcloud sql instances describe biochubs-db --format="value(connectionName)"
```

### 3. Build and Push Docker Image

The deployment script handles this automatically, but you can do it manually:

```bash
# Authenticate Docker with Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build and push
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/biochubs/biochubs-api:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/biochubs/biochubs-api:latest
```

### 4. Deploy to Cloud Run

Use the provided deployment script:

```bash
# Make the script executable
chmod +x cloudrun/deploy.sh

# Deploy
./cloudrun/deploy.sh
```

Or deploy manually:

```bash
gcloud run deploy biochubs-api \
    --image=us-central1-docker.pkg.dev/YOUR_PROJECT/biochubs/biochubs-api:latest \
    --platform=managed \
    --region=us-central1 \
    --allow-unauthenticated \
    --set-env-vars=POSTGRES_URI="postgresql://postgres:PASSWORD@/hubs_dev?host=/cloudsql/PROJECT:REGION:INSTANCE" \
    --add-cloudsql-instances=PROJECT:REGION:INSTANCE \
    --port=8000 \
    --memory=1Gi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=10 \
    --timeout=300
```

### 5. Initialize Database

Once deployed, initialize the database schema:

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe biochubs-api --region=us-central1 --format="value(status.url)")

# The database should be initialized using Cloud Run jobs or by exec into a container
# For initial setup, you can use Cloud Shell or a local connection:
export POSTGRES_URI="postgresql://postgres:PASSWORD@/hubs_dev?host=/cloudsql/PROJECT:REGION:INSTANCE"
uv run hubs-api db init
```

## Configuration

### Environment Variables

The following environment variables can be configured for Cloud Run:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `POSTGRES_URI` | PostgreSQL connection string | Yes | - |
| `LOG_LEVEL` | Logging level | No | `info` |
| `PORT` | Port to listen on | No | `8000` |

### Cloud SQL Connection

For Cloud SQL, use the Unix socket connection format:

```
postgresql://USER:PASSWORD@/DATABASE?host=/cloudsql/PROJECT:REGION:INSTANCE
```

Example:
```
postgresql://postgres:mypassword@/hubs_dev?host=/cloudsql/my-project:us-central1:biochubs-db
```

### Resource Limits

Default resource allocation:
- Memory: 1 GiB
- CPU: 1 vCPU
- Min instances: 0 (scales to zero)
- Max instances: 10
- Request timeout: 300 seconds

Adjust these in `deploy.sh` or via `gcloud run services update`.

## Using the Deployment Script

The `deploy.sh` script automates the entire deployment process:

```bash
# Deploy with all steps
./cloudrun/deploy.sh

# Skip image build (use existing image)
./cloudrun/deploy.sh --skip-build

# Use a specific tag
./cloudrun/deploy.sh --tag=v1.0.0

# Deploy to a different region
GCP_REGION=us-east1 ./cloudrun/deploy.sh
```

The script will:
1. Load configuration from `.env.cloudrun`
2. Create Artifact Registry repository if needed
3. Build and push Docker image
4. Deploy to Cloud Run with configured settings
5. Display the service URL

## Service Configuration Template

You can also deploy using a YAML service definition:

```bash
gcloud run services replace cloudrun/service.yaml
```

Edit `service.yaml` to customize your deployment configuration.

## Scaling and Performance

### Auto-scaling

Cloud Run automatically scales based on:
- Incoming request volume
- CPU utilization
- Memory usage

Configure scaling parameters:

```bash
gcloud run services update biochubs-api \
    --region=us-central1 \
    --min-instances=1 \
    --max-instances=20 \
    --concurrency=80
```

### Cold Starts

To minimize cold starts:
- Set `--min-instances=1` to keep at least one instance warm
- Use smaller images (current multi-stage build is optimized)
- Keep dependencies minimal

### Database Connection Pooling

For Cloud SQL, consider:
- Using connection poolers (PgBouncer)
- Limiting max connections per instance
- Adjusting `max-instances` based on database capacity

## Monitoring and Logging

### View Logs

```bash
# Real-time logs
gcloud run services logs tail biochubs-api --region=us-central1

# Recent logs
gcloud run services logs read biochubs-api --region=us-central1 --limit=50
```

### Metrics

View metrics in Cloud Console:
```bash
# Open metrics in browser
gcloud run services describe biochubs-api --region=us-central1 --format="value(status.url)"
```

Or use Cloud Monitoring API for custom dashboards.

### Health Checks

Cloud Run automatically uses the `/health` endpoint for health checks. Monitor:
- Container startup time
- Request latency
- Error rates

## Security

### Authentication

By default, the service is deployed with `--allow-unauthenticated`. For production:

```bash
# Require authentication
gcloud run services update biochubs-api \
    --region=us-central1 \
    --no-allow-unauthenticated

# Add IAM policy for specific users/groups
gcloud run services add-iam-policy-binding biochubs-api \
    --region=us-central1 \
    --member="user:email@example.com" \
    --role="roles/run.invoker"
```

### Secrets Management

Use Secret Manager instead of environment variables for sensitive data:

```bash
# Create secret
echo -n "postgresql://user:pass@..." | gcloud secrets create postgres-uri --data-file=-

# Grant access to Cloud Run
gcloud secrets add-iam-policy-binding postgres-uri \
    --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Deploy with secret
gcloud run deploy biochubs-api \
    --set-secrets=POSTGRES_URI=postgres-uri:latest \
    ...
```

### VPC Connector

For private database access via VPC:

```bash
# Create VPC connector
gcloud compute networks vpc-access connectors create biochubs-connector \
    --region=us-central1 \
    --network=default \
    --range=10.8.0.0/28

# Deploy with VPC connector
gcloud run deploy biochubs-api \
    --vpc-connector=biochubs-connector \
    --vpc-egress=private-ranges-only \
    ...
```

## Cost Optimization

Cloud Run pricing is based on:
- Request count
- Compute time (CPU + memory)
- Network egress

Optimization tips:
1. Set appropriate min/max instances
2. Use the smallest instance size that meets performance needs
3. Enable CPU throttling when idle: `--cpu-throttling` (default)
4. Monitor and adjust based on actual usage
5. Consider Cloud SQL edition (Enterprise vs Standard)

## Troubleshooting

### Deployment Failures

Check deployment logs:
```bash
gcloud run services describe biochubs-api --region=us-central1
```

Common issues:
- Image not found: Verify Artifact Registry permissions
- Database connection: Check Cloud SQL instance and connection string
- Port mismatch: Ensure app listens on `$PORT` or explicitly set `--port=8000`

### Service Not Responding

1. Check service logs:
```bash
gcloud run services logs read biochubs-api --region=us-central1 --limit=100
```

2. Verify health endpoint:
```bash
SERVICE_URL=$(gcloud run services describe biochubs-api --region=us-central1 --format="value(status.url)")
curl $SERVICE_URL/health
```

3. Check Cloud SQL connectivity:
```bash
gcloud sql operations list --instance=biochubs-db
```

### Database Connection Errors

- Verify Cloud SQL instance is running
- Check connection string format
- Ensure Cloud Run service account has Cloud SQL Client role
- Verify `--add-cloudsql-instances` parameter is correct

## Updates and Rollbacks

### Deploy New Version

```bash
./cloudrun/deploy.sh --tag=v2.0.0
```

### Rollback

```bash
# List revisions
gcloud run revisions list --service=biochubs-api --region=us-central1

# Route all traffic to previous revision
gcloud run services update-traffic biochubs-api \
    --region=us-central1 \
    --to-revisions=biochubs-api-00001-abc=100
```

### Gradual Rollout

```bash
# Split traffic between versions
gcloud run services update-traffic biochubs-api \
    --region=us-central1 \
    --to-revisions=biochubs-api-00002-def=90,biochubs-api-00001-abc=10
```

## CI/CD Integration

### GitHub Actions Example

**Recommended: Using Workload Identity Federation (more secure)**

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

permissions:
  contents: read
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: 'projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL/providers/PROVIDER'
          service_account: 'SERVICE_ACCOUNT@PROJECT.iam.gserviceaccount.com'
      
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2
      
      - name: Build and Push
        run: |
          gcloud auth configure-docker us-central1-docker.pkg.dev
          docker build -t us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT }}/biochubs/biochubs-api:${{ github.sha }} .
          docker push us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT }}/biochubs/biochubs-api:${{ github.sha }}
      
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy biochubs-api \
            --image=us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT }}/biochubs/biochubs-api:${{ github.sha }} \
            --region=us-central1 \
            --platform=managed
```

**Alternative: Using Service Account Key (less secure)**

If you cannot use Workload Identity Federation:

```yaml
- id: auth
  uses: google-github-actions/auth@v2
  with:
    credentials_json: ${{ secrets.GCP_SA_KEY }}
```

See [Workload Identity Federation setup](https://github.com/google-github-actions/auth#setup) for configuration details.

## Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres)
- [Artifact Registry](https://cloud.google.com/artifact-registry/docs)
- [Secret Manager](https://cloud.google.com/secret-manager/docs)
- [Cloud Run Pricing](https://cloud.google.com/run/pricing)

## Support

For issues specific to the BiocHubs API deployment, please open an issue on the GitHub repository.
