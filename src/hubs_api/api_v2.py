"""
FastAPI REST API v2 for Bioconductor Hub resources.

Supports the normalized PostgreSQL schema with nested entity relationships,
comprehensive filtering, sorting, and pagination.
"""
import os
from typing import Optional, List
from fastapi import FastAPI, Query, HTTPException, Depends, Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload, joinedload
from dotenv import load_dotenv
import sys
from loguru import logger

from .models import (
    Resource, Species, Genome, DataProvider, Recipe, User,
    Hub, ResourceStatus, Tag, ResourceTag, BiocRelease,
    ResourceBiocVersion, ResourceFile, SourceFile
)
from .schemas import (
    ResourceListResponse, ResourceDetailResponse, ResourceSchema,
    ResourceDetailSchema, PaginationMeta, SpeciesSchema, TagSchema,
    BiocReleaseSchema
)
from .db_utils import _convert_to_async_url

logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

load_dotenv()

# Database setup
DATABASE_URL = os.getenv("POSTGRES_URI", "postgresql://postgres@localhost:5432/hubs_dev")
DATABASE_URL = _convert_to_async_url(DATABASE_URL)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# FastAPI app
app = FastAPI(
    title="Bioconductor Hubs API",
    description="""
REST API for querying AnnotationHub and ExperimentHub resources.

Features:
- Comprehensive filtering with multiple operators
- Flexible sorting (single or multiple fields)
- Efficient pagination with metadata
- Nested entity relationships
- Tag-based filtering
- Bioconductor version filtering
    """,
    version="2.0.0",
)


async def get_db():
    """Dependency to get database session."""
    async with async_session_maker() as session:
        yield session


# ============================================================================
# Filtering Utilities
# ============================================================================

def build_resource_filters(
    hub_id: Optional[int] = None,
    hub_code: Optional[str] = None,
    species_id: Optional[int] = None,
    species_name: Optional[str] = None,
    taxonomy_id: Optional[int] = None,
    genome_id: Optional[int] = None,
    genome_build: Optional[str] = None,
    provider_id: Optional[int] = None,
    provider_name: Optional[str] = None,
    recipe_id: Optional[int] = None,
    maintainer_id: Optional[int] = None,
    status_id: Optional[int] = None,
    title_contains: Optional[str] = None,
    description_contains: Optional[str] = None,
    coordinate_1_based: Optional[bool] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    is_deleted: Optional[bool] = None,
    is_current: Optional[bool] = None,
) -> List:
    """Build filter conditions for resource queries."""
    conditions = []

    # Direct field filters
    if hub_id is not None:
        conditions.append(Resource.hub_id == hub_id)
    if species_id is not None:
        conditions.append(Resource.species_id == species_id)
    if genome_id is not None:
        conditions.append(Resource.genome_id == genome_id)
    if provider_id is not None:
        conditions.append(Resource.data_provider_id == provider_id)
    if recipe_id is not None:
        conditions.append(Resource.recipe_id == recipe_id)
    if maintainer_id is not None:
        conditions.append(Resource.maintainer_id == maintainer_id)
    if status_id is not None:
        conditions.append(Resource.status_id == status_id)
    if coordinate_1_based is not None:
        conditions.append(Resource.coordinate_1_based == coordinate_1_based)

    # Text search filters
    if title_contains:
        conditions.append(Resource.title.ilike(f"%{title_contains}%"))
    if description_contains:
        conditions.append(Resource.description.ilike(f"%{description_contains}%"))

    # Date filters
    if created_after:
        conditions.append(Resource.created_at >= created_after)
    if created_before:
        conditions.append(Resource.created_at <= created_before)

    # Soft delete filter
    if is_deleted is not None:
        if is_deleted:
            conditions.append(Resource.deleted_at.is_not(None))
        else:
            conditions.append(Resource.deleted_at.is_(None))
    else:
        # By default, exclude deleted resources
        conditions.append(Resource.deleted_at.is_(None))

    # Current version filter (not superseded)
    if is_current is not None:
        if is_current:
            conditions.append(Resource.valid_to.is_(None))
        else:
            conditions.append(Resource.valid_to.is_not(None))

    return conditions


def parse_sort_param(sort: Optional[str]) -> List[tuple]:
    """
    Parse sort parameter into list of (field, direction) tuples.

    Format: "field1,-field2,field3" where "-" prefix means descending.
    Returns: [("field1", "asc"), ("field2", "desc"), ("field3", "asc")]
    """
    if not sort:
        return []

    result = []
    for part in sort.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("-"):
            result.append((part[1:], "desc"))
        else:
            result.append((part, "asc"))
    return result


