# Bioconductor Hub Database Schema Design
## Next Generation PostgreSQL Backend

**Version:** 2.0
**Date:** 2025-10-16
**Status:** Draft

---

## Executive Summary

This document outlines the design for a modernized PostgreSQL database schema for the Bioconductor Hub system (AnnotationHub, ExperimentHub). The new schema addresses limitations of the current SQLite-based system by:

- **Full normalization** of entities (users, organizations, species, genomes)
- **Comprehensive provenance tracking** via audit logs and change history
- **Temporal versioning** with effective dating for all resources
- **CRUD-optimized design** supporting create, update, soft delete operations
- **Query performance** through materialized views and strategic indexing
- **Multi-hub support** with shared infrastructure for AnnotationHub and ExperimentHub

**Current Scale:** ~117,000 resources in AnnotationHub, with similar scale in ExperimentHub.

---

## Design Principles

1. **Normalization First:** Eliminate redundancy, establish clear relationships
2. **Audit Everything:** Track who changed what, when, and why
3. **Never Delete:** Use soft deletes and status transitions for data lifecycle
4. **Temporal Versioning:** Support querying "as of" any point in time
5. **Performance via Views:** Materialize common query patterns
6. **Extensibility:** Design for future features (workflows, citations, reviews)
7. **Multi-tenancy Ready:** Prepare for user accounts and permissions

---

## Core Schema Design

### 1. User & Organization Management

#### `users`
```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(500),
    orcid VARCHAR(19) UNIQUE,  -- ORCID identifier for researchers
    organization_id BIGINT REFERENCES organizations(id),
    role VARCHAR(50) NOT NULL DEFAULT 'user',  -- user, maintainer, curator, admin
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    metadata JSONB  -- extensible attributes (e.g., bio, URLs)
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_orcid ON users(orcid) WHERE orcid IS NOT NULL;
CREATE INDEX idx_users_org ON users(organization_id);
```

#### `organizations`
```sql
CREATE TABLE organizations (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    short_name VARCHAR(100) UNIQUE,
    website VARCHAR(500),
    ror_id VARCHAR(50) UNIQUE,  -- Research Organization Registry ID
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_orgs_short_name ON organizations(short_name);
```

---

### 2. Taxonomy & Genome Reference Data

#### `species`
```sql
CREATE TABLE species (
    id BIGSERIAL PRIMARY KEY,
    scientific_name VARCHAR(500) NOT NULL,
    common_name VARCHAR(500),
    taxonomy_id INTEGER UNIQUE NOT NULL,  -- NCBI Taxonomy ID
    lineage TEXT,  -- Full taxonomic lineage
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB  -- synonyms, strain info, etc.
);

CREATE UNIQUE INDEX idx_species_taxonomy ON species(taxonomy_id);
CREATE INDEX idx_species_scientific ON species(scientific_name);
```

#### `genomes`
```sql
CREATE TABLE genomes (
    id BIGSERIAL PRIMARY KEY,
    species_id BIGINT NOT NULL REFERENCES species(id),
    genome_build VARCHAR(100) NOT NULL,  -- e.g., GRCh38, mm10
    assembly_accession VARCHAR(50),  -- e.g., GCA_000001405.15
    ucsc_name VARCHAR(100),  -- e.g., hg38
    ensembl_name VARCHAR(100),  -- e.g., GRCh38
    is_reference BOOLEAN NOT NULL DEFAULT FALSE,
    release_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB,  -- patch level, aliases, etc.
    UNIQUE(species_id, genome_build)
);

CREATE INDEX idx_genomes_species ON genomes(species_id);
CREATE INDEX idx_genomes_build ON genomes(genome_build);
```

---

### 3. Data Provider & Recipe Infrastructure

#### `data_providers`
```sql
CREATE TABLE data_providers (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL UNIQUE,
    organization_id BIGINT REFERENCES organizations(id),
    url VARCHAR(1000),
    description TEXT,
    contact_email VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_providers_org ON data_providers(organization_id);
```

