# BiocHubsAPI Project Context

## Project Overview
This project provides a RESTful API for accessing and querying Bioconductor Hub resources (AnnotationHub and ExperimentHub). The Bioconductor Hubs host over 100,000 curated genomic data resources including annotations, experimental datasets, and reference genomes.

## Current State
- **Database**: SQLite (annotationhub.sqlite3, experimenthub.sqlite3)
- **Scale**: ~117,000 resources in AnnotationHub, similar in ExperimentHub
- **Tech Stack**: Python 3.11+, FastAPI, SQLAlchemy (async), uvicorn, loguru
- **Package Manager**: uv (not pip/poetry)
- **API**: Basic CRUD with filtering, pagination, sorting on `/resources` endpoint

## Migration Goal
Migrating from SQLite to PostgreSQL with:
- Full normalization (users, organizations, species, genomes, providers)
- Temporal versioning and provenance tracking
- Submission/curation workflow
- Materialized views for performance
- Multi-hub support (AnnotationHub, ExperimentHub)

## Key Files
- `src/hubs_api/api.py` - FastAPI application
- `src/hubs_api/models.py` - SQLAlchemy models
- `src/hubs_api/pydantic_models.py` - Pydantic schemas
- `src/hubs_api/cli.py` - CLI commands
- `POSTGRES_SCHEMA_DESIGN.md` - New schema design document
- `API_USAGE.md` - API documentation

## Database Schema (Current SQLite)
- `resources` - Core resource metadata (ah_id, title, species, genome, description)
- `tags` - Resource tags (many-to-many)
- `rdatapaths` - File paths and R data classes
- `input_sources` - Source file metadata
- `biocversions` - Bioconductor version compatibility
- `recipes`, `statuses`, `location_prefixes` - Lookup tables

## Environment
- Database connection: `POSTGRES_URI` in `.env` file
- CLI command: `hubs-api serve` to start API server
- Dev mode: `hubs-api serve --reload`