def apply_sorting(query, sort_fields: List[tuple]):
    """Apply sorting to query based on parsed sort fields."""
    for field_name, direction in sort_fields:
        if not hasattr(Resource, field_name):
            raise HTTPException(status_code=400, detail=f"Unknown sort field: {field_name}")

        column = getattr(Resource, field_name)
        if direction == "desc":
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())

    return query


# ============================================================================
# Resource Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Bioconductor Hubs API v2",
        "version": "2.0.0",
        "documentation": "/docs",
        "openapi": "/openapi.json",
        "endpoints": {
            "resources": "/api/v2/resources",
            "resource_detail": "/api/v2/resources/{id}",
            "species": "/api/v2/species",
            "tags": "/api/v2/tags",
            "bioc_releases": "/api/v2/bioc-releases",
            "health": "/health"
        }
    }


@app.get("/api/v2/resources", response_model=ResourceListResponse)
async def list_resources(
    db: AsyncSession = Depends(get_db),

    # Pagination
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum results per page"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),

    # Sorting
    sort: Optional[str] = Query(
        default="-created_at",
        description="Sort by field(s). Prefix with '-' for descending. Example: '-created_at,title'",
        example="-created_at"
    ),

    # Hub filters
    hub_id: Optional[int] = Query(None, description="Filter by hub ID (1=AnnotationHub, 2=ExperimentHub)"),
    hub_code: Optional[str] = Query(None, description="Filter by hub code (AH or EH)"),

    # Species/Genome filters
    species_id: Optional[int] = Query(None, description="Filter by species ID"),
    species_name: Optional[str] = Query(None, description="Filter by species scientific name (partial match)"),
    taxonomy_id: Optional[int] = Query(None, description="Filter by NCBI taxonomy ID"),
    genome_id: Optional[int] = Query(None, description="Filter by genome ID"),
    genome_build: Optional[str] = Query(None, description="Filter by genome build name"),

    # Provider/Recipe filters
    provider_id: Optional[int] = Query(None, description="Filter by data provider ID"),
    provider_name: Optional[str] = Query(None, description="Filter by provider name (partial match)"),
    recipe_id: Optional[int] = Query(None, description="Filter by recipe ID"),
    maintainer_id: Optional[int] = Query(None, description="Filter by maintainer user ID"),

    # Status filters
    status_id: Optional[int] = Query(None, description="Filter by status ID"),
    is_deleted: Optional[bool] = Query(None, description="Include deleted resources (default: False)"),
    is_current: Optional[bool] = Query(None, description="Filter by current version (not superseded)"),

    # Content filters
    title_contains: Optional[str] = Query(None, description="Search in title (case-insensitive)"),
    description_contains: Optional[str] = Query(None, description="Search in description (case-insensitive)"),
    coordinate_1_based: Optional[bool] = Query(None, description="Filter by coordinate system"),

    # Date filters
    created_after: Optional[str] = Query(None, description="Filter resources created after date (ISO 8601)"),
    created_before: Optional[str] = Query(None, description="Filter resources created before date (ISO 8601)"),

    # Tag filters
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated, must have ALL)"),
    tags_any: Optional[str] = Query(None, description="Filter by tags (comma-separated, must have ANY)"),

    # Bioc version filter
    bioc_version: Optional[str] = Query(None, description="Filter by Bioconductor version"),

    # Include nested data
    include_tags: bool = Query(False, description="Include tags in response"),
    include_files: bool = Query(False, description="Include file information"),
    include_bioc_versions: bool = Query(False, description="Include Bioconductor version associations"),
):
    """
    List resources with comprehensive filtering, sorting, and pagination.

    ## Filtering Examples

    - By hub: `?hub_id=1` or `?hub_code=AH`
    - By species: `?species_name=Homo sapiens`
    - By text: `?title_contains=RNA&description_contains=seq`
    - By date: `?created_after=2023-01-01&created_before=2024-01-01`
    - By tags: `?tags=ChIP-Seq,Homo_sapiens` (AND) or `?tags_any=RNA,DNA` (OR)
    - By Bioc version: `?bioc_version=3.18`

    ## Sorting Examples

    - Most recent: `?sort=-created_at`
    - Alphabetical: `?sort=title`
    - Multiple: `?sort=-created_at,title`

    ## Pagination

    - Page 1: `?limit=50&offset=0`
    - Page 2: `?limit=50&offset=50`
    """

    # Build base query with eager loading for nested entities
    query = select(Resource).options(
        joinedload(Resource.hub),
        joinedload(Resource.species),
        joinedload(Resource.genome),
        joinedload(Resource.data_provider),
        joinedload(Resource.recipe),
        joinedload(Resource.maintainer),
        joinedload(Resource.status),
    )

    # Optionally load collections
    if include_tags:
        query = query.options(
            selectinload(Resource.tags).joinedload(ResourceTag.tag_obj)
        )
    if include_files:
        query = query.options(
            selectinload(Resource.resource_files),
            selectinload(Resource.source_files)
        )
    if include_bioc_versions:
        query = query.options(
            selectinload(Resource.bioc_versions).joinedload(ResourceBiocVersion.bioc_release)
        )

    # Apply filters
    conditions = build_resource_filters(
        hub_id=hub_id,
        hub_code=hub_code,
        species_id=species_id,
        species_name=species_name,
        taxonomy_id=taxonomy_id,
        genome_id=genome_id,
        genome_build=genome_build,
        provider_id=provider_id,
        provider_name=provider_name,
        recipe_id=recipe_id,
        maintainer_id=maintainer_id,
        status_id=status_id,
        title_contains=title_contains,
        description_contains=description_contains,
        coordinate_1_based=coordinate_1_based,
        created_after=created_after,
        created_before=created_before,
        is_deleted=is_deleted,
        is_current=is_current,
    )

    # Join for species/genome/provider name filters
    if species_name:
        query = query.join(Resource.species).filter(Species.scientific_name.ilike(f"%{species_name}%"))
    if taxonomy_id:
        query = query.join(Resource.species).filter(Species.taxonomy_id == taxonomy_id)
    if genome_build:
        query = query.join(Resource.genome).filter(Genome.genome_build.ilike(f"%{genome_build}%"))
    if provider_name:
        query = query.join(Resource.data_provider).filter(DataProvider.name.ilike(f"%{provider_name}%"))
    if hub_code:
        query = query.join(Resource.hub).filter(Hub.code == hub_code.upper())

    # Tag filtering (requires subquery)
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        # Must have ALL tags (AND logic)
        for tag_name in tag_list:
            tag_subquery = select(ResourceTag.resource_id).join(Tag).filter(Tag.tag == tag_name)
            query = query.filter(Resource.id.in_(tag_subquery))

    if tags_any:
        tag_list = [t.strip() for t in tags_any.split(",") if t.strip()]
        # Must have ANY tag (OR logic)
        tag_subquery = select(ResourceTag.resource_id).join(Tag).filter(Tag.tag.in_(tag_list))
        query = query.filter(Resource.id.in_(tag_subquery))

    # Bioc version filtering
    if bioc_version:
        bioc_subquery = select(ResourceBiocVersion.resource_id).join(BiocRelease).filter(
            BiocRelease.version == bioc_version
        )
        query = query.filter(Resource.id.in_(bioc_subquery))

    # Apply all conditions
    if conditions:
        query = query.filter(and_(*conditions))

    # Count total (before pagination)
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total = await db.scalar(count_query) or 0

    # Apply sorting
    sort_fields = parse_sort_param(sort)
    query = apply_sorting(query, sort_fields)

    # Apply pagination
    query = query.limit(limit).offset(offset)

    # Execute query
    result = await db.execute(query)
    resources = result.unique().scalars().all()

    # Build response with nested entities
    data = []
    for resource in resources:
        resource_dict = {
            "id": resource.id,
            "hub_accession": resource.hub_accession,
            "title": resource.title,
            "description": resource.description,
            "hub_id": resource.hub_id,
            "species_id": resource.species_id,
            "genome_id": resource.genome_id,
            "data_provider_id": resource.data_provider_id,
            "recipe_id": resource.recipe_id,
            "maintainer_id": resource.maintainer_id,
            "status_id": resource.status_id,
            "coordinate_1_based": resource.coordinate_1_based,
            "valid_from": resource.valid_from,
            "valid_to": resource.valid_to,
            "version_number": resource.version_number,
            "created_at": resource.created_at,
            "updated_at": resource.updated_at,
            "deleted_at": resource.deleted_at,
            "hub": resource.hub,
            "species": resource.species,
            "genome": resource.genome,
            "data_provider": resource.data_provider,
            "recipe": resource.recipe,
            "maintainer": resource.maintainer,
            "status": resource.status,
        }

        # Add optional nested collections
        if include_tags:
            resource_dict["tags"] = [rt.tag_obj for rt in resource.tags]
        if include_bioc_versions:
            resource_dict["bioc_versions"] = [rbv.bioc_release for rbv in resource.bioc_versions]
        if include_files:
            resource_dict["resource_files"] = resource.resource_files
            resource_dict["source_files"] = resource.source_files

        data.append(ResourceSchema(**resource_dict))

    # Build pagination metadata
    meta = PaginationMeta(
        total=total,
        limit=limit,
        offset=offset,
        count=len(data),
        has_next=offset + limit < total,
        has_prev=offset > 0
    )

    return ResourceListResponse(meta=meta, data=data)


