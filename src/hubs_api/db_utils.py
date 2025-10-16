"""
Database utilities for schema creation, seeding, and migrations.
"""

from datetime import date
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from .models import (
    Base,
    Hub,
    ResourceStatus,
    BiocRelease,
    Organization,
    User,
)


def create_schema(database_url: str, drop_existing: bool = False, echo: bool = False) -> None:
    """
    Create all database tables from SQLAlchemy models.

    Args:
        database_url: PostgreSQL connection string
        drop_existing: If True, drop all existing tables first
        echo: If True, log all SQL statements
    """
    engine = create_engine(database_url, echo=echo)

    if drop_existing:
        Base.metadata.drop_all(engine)

    Base.metadata.create_all(engine)


def seed_initial_data(database_url: str) -> None:
    """
    Seed the database with initial reference data.

    Args:
        database_url: PostgreSQL connection string
    """
    engine = create_engine(database_url)

    with Session(engine) as session:
        # 1. Create Hubs
        if not session.query(Hub).first():
            hubs = [
                Hub(id=1, name="AnnotationHub", code="AH", description="Annotation resources for genomic data"),
                Hub(id=2, name="ExperimentHub", code="EH", description="Experimental data and workflows"),
            ]
            session.add_all(hubs)
            session.commit()

        # 2. Create Resource Statuses
        if not session.query(ResourceStatus).first():
            statuses = [
                ResourceStatus(id=1, status="Public", is_public=True, sort_order=1),
                ResourceStatus(id=2, status="Unreviewed", is_public=False, sort_order=2),
                ResourceStatus(id=3, status="Private", is_public=False, sort_order=3),
                ResourceStatus(id=10, status="Removed from original web location", is_public=False, sort_order=10),
                ResourceStatus(id=11, status="Removed by author request", is_public=False, sort_order=11),
                ResourceStatus(id=12, status="Moved from AnnotationHub to ExperimentHub", is_public=False, sort_order=12),
                ResourceStatus(id=13, status="Replaced by more current version", is_public=False, sort_order=13),
                ResourceStatus(id=14, status="Invalid metadata", is_public=False, sort_order=14),
                ResourceStatus(id=15, status="Did not make review deadline for biocversion", is_public=False, sort_order=15),
                ResourceStatus(id=99, status="Defunct", is_public=False, sort_order=99),
            ]
            session.add_all(statuses)
            session.commit()

        # 3. Create some example Bioconductor releases
        if not session.query(BiocRelease).first():
            releases = [
                BiocRelease(version="3.18", release_date=date(2023, 10, 25), is_current=False, r_version_min="4.3"),
                BiocRelease(version="3.19", release_date=date(2024, 5, 1), is_current=False, r_version_min="4.4"),
                BiocRelease(version="3.20", release_date=date(2024, 10, 30), is_current=True, r_version_min="4.4"),
            ]
            session.add_all(releases)
            session.commit()

        # 4. Create a system organization
        if not session.query(Organization).filter_by(short_name="bioconductor").first():
            bioc_org = Organization(
                name="Bioconductor",
                short_name="bioconductor",
                website="https://bioconductor.org",
            )
            session.add(bioc_org)
            session.commit()

        # 5. Create a system user for migrations
        if not session.query(User).filter_by(email="system@bioconductor.org").first():
            bioc_org = session.query(Organization).filter_by(short_name="bioconductor").first()
            system_user = User(
                email="system@bioconductor.org",
                full_name="Bioconductor System",
                role="admin",
                organization_id=bioc_org.id if bioc_org else None,
            )
            session.add(system_user)
            session.commit()


def get_database_stats(database_url: str) -> dict:
    """
    Get statistics about the database contents.

    Args:
        database_url: PostgreSQL connection string

    Returns:
        Dictionary with table counts
    """
    engine = create_engine(database_url)

    with Session(engine) as session:
        stats = {}

        # Query counts for each table
        tables = [
            "organizations",
            "users",
            "species",
            "genomes",
            "data_providers",
            "recipes",
            "hubs",
            "resource_statuses",
            "resources",
            "storage_locations",
            "resource_files",
            "source_files",
            "tags",
            "resource_tags",
            "bioc_releases",
            "resource_bioc_versions",
            "audit_log",
        ]

        for table in tables:
            result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            stats[table] = count

        return stats


def verify_schema(database_url: str) -> bool:
    """
    Verify that the database schema matches the models.

    Args:
        database_url: PostgreSQL connection string

    Returns:
        True if schema is valid, False otherwise
    """
    engine = create_engine(database_url)

    try:
        with Session(engine) as session:
            # Try a simple query on each core table
            session.query(Hub).first()
            session.query(ResourceStatus).first()
            session.query(BiocRelease).first()
            session.query(User).first()
            session.query(Organization).first()

        return True

    except Exception:
        return False


if __name__ == "__main__":
    import os

    # Example usage
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost/biochubs_dev"
    )

    print(f"Using database: {DATABASE_URL}\n")

    # Create schema
    create_schema(DATABASE_URL, drop_existing=True)

    # Seed initial data
    seed_initial_data(DATABASE_URL)

    # Verify
    verify_schema(DATABASE_URL)

    # Show stats
    stats = get_database_stats(DATABASE_URL)
    print("\nDatabase Statistics:")
    for table, count in stats.items():
        print(f"  {table}: {count} records")
