"""FastAPI REST API for AnnotationHub resources with flexible filtering."""
import os
from typing import Optional, Annotated
from fastapi import FastAPI, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, and_, func, desc
from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
import json
import sys
from loguru import logger

from hubs_api.pydantic_models import ResourceListResponse, ResourceModel
from . import models

logger.remove()
logger.add(sys.stdout, format="{message}", serialize=False)

load_dotenv()

# Database setup
DATABASE_URL = os.getenv("POSTGRES_URI", "postgresql+asyncpg://postgres@localhost:5432/ah")
if not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# FastAPI app
app = FastAPI(
    title="AnnotationHub API",
    description="REST API for querying AnnotationHub resources with flexible filtering",
    version="0.1.0",
)


async def get_db():
    """Dependency to get database session."""
    async with async_session_maker() as session:
        yield session


def parse_filter_value(value: str, field_type: type):
    """Parse a filter value string into the appropriate Python type."""
    if field_type in (int, float):
        try:
            return field_type(value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid numeric value: {value}")
    return value


def apply_filters(query, table, filters: dict):
    """
    Apply filters to a SQLAlchemy query based on field operators.
    
    Supports operators:
    - No suffix or __eq: exact match
    - __contains: substring match (case-sensitive)
    - __icontains: substring match (case-insensitive)
    - __startswith: prefix match
    - __endswith: suffix match
    - __in: value in comma-separated list
    - __not / __ne: not equal
    - __gt, __gte, __lt, __lte: comparisons (for numbers/dates)
    - __is_null: field IS NULL
    - __is_not_null: field IS NOT NULL
    """
    conditions = []
    
    # Get column objects for validation
    columns = {col.name: col for col in table.c}
    
    for param, value in filters.items():
        if value is None:
            continue
            
        # Parse field and operator
        if "__" in param:
            parts = param.rsplit("__", 1)
            field_name = parts[0]
            operator = parts[1]
        else:
            field_name = param
            operator = "eq"
        
        # Validate field exists
        if field_name not in columns:
            raise HTTPException(status_code=400, detail=f"Unknown field: {field_name}")
        
        column = columns[field_name]
        
        # Apply operator
        if operator == "eq":
            conditions.append(column == value)
        
        elif operator == "contains":
            conditions.append(column.contains(value))
        
        elif operator == "icontains":
            conditions.append(column.ilike(f"%{value}%"))
        
        elif operator == "startswith":
            conditions.append(column.startswith(value))
        
        elif operator == "endswith":
            conditions.append(column.endswith(value))
        
        elif operator == "in":
            # Split comma-separated values
            values = [v.strip() for v in value.split(",")]
            conditions.append(column.in_(values))
        
        elif operator in ("not", "ne"):
            conditions.append(column != value)
        
        elif operator == "gt":
            conditions.append(column > parse_filter_value(value, int))
        
        elif operator == "gte":
            conditions.append(column >= parse_filter_value(value, int))
        
        elif operator == "lt":
            conditions.append(column < parse_filter_value(value, int))
        
        elif operator == "lte":
            conditions.append(column <= parse_filter_value(value, int))
        
        elif operator == "is_null":
            # value should be "true" or "false"
            if value.lower() in ("true", "1", "yes"):
                conditions.append(column.is_(None))
            else:
                conditions.append(column.is_not(None))
        
        elif operator == "is_not_null":
            if value.lower() in ("true", "1", "yes"):
                conditions.append(column.is_not(None))
            else:
                conditions.append(column.is_(None))
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown operator: {operator}")
    
    if conditions:
        query = query.where(and_(*conditions))
    
    return query


def apply_sorting(query, table, sort: Optional[str]):
    """
    Apply sorting to query.
    
    Format: "field" for ascending, "-field" for descending.
    Multiple fields: "field1,-field2"
    """
    if not sort:
        return query
    
    columns = {col.name: col for col in table.c}
    
    for sort_expr in sort.split(","):
        sort_expr = sort_expr.strip()
        if not sort_expr:
            continue
        
        if sort_expr.startswith("-"):
            field_name = sort_expr[1:]
            descending = True
        else:
            field_name = sort_expr
            descending = False
        
        if field_name not in columns:
            raise HTTPException(status_code=400, detail=f"Unknown sort field: {field_name}")
        
        column = columns[field_name]
        if descending:
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column.asc())
    
    return query


class JSONLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        # Parse query params into a dict (support multi-values)
        qp = {}
        for key, value in request.query_params.multi_items():
            # accumulate multiple values under same key as list
            if key in qp:
                existing = qp[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    qp[key] = [existing, value]
            else:
                qp[key] = value

        log_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "method": request.method,
            "path": request.url.path,
            "query_string": request.url.query,
            "query_params": qp,
            "status_code": response.status_code,
            "duration_ms": int(process_time * 1000),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
        logger.info(json.dumps(log_data))
        return response


app.add_middleware(JSONLoggingMiddleware)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "AnnotationHub API",
        "version": "0.1.0",
        "endpoints": {
            "resources": "/resources",
            "docs": "/docs",
            "openapi": "/openapi.json"
        }
    }


