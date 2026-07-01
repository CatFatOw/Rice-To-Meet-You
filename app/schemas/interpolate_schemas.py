from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class InterpolatedPointBase(BaseModel):
    """Base schema for interpolated grid cell metrics."""

    grid_cell_id: int
    timestamp: datetime

    latitude: float
    longitude: float

    heat_index: Optional[float] = None
    heat_risk: Optional[float] = None
    crowd_density: Optional[float] = None
    population: Optional[float] = None
    cooling_centers: Optional[float] = None
    infrastructure_strain: Optional[float] = None

    interpolation_method: str = "kriging"
    source_count: Optional[int] = None
    confidence: Optional[float] = None


class InterpolatedPointCreate(InterpolatedPointBase):
    """Schema for creating an interpolated point."""
    pass


class InterpolatedPointUpdate(BaseModel):
    """Schema for updating an interpolated point."""

    grid_cell_id: Optional[int] = None
    timestamp: Optional[datetime] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    heat_index: Optional[float] = None
    heat_risk: Optional[float] = None
    crowd_density: Optional[float] = None
    population: Optional[float] = None
    cooling_centers: Optional[float] = None
    infrastructure_strain: Optional[float] = None

    interpolation_method: Optional[str] = None
    source_count: Optional[int] = None
    confidence: Optional[float] = None


class InterpolationRunRequest(BaseModel):
    """Request body for interpolating known points onto a city grid."""

    city: str
    state: str
    timestamp: datetime
    known_points: list[dict[str, Any]] = Field(default_factory=list)
    metric_key: str = "heat_index"
    replace_existing: bool = True


class InterpolatedPointResponse(InterpolatedPointBase):
    """Schema returned after creating/retrieving an interpolated point."""

    id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
