# app/schemas/poi_schemas.py

from pydantic import BaseModel, Field
from typing import Any, Optional


class PoiPolygonCreate(BaseModel):
    poi_id: int
    name: str
    cityName: str
    stateName: Optional[str] = None
    category: Optional[str] = None
    color: list[int]
    polygon: list[list[float]]
    properties: dict[str, Any] = Field(default_factory=dict)


class PoiPolygonResponse(BaseModel):
    id: str
    poi_id: int
    name: str
    cityName: str
    stateName: Optional[str] = None
    category: Optional[str] = None
    color: list[int]
    polygon: list[list[float]]
    properties: dict[str, Any]

    model_config = {
        "from_attributes": True
    }


class PoiImportResponse(BaseModel):
    filename: str
    imported_count: int
    skipped_count: int
    total_rows: int
    errors: list[str] = Field(default_factory=list)
