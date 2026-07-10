from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MlPredictionPointRequest(BaseModel):
    lat: float = Field(..., description="Clicked latitude, usually a grid centroid or POI latitude.")
    lon: float = Field(..., description="Clicked longitude, usually a grid centroid or POI longitude.")
    state: str = Field(..., description="State or state abbreviation for grid/POI lookup.")
    city: str | None = Field(None, description="Optional city/market name.")
    timestamp: datetime | None = Field(None, description="Prediction time as an ISO-8601 string. Defaults to current UTC time.")
    grid_cell_id: int | None = Field(None, description="Optional grid cell id when the frontend clicked a known cell.")
    poi_id: int | None = Field(None, description="Optional Core POI id when the frontend clicked a known POI.")
    source: str | None = Field(None, description="Optional frontend source label, such as grid_centroid or poi.")


class MlTaskSummary(BaseModel):
    name: str
    path: str
    description: str
    target_columns: list[str] = Field(default_factory=list)


class MlInputResponse(BaseModel):
    task: str
    dataset: str | None = None
    grain: str
    description: str
    row_count: int
    join_keys: list[str]
    feature_columns: list[str]
    target_columns: list[str]
    rows: list[dict[str, Any]]
