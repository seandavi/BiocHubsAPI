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


__all__ = ["cli"]
