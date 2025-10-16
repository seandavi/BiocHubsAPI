"""
SQLAlchemy ORM models for Bioconductor Hub PostgreSQL database.

This module defines the normalized schema for AnnotationHub and ExperimentHub,
including proper entity relationships, temporal versioning, and audit trails.
"""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID, ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ============================================================================
# User & Organization Management
# ============================================================================

class Organization(Base):
    """Research organizations and institutions."""
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    website: Mapped[Optional[str]] = mapped_column(String(500))
    ror_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True)  # Research Organization Registry
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    meta: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    users: Mapped[List["User"]] = relationship(back_populates="organization")
    data_providers: Mapped[List["DataProvider"]] = relationship(back_populates="organization")

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name='{self.name}')>"


class User(Base):
    """Users, maintainers, curators, and administrators."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(500))
    orcid: Mapped[Optional[str]] = mapped_column(String(19), unique=True)
    organization_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("organizations.id"))
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    meta: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(back_populates="users")
    maintained_resources: Mapped[List["Resource"]] = relationship(
        back_populates="maintainer",
        foreign_keys="Resource.maintainer_id"
    )
    created_resources: Mapped[List["Resource"]] = relationship(
        back_populates="created_by_user",
        foreign_keys="Resource.created_by"
    )
    updated_resources: Mapped[List["Resource"]] = relationship(
        back_populates="updated_by_user",
        foreign_keys="Resource.updated_by"
    )
    deleted_resources: Mapped[List["Resource"]] = relationship(
        back_populates="deleted_by_user",
        foreign_keys="Resource.deleted_by"
    )

    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_orcid", "orcid", postgresql_where=Column("orcid").isnot(None)),
        Index("idx_users_org", "organization_id"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


# ============================================================================
# Taxonomy & Genome Reference Data
# ============================================================================

class Species(Base):
    """Taxonomic species information."""
    __tablename__ = "species"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scientific_name: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    common_name: Mapped[Optional[str]] = mapped_column(String(500))
    taxonomy_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    lineage: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    meta: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    genomes: Mapped[List["Genome"]] = relationship(back_populates="species")
    resources: Mapped[List["Resource"]] = relationship(back_populates="species")

    __table_args__ = (
        Index("idx_species_taxonomy", "taxonomy_id"),
        Index("idx_species_scientific", "scientific_name"),
    )

    def __repr__(self) -> str:
        return f"<Species(id={self.id}, name='{self.scientific_name}', taxonomy_id={self.taxonomy_id})>"


class Genome(Base):
    """Genome builds and assemblies."""
    __tablename__ = "genomes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    species_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("species.id"), nullable=False)
    genome_build: Mapped[str] = mapped_column(String(255), nullable=False)
    assembly_accession: Mapped[Optional[str]] = mapped_column(String(50))
    ucsc_name: Mapped[Optional[str]] = mapped_column(String(100))
    ensembl_name: Mapped[Optional[str]] = mapped_column(String(100))
    is_reference: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    release_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    meta: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    species: Mapped["Species"] = relationship(back_populates="genomes")
    resources: Mapped[List["Resource"]] = relationship(back_populates="genome")

    __table_args__ = (
        UniqueConstraint("species_id", "genome_build", name="uq_species_genome_build"),
        Index("idx_genomes_species", "species_id"),
        Index("idx_genomes_build", "genome_build"),
    )

    def __repr__(self) -> str:
        return f"<Genome(id={self.id}, build='{self.genome_build}', species_id={self.species_id})>"


# ============================================================================
# Data Provider & Recipe Infrastructure
# ============================================================================

class DataProvider(Base):
    """Data source providers (e.g., Ensembl, UCSC, NCBI)."""
    __tablename__ = "data_providers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    organization_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("organizations.id"))
    url: Mapped[Optional[str]] = mapped_column(String(1000))
    description: Mapped[Optional[str]] = mapped_column(Text)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    meta: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(back_populates="data_providers")
    resources: Mapped[List["Resource"]] = relationship(back_populates="data_provider")

    __table_args__ = (
        Index("idx_providers_org", "organization_id"),
    )

    def __repr__(self) -> str:
        return f"<DataProvider(id={self.id}, name='{self.name}')>"


class Recipe(Base):
    """Data processing recipes and preparers."""
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    package_name: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    preparer_class: Mapped[Optional[str]] = mapped_column(String(255))
    version: Mapped[Optional[str]] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    meta: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    resources: Mapped[List["Resource"]] = relationship(back_populates="recipe")

    __table_args__ = (
        Index("idx_recipes_package", "package_name"),
    )

    def __repr__(self) -> str:
        return f"<Recipe(id={self.id}, name='{self.name}', class='{self.preparer_class}')>"


# ============================================================================
# Hub Infrastructure
# ============================================================================

class Hub(Base):
    """Hub types (AnnotationHub, ExperimentHub)."""
    __tablename__ = "hubs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    resources: Mapped[List["Resource"]] = relationship(back_populates="hub")

    def __repr__(self) -> str:
        return f"<Hub(id={self.id}, name='{self.name}', code='{self.code}')>"


class ResourceStatus(Base):
    """Resource lifecycle statuses."""
    __tablename__ = "resource_statuses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Relationships
    resources: Mapped[List["Resource"]] = relationship(back_populates="status")

    def __repr__(self) -> str:
        return f"<ResourceStatus(id={self.id}, status='{self.status}', public={self.is_public})>"


# ============================================================================
# Core Resources
# ============================================================================

class Resource(Base):
    """Hub resources with temporal versioning."""
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    hub_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("hubs.id"), nullable=False)
    hub_accession: Mapped[str] = mapped_column(String(50), nullable=False)

    # Core metadata
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Taxonomy & genome
    species_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("species.id"))
    genome_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("genomes.id"))
    coordinate_1_based: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Provenance
    data_provider_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("data_providers.id"))
    recipe_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("recipes.id"))
    maintainer_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))

    # Status & lifecycle
    status_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("resource_statuses.id"), nullable=False)

    # Temporal versioning
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    superseded_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("resources.id"))

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))

    # Extensibility
    meta: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    hub: Mapped["Hub"] = relationship(back_populates="resources")
    species: Mapped[Optional["Species"]] = relationship(back_populates="resources")
    genome: Mapped[Optional["Genome"]] = relationship(back_populates="resources")
    data_provider: Mapped[Optional["DataProvider"]] = relationship(back_populates="resources")
    recipe: Mapped[Optional["Recipe"]] = relationship(back_populates="resources")
    maintainer: Mapped[Optional["User"]] = relationship(
        back_populates="maintained_resources",
        foreign_keys=[maintainer_id]
    )
    status: Mapped["ResourceStatus"] = relationship(back_populates="resources")

    # Audit relationships
    created_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="created_resources",
        foreign_keys=[created_by]
    )
    updated_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="updated_resources",
        foreign_keys=[updated_by]
    )
    deleted_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="deleted_resources",
        foreign_keys=[deleted_by]
    )

    # Child relationships
    resource_files: Mapped[List["ResourceFile"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    source_files: Mapped[List["SourceFile"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    tags: Mapped[List["ResourceTag"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    bioc_versions: Mapped[List["ResourceBiocVersion"]] = relationship(back_populates="resource", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("hub_id", "hub_accession", "version_number", name="uq_hub_accession_version"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="chk_valid_dates"),
        Index("idx_resources_hub_accession", "hub_id", "hub_accession"),
        Index("idx_resources_status", "status_id"),
        Index("idx_resources_species", "species_id"),
        Index("idx_resources_genome", "genome_id"),
        Index("idx_resources_provider", "data_provider_id"),
        Index("idx_resources_maintainer", "maintainer_id"),
        Index("idx_resources_valid_from", "valid_from"),
        Index("idx_resources_valid_to", "valid_to", postgresql_where=Column("valid_to").isnot(None)),
        Index("idx_resources_current", "id", postgresql_where=(Column("valid_to").is_(None) & Column("deleted_at").is_(None))),
        Index("idx_resources_deleted", "deleted_at", postgresql_where=Column("deleted_at").isnot(None)),
    )

    def __repr__(self) -> str:
        return f"<Resource(id={self.id}, accession='{self.hub_accession}', title='{self.title[:50]}...')>"


# ============================================================================
# Storage & File Management
# ============================================================================

class StorageLocation(Base):
    """Storage backend locations."""
    __tablename__ = "storage_locations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    location_type: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    meta: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    resource_files: Mapped[List["ResourceFile"]] = relationship(back_populates="storage_location")

    def __repr__(self) -> str:
        return f"<StorageLocation(id={self.id}, name='{self.name}', type='{self.location_type}')>"


class ResourceFile(Base):
    """Data files associated with resources."""
    __tablename__ = "resource_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    resource_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    storage_location_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("storage_locations.id"))

    # File metadata
    file_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    file_type: Mapped[Optional[str]] = mapped_column(String(100))

    # R/Bioconductor specific
    rdata_class: Mapped[Optional[str]] = mapped_column(String(255))
    dispatch_class: Mapped[Optional[str]] = mapped_column(String(255))

    # Checksums
    md5_hash: Mapped[Optional[str]] = mapped_column(String(32))
    sha256_hash: Mapped[Optional[str]] = mapped_column(String(64))

    # Temporal
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    resource: Mapped["Resource"] = relationship(back_populates="resource_files")
    storage_location: Mapped[Optional["StorageLocation"]] = relationship(back_populates="resource_files")

    __table_args__ = (
        UniqueConstraint("resource_id", "file_path", "valid_from", name="uq_resource_file_path_valid"),
        Index("idx_resource_files_resource", "resource_id"),
        Index("idx_resource_files_storage", "storage_location_id"),
        Index("idx_resource_files_type", "file_type"),
        Index("idx_resource_files_current", "resource_id", postgresql_where=Column("valid_to").is_(None)),
    )

    def __repr__(self) -> str:
        return f"<ResourceFile(id={self.id}, resource_id={self.resource_id}, path='{self.file_path}')>"


class SourceFile(Base):
    """Upstream source files from data providers."""
    __tablename__ = "source_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    resource_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)

    # Source location
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_type: Mapped[Optional[str]] = mapped_column(String(100))
    source_version: Mapped[Optional[str]] = mapped_column(String(255))

    # File metadata
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    md5_hash: Mapped[Optional[str]] = mapped_column(String(32))
    last_modified_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Temporal
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    resource: Mapped["Resource"] = relationship(back_populates="source_files")

    __table_args__ = (
        Index("idx_source_files_resource", "resource_id"),
        Index("idx_source_files_url", "source_url"),
    )

    def __repr__(self) -> str:
        return f"<SourceFile(id={self.id}, resource_id={self.resource_id}, url='{self.source_url[:50]}...')>"


# ============================================================================
# Tags & Classification
# ============================================================================

class Tag(Base):
    """Resource classification tags."""
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tag: Mapped[str] = mapped_column(String(400), nullable=False, unique=True)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    resource_tags: Mapped[List["ResourceTag"]] = relationship(back_populates="tag_obj", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_tags_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, tag='{self.tag}', category='{self.category}')>"


class ResourceTag(Base):
    """Many-to-many junction table for resources and tags."""
    __tablename__ = "resource_tags"

    resource_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    added_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))

    # Relationships
    resource: Mapped["Resource"] = relationship(back_populates="tags")
    tag_obj: Mapped["Tag"] = relationship(back_populates="resource_tags")
    added_by_user: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        Index("idx_resource_tags_tag", "tag_id"),
    )

    def __repr__(self) -> str:
        return f"<ResourceTag(resource_id={self.resource_id}, tag_id={self.tag_id})>"


# ============================================================================
# Bioconductor Version Compatibility
# ============================================================================

class BiocRelease(Base):
    """Bioconductor release versions."""
    __tablename__ = "bioc_releases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    release_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_of_life_date: Mapped[Optional[date]] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    r_version_min: Mapped[Optional[str]] = mapped_column(String(10))
    r_version_max: Mapped[Optional[str]] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    resource_versions: Mapped[List["ResourceBiocVersion"]] = relationship(back_populates="bioc_release", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_bioc_releases_current", "is_current", postgresql_where=Column("is_current").is_(True)),
    )

    def __repr__(self) -> str:
        return f"<BiocRelease(id={self.id}, version='{self.version}', current={self.is_current})>"


class ResourceBiocVersion(Base):
    """Resource compatibility with Bioconductor versions."""
    __tablename__ = "resource_bioc_versions"

    resource_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True)
    bioc_release_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bioc_releases.id"), primary_key=True)
    is_compatible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    resource: Mapped["Resource"] = relationship(back_populates="bioc_versions")
    bioc_release: Mapped["BiocRelease"] = relationship(back_populates="resource_versions")

    __table_args__ = (
        Index("idx_resource_bioc_release", "bioc_release_id"),
    )

    def __repr__(self) -> str:
        return f"<ResourceBiocVersion(resource_id={self.resource_id}, bioc_release_id={self.bioc_release_id})>"


# ============================================================================
# Audit & Provenance
# ============================================================================

class AuditLog(Base):
    """Complete audit trail for all CRUD operations."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operation: Mapped[str] = mapped_column(String(10), nullable=False)

    # Who & when
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # What changed
    old_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    new_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    changed_fields: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))

    # Why
    change_reason: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)

    # Context
    request_id: Mapped[Optional[str]] = mapped_column(UUID)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    user: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        Index("idx_audit_table_record", "table_name", "record_id"),
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_performed_at", "performed_at"),
        Index("idx_audit_operation", "operation"),
        Index("idx_audit_request", "request_id", postgresql_where=Column("request_id").isnot(None)),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, table='{self.table_name}', op='{self.operation}', record_id={self.record_id})>"


# ============================================================================
# Legacy/Compatibility Tables
# ============================================================================

class SchemaInfo(Base):
    """Schema version tracking."""
    __tablename__ = "schema_info"

    version: Mapped[int] = mapped_column(Integer, primary_key=True, server_default="0")

    def __repr__(self) -> str:
        return f"<SchemaInfo(version={self.version})>"


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "Base",
    # User & Organization
    "Organization",
    "User",
    # Taxonomy
    "Species",
    "Genome",
    # Providers & Recipes
    "DataProvider",
    "Recipe",
    # Hub Infrastructure
    "Hub",
    "ResourceStatus",
    # Resources
    "Resource",
    # Files
    "StorageLocation",
    "ResourceFile",
    "SourceFile",
    # Tags
    "Tag",
    "ResourceTag",
    # Bioc Versions
    "BiocRelease",
    "ResourceBiocVersion",
    # Audit
    "AuditLog",
    # Legacy
    "SchemaInfo",
]
