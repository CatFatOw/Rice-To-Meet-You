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


class SurfacePoint(BaseModel):
    """One observation feeding a kriged surface."""

    longitude: float
    latitude: float
    value: float


class SurfaceRequest(BaseModel):
    """Request body for kriging observations into a continuous surface.

    Points are supplied by the caller rather than read from the database: the
    simulation page krige the readings it is currently displaying, which for a
    running simulation exist only in the browser.
    """

    metric_key: str = "average_temperature_c"
    points: list[SurfacePoint] = Field(default_factory=list)
    rows: int = 48
    cols: int = 48
    # The city the surface covers. Its rectangle sets both the readings that are
    # fitted and the lattice extent, so the same city renders at the same extent
    # on every date. Omitting it falls back to the bounding box of the points,
    # which is only appropriate for a view that is not scoped to one city.
    city: Optional[str] = None
    # Optional [minLon, minLat, maxLon, maxLat] override. Takes precedence over
    # the city extent; rarely needed.
    bounds: Optional[list[float]] = None
    # Degrees by which to widen the rectangle when selecting the readings to fit
    # on. 0 keeps it strict: only readings inside the city rectangle are used.
    boundary_buffer_deg: float = 0.0


class SurfaceResponse(BaseModel):
    """A regular value lattice ready to be drawn as one continuous image."""

    metric_key: str
    bounds: list[float]
    rows: int
    cols: int
    # values[row][col]; row 0 is the southernmost row. The lattice spans exactly
    # the city rectangle, so every cell carries a value.
    values: list[list[float]]
    min: float
    max: float
    variance_mean: float
    # Readings inside the city rectangle that fed this surface's fit.
    source_count: int
    # Resolved city name, and its rectangle as a GeoJSON Polygon for drawing.
    # Both null when the request carried no city.
    city: Optional[str] = None
    boundary: Optional[dict[str, Any]] = None
    interpolation_method: str = "ordinary_kriging"


class CityBoundaryResponse(BaseModel):
    """A city's interpolation rectangle."""

    city: str
    state: str
    # [minLon, minLat, maxLon, maxLat].
    bounds: list[float]
    # The same rectangle as a GeoJSON Polygon, for drawing.
    geometry: dict[str, Any]


class CitySurfacesRequest(BaseModel):
    """Request body for kriging one independent surface per city.

    Readings are partitioned by city rectangle and each city is fitted on its
    own readings alone, so no city's surface is influenced by another's.
    """

    metric_key: str = "average_temperature_c"
    points: list[SurfacePoint] = Field(default_factory=list)
    rows: int = 48
    cols: int = 48
    # Cities to build surfaces for. Defaults to every city with a rectangle;
    # cities with no readings inside them are simply absent from the response.
    cities: Optional[list[str]] = None
    boundary_buffer_deg: float = 0.0


class CitySurfacesResponse(BaseModel):
    """One independently kriged surface per city that had enough readings."""

    metric_key: str
    surfaces: list[SurfaceResponse]
    # City -> why it produced no surface (too few readings inside its rectangle,
    # or a fit that failed). Reported rather than silently omitted.
    skipped: dict[str, str] = Field(default_factory=dict)