@app.get("/resources", response_model=ResourceListResponse)
async def list_resources(
    db: AsyncSession = Depends(get_db),
    # Pagination
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Optional[str] = Query(None, description="Sort by field(s). Use '-' prefix for descending. Example: '-rdatadateadded,title'"),
    
    # Filter fields - exact match or with operators
    id: Optional[int] = None,
    ah_id: Optional[str] = None,
    title: Optional[str] = None,
    title__contains: Optional[str] = None,
    title__icontains: Optional[str] = None,
    dataprovider: Optional[str] = None,
    dataprovider__in: Optional[str] = None,
    species: Optional[str] = None,
    species__in: Optional[str] = None,
    species__contains: Optional[str] = None,
    taxonomyid: Optional[int] = None,
    genome: Optional[str] = None,
    genome__in: Optional[str] = None,
    description: Optional[str] = None,
    description__contains: Optional[str] = None,
    description__icontains: Optional[str] = None,
    coordinate_1_based: Optional[int] = None,
    maintainer: Optional[str] = None,
    maintainer__contains: Optional[str] = None,
    status_id: Optional[int] = None,
    location_prefix_id: Optional[int] = None,
    recipe_id: Optional[int] = None,
    rdatadateadded: Optional[str] = None,
    rdatadateadded__gte: Optional[str] = None,
    rdatadateadded__lte: Optional[str] = None,
    rdatadateremoved: Optional[str] = None,
    rdatadateremoved__gte: Optional[str] = None,
    rdatadateremoved__lte: Optional[str] = None,
    record_id: Optional[int] = None,
    preparerclass: Optional[str] = None,
):
    """
    List resources with flexible filtering.
    
    ## Filtering
    
    Supports various operators via field suffixes:
    
    - **Exact match**: `?species=Homo sapiens`
    - **Contains**: `?title__contains=RNA`
    - **Case-insensitive contains**: `?description__icontains=chip-seq`
    - **In list**: `?genome__in=GRCh38,GRCh37,mm10`
    - **Comparison**: `?rdatadateadded__gte=2023-01-01&rdatadateadded__lte=2024-01-01`

    ## Pagination
    
    - `limit`: Max results (1-1000, default 100)
    - `offset`: Skip N results (default 0)
    
    ## Sorting
    
    - `sort`: Field name(s), comma-separated
    - Use `-` prefix for descending: `?sort=-rdatadateadded,title`
    
    ## Examples
    
    - `?species=Homo sapiens&limit=10`
    - `?genome__in=GRCh38,GRCh37&sort=-rdatadateadded`
    - `?description__icontains=chip&rdatadateadded__gte=2023-01-01`
    """
    # Collect all query parameters
    filter_params = {}
    
    for param_name, param_value in [
        ("id", id),
        ("ah_id", ah_id),
        ("title", title),
        ("title__contains", title__contains),
        ("title__icontains", title__icontains),
        ("dataprovider", dataprovider),
        ("dataprovider__in", dataprovider__in),
        ("species", species),
        ("species__in", species__in),
        ("species__contains", species__contains),
        ("taxonomyid", taxonomyid),
        ("genome", genome),
        ("genome__in", genome__in),
        ("description", description),
        ("description__contains", description__contains),
        ("description__icontains", description__icontains),
        ("coordinate_1_based", coordinate_1_based),
        ("maintainer", maintainer),
        ("maintainer__contains", maintainer__contains),
        ("status_id", status_id),
        ("location_prefix_id", location_prefix_id),
        ("recipe_id", recipe_id),
        ("rdatadateadded", rdatadateadded),
        ("rdatadateadded__gte", rdatadateadded__gte),
        ("rdatadateadded__lte", rdatadateadded__lte),
        ("rdatadateremoved", rdatadateremoved),
        ("rdatadateremoved__gte", rdatadateremoved__gte),
        ("rdatadateremoved__lte", rdatadateremoved__lte),
        ("record_id", record_id),
        ("preparerclass", preparerclass),
    ]:
        if param_value is not None:
            filter_params[param_name] = param_value
    
    # Build query
    query = select(models.resources)
    
    # Apply filters
    query = apply_filters(query, models.resources, filter_params)
    
    # Apply sorting
    query = apply_sorting(query, models.resources, sort)
    
    # Count total (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    _total_val = total_result.scalar() if total_result else 0
    total = int(_total_val or 0)
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    # Execute query
    result = await db.execute(query)
    rows = result.fetchall()
    
    # Convert to dictionaries
    resources_list = []
    for row in rows:
        resource_dict = {
            "id": row.id,
            "ah_id": row.ah_id,
            "title": row.title,
            "dataprovider": row.dataprovider,
            "species": row.species,
            "taxonomyid": row.taxonomyid,
            "genome": row.genome,
            "description": row.description,
            "coordinate_1_based": row.coordinate_1_based,
            "maintainer": row.maintainer,
            "status_id": row.status_id,
            "location_prefix_id": row.location_prefix_id,
            "recipe_id": row.recipe_id,
            "rdatadateadded": row.rdatadateadded.isoformat() if row.rdatadateadded else None,
            "rdatadateremoved": row.rdatadateremoved.isoformat() if row.rdatadateremoved else None,
            "record_id": row.record_id,
            "preparerclass": row.preparerclass,
        }
        resources_list.append(ResourceModel(**resource_dict))
    
    return ResourceListResponse(
        total=total,
        limit=limit,
        offset=offset,
        count=len(resources_list),
        results=resources_list,
    )


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint - verifies database connectivity."""
    try:
        await db.execute(select(1))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")

@app.get("/species")
async def get_species(db: AsyncSession = Depends(get_db)):
    """Get a list of all species."""
    try:
        sql = select(models.resources.c.species, func.count().label('count')).group_by(models.resources.c.species).order_by(desc('count'))
        result = await db.execute(sql)
        resp = [{"species": row[0], "count": row[1]} for row in result.fetchall()]
        return resp
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")