#### `recipes`
```sql
CREATE TABLE recipes (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    package_name VARCHAR(255),  -- R package implementing recipe
    description TEXT,
    preparer_class VARCHAR(255),  -- e.g., EnsemblFastaImportPreparer
    version VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB  -- configuration, parameters
);

CREATE INDEX idx_recipes_package ON recipes(package_name);
```

---

### 4. Resource Core (Hub-agnostic)

#### `hubs`
```sql
CREATE TABLE hubs (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,  -- AnnotationHub, ExperimentHub
    code VARCHAR(10) NOT NULL UNIQUE,   -- AH, EH
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed data
INSERT INTO hubs (name, code) VALUES
    ('AnnotationHub', 'AH'),
    ('ExperimentHub', 'EH');
```

#### `resource_statuses`
```sql
CREATE TABLE resource_statuses (
    id BIGSERIAL PRIMARY KEY,
    status VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255),
    description TEXT,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,  -- visible to public?
    sort_order INTEGER NOT NULL DEFAULT 0
);

-- Seed from current statuses
INSERT INTO resource_statuses (status, is_public, sort_order) VALUES
    ('Public', TRUE, 1),
    ('Unreviewed', FALSE, 2),
    ('Private', FALSE, 3),
    ('Removed from original web location', FALSE, 10),
    ('Removed by author request', FALSE, 11),
    ('Moved from AnnotationHub to ExperimentHub', FALSE, 12),
    ('Replaced by more current version', FALSE, 13),
    ('Invalid metadata', FALSE, 14),
    ('Did not make review deadline for biocversion', FALSE, 15),
    ('Defunct', FALSE, 99);
```

#### `resources`
Core table for all hub resources with temporal versioning.

```sql
CREATE TABLE resources (
    id BIGSERIAL PRIMARY KEY,
    hub_id BIGINT NOT NULL REFERENCES hubs(id),
    hub_accession VARCHAR(50) NOT NULL,  -- AH5086, EH1234

    -- Core metadata
    title VARCHAR(1000) NOT NULL,
    description TEXT,

    -- Taxonomy & genome
    species_id BIGINT REFERENCES species(id),
    genome_id BIGINT REFERENCES genomes(id),
    coordinate_1_based BOOLEAN,

    -- Provenance
    data_provider_id BIGINT REFERENCES data_providers(id),
    recipe_id BIGINT REFERENCES recipes(id),
    maintainer_id BIGINT REFERENCES users(id),

    -- Status & lifecycle
    status_id BIGINT NOT NULL REFERENCES resource_statuses(id),

    -- Temporal versioning (effective dating)
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMPTZ,  -- NULL = current version
    version_number INTEGER NOT NULL DEFAULT 1,
    superseded_by BIGINT REFERENCES resources(id),  -- link to newer version

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by BIGINT REFERENCES users(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by BIGINT REFERENCES users(id),
    deleted_at TIMESTAMPTZ,  -- soft delete
    deleted_by BIGINT REFERENCES users(id),

    -- Extensibility
    metadata JSONB,  -- additional structured metadata

    UNIQUE(hub_id, hub_accession, version_number),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);

-- Critical indexes for performance
CREATE INDEX idx_resources_hub_accession ON resources(hub_id, hub_accession);
CREATE INDEX idx_resources_status ON resources(status_id);
CREATE INDEX idx_resources_species ON resources(species_id);
CREATE INDEX idx_resources_genome ON resources(genome_id);
CREATE INDEX idx_resources_provider ON resources(data_provider_id);
CREATE INDEX idx_resources_maintainer ON resources(maintainer_id);
CREATE INDEX idx_resources_valid_from ON resources(valid_from);
CREATE INDEX idx_resources_valid_to ON resources(valid_to) WHERE valid_to IS NOT NULL;
CREATE INDEX idx_resources_current ON resources(id) WHERE valid_to IS NULL AND deleted_at IS NULL;
CREATE INDEX idx_resources_deleted ON resources(deleted_at) WHERE deleted_at IS NOT NULL;

-- Full-text search
CREATE INDEX idx_resources_title_fts ON resources USING gin(to_tsvector('english', title));
CREATE INDEX idx_resources_description_fts ON resources USING gin(to_tsvector('english', description));
CREATE INDEX idx_resources_metadata_gin ON resources USING gin(metadata);
```

