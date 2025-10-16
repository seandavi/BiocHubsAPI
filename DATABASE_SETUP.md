# Database Setup Guide

This guide covers setting up the PostgreSQL database for the BiocHubs API using the new normalized schema.

## Prerequisites

- PostgreSQL server running (tested with PostgreSQL 14+)
- `POSTGRES_URI` environment variable set in `.env`

Example `.env` configuration:
```bash
POSTGRES_URI=postgresql://postgres@localhost:5432/biochubs
```

## Quick Start

### Initialize New Database

To create the schema and seed initial data in one command:

```bash
uv run hubs-api db init
```

This will:
1. Create all database tables from SQLAlchemy models
2. Seed initial reference data (hubs, statuses, bioc releases)
3. Verify the schema is correct

### Reset Database (Destructive)

To drop and recreate everything:

```bash
uv run hubs-api db init --drop-existing
```

⚠️ **Warning**: This will delete all existing data!

## Individual Commands

### Create Schema

Create database tables without seeding data:

```bash
uv run hubs-api db create-schema
```

### Seed Data

Add initial reference data (hubs, statuses, bioc releases, system user):

```bash
uv run hubs-api db seed
```

### Verify Schema

Check that the database schema matches the SQLAlchemy models:

```bash
uv run hubs-api db verify
```

### Show Statistics

Display record counts for all tables:

```bash
uv run hubs-api db stats
```

Example output:
```
Database Statistics
====================================

Infrastructure
  hubs                      : 2
  resource_statuses         : 10
  bioc_releases             : 3

Organizations & Users
  organizations             : 1
  users                     : 1

Taxonomy
  species                   : 0
  genomes                   : 0

...

Total Records              : 17
```

## Database URL Options

All commands accept `--database-url` to override the environment variable:

```bash
uv run hubs-api db stats --database-url postgresql://localhost/test_db
```

If `POSTGRES_URI` is set in your environment, you can omit this option.

## Initial Data Seeded

After running `db init` or `db seed`, the following reference data is created:

### Hubs (2 records)
- **AnnotationHub** (code: AH) - Annotation resources for genomic data
- **ExperimentHub** (code: EH) - Experimental data and workflows

### Resource Statuses (10 records)
1. Public
2. Unreviewed
3. Private
10. Removed from original web location
11. Removed by author request
12. Moved from AnnotationHub to ExperimentHub
13. Replaced by more current version
14. Invalid metadata
15. Did not make review deadline for biocversion
99. Defunct

### Bioconductor Releases (3 records)
- **3.18** (released 2023-10-25, R 4.3+)
- **3.19** (released 2024-05-01, R 4.4+)
- **3.20** (released 2024-10-30, R 4.4+, current)

### System User
- **Email**: system@bioconductor.org
- **Role**: admin
- **Purpose**: Used for data migration and automated processes

## Next Steps

After initializing the database:

1. **Migrate existing data** from SQLite to PostgreSQL (migration scripts coming soon)
2. **Start the API server**: `uv run hubs-api serve`
3. **Explore the API**: Visit `http://localhost:8000/docs`

## Troubleshooting

### Connection Errors

If you get connection errors, verify:

1. PostgreSQL is running: `pg_isready`
2. Database exists: `psql -l | grep biochubs`
3. Connection string is correct: `echo $POSTGRES_URI`

Create database if needed:
```bash
createdb biochubs
```

### Permission Errors

Ensure your PostgreSQL user has CREATE privileges:

```sql
GRANT ALL PRIVILEGES ON DATABASE biochubs TO your_username;
```

### Schema Conflicts

If you encounter schema conflicts, use `--drop-existing` to start fresh:

```bash
uv run hubs-api db init --drop-existing
```

## Schema Details

See `POSTGRES_SCHEMA_DESIGN.md` for complete schema documentation, including:
- Entity-relationship diagrams
- Normalization strategy
- Performance optimization
- Migration planning
