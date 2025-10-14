# AnnotationHub API - Usage Guide

## Quick Start

### 1. Install dependencies
```bash
# From project root
uv sync
# or
pip install -e .
```

### 2. Set up environment
Make sure your `.env` file contains the Postgres connection string:
```
POSTGRES_URI=postgresql://postgres@localhost:5432/ah
```

### 3. Start the API server
```bash
# Using the CLI
hubs-api serve

# With auto-reload for development
hubs-api serve --reload

# Custom host/port
hubs-api serve --host 127.0.0.1 --port 8080

# Or run directly with uvicorn
uvicorn hubs_api.api:app --reload
```

### 4. Access the API
- **Interactive docs**: http://localhost:8000/docs
- **OpenAPI spec**: http://localhost:8000/openapi.json
- **Health check**: http://localhost:8000/health

---

## API Endpoints

### GET /resources

List and filter AnnotationHub resources with flexible query parameters.

#### Basic Usage

```bash
# Get first 10 resources
curl "http://localhost:8000/resources?limit=10"

# Filter by species
curl "http://localhost:8000/resources?species=Homo%20sapiens"

# Filter by genome
curl "http://localhost:8000/resources?genome=GRCh38"
```

#### Filtering Examples

**Exact match:**
```bash
curl "http://localhost:8000/resources?species=Homo%20sapiens&genome=GRCh38"
```

**Substring search (case-insensitive):**
```bash
curl "http://localhost:8000/resources?description__icontains=chip-seq"
curl "http://localhost:8000/resources?title__icontains=rna"
```

**Multiple values (OR logic):**
```bash
# Resources with genome GRCh38, GRCh37, or mm10
curl "http://localhost:8000/resources?genome__in=GRCh38,GRCh37,mm10"

# Resources from multiple species
curl "http://localhost:8000/resources?species__in=Homo%20sapiens,Mus%20musculus"
```

**Date range filtering:**
```bash
# Resources added in 2023
curl "http://localhost:8000/resources?rdatadateadded__gte=2023-01-01&rdatadateadded__lt=2024-01-01"

# Resources added after a specific date
curl "http://localhost:8000/resources?rdatadateadded__gte=2023-06-01"
```

**Complex filters (combining multiple conditions):**
```bash
# Human genome resources added in 2023 with "ChIP" in description
curl "http://localhost:8000/resources?species=Homo%20sapiens&rdatadateadded__gte=2023-01-01&rdatadateadded__lt=2024-01-01&description__icontains=chip"
```

#### Pagination

```bash
# Get first 50 results
curl "http://localhost:8000/resources?limit=50"

# Skip first 100, get next 50
curl "http://localhost:8000/resources?limit=50&offset=100"
```

#### Sorting

```bash
# Sort by date added (ascending)
curl "http://localhost:8000/resources?sort=rdatadateadded"

# Sort by date added (descending, most recent first)
curl "http://localhost:8000/resources?sort=-rdatadateadded"

# Multi-field sort: by species (asc), then date (desc)
curl "http://localhost:8000/resources?sort=species,-rdatadateadded"
```

#### Combined Example

```bash
# Human GRCh38 resources with "RNA-seq" in description, 
# added in 2023, sorted by date (newest first), limit 20
curl "http://localhost:8000/resources?\
species=Homo%20sapiens&\
genome=GRCh38&\
description__icontains=rna-seq&\
rdatadateadded__gte=2023-01-01&\
rdatadateadded__lt=2024-01-01&\
sort=-rdatadateadded&\
limit=20"
```

---

## Supported Filter Operators

| Operator | Example | Description |
|----------|---------|-------------|
| (none) or `__eq` | `?species=Homo sapiens` | Exact match |
| `__contains` | `?title__contains=RNA` | Substring match (case-sensitive) |
| `__icontains` | `?description__icontains=chip` | Substring match (case-insensitive) |
| `__startswith` | `?ah_id__startswith=AH` | Prefix match |
| `__endswith` | `?title__endswith=.bed` | Suffix match |
| `__in` | `?genome__in=GRCh38,mm10` | Value in list (comma-separated) |
| `__not` / `__ne` | `?species__not=Homo sapiens` | Not equal |
| `__gt` | `?id__gt=1000` | Greater than |
| `__gte` | `?rdatadateadded__gte=2023-01-01` | Greater than or equal |
| `__lt` | `?id__lt=5000` | Less than |
| `__lte` | `?rdatadateadded__lte=2024-01-01` | Less than or equal |
| `__is_null` | `?rdatadateremoved__is_null=true` | Field is NULL |
| `__is_not_null` | `?genome__is_not_null=true` | Field is NOT NULL |

---

## Response Format

All `/resources` responses include:

```json
{
  "total": 12345,        // Total matching records (before pagination)
  "limit": 100,          // Requested limit
  "offset": 0,           // Requested offset
  "count": 100,          // Number of results in this response
  "results": [           // Array of resource objects
    {
      "id": 1,
      "ah_id": "AH5086",
      "title": "Homo sapiens GRCh38 Ensembl Genes",
      "dataprovider": "Ensembl",
      "species": "Homo sapiens",
      "taxonomyid": 9606,
      "genome": "GRCh38",
      "description": "Gene annotation for Homo sapiens genome build GRCh38",
      "coordinate_1_based": 1,
      "maintainer": "Bioconductor Package Maintainer",
      "status_id": 1,
      "location_prefix_id": 1,
      "recipe_id": 42,
      "rdatadateadded": "2023-04-15",
      "rdatadateremoved": null,
      "record_id": 5086,
      "preparerclass": "Ensembl"
    },
    // ... more results
  ]
}
```

---

## Python Client Example

```python
import httpx

BASE_URL = "http://localhost:8000"

# Simple query
response = httpx.get(f"{BASE_URL}/resources", params={
    "species": "Homo sapiens",
    "genome": "GRCh38",
    "limit": 10
})
data = response.json()
print(f"Found {data['total']} resources, showing {data['count']}")
for resource in data['results']:
    print(f"  - {resource['ah_id']}: {resource['title']}")

# Complex query with multiple filters
response = httpx.get(f"{BASE_URL}/resources", params={
    "species__in": "Homo sapiens,Mus musculus",
    "description__icontains": "chip-seq",
    "rdatadateadded__gte": "2023-01-01",
    "sort": "-rdatadateadded",
    "limit": 50
})
data = response.json()
```

---

## Development Tips

### Enable SQL query logging
Set `echo=True` in `api.py`:
```python
engine = create_async_engine(DATABASE_URL, echo=True)
```

### Test filters quickly
Use the interactive docs at `/docs` - FastAPI automatically generates a UI where you can test all query parameters.

### Add custom endpoints
Edit `src/hubs_api/api.py` to add new endpoints for other tables (tags, recipes, etc.)

---

## Next Steps (Future Enhancements)

- **Tier 2 filtering**: Add JSON filter DSL for complex AND/OR/NOT combinations
- **Full-text search**: Add Postgres full-text search on title/description
- **Relationships**: Join with tags, recipes, statuses tables
- **Aggregations**: Add endpoints for counts/grouping by species, genome, etc.
- **Export formats**: Support CSV/TSV/JSON-lines output
- **Authentication**: Add API keys or OAuth for production use