---

### 5. Resource Files & Data Locations

#### `storage_locations`
```sql
CREATE TABLE storage_locations (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    location_type VARCHAR(50) NOT NULL,  -- s3, http, ftp, local
    base_url VARCHAR(1000) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB  -- credentials, region, bucket
);
```

#### `resource_files`
Data file locations for each resource (one resource may have multiple files).

```sql
CREATE TABLE resource_files (
    id BIGSERIAL PRIMARY KEY,
    resource_id BIGINT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    storage_location_id BIGINT NOT NULL REFERENCES storage_locations(id),

    -- File path & metadata
    file_path VARCHAR(2000) NOT NULL,  -- relative path from base_url
    file_size_bytes BIGINT,
    file_type VARCHAR(100),  -- FASTA, GTF, BAM, VCF, RDS, etc.

    -- R/Bioconductor specific
    rdata_class VARCHAR(255),  -- R class: FaFile, GRanges, etc.
    dispatch_class VARCHAR(255),  -- How to load in R

    -- Checksums
    md5_hash VARCHAR(32),
    sha256_hash VARCHAR(64),

    -- Temporal
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(resource_id, file_path, valid_from)
);

CREATE INDEX idx_resource_files_resource ON resource_files(resource_id);
CREATE INDEX idx_resource_files_storage ON resource_files(storage_location_id);
CREATE INDEX idx_resource_files_type ON resource_files(file_type);
CREATE INDEX idx_resource_files_current ON resource_files(resource_id) WHERE valid_to IS NULL;
```

#### `source_files`
Upstream source files from data providers (pre-processing).

```sql
CREATE TABLE source_files (
    id BIGSERIAL PRIMARY KEY,
    resource_id BIGINT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,

    -- Source location
    source_url VARCHAR(2000) NOT NULL,
    source_type VARCHAR(100),  -- FASTA, GFF3, etc.
    source_version VARCHAR(255),

    -- File metadata
    file_size_bytes BIGINT,
    md5_hash VARCHAR(32),
    last_modified_date TIMESTAMPTZ,

    -- Temporal
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_source_files_resource ON source_files(resource_id);
CREATE INDEX idx_source_files_url ON source_files(source_url);
```

---

### 6. Tags & Classification

#### `tags`
```sql
CREATE TABLE tags (
    id BIGSERIAL PRIMARY KEY,
    tag VARCHAR(400) NOT NULL UNIQUE,
    category VARCHAR(100),  -- file_format, data_type, method, etc.
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tags_category ON tags(category);
```

#### `resource_tags`
Many-to-many junction table.

```sql
CREATE TABLE resource_tags (
    resource_id BIGINT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    added_by BIGINT REFERENCES users(id),
    PRIMARY KEY (resource_id, tag_id)
);

CREATE INDEX idx_resource_tags_tag ON resource_tags(tag_id);
```

---

### 7. Bioconductor Version Compatibility

#### `bioc_releases`
```sql
CREATE TABLE bioc_releases (
    id BIGSERIAL PRIMARY KEY,
    version VARCHAR(10) NOT NULL UNIQUE,  -- 3.18, 3.19
    release_date DATE NOT NULL,
    end_of_life_date DATE,
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    r_version_min VARCHAR(10),  -- minimum R version
    r_version_max VARCHAR(10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bioc_releases_current ON bioc_releases(is_current) WHERE is_current = TRUE;
```

#### `resource_bioc_versions`
```sql
CREATE TABLE resource_bioc_versions (
    resource_id BIGINT NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    bioc_release_id BIGINT NOT NULL REFERENCES bioc_releases(id),
    is_compatible BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (resource_id, bioc_release_id)
);

CREATE INDEX idx_resource_bioc_release ON resource_bioc_versions(bioc_release_id);
```

