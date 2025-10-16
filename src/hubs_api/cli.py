import os
import asyncio
import click
from . import mirror


@click.group()
def cli():
    """Top-level CLI group for the hubs_api tool."""
    pass


@cli.command(name='pg-dump-schema')
def pg_dump_schema():
    """Dump the PostgreSQL schema from the attached Postgres via DuckDB."""
    mirror.dump_postgresql_schema_from_duckdb()


@cli.command(name="mirror")
def mirror_command():
    """Mirror the AnnotationHub SQLite to Postgres."""
    mirror.main()


@cli.command(name="serve")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int, reload: bool):
    """Start the FastAPI REST API server (v2 with normalized schema)."""
    import uvicorn
    click.echo(f"Starting API server on {host}:{port}")
    click.echo(f"API documentation: http://{host}:{port}/docs")
    uvicorn.run(
        "hubs_api.api_v2:app",
        host=host,
        port=port,
        reload=reload,
        access_log=False,
    )


# ============================================================================
# Database Management Commands
# ============================================================================

@cli.group(name="db")
def db_group():
    """Database schema and data management commands."""
    pass


@db_group.command(name="create-schema")
@click.option(
    "--database-url",
    envvar="POSTGRES_URI",
    required=True,
    help="PostgreSQL connection string (or set POSTGRES_URI env var)"
)
@click.option(
    "--drop-existing",
    is_flag=True,
    help="Drop existing tables before creating schema"
)
@click.confirmation_option(
    prompt="Are you sure you want to create the database schema?",
    help="Skip confirmation prompt"
)
def create_schema(database_url: str, drop_existing: bool):
    """Create database schema from SQLAlchemy models."""
    from . import db_utils

    click.echo(f"Creating schema in database: {database_url}")

    if drop_existing:
        click.echo(click.style("⚠️  WARNING: Dropping all existing tables!", fg="yellow", bold=True))

    try:
        asyncio.run(db_utils.create_schema(database_url, drop_existing=drop_existing))
        click.echo(click.style("✓ Schema created successfully!", fg="green"))
    except Exception as e:
        click.echo(click.style(f"✗ Error creating schema: {e}", fg="red"), err=True)
        raise click.Abort()


@db_group.command(name="seed")
@click.option(
    "--database-url",
    envvar="POSTGRES_URI",
    required=True,
    help="PostgreSQL connection string (or set POSTGRES_URI env var)"
)
def seed_data(database_url: str):
    """Seed database with initial reference data (hubs, statuses, bioc releases)."""
    from . import db_utils

    click.echo(f"Seeding initial data in database: {database_url}")

    try:
        asyncio.run(db_utils.seed_initial_data(database_url))
        click.echo(click.style("✓ Initial data seeded successfully!", fg="green"))
    except Exception as e:
        click.echo(click.style(f"✗ Error seeding data: {e}", fg="red"), err=True)
        raise click.Abort()


@db_group.command(name="stats")
@click.option(
    "--database-url",
    envvar="POSTGRES_URI",
    required=True,
    help="PostgreSQL connection string (or set POSTGRES_URI env var)"
)
def show_stats(database_url: str):
    """Show database statistics (record counts per table)."""
    from . import db_utils

    click.echo(f"Fetching statistics from database: {database_url}\n")

    try:
        stats = asyncio.run(db_utils.get_database_stats(database_url))

        # Calculate column width for alignment
        max_table_len = max(len(table) for table in stats.keys())

        click.echo(click.style("Database Statistics", bold=True))
        click.echo("=" * (max_table_len + 20))

        # Group tables by category
        categories = {
            "Infrastructure": ["hubs", "resource_statuses", "bioc_releases"],
            "Organizations & Users": ["organizations", "users"],
            "Taxonomy": ["species", "genomes"],
            "Data Providers": ["data_providers", "recipes", "storage_locations"],
            "Resources": ["resources"],
            "Files": ["resource_files", "source_files"],
            "Classification": ["tags", "resource_tags"],
            "Bioconductor": ["resource_bioc_versions"],
            "Audit": ["audit_log"],
        }

        for category, tables in categories.items():
            click.echo(f"\n{click.style(category, fg='cyan', bold=True)}")
            for table in tables:
                if table in stats:
                    count = stats[table]
                    color = "green" if count > 0 else "white"
                    click.echo(f"  {table:<{max_table_len}} : {click.style(str(count), fg=color)}")

        # Show totals
        total_records = sum(stats.values())
        click.echo("\n" + "=" * (max_table_len + 20))
        click.echo(f"{click.style('Total Records', bold=True):<{max_table_len + 2}}: {click.style(str(total_records), fg='cyan', bold=True)}")

    except Exception as e:
        click.echo(click.style(f"✗ Error fetching statistics: {e}", fg="red"), err=True)
        raise click.Abort()


