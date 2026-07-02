from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

# INPUT SCHEMAS

# Geometry Schemas
class GridCellCreate(BaseModel):
    cell_id: str

    row: int
    col: int

    grid_centroid_lat: float
    grid_centroid_lon: float

    # GeoJSON Polygon
    geometry: dict[str, Any]

    state: Optional[str] = "Texas"

# Metric schemas
class GridCellMetricsCreate(BaseModel):
    grid_cell_id: int
    timestamp: datetime

    heat_index: Optional[float] = None
    heat_risk: Optional[float] = None
    crowd_density: Optional[float] = None
    population: Optional[float] = None
    cooling_centers: Optional[int] = None
    cooling_centers_impact_radius: Optional[float] = None
    infrastructure_strain: Optional[float] = None

    heat_index_color: Optional[str] = "#00BFFF"
    heat_risk_color: Optional[str] = "#00BFFF"
    crowd_density_color: Optional[str] = "#00BFFF"
    population_color: Optional[str] = "#00BFFF"
    cooling_centers_color: Optional[str] = "#00BFFF"
    infrastructure_strain_color: Optional[str] = "#00BFFF"

    overall_risk_color: Optional[str] = "#00BFFF"


class GridCellMetricsAssignAll(BaseModel):
    timestamp: datetime

    heat_index: Optional[float] = None
    heat_risk: Optional[float] = None
    crowd_density: Optional[float] = None
    population: Optional[float] = None
    cooling_centers: Optional[int] = None
    cooling_centers_impact_radius: Optional[float] = None
    infrastructure_strain: Optional[float] = None

    heat_index_color: Optional[str] = "#00BFFF"
    heat_risk_color: Optional[str] = "#00BFFF"
    crowd_density_color: Optional[str] = "#00BFFF"
    population_color: Optional[str] = "#00BFFF"
    cooling_centers_color: Optional[str] = "#00BFFF"
    infrastructure_strain_color: Optional[str] = "#00BFFF"

    overall_risk_color: Optional[str] = "#00BFFF"

# OUTPUT SCHEMAS

# Geometry Schema 
class GridCellResponse(BaseModel):
    id: int

    cell_id: str

    row: int
    col: int

    grid_centroid_lat: float
    grid_centroid_lon: float

    geometry: dict[str, Any]

    state: str

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CityGridNeighborsResponse(BaseModel):
    city: str
    state: str
    lat: float
    lon: float
    center_cell_id: int
    center_cell_cell_id: str
    neighbors: list[GridCellResponse]
    neighbor_count: int
    radius: int

    model_config = ConfigDict(from_attributes=True)


# metric schemas
class GridCellMetricsResponse(BaseModel):
    id: int

    grid_cell_id: int
    cell_id: Optional[str] = None
    timestamp: datetime

    heat_index: Optional[float]
    heat_risk: Optional[float]
    crowd_density: Optional[float]
    population: Optional[float]
    cooling_centers: Optional[int]
    cooling_centers_impact_radius: Optional[float]
    infrastructure_strain: Optional[float]

    heat_index_color: Optional[str]
    heat_risk_color: Optional[str]
    crowd_density_color: Optional[str]
    population_color: Optional[str]
    cooling_centers_color: Optional[str]
    infrastructure_strain_color: Optional[str]

    overall_risk_color: Optional[str]

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
