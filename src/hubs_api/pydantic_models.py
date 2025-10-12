from pydantic import BaseModel, Field

class HubReturnEnvelope(BaseModel):
    """Pydantic model for the return envelope of a hub."""

    total: int = Field(..., description="Total number of items available.")
    limit: int = Field(..., description="Number of items returned in this response.")
    offset: int = Field(..., description="Offset of the first item in this response.")
    count: int = Field(..., description="Number of items in this response.")
    
    
class ResourceModel(BaseModel):
    """Pydantic model for a resource."""
    
    id: int
    ah_id: str
    title: str
    dataprovider: str
    species: str | None = None
    taxonomyid: int | None = None
    genome: str | None = None
    description: str | None = None
    coordinate_1_based: int | None = None
    maintainer: str | None = None
    status_id: int | None = None
    location_prefix_id: int | None = None
    recipe_id: int | None = None
    rdatadateadded: str | None = None  # ISO date string
    rdatadateremoved: str | None = None  # ISO date string
    record_id: int | None = None
    preparerclass: str | None = None
    
class ResourceListResponse(HubReturnEnvelope):
    """Pydantic model for a list of resources with pagination."""
    
    results: list[ResourceModel] = Field(..., description="List of resources.")