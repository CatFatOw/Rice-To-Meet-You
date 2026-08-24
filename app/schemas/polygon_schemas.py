from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Any

# CREATE SCHEMAS
class PolygonGeometryCreate(BaseModel):
    name: str | None = None
    city_name: str | None = None
    state_name: str | None = None
    color: list[int] | None = None
    geometry: dict[str, Any]


class PolygonGeometryUpdate(BaseModel):
    name: str | None = None
    city_name: str | None = None
    state_name: str | None = None
    color: list[int] | None = None
    geometry: dict[str, Any]


class PolygonImpactGridsCreate(BaseModel):
    polygon_geometry_id: int
    grid_cell_id: int



# RESPONSE SCHEMAS 
class PolygonGeometryResponse(BaseModel):
    id: int
    name: str | None = None
    city_name: str | None = None
    state_name: str | None = None
    color: list[int] | None = None
    geometry: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PolygonImpactGridsResponse(BaseModel):
    id: int
    polygon_geometry_id: int
    grid_cell_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PolygonImpactComputeResponse(BaseModel):
    polygon_id: int
    impacted_grid_count: int
    impacted_grids: list[PolygonImpactGridsResponse]

    model_config = ConfigDict(from_attributes=True)


class PolygonImpactSummaryResponse(BaseModel):
    polygon_geometry_id: int
    impacted_count: int
    impacted_grid_cell_ids: list[int]
