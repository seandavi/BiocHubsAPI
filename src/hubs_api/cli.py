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
    """Start the FastAPI REST API server."""
    import uvicorn
    uvicorn.run(
        "hubs_api.api:app",
        host=host,
        port=port,
        reload=reload,
    )


__all__ = ["cli"]