---

### 8. Audit & Provenance Tracking

#### `audit_log`
Complete change log for all CRUD operations.

```sql
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_id BIGINT NOT NULL,
    operation VARCHAR(10) NOT NULL,  -- INSERT, UPDATE, DELETE

    -- Who & when
    user_id BIGINT REFERENCES users(id),
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- What changed
    old_values JSONB,
    new_values JSONB,
    changed_fields TEXT[],  -- array of field names

    -- Why
    change_reason TEXT,
    ip_address INET,
    user_agent TEXT,

    -- Context
    request_id UUID,  -- link related changes
    metadata JSONB
);

CREATE INDEX idx_audit_table_record ON audit_log(table_name, record_id);
CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_performed_at ON audit_log(performed_at);
CREATE INDEX idx_audit_operation ON audit_log(operation);
CREATE INDEX idx_audit_request ON audit_log(request_id) WHERE request_id IS NOT NULL;

-- Partition by month for performance
CREATE TABLE audit_log_y2025m01 PARTITION OF audit_log
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
-- ... (create partitions as needed)
```

---

### 9. Submission & Curation Workflow

#### `submissions`
Track new resource submissions before they become public.

```sql
CREATE TABLE submissions (
    id BIGSERIAL PRIMARY KEY,
    hub_id BIGINT NOT NULL REFERENCES hubs(id),

    -- Submitter
    submitted_by BIGINT NOT NULL REFERENCES users(id),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Submission data (staged)
    submission_data JSONB NOT NULL,  -- full resource metadata

    -- Workflow state
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
        -- pending, under_review, approved, rejected, revision_requested
    assigned_to BIGINT REFERENCES users(id),  -- curator

    -- Review
    review_notes TEXT,
    reviewed_at TIMESTAMPTZ,
    reviewed_by BIGINT REFERENCES users(id),

    -- Result
    resource_id BIGINT REFERENCES resources(id),  -- created resource
    rejection_reason TEXT,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_submissions_status ON submissions(status);
CREATE INDEX idx_submissions_submitter ON submissions(submitted_by);
CREATE INDEX idx_submissions_assignee ON submissions(assigned_to);
CREATE INDEX idx_submissions_hub ON submissions(hub_id);
```

#### `submission_comments`
```sql
CREATE TABLE submission_comments (
    id BIGSERIAL PRIMARY KEY,
    submission_id BIGINT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id),
    comment TEXT NOT NULL,
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,  -- curator-only comments
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_submission_comments_submission ON submission_comments(submission_id);
```

---

### 10. Materialized Views for Query Performance

#### `mv_current_resources`
Denormalized view of current, public resources with all commonly queried fields.

