## BiocHubs API

This project provides a RESTful API for accessing and querying Bioconductor Hub (AnnotationHub, ExperimentHub) resources.

The Bioconductor Hubs are a collection of curated, versioned, and easily accessible genomic data resources for the R/Bioconductor ecosystem. 
The current system hosts over 100,000 resources including genomic annotations, experimental datasets, and reference genomes in various formats (e.g., FASTA, GTF, BAM, VCF).
The data are currently stored in SQLite databases with a minimal relational schema.
The goal is to convert these to a more robust and scalable backend (Postgres) and provide a modern API for accessing the data.

Over time, we plan to add more features such as authentication, user accounts, data submission, validation, curation, versioning, and more.

## Try me

You can try out the API (which may be down at times) at <https://ahub-api.cancerdatasci.org/docs> or to list resources at <https://ahub-api.cancerdatasci.org/api/v2/resources>

## Deployment Options

The BiocHubs API can be deployed in multiple ways. **[See detailed comparison →](DEPLOYMENT_COMPARISON.md)**

### 1. **Google Cloud Run** (Recommended for production)
Serverless, automatically scalable deployment on Google Cloud Platform.

- **Quick Start**: See [Cloud Run Deployment Guide](cloudrun/README.md)
- **One-command deploy**: `./cloudrun/deploy.sh`
- **Features**: Auto-scaling, pay-per-use, zero ops, Cloud SQL integration

```bash
# Quick deployment
cp .env.cloudrun.example .env.cloudrun
# Edit .env.cloudrun with your settings
./cloudrun/deploy.sh
```

### 2. **Kubernetes**
Full control deployment for on-premises or cloud Kubernetes clusters.

- **Guide**: See [Kubernetes Deployment Guide](k8s/README.md)
- **Includes**: PostgreSQL StatefulSet, API Deployment, Services, Ingress
- **Best for**: On-premises, multi-cloud, or existing K8s infrastructure

```bash
# Quick deployment with justfile
just setup
```

### 3. **Docker Standalone**
Simple containerized deployment for development or small-scale production.

```bash
# Build and run locally
docker build -t biochubs-api .
docker run -p 8000:8000 -e POSTGRES_URI="postgresql://user:pass@host/db" biochubs-api
```

### 4. **Local Development**
Direct Python execution for development and testing.

```bash
# Install dependencies
uv sync

# Run development server with auto-reload
uv run hubs-api serve --reload

# Or use justfile
just dev
```

## Environment Configuration

All deployment methods use the `POSTGRES_URI` environment variable for database configuration:

```bash
# Standard PostgreSQL
POSTGRES_URI="postgresql://user:password@host:5432/database"

# Cloud SQL (Google Cloud Run)
POSTGRES_URI="postgresql://user:password@/database?host=/cloudsql/project:region:instance"

# With async driver (automatically converted by the app)
POSTGRES_URI="postgresql+asyncpg://user:password@host:5432/database"
```