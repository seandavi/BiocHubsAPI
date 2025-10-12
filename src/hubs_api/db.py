import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv
from . import models  # Ensure models are imported to register tables

load_dotenv()

# Get PostgreSQL URI from environment variable
DATABASE_URL = os.getenv("POSTGRES_URI", "postgres+asyncpg://localhost/ah")

if not DATABASE_URL.startswith("postgres+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://")
    

async def async_main():
    # Create an asynchronous engine
    engine = create_async_engine(DATABASE_URL, echo=True)

    # Create a configured "Session" class
    async with engine.begin() as conn:
        sql = models.resources.select().limit(10)
        sql = models.resources.select().where(models.resources.c.species == "Homo sapiens").limit(10)
        result = await conn.execute(sql)
        for row in result:
            print(row)


if __name__ == "__main__":
    import asyncio
    asyncio.run(async_main())        