```sql
CREATE MATERIALIZED VIEW mv_current_resources AS
SELECT
    r.id,
    r.hub_accession,
    h.code AS hub_code,
    h.name AS hub_name,
    r.title,
    r.description,

    -- Species & Genome
    s.scientific_name AS species,
    s.common_name AS species_common_name,
    s.taxonomy_id,
    g.genome_build AS genome,
    g.assembly_accession,
    r.coordinate_1_based,

    -- Provenance
    dp.name AS data_provider,
    u.full_name AS maintainer_name,
    u.email AS maintainer_email,
    rec.name AS recipe_name,
    rec.preparer_class,

    -- Status
    rs.status,
    rs.is_public,

    -- Dates
    r.valid_from AS date_added,
    r.created_at,
    r.updated_at,

    -- Tags (aggregated)
    ARRAY_AGG(DISTINCT t.tag ORDER BY t.tag) FILTER (WHERE t.tag IS NOT NULL) AS tags,

    -- Bioc versions (aggregated)
    ARRAY_AGG(DISTINCT br.version ORDER BY br.version) FILTER (WHERE br.version IS NOT NULL) AS bioc_versions,

    -- File info (first file as primary)
    (SELECT rf.file_path FROM resource_files rf
     WHERE rf.resource_id = r.id AND rf.valid_to IS NULL
     ORDER BY rf.id LIMIT 1) AS primary_file_path,
    (SELECT rf.file_size_bytes FROM resource_files rf
     WHERE rf.resource_id = r.id AND rf.valid_to IS NULL
     ORDER BY rf.id LIMIT 1) AS primary_file_size,
    (SELECT rf.rdata_class FROM resource_files rf
     WHERE rf.resource_id = r.id AND rf.valid_to IS NULL
     ORDER BY rf.id LIMIT 1) AS rdata_class,

    -- Search vectors
    to_tsvector('english', r.title || ' ' || COALESCE(r.description, '')) AS search_vector

FROM resources r
INNER JOIN hubs h ON r.hub_id = h.id
INNER JOIN resource_statuses rs ON r.status_id = rs.id
LEFT JOIN species s ON r.species_id = s.id
LEFT JOIN genomes g ON r.genome_id = g.id
LEFT JOIN data_providers dp ON r.data_provider_id = dp.id
LEFT JOIN users u ON r.maintainer_id = u.id
LEFT JOIN recipes rec ON r.recipe_id = rec.id
LEFT JOIN resource_tags rt ON r.id = rt.resource_id
LEFT JOIN tags t ON rt.tag_id = t.id
LEFT JOIN resource_bioc_versions rbv ON r.id = rbv.resource_id
LEFT JOIN bioc_releases br ON rbv.bioc_release_id = br.id

WHERE r.valid_to IS NULL  -- current version only
  AND r.deleted_at IS NULL  -- not soft-deleted
  AND rs.is_public = TRUE  -- public resources only

GROUP BY
    r.id, h.code, h.name, s.scientific_name, s.common_name,
    s.taxonomy_id, g.genome_build, g.assembly_accession,
    dp.name, u.full_name, u.email, rec.name, rec.preparer_class,
    rs.status, rs.is_public;

-- Indexes on materialized view
CREATE UNIQUE INDEX idx_mv_current_resources_id ON mv_current_resources(id);
CREATE INDEX idx_mv_current_resources_hub ON mv_current_resources(hub_code);
CREATE INDEX idx_mv_current_resources_accession ON mv_current_resources(hub_accession);
CREATE INDEX idx_mv_current_resources_species ON mv_current_resources(species);
CREATE INDEX idx_mv_current_resources_genome ON mv_current_resources(genome);
CREATE INDEX idx_mv_current_resources_provider ON mv_current_resources(data_provider);
CREATE INDEX idx_mv_current_resources_search ON mv_current_resources USING gin(search_vector);
CREATE INDEX idx_mv_current_resources_tags ON mv_current_resources USING gin(tags);
CREATE INDEX idx_mv_current_resources_bioc ON mv_current_resources USING gin(bioc_versions);

-- Refresh strategy (concurrently to avoid locks)
CREATE UNIQUE INDEX ON mv_current_resources(id);  -- required for concurrent refresh
```

#### `mv_resource_statistics`
Aggregated statistics for dashboards and reports.

```sql
CREATE MATERIALIZED VIEW mv_resource_statistics AS
SELECT
    h.name AS hub_name,
    s.scientific_name AS species,
    g.genome_build AS genome,
    dp.name AS data_provider,
    rs.status,
    DATE_TRUNC('month', r.created_at) AS month,

    COUNT(*) AS resource_count,
    SUM(COALESCE((
        SELECT rf.file_size_bytes
        FROM resource_files rf
        WHERE rf.resource_id = r.id AND rf.valid_to IS NULL
        LIMIT 1
    ), 0)) AS total_size_bytes,

    COUNT(DISTINCT r.maintainer_id) AS maintainer_count,
    COUNT(DISTINCT rt.tag_id) AS tag_count

FROM resources r
INNER JOIN hubs h ON r.hub_id = h.id
INNER JOIN resource_statuses rs ON r.status_id = rs.id
LEFT JOIN species s ON r.species_id = s.id
LEFT JOIN genomes g ON r.genome_id = g.id
LEFT JOIN data_providers dp ON r.data_provider_id = dp.id
LEFT JOIN resource_tags rt ON r.id = rt.resource_id

WHERE r.valid_to IS NULL AND r.deleted_at IS NULL

GROUP BY h.name, s.scientific_name, g.genome_build, dp.name, rs.status,
         DATE_TRUNC('month', r.created_at);

CREATE INDEX idx_mv_stats_hub ON mv_resource_statistics(hub_name);
CREATE INDEX idx_mv_stats_species ON mv_resource_statistics(species);
CREATE INDEX idx_mv_stats_month ON mv_resource_statistics(month);
```

