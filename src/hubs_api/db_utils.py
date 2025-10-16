"""
Database utilities for schema creation, seeding, and migrations.

Uses async/await with asyncpg for PostgreSQL operations.
"""

from datetime import date
from typing import Optional
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from .models import (
    Base,
    Hub,
    ResourceStatus,
    BiocRelease,
    Organization,
    User,
)


def _convert_to_async_url(database_url: str) -> str:
    """Convert postgresql:// URL to postgresql+asyncpg:// for async operations."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql+asyncpg://"):
        return database_url
    else:
        raise ValueError(f"Unsupported database URL scheme: {database_url}")


async def create_schema(database_url: str, drop_existing: bool = False, echo: bool = False) -> None:
    """
    Create all database tables from SQLAlchemy models.

    Args:
        database_url: PostgreSQL connection string (will be converted to asyncpg)
        drop_existing: If True, drop all existing tables first
        echo: If True, log all SQL statements
    """
    async_url = _convert_to_async_url(database_url)
    engine = create_async_engine(async_url, echo=echo)

    async with engine.begin() as conn:
        if drop_existing:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()


async def seed_initial_data(database_url: str) -> None:
    """
    Seed the database with initial reference data.

    Args:
        database_url: PostgreSQL connection string (will be converted to asyncpg)
    """
    async_url = _convert_to_async_url(database_url)
    engine = create_async_engine(async_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Create Hubs
        result = await session.execute(select(Hub))
        if not result.first():
            hubs = [
                Hub(id=1, name="AnnotationHub", code="AH", description="Annotation resources for genomic data"),
                Hub(id=2, name="ExperimentHub", code="EH", description="Experimental data and workflows"),
            ]
            session.add_all(hubs)
            await session.commit()

        # 2. Create Resource Statuses
        result = await session.execute(select(ResourceStatus))
        if not result.first():
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
            await session.commit()

        # 3. Create some example Bioconductor releases
        result = await session.execute(select(BiocRelease))
        if not result.first():
            releases = [
                BiocRelease(version="3.18", release_date=date(2023, 10, 25), is_current=False, r_version_min="4.3"),
                BiocRelease(version="3.19", release_date=date(2024, 5, 1), is_current=False, r_version_min="4.4"),
                BiocRelease(version="3.20", release_date=date(2024, 10, 30), is_current=True, r_version_min="4.4"),
            ]
            session.add_all(releases)
            await session.commit()

        # 4. Create a system organization
        result = await session.execute(select(Organization).filter_by(short_name="bioconductor"))
        if not result.scalar_one_or_none():
            bioc_org = Organization(
                name="Bioconductor",
                short_name="bioconductor",
                website="https://bioconductor.org",
            )
            session.add(bioc_org)
            await session.commit()

        # 5. Create a system user for migrations
        result = await session.execute(select(User).filter_by(email="system@bioconductor.org"))
        if not result.scalar_one_or_none():
            bioc_org_result = await session.execute(select(Organization).filter_by(short_name="bioconductor"))
            bioc_org = bioc_org_result.scalar_one_or_none()

            system_user = User(
                email="system@bioconductor.org",
                full_name="Bioconductor System",
                role="admin",
                organization_id=bioc_org.id if bioc_org else None,
            )
            session.add(system_user)
            await session.commit()

    await engine.dispose()


async def get_database_stats(database_url: str) -> dict:
    """
    Get statistics about the database contents.

    Args:
        database_url: PostgreSQL connection string (will be converted to asyncpg)

    Returns:
        Dictionary with table counts
    """
    async_url = _convert_to_async_url(database_url)
    engine = create_async_engine(async_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
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
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            stats[table] = count

    await engine.dispose()
    return stats


async def verify_schema(database_url: str) -> bool:
    """
    Verify that the database schema matches the models.

    Args:
        database_url: PostgreSQL connection string (will be converted to asyncpg)

    Returns:
        True if schema is valid, False otherwise
    """
    async_url = _convert_to_async_url(database_url)
    engine = create_async_engine(async_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            # Try a simple query on each core table
            await session.execute(select(Hub).limit(1))
            await session.execute(select(ResourceStatus).limit(1))
            await session.execute(select(BiocRelease).limit(1))
            await session.execute(select(User).limit(1))
            await session.execute(select(Organization).limit(1))

        await engine.dispose()
        return True

    except Exception:
        await engine.dispose()
        return False


if __name__ == "__main__":
    import os
    import asyncio

    async def main():
        # Example usage
        DATABASE_URL = os.getenv(
            "POSTGRES_URI",
            "postgresql://localhost/biochubs_dev"
        )

        print(f"Using database: {DATABASE_URL}\n")

        # Create schema
        await create_schema(DATABASE_URL, drop_existing=True)

        # Seed initial data
        await seed_initial_data(DATABASE_URL)

        # Verify
        is_valid = await verify_schema(DATABASE_URL)
        print(f"\nSchema valid: {is_valid}")

        # Show stats
        stats = await get_database_stats(DATABASE_URL)
        print("\nDatabase Statistics:")
        for table, count in stats.items():
            print(f"  {table}: {count} records")

    asyncio.run(main())
