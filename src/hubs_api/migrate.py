"""
Migration utilities to import data from SQLite to PostgreSQL.

Migrates data from annotationhub.sqlite3 and experimenthub.sqlite3 into
the normalized PostgreSQL schema.
"""

import re
import asyncio
from typing import Dict, Optional, Tuple
from pathlib import Path
import sqlite3
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from .models import (
    Base,
    Hub,
    Species,
    Genome,
    DataProvider,
    Recipe,
    User,
    Organization,
    ResourceStatus,
    StorageLocation,
    Resource,
    ResourceFile,
    SourceFile,
    Tag,
    ResourceTag,
    BiocRelease,
    ResourceBiocVersion,
)
from .db_utils import _convert_to_async_url


class DataMigrator:
    """Handles migration from SQLite to PostgreSQL."""

    def __init__(self, postgres_url: str, sqlite_ah_path: str, sqlite_eh_path: str):
        """
        Initialize migrator.

        Args:
            postgres_url: PostgreSQL connection string
            sqlite_ah_path: Path to annotationhub.sqlite3
            sqlite_eh_path: Path to experimenthub.sqlite3
        """
        self.postgres_url = _convert_to_async_url(postgres_url)
        self.sqlite_ah_path = sqlite_ah_path
        self.sqlite_eh_path = sqlite_eh_path

        # Cache for lookups during migration
        self.species_cache: Dict[str, int] = {}
        self.genome_cache: Dict[Tuple[str, str], int] = {}  # (species_name, genome_build) -> id
        self.provider_cache: Dict[str, int] = {}
        self.user_cache: Dict[str, int] = {}
        self.recipe_cache: Dict[str, int] = {}
        self.storage_cache: Dict[str, int] = {}
        self.tag_cache: Dict[str, int] = {}
        self.status_cache: Dict[str, int] = {}
        self.bioc_release_cache: Dict[str, int] = {}

    @staticmethod
    def parse_maintainer_email(maintainer: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse maintainer string to extract name and email.

        Examples:
            "Martin Morgan <mtmorgan@fhcrc.org>" -> ("Martin Morgan", "mtmorgan@fhcrc.org")
            "<maintainer@bioconductor.org>" -> (None, "maintainer@bioconductor.org")
            "maintainer@bioconductor.org" -> (None, "maintainer@bioconductor.org")
        """
        if not maintainer:
            return None, None

        # Pattern: Name <email>
        match = re.match(r'^(.+?)\s*<(.+?)>$', maintainer.strip())
        if match:
            name = match.group(1).strip() or None
            email = match.group(2).strip()
            return name, email

        # Pattern: <email>
        match = re.match(r'^<(.+?)>$', maintainer.strip())
        if match:
            return None, match.group(1).strip()

        # Plain email
        if '@' in maintainer:
            return None, maintainer.strip()

        return None, None

    async def load_caches(self, session: AsyncSession):
        """Pre-load lookup caches from existing PostgreSQL data."""
        # Load statuses
        result = await session.execute(select(ResourceStatus))
        for status in result.scalars():
            self.status_cache[status.status] = status.id

        # Load bioc releases
        result = await session.execute(select(BiocRelease))
        for release in result.scalars():
            self.bioc_release_cache[release.version] = release.id

        # Load species
        result = await session.execute(select(Species))
        for species in result.scalars():
            self.species_cache[species.scientific_name] = species.id

        # Load genomes
        result = await session.execute(select(Genome))
        for genome in result.scalars():
            species_result = await session.execute(
                select(Species).where(Species.id == genome.species_id)
            )
            species = species_result.scalar_one()
            self.genome_cache[(species.scientific_name, genome.genome_build)] = genome.id

        # Load providers
        result = await session.execute(select(DataProvider))
        for provider in result.scalars():
            self.provider_cache[provider.name] = provider.id

        # Load users
        result = await session.execute(select(User))
        for user in result.scalars():
            self.user_cache[user.email] = user.id

        # Load recipes
        result = await session.execute(select(Recipe))
        for recipe in result.scalars():
            self.recipe_cache[recipe.name] = recipe.id

        # Load storage locations
        result = await session.execute(select(StorageLocation))
        for storage in result.scalars():
            self.storage_cache[storage.name] = storage.id

        # Load tags
        result = await session.execute(select(Tag))
        for tag in result.scalars():
            self.tag_cache[tag.tag] = tag.id

    async def extract_and_create_species(self, session: AsyncSession, sqlite_conn: sqlite3.Connection):
        """Extract unique species from SQLite and create in PostgreSQL."""
        print("  Extracting species...")

        # Group by taxonomy_id to handle duplicates (same tax ID, different names)
        cursor = sqlite_conn.execute("""
            SELECT species, taxonomyid, COUNT(*) as cnt
            FROM resources
            WHERE species IS NOT NULL AND taxonomyid IS NOT NULL
            GROUP BY taxonomyid, species
            ORDER BY taxonomyid, cnt DESC
        """)

        # Track taxonomy IDs to handle duplicates
        taxonomy_id_map = {}  # taxonomy_id -> species_name
        species_data = []

        for row in cursor:
            species_name, taxonomy_id, count = row

            # Use the first (most common) name for each taxonomy_id
            if taxonomy_id not in taxonomy_id_map:
                taxonomy_id_map[taxonomy_id] = species_name
                species_data.append((species_name, taxonomy_id))

        # Create species records
        count = 0
        for species_name, taxonomy_id in species_data:
            if species_name not in self.species_cache:
                # Check if species with this taxonomy_id already exists in DB
                result = await session.execute(
                    select(Species).where(Species.taxonomy_id == taxonomy_id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Already exists, just cache it
                    self.species_cache[species_name] = existing.id
                else:
                    # Create new species
                    species = Species(
                        scientific_name=species_name,
                        taxonomy_id=taxonomy_id
                    )
                    session.add(species)
                    await session.flush()
                    self.species_cache[species_name] = species.id
                    count += 1

        await session.commit()
        print(f"    Created {count} species (total: {len(self.species_cache)})")

    async def extract_and_create_genomes(self, session: AsyncSession, sqlite_conn: sqlite3.Connection):
        """Extract unique genomes from SQLite and create in PostgreSQL."""
        print("  Extracting genomes...")

        cursor = sqlite_conn.execute("""
            SELECT DISTINCT species, genome
            FROM resources
            WHERE species IS NOT NULL AND genome IS NOT NULL
            ORDER BY species, genome
        """)

        count = 0
        for row in cursor:
            species_name, genome_build = row
            key = (species_name, genome_build)

            if key not in self.genome_cache and species_name in self.species_cache:
                # Check if genome already exists
                result = await session.execute(
                    select(Genome).where(
                        Genome.species_id == self.species_cache[species_name],
                        Genome.genome_build == genome_build
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    self.genome_cache[key] = existing.id
                else:
                    genome = Genome(
                        species_id=self.species_cache[species_name],
                        genome_build=genome_build
                    )
                    session.add(genome)
                    await session.flush()
                    self.genome_cache[key] = genome.id
                    count += 1

        await session.commit()
        print(f"    Created {count} genomes (total: {len(self.genome_cache)})")

    async def extract_and_create_providers(self, session: AsyncSession, sqlite_conn: sqlite3.Connection):
        """Extract unique data providers from SQLite and create in PostgreSQL."""
        print("  Extracting data providers...")

        cursor = sqlite_conn.execute("""
            SELECT DISTINCT dataprovider
            FROM resources
            WHERE dataprovider IS NOT NULL
            ORDER BY dataprovider
        """)

        count = 0
        for row in cursor:
            provider_name = row[0]
            if provider_name not in self.provider_cache:
                # Check if provider already exists
                result = await session.execute(
                    select(DataProvider).where(DataProvider.name == provider_name)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    self.provider_cache[provider_name] = existing.id
                else:
                    provider = DataProvider(name=provider_name)
                    session.add(provider)
                    await session.flush()
                    self.provider_cache[provider_name] = provider.id
                    count += 1

        await session.commit()
        print(f"    Created {count} data providers (total: {len(self.provider_cache)})")

    async def extract_and_create_users(self, session: AsyncSession, sqlite_conn: sqlite3.Connection):
        """Extract unique users from maintainer field and create in PostgreSQL."""
        print("  Extracting users...")

        cursor = sqlite_conn.execute("""
            SELECT DISTINCT maintainer
            FROM resources
            WHERE maintainer IS NOT NULL
            ORDER BY maintainer
        """)

        count = 0
        for row in cursor:
            maintainer_str = row[0]
            full_name, email = self.parse_maintainer_email(maintainer_str)

            if email and email not in self.user_cache:
                # Check if user already exists
                result = await session.execute(
                    select(User).where(User.email == email)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    self.user_cache[email] = existing.id
                else:
                    user = User(
                        email=email,
                        full_name=full_name,
                        role="maintainer"
                    )
                    session.add(user)
                    await session.flush()
                    self.user_cache[email] = user.id
                    count += 1

        await session.commit()
        print(f"    Created {count} users (total: {len(self.user_cache)})")

    async def extract_and_create_recipes(self, session: AsyncSession, sqlite_conn: sqlite3.Connection):
        """Extract recipes from SQLite and create in PostgreSQL."""
        print("  Extracting recipes...")

        # Get recipes from recipes table
        cursor = sqlite_conn.execute("""
            SELECT id, recipe, package
            FROM recipes
            ORDER BY id
        """)

        recipe_id_map = {}  # SQLite ID -> PostgreSQL ID
        count = 0

        for row in cursor:
            sqlite_id, recipe_name, package_name = row
            if recipe_name and recipe_name not in self.recipe_cache:
                # Check if recipe already exists
                result = await session.execute(
                    select(Recipe).where(Recipe.name == recipe_name)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    self.recipe_cache[recipe_name] = existing.id
                    recipe_id_map[sqlite_id] = existing.id
                else:
                    recipe = Recipe(
                        name=recipe_name,
                        package_name=package_name
                    )
                    session.add(recipe)
                    await session.flush()
                    self.recipe_cache[recipe_name] = recipe.id
                    recipe_id_map[sqlite_id] = recipe.id
                    count += 1

        # Also get unique preparer classes
        cursor = sqlite_conn.execute("""
            SELECT DISTINCT preparerclass
            FROM resources
            WHERE preparerclass IS NOT NULL
            ORDER BY preparerclass
        """)

        for row in cursor:
            preparer_class = row[0]
            if preparer_class and preparer_class not in self.recipe_cache:
                # Check if recipe already exists
                result = await session.execute(
                    select(Recipe).where(Recipe.name == preparer_class)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    self.recipe_cache[preparer_class] = existing.id
                else:
                    recipe = Recipe(
                        name=preparer_class,
                        preparer_class=preparer_class
                    )
                    session.add(recipe)
                    await session.flush()
                    self.recipe_cache[preparer_class] = recipe.id
                    count += 1

        await session.commit()
        print(f"    Created {count} recipes (total: {len(self.recipe_cache)})")
        return recipe_id_map

    async def extract_and_create_storage_locations(self, session: AsyncSession, sqlite_conn: sqlite3.Connection):
        """Extract storage locations from SQLite and create in PostgreSQL."""
        print("  Extracting storage locations...")

        cursor = sqlite_conn.execute("""
            SELECT id, location_prefix
            FROM location_prefixes
            ORDER BY id
        """)

        location_id_map = {}  # SQLite ID -> PostgreSQL ID
        count = 0

        for row in cursor:
            sqlite_id, location_prefix = row
            storage_name = f"Storage {sqlite_id}"

            if location_prefix and storage_name not in self.storage_cache:
                # Check if storage location already exists
                result = await session.execute(
                    select(StorageLocation).where(StorageLocation.name == storage_name)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    self.storage_cache[storage_name] = existing.id
                    location_id_map[sqlite_id] = existing.id
                else:
                    # Determine storage type from URL
                    if location_prefix.startswith('http://') or location_prefix.startswith('https://'):
                        storage_type = 'http'
                    elif location_prefix.startswith('ftp://'):
                        storage_type = 'ftp'
                    elif location_prefix.startswith('s3://'):
                        storage_type = 's3'
                    else:
                        storage_type = 'local'

                    storage = StorageLocation(
                        name=storage_name,
                        location_type=storage_type,
                        base_url=location_prefix
                    )
                    session.add(storage)
                    await session.flush()
                    self.storage_cache[storage_name] = storage.id
                    location_id_map[sqlite_id] = storage.id
                    count += 1
            elif storage_name in self.storage_cache:
                # Already in cache, just add to map
                location_id_map[sqlite_id] = self.storage_cache[storage_name]

        await session.commit()
        print(f"    Created {count} storage locations (total: {len(self.storage_cache)})")
        return location_id_map

    async def migrate_hub_resources(
        self,
        session: AsyncSession,
        sqlite_path: str,
        hub_name: str,
        hub_id: int,
        recipe_id_map: Dict[int, int],
        storage_id_map: Dict[int, int]
    ):
        """Migrate resources from a specific hub's SQLite database."""
        print(f"\n  Migrating {hub_name} resources...")

        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT *
            FROM resources
            ORDER BY id
        """)

        resources_created = 0
        batch_size = 1000
        batch = []

        for row in cursor:
            # Get foreign key IDs
            species_id = self.species_cache.get(row['species'])
            genome_id = self.genome_cache.get((row['species'], row['genome'])) if row['species'] and row['genome'] else None
            provider_id = self.provider_cache.get(row['dataprovider'])
            status_id = self.status_cache.get(row['status_id']) if 'status_id' in row.keys() else self.status_cache.get('Public', 1)

            # Parse maintainer
            _, email = self.parse_maintainer_email(row['maintainer']) if row['maintainer'] else (None, None)
            maintainer_id = self.user_cache.get(email) if email else None

            # Get recipe ID
            recipe_id = None
            if row['recipe_id'] and row['recipe_id'] in recipe_id_map:
                recipe_id = recipe_id_map[row['recipe_id']]
            elif row['preparerclass']:
                recipe_id = self.recipe_cache.get(row['preparerclass'])

            # Create resource
            resource = Resource(
                hub_id=hub_id,
                hub_accession=row['ah_id'],
                title=row['title'],
                description=row['description'],
                species_id=species_id,
                genome_id=genome_id,
                coordinate_1_based=bool(row['coordinate_1_based']) if row['coordinate_1_based'] is not None else None,
                data_provider_id=provider_id,
                recipe_id=recipe_id,
                maintainer_id=maintainer_id,
                status_id=status_id or 1,  # Default to Public
                created_at=datetime.fromisoformat(row['rdatadateadded']) if row['rdatadateadded'] else datetime.now(),
                valid_from=datetime.fromisoformat(row['rdatadateadded']) if row['rdatadateadded'] else datetime.now(),
                deleted_at=datetime.fromisoformat(row['rdatadateremoved']) if row['rdatadateremoved'] else None,
            )

            batch.append(resource)
            resources_created += 1

            # Commit in batches
            if len(batch) >= batch_size:
                session.add_all(batch)
                await session.flush()
                batch = []
                print(f"    Migrated {resources_created} resources...", end='\r')

        # Commit remaining
        if batch:
            session.add_all(batch)
            await session.flush()

        await session.commit()
        print(f"    Migrated {resources_created} resources from {hub_name}")

        conn.close()
        return resources_created

    async def migrate_tags(self, session: AsyncSession, sqlite_path: str, hub_id: int):
        """Migrate tags for resources."""
        print(f"  Migrating tags...")

        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row

        # First, extract unique tags and create Tag records
        cursor = conn.execute("""
            SELECT DISTINCT tag
            FROM tags
            WHERE tag IS NOT NULL
            ORDER BY tag
        """)

        new_tags = 0
        for row in cursor:
            tag_name = row['tag']
            if tag_name and tag_name not in self.tag_cache:
                tag = Tag(tag=tag_name)
                session.add(tag)
                await session.flush()
                self.tag_cache[tag_name] = tag.id
                new_tags += 1

        await session.commit()
        print(f"    Created {new_tags} new tags")

        # Now create resource-tag relationships
        # Need to map old resource IDs to new ones
        cursor = conn.execute("""
            SELECT r.ah_id, t.tag
            FROM tags t
            JOIN resources r ON t.resource_id = r.id
            WHERE t.tag IS NOT NULL
        """)

        resource_tags_created = 0
        batch = []
        batch_size = 5000

        for row in cursor:
            hub_accession = row['ah_id']
            tag_name = row['tag']

            if tag_name in self.tag_cache:
                # Find the PostgreSQL resource by hub_accession
                result = await session.execute(
                    select(Resource).where(
                        Resource.hub_id == hub_id,
                        Resource.hub_accession == hub_accession
                    ).limit(1)
                )
                resource = result.scalar_one_or_none()

                if resource:
                    resource_tag = ResourceTag(
                        resource_id=resource.id,
                        tag_id=self.tag_cache[tag_name]
                    )
                    batch.append(resource_tag)
                    resource_tags_created += 1

                    if len(batch) >= batch_size:
                        session.add_all(batch)
                        await session.flush()
                        batch = []
                        print(f"    Created {resource_tags_created} resource-tag links...", end='\r')

        if batch:
            session.add_all(batch)
            await session.flush()

        await session.commit()
        print(f"    Created {resource_tags_created} resource-tag relationships")

        conn.close()

    async def migrate_resource_files(self, session: AsyncSession, sqlite_path: str, hub_id: int, storage_id_map: Dict[int, int]):
        """Migrate resource files (rdatapaths)."""
        print(f"  Migrating resource files...")

        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT r.ah_id, rp.rdatapath, rp.rdataclass, rp.dispatchclass
            FROM rdatapaths rp
            JOIN resources r ON rp.resource_id = r.id
        """)

        files_created = 0
        batch = []
        batch_size = 2000

        for row in cursor:
            hub_accession = row['ah_id']

            # Find the PostgreSQL resource
            result = await session.execute(
                select(Resource).where(
                    Resource.hub_id == hub_id,
                    Resource.hub_accession == hub_accession
                ).limit(1)
            )
            resource = result.scalar_one_or_none()

            if resource:
                resource_file = ResourceFile(
                    resource_id=resource.id,
                    file_path=row['rdatapath'],
                    rdata_class=row['rdataclass'],
                    dispatch_class=row['dispatchclass']
                )
                batch.append(resource_file)
                files_created += 1

                if len(batch) >= batch_size:
                    session.add_all(batch)
                    await session.flush()
                    batch = []
                    print(f"    Created {files_created} resource files...", end='\r')

        if batch:
            session.add_all(batch)
            await session.flush()

        await session.commit()
        print(f"    Created {files_created} resource files")

        conn.close()

    async def migrate_source_files(self, session: AsyncSession, sqlite_path: str, hub_id: int):
        """Migrate source files (input_sources)."""
        print(f"  Migrating source files...")

        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT r.ah_id, i.sourceurl, i.sourcetype, i.sourceversion,
                   i.sourcemd5, i.sourcesize, i.sourcelastmodifieddate
            FROM input_sources i
            JOIN resources r ON i.resource_id = r.id
        """)

        files_created = 0
        batch = []
        batch_size = 2000

        for row in cursor:
            hub_accession = row['ah_id']

            # Find the PostgreSQL resource
            result = await session.execute(
                select(Resource).where(
                    Resource.hub_id == hub_id,
                    Resource.hub_accession == hub_accession
                ).limit(1)
            )
            resource = result.scalar_one_or_none()

            if resource:
                source_file = SourceFile(
                    resource_id=resource.id,
                    source_url=row['sourceurl'],
                    source_type=row['sourcetype'],
                    source_version=row['sourceversion'],
                    md5_hash=row['sourcemd5'],
                    file_size_bytes=int(row['sourcesize']) if row['sourcesize'] and row['sourcesize'].isdigit() else None,
                    last_modified_date=datetime.fromisoformat(row['sourcelastmodifieddate']) if row['sourcelastmodifieddate'] else None
                )
                batch.append(source_file)
                files_created += 1

                if len(batch) >= batch_size:
                    session.add_all(batch)
                    await session.flush()
                    batch = []
                    print(f"    Created {files_created} source files...", end='\r')

        if batch:
            session.add_all(batch)
            await session.flush()

        await session.commit()
        print(f"    Created {files_created} source files")

        conn.close()

    async def migrate_bioc_versions(self, session: AsyncSession, sqlite_path: str, hub_id: int):
        """Migrate Bioconductor version associations."""
        print(f"  Migrating Bioc version associations...")

        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT r.ah_id, b.biocversion
            FROM biocversions b
            JOIN resources r ON b.resource_id = r.id
        """)

        associations_created = 0
        batch = []
        batch_size = 5000

        for row in cursor:
            hub_accession = row['ah_id']
            bioc_version = row['biocversion']

            if bioc_version in self.bioc_release_cache:
                # Find the PostgreSQL resource
                result = await session.execute(
                    select(Resource).where(
                        Resource.hub_id == hub_id,
                        Resource.hub_accession == hub_accession
                    ).limit(1)
                )
                resource = result.scalar_one_or_none()

                if resource:
                    resource_bioc = ResourceBiocVersion(
                        resource_id=resource.id,
                        bioc_release_id=self.bioc_release_cache[bioc_version]
                    )
                    batch.append(resource_bioc)
                    associations_created += 1

                    if len(batch) >= batch_size:
                        session.add_all(batch)
                        await session.flush()
                        batch = []
                        print(f"    Created {associations_created} bioc associations...", end='\r')

        if batch:
            session.add_all(batch)
            await session.flush()

        await session.commit()
        print(f"    Created {associations_created} bioc version associations")

        conn.close()

    async def run_migration(self):
        """Run the full migration process."""
        print("Starting migration from SQLite to PostgreSQL...\n")

        engine = create_async_engine(self.postgres_url)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            # Load existing caches
            print("Loading existing data...")
            await self.load_caches(session)

            # Connect to AnnotationHub SQLite
            print("\nExtracting entities from AnnotationHub...")
            ah_conn = sqlite3.connect(self.sqlite_ah_path)

            await self.extract_and_create_species(session, ah_conn)
            await self.extract_and_create_genomes(session, ah_conn)
            await self.extract_and_create_providers(session, ah_conn)
            await self.extract_and_create_users(session, ah_conn)
            recipe_id_map = await self.extract_and_create_recipes(session, ah_conn)
            storage_id_map = await self.extract_and_create_storage_locations(session, ah_conn)

            ah_conn.close()

            # Also extract from ExperimentHub
            print("\nExtracting entities from ExperimentHub...")
            eh_conn = sqlite3.connect(self.sqlite_eh_path)

            await self.extract_and_create_species(session, eh_conn)
            await self.extract_and_create_genomes(session, eh_conn)
            await self.extract_and_create_providers(session, eh_conn)
            await self.extract_and_create_users(session, eh_conn)
            eh_recipe_map = await self.extract_and_create_recipes(session, eh_conn)
            eh_storage_map = await self.extract_and_create_storage_locations(session, eh_conn)

            eh_conn.close()

            # Migrate resources
            ah_count = await self.migrate_hub_resources(
                session, self.sqlite_ah_path, "AnnotationHub", 1, recipe_id_map, storage_id_map
            )
            eh_count = await self.migrate_hub_resources(
                session, self.sqlite_eh_path, "ExperimentHub", 2, eh_recipe_map, eh_storage_map
            )

            # Migrate related data for AnnotationHub
            print("\nMigrating AnnotationHub related data...")
            await self.migrate_tags(session, self.sqlite_ah_path, 1)
            await self.migrate_resource_files(session, self.sqlite_ah_path, 1, storage_id_map)
            await self.migrate_source_files(session, self.sqlite_ah_path, 1)
            await self.migrate_bioc_versions(session, self.sqlite_ah_path, 1)

            # Migrate related data for ExperimentHub
            print("\nMigrating ExperimentHub related data...")
            await self.migrate_tags(session, self.sqlite_eh_path, 2)
            await self.migrate_resource_files(session, self.sqlite_eh_path, 2, eh_storage_map)
            await self.migrate_source_files(session, self.sqlite_eh_path, 2)
            await self.migrate_bioc_versions(session, self.sqlite_eh_path, 2)

        await engine.dispose()

        print(f"\n{'='*60}")
        print(f"Migration completed successfully!")
        print(f"{'='*60}")
        print(f"Total resources migrated: {ah_count + eh_count}")
        print(f"  AnnotationHub: {ah_count}")
        print(f"  ExperimentHub: {eh_count}")
        print(f"\nEntity counts:")
        print(f"  Species: {len(self.species_cache)}")
        print(f"  Genomes: {len(self.genome_cache)}")
        print(f"  Data Providers: {len(self.provider_cache)}")
        print(f"  Users: {len(self.user_cache)}")
        print(f"  Recipes: {len(self.recipe_cache)}")
        print(f"  Storage Locations: {len(self.storage_cache)}")
        print(f"  Tags: {len(self.tag_cache)}")


async def migrate_sqlite_to_postgres(
    postgres_url: str,
    sqlite_ah_path: str = "annotationhub.sqlite3",
    sqlite_eh_path: str = "experimenthub.sqlite3"
):
    """
    Main migration function.

    Args:
        postgres_url: PostgreSQL connection string
        sqlite_ah_path: Path to AnnotationHub SQLite database
        sqlite_eh_path: Path to ExperimentHub SQLite database
    """
    migrator = DataMigrator(postgres_url, sqlite_ah_path, sqlite_eh_path)
    await migrator.run_migration()


if __name__ == "__main__":
    import os

    async def main():
        postgres_url = os.getenv("POSTGRES_URI", "postgresql://localhost/hubs_dev")
        await migrate_sqlite_to_postgres(postgres_url)

    asyncio.run(main())
