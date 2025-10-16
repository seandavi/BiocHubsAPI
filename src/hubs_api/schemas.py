"""Pydantic schemas for API request/response models."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Nested Entity Schemas
# ============================================================================

class SpeciesSchema(BaseModel):
    """Species information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    scientific_name: str
    common_name: Optional[str] = None
    taxonomy_id: int


class GenomeSchema(BaseModel):
    """Genome build information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    genome_build: str
    assembly_accession: Optional[str] = None
    ucsc_name: Optional[str] = None
    ensembl_name: Optional[str] = None
    is_reference: bool


class DataProviderSchema(BaseModel):
    """Data provider information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: Optional[str] = None
    description: Optional[str] = None


class RecipeSchema(BaseModel):
    """Recipe/preparer information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    package_name: Optional[str] = None
    preparer_class: Optional[str] = None
    description: Optional[str] = None


class UserSchema(BaseModel):
    """User/maintainer information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: Optional[str] = None
    role: str


class HubSchema(BaseModel):
    """Hub information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str


class ResourceStatusSchema(BaseModel):
    """Resource status information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    display_name: Optional[str] = None
    is_public: bool


class TagSchema(BaseModel):
    """Tag information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    tag: str
    category: Optional[str] = None


class BiocReleaseSchema(BaseModel):
    """Bioconductor release information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    is_current: bool


class ResourceFileSchema(BaseModel):
    """Resource file information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_path: str
    file_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    rdata_class: Optional[str] = None
    dispatch_class: Optional[str] = None
    md5_hash: Optional[str] = None


class SourceFileSchema(BaseModel):
    """Source file information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_url: str
    source_type: Optional[str] = None
    source_version: Optional[str] = None
    file_size_bytes: Optional[int] = None


# ============================================================================
# Resource Schemas (with varying levels of detail)
# ============================================================================

class ResourceSummarySchema(BaseModel):
    """Minimal resource information for lists."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    hub_accession: str
    title: str
    hub_id: int
    status_id: int
    created_at: datetime

    # Simple string fields for quick overview
    species_name: Optional[str] = Field(None, description="Scientific name")
    genome_build: Optional[str] = None
    provider_name: Optional[str] = None


class ResourceSchema(BaseModel):
    """Full resource information with nested entities."""
    model_config = ConfigDict(from_attributes=True)

    # Core fields
    id: int
    hub_accession: str
    title: str
    description: Optional[str] = None

    # Foreign key IDs
    hub_id: int
    species_id: Optional[int] = None
    genome_id: Optional[int] = None
    data_provider_id: Optional[int] = None
    recipe_id: Optional[int] = None
    maintainer_id: Optional[int] = None
    status_id: int

    # Nested entities
    hub: Optional[HubSchema] = None
    species: Optional[SpeciesSchema] = None
    genome: Optional[GenomeSchema] = None
    data_provider: Optional[DataProviderSchema] = None
    recipe: Optional[RecipeSchema] = None
    maintainer: Optional[UserSchema] = None
    status: Optional[ResourceStatusSchema] = None

    # Metadata
    coordinate_1_based: Optional[bool] = None

    # Temporal fields
    valid_from: datetime
    valid_to: Optional[datetime] = None
    version_number: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    # Optional nested collections (can be null to reduce payload)
    tags: Optional[List[TagSchema]] = None
    bioc_versions: Optional[List[BiocReleaseSchema]] = None
    resource_files: Optional[List[ResourceFileSchema]] = None
    source_files: Optional[List[SourceFileSchema]] = None


class ResourceDetailSchema(ResourceSchema):
    """Extended resource with all related data."""
    # Inherits everything from ResourceSchema
    # Ensures all nested collections are populated
    tags: List[TagSchema] = Field(default_factory=list)
    bioc_versions: List[BiocReleaseSchema] = Field(default_factory=list)
    resource_files: List[ResourceFileSchema] = Field(default_factory=list)
    source_files: List[SourceFileSchema] = Field(default_factory=list)


# ============================================================================
# Response Schemas
# ============================================================================

class PaginationMeta(BaseModel):
    """Pagination metadata."""
    total: int = Field(..., description="Total number of records matching filters")
    limit: int = Field(..., description="Maximum records returned per page")
    offset: int = Field(..., description="Number of records skipped")
    count: int = Field(..., description="Number of records in this response")
    has_next: bool = Field(..., description="Whether more records are available")
    has_prev: bool = Field(..., description="Whether previous records exist")


class ResourceListResponse(BaseModel):
    """Paginated list of resources."""
    meta: PaginationMeta
    data: List[ResourceSchema]


class ResourceDetailResponse(BaseModel):
    """Single resource with full details."""
    data: ResourceDetailSchema


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
    status_code: int
