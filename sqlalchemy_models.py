from sqlalchemy import (
    MetaData,
    Table,
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Date,
    DateTime,
    Boolean,
    Numeric,
)


metadata = MetaData()


# Table: tags
tags = Table(
    "tags",
    metadata,
    Column("tag", String, nullable=True),
    Column("resource_id", BigInteger, nullable=True),
    schema="public",
)


# Table: resources
resources = Table(
    "resources",
    metadata,
    Column("id", BigInteger, nullable=True),
    Column("ah_id", String, nullable=True),
    Column("title", String, nullable=True),
    Column("dataprovider", String, nullable=True),
    Column("species", String, nullable=True),
    Column("taxonomyid", BigInteger, nullable=True),
    Column("genome", String, nullable=True),
    Column("description", String, nullable=True),
    Column("coordinate_1_based", BigInteger, nullable=True),
    Column("maintainer", String, nullable=True),
    Column("status_id", BigInteger, nullable=True),
    Column("location_prefix_id", BigInteger, nullable=True),
    Column("recipe_id", BigInteger, nullable=True),
    Column("rdatadateadded", Date, nullable=True),
    Column("rdatadateremoved", Date, nullable=True),
    Column("record_id", BigInteger, nullable=True),
    Column("preparerclass", String, nullable=True),
    schema="public",
)


# Table: schema_info
schema_info = Table(
    "schema_info",
    metadata,
    Column("version", BigInteger, nullable=True),
    schema="public",
)


# Table: recipes
recipes = Table(
    "recipes",
    metadata,
    Column("id", BigInteger, nullable=True),
    Column("recipe", String, nullable=True),
    Column("package", String, nullable=True),
    schema="public",
)


# Table: timestamp
# Note: table name 'timestamp' is valid but shadows SQL type name in many contexts
timestamp = Table(
    "timestamp",
    metadata,
    Column("timestamp", DateTime, nullable=True),
    schema="public",
)


# Table: statuses
statuses = Table(
    "statuses",
    metadata,
    Column("id", BigInteger, nullable=True),
    Column("status", String, nullable=True),
    schema="public",
)


# Table: location_prefixes
location_prefixes = Table(
    "location_prefixes",
    metadata,
    Column("id", BigInteger, nullable=True),
    Column("location_prefix", String, nullable=True),
    schema="public",
)


# Table: input_sources
input_sources = Table(
    "input_sources",
    metadata,
    Column("id", BigInteger, nullable=True),
    Column("sourcesize", String, nullable=True),
    Column("sourceurl", String, nullable=True),
    Column("sourceversion", String, nullable=True),
    Column("sourcemd5", String, nullable=True),
    Column("sourcelastmodifieddate", Date, nullable=True),
    Column("resource_id", BigInteger, nullable=True),
    Column("sourcetype", String, nullable=True),
    schema="public",
)


# Table: test
test = Table(
    "test",
    metadata,
    Column("id", BigInteger, nullable=True),
    Column("name", String, nullable=True),
    schema="public",
)


# Table: rdatapaths
rdatapaths = Table(
    "rdatapaths",
    metadata,
    Column("id", BigInteger, nullable=True),
    Column("rdatapath", String, nullable=True),
    Column("rdataclass", String, nullable=True),
    Column("resource_id", BigInteger, nullable=True),
    Column("dispatchclass", String, nullable=True),
    schema="public",
)


# Table: biocversions
biocversions = Table(
    "biocversions",
    metadata,
    Column("id", BigInteger, nullable=True),
    Column("biocversion", String, nullable=True),
    Column("resource_id", BigInteger, nullable=True),
    schema="public",
)


__all__ = [
    "metadata",
    "tags",
    "resources",
    "schema_info",
    "recipes",
    "timestamp",
    "statuses",
    "location_prefixes",
    "input_sources",
    "test",
    "rdatapaths",
    "biocversions",
]
