"""Routes for kriging metric readings into continuous map surfaces."""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from data.city_boundaries import (
    get_market_code,
    resolve_city_name,
    supported_cities,
)
from repository.heatmap_repository import HeatmapRepository
from schemas import interpolate_schemas
from services.grid_interpolation_service import (
    SURFACE_MAX_RESOLUTION,
    SURFACE_METRICS,
    krige_surface,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grid_interpolation", tags=["grid_interpolation"])


def validate_surface_metric(metric_key: str):
    """Raise a 400 if a requested metric has no continuous surface."""
    if metric_key not in SURFACE_METRICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"metric_key must be one of: {sorted(SURFACE_METRICS)}",
        )


def validate_surface_city(city: str | None):
    """Reject an unknown city rather than silently widening the surface.

    Falling back to the observations' bounding box for a city we have no
    rectangle for would draw a surface well past the city, which is exactly the
    behaviour the city extent exists to prevent.
    """
    if city and resolve_city_name(city) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown city '{city}'. Known cities: {supported_cities()}",
        )


# ---------------------------------------------------------------------------
# Reading sources for a surface
# ---------------------------------------------------------------------------
# A metric is not always a column. The map reads its points through more than
# one route depending on the metric, and a surface has to be kriged from
# exactly those readings, or the surface would describe a different field from
# the heatmap it replaces. These helpers route a metric name the same way.
#
# The visitor cache is deliberately not one of the sources. Its two metrics -
# avg_daily_visits and heat_risk_score - are per-POI records rather than
# samples of a field, so neither is kriged and neither appears as a tooltip row
# under a metric that is.

# Local temperature is computed per point from one market temperature plus that
# point's urban-heat-island offset, so it has its own repository call and its
# own source column per unit. Mirrors getLocalTemperature*ByCityDate in
# frontend/src/api/map.ts.
LOCAL_TEMPERATURE_SOURCES = {
    "local_temperature_c": ("average_temperature_c", "c"),
    "local_temperature_f": ("average_temperature_f", "f"),
}


def surface_metric_unit(metric_name: str) -> str:
    """The display suffix the tooltip appends to a metric, e.g. "\u00b0C" or "%".

    Same rule the heatmap repository applies when it formats a measured value,
    read off the same hint table, so an interpolated row reads exactly as the
    measured row it replaces.
    """
    lowered = metric_name.lower()
    for fragment, unit in HeatmapRepository.UNIT_HINTS:
        if fragment in lowered:
            return unit
    return ""


def _flatten_readings(points_by_date):
    """HeatmapPointsByDate -> the {longitude, latitude, value} kriging takes."""
    return [
        {
            "longitude": point["location_coordinates"][0],
            "latitude": point["location_coordinates"][1],
            "value": point["value"],
        }
        for points in points_by_date.values()
        for point in points
        if point.get("value") is not None
    ]


def surface_readings_for_metric(
    metric_name: str,
    city: str,
    date: str,
    heatmap_repository: HeatmapRepository,
):
    """Return (readings, unit) for one metric, from whichever source owns it.

    `unit` is the display suffix the tooltip appends, taken from the same place
    the point routes take it, so an interpolated row reads exactly as the
    measured row it replaces.

    Raises ValueError when no source can serve the metric.
    """
    market_code = get_market_code(city)

    if metric_name in LOCAL_TEMPERATURE_SOURCES:
        source_column, temperature_unit = LOCAL_TEMPERATURE_SOURCES[metric_name]
        points_by_date = heatmap_repository.getLocalTemperatureByCityDate(
            weather_date=date,
            metric=source_column,
            market_code=market_code,
            temperature_unit=temperature_unit,
        )
        return _flatten_readings(points_by_date), surface_metric_unit(metric_name)

    # Everything else is a weather, heat-index or synthetic metric, read by
    # name. Asking for it by name yields plain numbers, whereas the route's
    # `additional_metrics` would return display strings needing to be parsed
    # back before kriging. Each metric also drops its own NULL rows, so it is
    # interpolated over exactly the points that have a value.
    points_by_date = heatmap_repository.getDataPointsForCityDateMetric(
        weather_date=date, metric=metric_name, market_code=market_code
    )
    return _flatten_readings(points_by_date), surface_metric_unit(metric_name)


def collect_extra_readings(
    extra_names,
    metric_key: str,
    city: str,
    date: str,
    heatmap_repository: HeatmapRepository,
):
    """Readings and units for the tooltip's secondary rows.

    The drawn metric is skipped: it is served from the primary lattice by
    attach_tooltip_layers rather than fitted a second time. An unknown, empty
    or non-numeric metric costs the tooltip one row; it must not cost the map
    its surface, so each failure is logged and dropped.
    """
    readings_by_metric = {}
    units_by_metric = {}

    for name in extra_names:
        if name == metric_key:
            continue
        try:
            values, unit = surface_readings_for_metric(
                name, city, date, heatmap_repository
            )
        except (ValueError, KeyError, TypeError):
            logger.warning("Skipping additional metric %r for a surface", name)
            continue
        if values:
            readings_by_metric[name] = values
            units_by_metric[name] = unit

    return readings_by_metric, units_by_metric


def attach_tooltip_layers(
    surface,
    metric_key: str,
    extra_names,
    extra_units,
    primary_unit: str = "",
):
    """Finish a surface's `metrics` block: units, the drawn metric, and order.

    The drawn metric is a tooltip row like any other when the caller asks for
    it, but its values are the surface itself, so it reuses the primary lattice
    instead of paying for an identical second fit. Rows are then restored to
    the caller's requested order, which is the order the tooltip renders them.
    """
    layers = surface.get("metrics") or {}

    for name, layer in layers.items():
        layer["unit"] = extra_units.get(name, "")

    if metric_key in extra_names:
        layers[metric_key] = {
            "values": surface["values"],
            "min": surface["min"],
            "max": surface["max"],
            "source_count": surface["source_count"],
            "variogram_model": surface["variogram_model"],
            "unit": primary_unit,
        }

    surface["metrics"] = {name: layers[name] for name in extra_names if name in layers}
    return surface