@app.get("/api/v2/resources/{resource_id}", response_model=ResourceDetailResponse)
async def get_resource(
    resource_id: int = Path(..., description="Resource ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single resource by ID with full details including all nested entities.

    Includes:
    - Hub, species, genome, provider, recipe, maintainer, status
    - All tags
    - All Bioconductor version associations
    - All resource files
    - All source files
    """
    query = select(Resource).where(Resource.id == resource_id).options(
        joinedload(Resource.hub),
        joinedload(Resource.species),
        joinedload(Resource.genome),
        joinedload(Resource.data_provider),
        joinedload(Resource.recipe),
        joinedload(Resource.maintainer),
        joinedload(Resource.status),
        selectinload(Resource.tags).joinedload(ResourceTag.tag_obj),
        selectinload(Resource.bioc_versions).joinedload(ResourceBiocVersion.bioc_release),
        selectinload(Resource.resource_files),
        selectinload(Resource.source_files),
    )

    result = await db.execute(query)
    resource = result.unique().scalar_one_or_none()

    if not resource:
        raise HTTPException(status_code=404, detail=f"Resource {resource_id} not found")

    # Build full response
    resource_dict = {
        "id": resource.id,
        "hub_accession": resource.hub_accession,
        "title": resource.title,
        "description": resource.description,
        "hub_id": resource.hub_id,
        "species_id": resource.species_id,
        "genome_id": resource.genome_id,
        "data_provider_id": resource.data_provider_id,
        "recipe_id": resource.recipe_id,
        "maintainer_id": resource.maintainer_id,
        "status_id": resource.status_id,
        "coordinate_1_based": resource.coordinate_1_based,
        "valid_from": resource.valid_from,
        "valid_to": resource.valid_to,
        "version_number": resource.version_number,
        "created_at": resource.created_at,
        "updated_at": resource.updated_at,
        "deleted_at": resource.deleted_at,
        "hub": resource.hub,
        "species": resource.species,
        "genome": resource.genome,
        "data_provider": resource.data_provider,
        "recipe": resource.recipe,
        "maintainer": resource.maintainer,
        "status": resource.status,
        "tags": [rt.tag_obj for rt in resource.tags],
        "bioc_versions": [rbv.bioc_release for rbv in resource.bioc_versions],
        "resource_files": resource.resource_files,
        "source_files": resource.source_files,
    }

    return ResourceDetailResponse(data=ResourceDetailSchema(**resource_dict))


# ============================================================================
# Reference Data Endpoints
# ============================================================================

@app.get("/api/v2/species", response_model=List[SpeciesSchema])
async def list_species(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(None, description="Search in scientific or common name"),
):
    """List all species with optional search."""
    query = select(Species)

    if search:
        query = query.filter(
            or_(
                Species.scientific_name.ilike(f"%{search}%"),
                Species.common_name.ilike(f"%{search}%")
            )
        )

    query = query.order_by(Species.scientific_name).limit(limit).offset(offset)

    result = await db.execute(query)
    species = result.scalars().all()

    return [SpeciesSchema.model_validate(s) for s in species]


@app.get("/api/v2/tags", response_model=List[TagSchema])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(None, description="Search in tag name"),
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """List all tags with optional search and filtering."""
    query = select(Tag)

    if search:
        query = query.filter(Tag.tag.ilike(f"%{search}%"))
    if category:
        query = query.filter(Tag.category == category)

    query = query.order_by(Tag.tag).limit(limit).offset(offset)

    result = await db.execute(query)
    tags = result.scalars().all()

    return [TagSchema.model_validate(t) for t in tags]


@app.get("/api/v2/bioc-releases", response_model=List[BiocReleaseSchema])
async def list_bioc_releases(
    db: AsyncSession = Depends(get_db),
):
    """List all Bioconductor releases."""
    query = select(BiocRelease).order_by(BiocRelease.version.desc())

    result = await db.execute(query)
    releases = result.scalars().all()

    return [BiocReleaseSchema.model_validate(r) for r in releases]


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint - verifies database connectivity."""
    try:
        await db.execute(select(1))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")
