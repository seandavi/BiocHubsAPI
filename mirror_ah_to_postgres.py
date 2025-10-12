import os
import duckdb
import httpx
import pathlib
import datetime
from loguru import logger
from dotenv import load_dotenv
import click

load_dotenv()

@click.group()
def cli():
    """Top-level CLI group for the api1 tool."""
    pass


AH_SQLITE_URL = "https://annotationhub.bioconductor.org/metadata/annotationhub.sqlite3"

def get_duckdb_connection():
    # Connect to an in-memory DuckDB database
    conn = duckdb.connect(database=':memory:')
    return conn

def attach_extension(conn, extension_name):
    # Attach the specified extension to the DuckDB connection
    conn.execute(f"INSTALL {extension_name}")
    conn.execute(f"LOAD {extension_name}")
    

def is_file_recent(file_path, max_age_days=2):
    # Check if file exists and is less than max_age_days old
    path = pathlib.Path(file_path)
    if not path.exists():
        return False
    
    file_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(path.stat().st_mtime)
    return file_age < datetime.timedelta(days=max_age_days)
    
def get_ah_sqlite_file(url, output_file):
    # check if file exists and is less than 2 days old
    if is_file_recent(output_file, max_age_days=2):
        logger.info(f"{output_file} is recent. Skipping download.")
        return
    with httpx.Client() as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(output_file, "wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
                    
def attach_postgres_database(conn: duckdb.DuckDBPyConnection, uri: str, alias: str):
    # Attach a PostgreSQL database using the provided URI and alias
    conn.execute(f"ATTACH DATABASE '{uri}' AS {alias} (type POSTGRES);")


def copy_single_table(
    conn: duckdb.DuckDBPyConnection, 
    source_alias: str,                  # the alias of the attached database (sqlite)
    table_name: str,                    # the name of the table to copy
    target_alias: str,                  # the alias of the target attached database (postgres)
    target_table_name: str | None = None):
    # Copy a table from the attached database to the DuckDB connection
    if target_table_name is None:
        target_table_name = table_name
    conn.execute(f"""
        DROP TABLE IF EXISTS {target_alias}.{target_table_name};
    """)
    conn.execute(f"""
        CREATE TABLE {target_alias}.{target_table_name} 
        AS SELECT * FROM {source_alias}.{table_name};
    """)
    
def main():
    conn = get_duckdb_connection()
    
    # Attach the HTTP extension
    attach_extension(conn, 'sqlite3')
    attach_extension(conn, 'postgres')
    
    # Download the SQLite file from the URL
    sqlite_file = "annotationhub.sqlite3"
    get_ah_sqlite_file(AH_SQLITE_URL, sqlite_file)
    
    # Attach the SQLite database
    conn.execute(f"ATTACH DATABASE '{sqlite_file}' AS ah_sqlite")
    df = conn.sql("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_catalog = 'ah_sqlite'
    """).pl()
    
    # Read Postgres URI from environment variable POSTGRES_URI
    postgres_uri = os.environ.get("POSTGRES_URI")
    if not postgres_uri:
        logger.error("Environment variable POSTGRES_URI is not set. Set it in a .env file or the environment.")
        raise RuntimeError("POSTGRES_URI not set")

    attach_postgres_database(conn, postgres_uri, "ah_postgres")
    
    # loop over tables in the SQLite database and copy them to DuckDB
    for row in df.iter_rows():
        table_name = row[0]
        logger.info(f"Copying table {table_name} from SQLite to PostgreSQL...")
        copy_single_table(conn, "ah_sqlite", table_name, 'ah_postgres', table_name)

    logger.info("All tables copied successfully.")
    

@cli.command(name='pg-dump-schema') 
def dump_postgresql_schema_from_duckdb():
    # Dump the PostgreSQL schema from DuckDB to a SQL file
    conn = get_duckdb_connection()
    attach_extension(conn, 'postgres')
    
    # Read Postgres URI from environment variable POSTGRES_URI
    postgres_uri = os.environ.get("POSTGRES_URI")
    if not postgres_uri:
        logger.error("Environment variable POSTGRES_URI is not set. Set it in a .env file or the environment.")
        raise RuntimeError("POSTGRES_URI not set")
    
    attach_postgres_database(conn, postgres_uri, "ah_postgres")
    
    # Get the schema creation statements
    result = conn.execute("""
        SELECT *
        FROM information_schema.columns
        WHERE table_catalog = 'ah_postgres'
    """).pl()
    
    schema_file = "postgres_schema.csv"
    result.write_csv(schema_file)
    
    logger.info(f"PostgreSQL schema dumped to {schema_file}")





@cli.command(name="mirror")
def mirror_command():
    """Mirror the AnnotationHub SQLite to Postgres."""
    main()
if __name__ == "__main__":
    cli()


