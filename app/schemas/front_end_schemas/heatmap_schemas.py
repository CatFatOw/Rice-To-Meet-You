"""Pydantic response schemas for frontend heatmap endpoints."""

from pydantic import BaseModel, Field
from typing import Any, List
from datetime import datetime


class HeatmapPolygonBase(BaseModel):
    """Frontend polygon overlay shape used by deck.gl polygon layers."""
    id: str
    name: str
    cityName: str
    stateName: str | None = None
    category: str | None = None
    poi_id: int | None = None
    color: List[int] = Field(..., min_length=4, max_length=4)
    polygon: List[List[float]]
    properties: dict[str, Any] | None = None


class HeatmapPolygonCreate(HeatmapPolygonBase):
    pass


class HeatmapPolygonResponse(HeatmapPolygonBase):
    pass


class LocationPOIResponse(HeatmapPolygonBase):
    pass


class HeatmapMetricValue(BaseModel):
    """One weighted point rendered by the frontend heatmap layer."""
    value: float
    location_name: str
    location_coordinates: List[float] = Field(..., min_length=2, max_length=2)
    individual_metrics: dict[str, float | None] | None = None


class HeatmapMetricPoint(BaseModel):
    """One named metric layer and all points for that layer."""
    metric: str
    points: List[HeatmapMetricValue]


class MetricGrid(BaseModel):
    """One metric's interpolated value lattice for a city (row 0 = south)."""
    min: float
    max: float
    values: List[List[float | None]]


class CityMetricGrid(BaseModel):
    """A city's full interpolated raster grid for continuous map rendering."""
    state: str | None = None
    bounds: List[float] = Field(..., min_length=4, max_length=4)
    rows: int
    cols: int
    timestamp: str
    metrics: dict[str, MetricGrid]


class SimulationPolygonCreate(BaseModel):
    """Frontend drawing payload for creating a simulation polygon."""
    name: str | None = None
    cityName: str
    stateName: str | None = None
    color: List[int] | None = Field(default=None, min_length=4, max_length=4)
    polygon: List[List[float]] = Field(..., min_length=3)


class SimulationPlacedObject(BaseModel):
    """Toolbox object dropped onto the map by the frontend simulation UI."""
    id: str
    type: str
    longitude: float
    latitude: float


class SimulationApplyRequest(BaseModel):
    """Frontend payload for applying simulation objects to impacted grids."""
    cityName: str | None = None
    stateName: str | None = None
    polygonGeometryId: int | None = None
    impactedGridCellIds: List[int] | None = None
    placedObjects: List[SimulationPlacedObject] = Field(default_factory=list)
    timestamp: datetime | None = None