---

## Migration Strategy

### Phase 1: Schema Creation & Seeding
1. Create PostgreSQL database with all tables
2. Populate reference tables: `hubs`, `resource_statuses`, `bioc_releases`
3. Extract and normalize: `species`, `genomes`, `data_providers`, `recipes`
4. Create system user for legacy data migration

### Phase 2: Data Migration
1. Migrate resources from SQLite to PostgreSQL
   - Map legacy `ah_id` to `hub_accession`
   - Normalize species/genome references
   - Set `created_by` to migration system user
2. Migrate related tables: `resource_files`, `source_files`, `tags`, `bioc_versions`
3. Validate data integrity and counts

### Phase 3: Materialized Views
1. Build initial materialized views
2. Set up automatic refresh schedules (hourly for statistics, daily for resources)
3. Create refresh triggers for real-time critical views

### Phase 4: API Updates
1. Update SQLAlchemy models to new schema
2. Refactor API endpoints to use new tables/views
3. Add new CRUD endpoints for submissions, users
4. Implement temporal queries ("as of" date)

### Phase 5: Automation & Monitoring
1. Database triggers for audit logging
2. Automated materialized view refresh
3. Data validation constraints and checks
4. Performance monitoring and query optimization

---

## CRUD Operations Design

### Create Resource
```sql
-- New submission workflow
INSERT INTO submissions (hub_id, submitted_by, submission_data, status)
VALUES (1, 42, '{"title": "...", ...}', 'pending');

-- After approval, create resource
INSERT INTO resources (
    hub_id, hub_accession, title, species_id, status_id,
    created_by, valid_from, version_number
) VALUES (...);
```

### Update Resource (Versioning)
```sql
-- Close current version
UPDATE resources
SET valid_to = NOW(), superseded_by = NEW_ID
WHERE id = OLD_ID;

-- Create new version
INSERT INTO resources (
    hub_id, hub_accession, title, ..., version_number, valid_from
) SELECT
    hub_id, hub_accession, 'Updated Title', ..., version_number + 1, NOW()
FROM resources WHERE id = OLD_ID;
```

### Soft Delete
```sql
UPDATE resources
SET deleted_at = NOW(), deleted_by = USER_ID
WHERE id = RESOURCE_ID;

-- Still queryable for audit/historical purposes
```

### Query Current Resources (via Materialized View)
```sql
SELECT * FROM mv_current_resources
WHERE species = 'Homo sapiens'
  AND genome = 'GRCh38'
  AND 'ChIP-seq' = ANY(tags)
ORDER BY date_added DESC
LIMIT 100;
```

### Temporal Query (Point-in-Time)
```sql
SELECT * FROM resources
WHERE hub_accession = 'AH5086'
  AND valid_from <= '2023-06-01'
  AND (valid_to IS NULL OR valid_to > '2023-06-01')
  AND (deleted_at IS NULL OR deleted_at > '2023-06-01');
```

---

## Performance Considerations

### Indexing Strategy
- **B-tree indexes:** Foreign keys, temporal columns, frequently filtered fields
- **GIN indexes:** JSONB, arrays, full-text search vectors
- **Partial indexes:** `WHERE valid_to IS NULL`, `WHERE deleted_at IS NOT NULL`
- **Covering indexes:** Include commonly selected columns