@db_group.command(name="verify")
@click.option(
    "--database-url",
    envvar="POSTGRES_URI",
    required=True,
    help="PostgreSQL connection string (or set POSTGRES_URI env var)"
)
def verify_schema(database_url: str):
    """Verify that database schema matches SQLAlchemy models."""
    from . import db_utils

    click.echo(f"Verifying schema in database: {database_url}\n")

    try:
        is_valid = asyncio.run(db_utils.verify_schema(database_url))

        if is_valid:
            click.echo(click.style("✓ Schema verification passed!", fg="green", bold=True))
        else:
            click.echo(click.style("✗ Schema verification failed!", fg="red", bold=True))
            raise click.Abort()

    except Exception as e:
        click.echo(click.style(f"✗ Error verifying schema: {e}", fg="red"), err=True)
        raise click.Abort()


@db_group.command(name="init")
@click.option(
    "--database-url",
    envvar="POSTGRES_URI",
    required=True,
    help="PostgreSQL connection string (or set POSTGRES_URI env var)"
)
@click.option(
    "--drop-existing",
    is_flag=True,
    help="Drop existing tables before creating schema"
)
def init_database(database_url: str, drop_existing: bool):
    """Initialize database (create schema + seed data)."""
    from . import db_utils

    click.echo(click.style("Initializing database...\n", bold=True))
    click.echo(f"Database: {database_url}\n")

    if drop_existing:
        click.echo(click.style("⚠️  WARNING: This will drop all existing tables!", fg="yellow", bold=True))
        if not click.confirm("Are you sure you want to continue?"):
            raise click.Abort()

    try:
        # Step 1: Create schema
        click.echo("\n[1/3] Creating schema...")
        asyncio.run(db_utils.create_schema(database_url, drop_existing=drop_existing))
        click.echo(click.style("  ✓ Schema created", fg="green"))

        # Step 2: Seed data
        click.echo("\n[2/3] Seeding initial data...")
        asyncio.run(db_utils.seed_initial_data(database_url))
        click.echo(click.style("  ✓ Data seeded", fg="green"))

        # Step 3: Verify
        click.echo("\n[3/3] Verifying schema...")
        is_valid = asyncio.run(db_utils.verify_schema(database_url))
        if is_valid:
            click.echo(click.style("  ✓ Verification passed", fg="green"))
        else:
            click.echo(click.style("  ✗ Verification failed", fg="red"))
            raise click.Abort()

        # Show final stats
        click.echo("\n" + "=" * 60)
        click.echo(click.style("Database initialized successfully! 🎉", fg="green", bold=True))
        click.echo("=" * 60 + "\n")

        stats = asyncio.run(db_utils.get_database_stats(database_url))
        click.echo("Initial record counts:")
        for table, count in sorted(stats.items()):
            if count > 0:
                click.echo(f"  {table}: {count}")

    except Exception as e:
        click.echo(click.style(f"\n✗ Database initialization failed: {e}", fg="red", bold=True), err=True)
        raise click.Abort()


@db_group.command(name="migrate")
@click.option(
    "--database-url",
    envvar="POSTGRES_URI",
    required=True,
    help="PostgreSQL connection string (or set POSTGRES_URI env var)"
)
@click.option(
    "--sqlite-ah",
    default="annotationhub.sqlite3",
    help="Path to AnnotationHub SQLite database"
)
@click.option(
    "--sqlite-eh",
    default="experimenthub.sqlite3",
    help="Path to ExperimentHub SQLite database"
)
@click.confirmation_option(
    prompt="This will migrate all data from SQLite to PostgreSQL. Continue?",
    help="Skip confirmation prompt"
)
def migrate_data(database_url: str, sqlite_ah: str, sqlite_eh: str):
    """Migrate data from SQLite databases to PostgreSQL."""
    from pathlib import Path
    from . import migrate

    # Verify SQLite files exist
    ah_path = Path(sqlite_ah)
    eh_path = Path(sqlite_eh)

    if not ah_path.exists():
        click.echo(click.style(f"✗ AnnotationHub database not found: {sqlite_ah}", fg="red"), err=True)
        raise click.Abort()

    if not eh_path.exists():
        click.echo(click.style(f"✗ ExperimentHub database not found: {sqlite_eh}", fg="red"), err=True)
        raise click.Abort()

    click.echo(click.style("Starting migration...\n", bold=True))
    click.echo(f"Source databases:")
    click.echo(f"  AnnotationHub: {click.style(sqlite_ah, fg='cyan')}")
    click.echo(f"  ExperimentHub:  {click.style(sqlite_eh, fg='cyan')}")
    click.echo(f"Target database: {click.style(database_url, fg='cyan')}\n")

    try:
        asyncio.run(migrate.migrate_sqlite_to_postgres(
            postgres_url=database_url,
            sqlite_ah_path=sqlite_ah,
            sqlite_eh_path=sqlite_eh
        ))
        click.echo(click.style("\n✓ Migration completed successfully!", fg="green", bold=True))
    except Exception as e:
        click.echo(click.style(f"\n✗ Migration failed: {e}", fg="red", bold=True), err=True)
        import traceback
        traceback.print_exc()
        raise click.Abort()


__all__ = ["cli"]