# Surfaces are derived from a startup-preloaded, immutable reading cache, so the
# same query always yields the same surface and can be memoized outright. Keyed
# on everything that changes the result.
_SURFACE_CACHE: dict[tuple, dict] = {}
_SURFACE_CACHE_MAX_ENTRIES = 64


@router.get("/surface", response_model=interpolate_schemas.SurfaceResponse)
async def get_city_surface(
    city: str,
    date: str,
    metric_key: str = "average_temperature_c",
    rows: int = 48,
    cols: int = 48,
    additional_metrics: Optional[List[str]] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Build a city's continuous surface entirely server-side.

    The caller names a city, a date and a metric; the readings never leave the
    backend. They are already resident in the heatmap and visitor repositories'
    in-process caches, so this reads them directly, krige them, and returns only
    the lattice - roughly 44 KB, against the ~740 KB the raw readings would cost
    in each direction if the client fetched and returned them.

    Readings are sourced through surface_readings_for_metric, which routes a
    metric to the same repository call the map's own point route uses, so the
    surface describes the same field the heatmap it replaces did.

    `additional_metrics` are interpolated onto the same lattice and returned
    under `metrics`. They are never drawn - they are what the tooltip reports
    for the coordinate under the cursor - but they go through the same kriging
    as the drawn metric rather than being snapped to the nearest reading.

    The POST form below still exists for the one case this cannot serve: a
    running simulation, whose adjusted readings exist only in the browser.
    """
    validate_surface_metric(metric_key)
    validate_surface_city(city)

    # The drawn metric is kept in this list when the caller asks for it, so the
    # tooltip shows the row it always showed. It is served from the primary
    # lattice below rather than kriged twice.
    extra_names = [
        stripped
        for name in dict.fromkeys(additional_metrics or [])
        if (stripped := str(name).strip())
    ]

    resolved_city = resolve_city_name(city)
    cache_key = (resolved_city, date, metric_key, rows, cols, tuple(extra_names))
    cached = _SURFACE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    if rows * cols > SURFACE_MAX_RESOLUTION**2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"rows * cols cannot exceed {SURFACE_MAX_RESOLUTION**2}.",
        )

    heatmap_repository = HeatmapRepository(db)

    try:
        readings, primary_unit = surface_readings_for_metric(
            metric_key, city, date, heatmap_repository
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if not readings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {metric_key} readings for {resolved_city} on {date}.",
        )

    extra_readings, extra_units = collect_extra_readings(
        extra_names, metric_key, city, date, heatmap_repository
    )

    try:
        surface = krige_surface(
            readings,
            rows=rows,
            cols=cols,
            city=city,
            extra_points_by_metric=extra_readings,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    attach_tooltip_layers(
        surface, metric_key, extra_names, extra_units, primary_unit=primary_unit
    )

    response = {"metric_key": metric_key, **surface}

    if len(_SURFACE_CACHE) >= _SURFACE_CACHE_MAX_ENTRIES:
        _SURFACE_CACHE.pop(next(iter(_SURFACE_CACHE)))
    _SURFACE_CACHE[cache_key] = response

    return response


@router.post("/surface", response_model=interpolate_schemas.SurfaceResponse)
async def get_interpolated_surface(
    payload: interpolate_schemas.SurfaceRequest,
    db: Session = Depends(get_db),
):
    """Ordinary-krige the supplied readings into a continuous value lattice.

    This is the surface the map draws while a simulation is running. It takes
    its observations from the request rather than the database so that the
    adjusted readings - which only exist in the browser - can be rendered the
    same way as saved data. Nothing is persisted.

    `additional_metrics` (with `date`) are the tooltip's secondary rows. A
    simulation only alters the drawn metric, so those are read server-side for
    the city and date instead of being posted, and are kriged onto the same
    lattice as the simulated surface.
    """
    validate_surface_metric(payload.metric_key)
    validate_surface_city(payload.city)

    if not payload.points:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="points cannot be empty.",
        )

    if payload.bounds is not None and len(payload.bounds) != 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bounds must be [minLon, minLat, maxLon, maxLat].",
        )

    if payload.rows * payload.cols > SURFACE_MAX_RESOLUTION**2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"rows * cols cannot exceed {SURFACE_MAX_RESOLUTION**2}.",
        )

    extra_names = [
        stripped
        for name in dict.fromkeys(payload.additional_metrics or [])
        if (stripped := str(name).strip())
    ]

    # Secondary rows need a city and a date to read from; without either there
    # is nothing to source them from and the surface stands on its own.
    extra_readings = {}
    extra_units = {}
    if extra_names and payload.city and payload.date:
        extra_readings, extra_units = collect_extra_readings(
            extra_names,
            payload.metric_key,
            payload.city,
            payload.date,
            HeatmapRepository(db),
        )

    try:
        surface = krige_surface(
            [point.model_dump() for point in payload.points],
            rows=payload.rows,
            cols=payload.cols,
            bounds=payload.bounds,
            city=payload.city,
            buffer_deg=payload.boundary_buffer_deg,
            extra_points_by_metric=extra_readings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # The drawn metric's own row comes from the simulated lattice, so the
    # tooltip reports the simulated value rather than the stored one.
    attach_tooltip_layers(
        surface,
        payload.metric_key,
        extra_names,
        extra_units,
        primary_unit=surface_metric_unit(payload.metric_key),
    )

    return {"metric_key": payload.metric_key, **surface}
