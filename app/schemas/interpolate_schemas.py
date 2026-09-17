from typing import Optional
from pydantic import BaseModel, Field


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
    # The date the posted readings describe. Only needed alongside
    # additional_metrics, which are read from storage for that date.
    date: Optional[str] = None
    # Secondary metrics for the tooltip, interpolated onto the same lattice.
    # A simulation only alters the drawn metric, so these are read server-side
    # for `city`/`date` rather than travelling up with the points. Requires
    # `date`; the drawn metric itself is served from the primary lattice.
    additional_metrics: Optional[list[str]] = None


class MetricLayer(BaseModel):
    """One secondary metric interpolated onto the surface's lattice.

    Not drawn: these are the extra values the tooltip reports for the exact
    coordinate under the cursor. Same rows/cols/bounds as the parent surface.
    """

    # values[row][col], row 0 southernmost, in the metric's own units.
    values: list[list[float]]
    min: float
    max: float
    source_count: int
    variogram_model: Optional[str] = None
    # Display suffix, e.g. " C" or "%". Empty when the metric is unitless.
    unit: str = ""


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
    # Resolved city name; null when the request carried no city.
    city: Optional[str] = None
    interpolation_method: str = "ordinary_kriging"
    # Which variogram model actually fitted, or "constant" for a flat field.
    # Useful when a surface looks wrong: it says how it was derived.
    variogram_model: Optional[str] = None
    # Secondary metrics on the same lattice, keyed by metric name. Interpolated
    # for the tooltip but never coloured.
    metrics: dict[str, MetricLayer] = Field(default_factory=dict)