### Materialized View Refresh
```sql
-- Scheduled refresh (off-peak hours)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_current_resources;

-- Incremental refresh via triggers (for smaller tables)
CREATE TRIGGER refresh_stats_trigger
AFTER INSERT OR UPDATE OR DELETE ON resources
FOR EACH STATEMENT EXECUTE FUNCTION refresh_stats_mv();
```

### Partitioning
- **`audit_log`:** Partition by month (time-series data)
- **Future:** Consider partitioning `resources` by hub if tables grow very large

### Query Optimization
- Use materialized views for read-heavy endpoints
- Implement query result caching at application layer (Redis)
- Connection pooling (pgBouncer)
- Read replicas for analytics/reporting

---

## Security & Access Control

### Row-Level Security (RLS)
```sql
ALTER TABLE resources ENABLE ROW LEVEL SECURITY;

-- Public users see only public resources
CREATE POLICY public_resources ON resources
    FOR SELECT
    TO public
    USING (
        status_id IN (SELECT id FROM resource_statuses WHERE is_public = TRUE)
        AND deleted_at IS NULL
        AND valid_to IS NULL
    );

-- Maintainers see their own resources
CREATE POLICY maintainer_resources ON resources
    FOR ALL
    TO authenticated
    USING (maintainer_id = current_user_id());
```

### API Key Management (Future)
```sql
CREATE TABLE api_keys (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(255),
    scopes TEXT[],  -- read, write, admin
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Monitoring & Maintenance

### Health Checks
```sql
-- View freshness
SELECT
    schemaname, matviewname,
    last_refresh,
    NOW() - last_refresh AS staleness
FROM pg_matviews
WHERE schemaname = 'public';

-- Replication lag (if using replicas)
SELECT EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp())) AS lag_seconds;
```

### Data Quality Checks
```sql
-- Resources without files
SELECT COUNT(*) FROM resources r
WHERE NOT EXISTS (
    SELECT 1 FROM resource_files rf
    WHERE rf.resource_id = r.id AND rf.valid_to IS NULL
) AND r.deleted_at IS NULL;

-- Orphaned tags
SELECT COUNT(*) FROM tags t
WHERE NOT EXISTS (
    SELECT 1 FROM resource_tags rt WHERE rt.tag_id = t.id
);
```

---

## Future Enhancements

### Near-term (3-6 months)
- [ ] User authentication & authorization (OAuth2, OIDC)
- [ ] Submission review workflow UI
- [ ] Citation tracking (DOIs, PMIDs)
- [ ] Download statistics & analytics
- [ ] Automated data validation pipelines

### Medium-term (6-12 months)
- [ ] Workflow provenance (record processing pipelines)
- [ ] Resource collections (curated bundles)
- [ ] Advanced search (faceted, graph-based)
- [ ] Data quality scoring
- [ ] Community annotations & comments

### Long-term (12+ months)
- [ ] Federated query across multiple hubs
- [ ] Machine learning metadata enhancement
- [ ] Knowledge graph integration (ontologies)
- [ ] Blockchain-based immutable audit trail
- [ ] Multi-region replication

---

## Appendix

### Schema Diagram
(To be created with tool like dbdiagram.io or schemaspy)

### Glossary
- **Hub:** A collection repository (AnnotationHub, ExperimentHub)
- **Resource:** A single data object/file with metadata
- **Temporal versioning:** Tracking changes over time with validity periods
- **Soft delete:** Marking records as deleted without removing them
- **Materialized view:** Pre-computed query result stored as table

### References
- Bioconductor AnnotationHub: https://bioconductor.org/packages/AnnotationHub
- PostgreSQL Temporal Tables: https://www.postgresql.org/docs/current/ddl-temporal.html
- Database Auditing Best Practices: https://www.2ndquadrant.com/en/blog/auditing-postgresql/

---

**Document Status:** Draft for review
**Next Steps:**
1. Review with stakeholders
2. Prototype schema in test environment
3. Benchmark queries against current SQLite
4. Finalize migration scripts
