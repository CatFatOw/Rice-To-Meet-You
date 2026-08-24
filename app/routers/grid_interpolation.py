"""Routes for interpolating metrics onto generated grid cells."""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from repository.grid_interpolation_repository import (
    create_interpolated_points,
    delete_interpolated_point,
    delete_interpolated_points_for_cells,
    get_all_points,
    get_interpolated_point_by_id,
    get_interpolated_points_for_cells,
    get_interpolated_points_query,
    get_metrics_for_grid_cells,
    update_interpolated_point,
)
from data.city_boundaries import (
    get_city_boundary,
    get_city_boundary_geojson,
    get_market_code,
    resolve_city_name,
    supported_cities,
)
from repository.heatmap_repository import HeatmapRepository
from routers.grid_geometry import get_city_grid_cells
from schemas import interpolate_schemas
from services.grid_geometry_services import grid_cells_to_geojson
from services.grid_interpolation_service import (
    INTERPOLATABLE_METRICS,
    SURFACE_MAX_RESOLUTION,
    SURFACE_METRICS,
    add_relative_confidence,
    apply_exact_grid_metrics,
    grid_metrics_to_known_points,
    interpolate_available_metrics,
    interpolated_points_to_geojson,
    interpolated_points_to_heatmap_geojson,
    interpolated_points_to_polygon_geojson,
    krige_city_surfaces,
    krige_surface,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grid_interpolation", tags=["grid_interpolation"])


def validate_metric_key(metric_key: str, field_name: str = "metric_key"):
    """Raise a 400 if a requested metric is not interpolatable."""
    if metric_key not in INTERPOLATABLE_METRICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be one of: {sorted(INTERPOLATABLE_METRICS)}",
        )


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


def validate_city_state_filter(city: str | None, state: str | None):
    """City and state filters only make sense as a pair."""
    if city or state:
        if not city or not state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="city and state must be provided together.",
            )


# Get the grid cells (geojson format)
@router.get("/grid_cells_city")
async def get_grid_cells_city(city: str, state: str, db: Session = Depends(get_db)):
    """Route gets all grid cells related with the city."""
    all_cells = get_city_grid_cells(city, state, db)
    return grid_cells_to_geojson(all_cells)


# Route to actually interpolate
@router.post("/interpolate", response_model=list[interpolate_schemas.InterpolatedPointResponse])
async def interpolate(
    payload: interpolate_schemas.InterpolationRunRequest,
    db: Session = Depends(get_db),
):
    """Interpolate known points onto city grid centroids and save the results."""
    validate_metric_key(payload.metric_key)

    grid_cells = get_city_grid_cells(payload.city, payload.state, db)
    grid_cell_ids = [cell.id for cell in grid_cells]
    metrics = get_metrics_for_grid_cells(grid_cell_ids, payload.timestamp, db)
    grid_metric_points, exact_metrics_by_cell_id = grid_metrics_to_known_points(
        grid_cells,
        metrics,
    )
    known_points = [*grid_metric_points, *payload.known_points]

    try:
        results = interpolate_available_metrics(
            grid_cells,
            known_points,
            payload.metric_key,
        )
        apply_exact_grid_metrics(results, exact_metrics_by_cell_id)
        add_relative_confidence(results)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    result_grid_cell_ids = [result["grid_cell_id"] for result in results]

    if payload.replace_existing:
        delete_interpolated_points_for_cells(result_grid_cell_ids, payload.timestamp, db)
        db.flush()

    create_interpolated_points(
        results,
        payload.timestamp,
        len(known_points),
        INTERPOLATABLE_METRICS,
        db,
    )

    return get_interpolated_points_for_cells(result_grid_cell_ids, payload.timestamp, db)


# Get all interpolated values
@router.get("/all")
async def get_all(db: Session = Depends(get_db)):
    """Get all interpolated points and return them in GeoJSON format."""
    data = get_all_points(db)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")
    return interpolated_points_to_geojson(data)


@router.get("/mesh")
async def get_interpolated_mesh(
    city: str | None = None,
    state: str | None = None,
    timestamp: datetime | None = None,
    color_metric: str = "heat_index",
    db: Session = Depends(get_db),
):
    """Return interpolated values as grid-cell polygons for mesh rendering."""
    validate_metric_key(color_metric, field_name="color_metric")
    validate_city_state_filter(city, state)

    data = get_interpolated_points_query(db, city, state, timestamp).all()
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")

    return interpolated_points_to_polygon_geojson(data, color_metric=color_metric)


@router.get("/heatmap")
async def get_interpolated_heatmap(
    city: str | None = None,
    state: str | None = None,
    timestamp: datetime | None = None,
    metric_key: str = "heat_index",
    db: Session = Depends(get_db),
):
    """Return interpolated centroids as normalized points for smooth heatmaps."""
    validate_metric_key(metric_key)
    validate_city_state_filter(city, state)

    data = get_interpolated_points_query(db, city, state, timestamp).all()
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")

    return interpolated_points_to_heatmap_geojson(data, metric_key=metric_key)


@router.get(
    "/city_boundary",
    response_model=interpolate_schemas.CityBoundaryResponse,
)
async def get_city_boundary_route(city: str):
    """Return the rectangle the surface for this city is built over."""
    validate_surface_city(city)
    boundary = get_city_boundary(city)
    if not boundary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO CITY BOUNDARY FOUND",
        )

    return {
        "city": resolve_city_name(city),
        "state": boundary["state"],
        "bounds": boundary["bounds"],
        "geometry": get_city_boundary_geojson(city),
    }


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
    backend. They are already resident in the heatmap repository's in-process
    cache, so this reads them directly, krige them, and returns only the
    lattice - roughly 44 KB, against the ~740 KB the raw readings would cost in
    each direction if the client fetched and returned them.

    `additional_metrics` are interpolated onto the same lattice and returned
    under `metrics`. They are never drawn - they are what the tooltip reports
    for the coordinate under the cursor - but they go through the same kriging
    as the drawn metric rather than being snapped to the nearest reading.

    The POST form below still exists for the one case this cannot serve: a
    running simulation, whose adjusted readings exist only in the browser.
    """
    validate_surface_metric(metric_key)
    validate_surface_city(city)

    extra_names = [
        stripped
        for name in dict.fromkeys(additional_metrics or [])
        if (stripped := str(name).strip()) and stripped != metric_key
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

    repository = HeatmapRepository(db)
    market_code = get_market_code(city)

    def readings_for(name: str):
        """Numeric readings for one metric, straight from the in-memory cache.

        One call per metric: asking for a metric by name yields its value as a
        plain number, whereas `additional_metrics` would return it pre-formatted
        as a display string that would have to be parsed back before kriging.
        Each metric also drops its own NULL rows, so the point sets differ - and
        each is interpolated over exactly the points that have a value.
        """
        return [
            {
                "longitude": point["location_coordinates"][0],
                "latitude": point["location_coordinates"][1],
                "value": point["value"],
            }
            for points in repository.getDataPointsForCityDateMetric(
                weather_date=date, metric=name, market_code=market_code
            ).values()
            for point in points
        ]

    try:
        readings = readings_for(metric_key)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if not readings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {metric_key} readings for {resolved_city} on {date}.",
        )

    # An unknown or empty secondary metric costs the tooltip one row; it must
    # not cost the map its surface.
    extra_readings = {}
    for name in extra_names:
        try:
            values = readings_for(name)
        except ValueError:
            logger.warning("Skipping unknown additional metric %r", name)
            continue
        if values:
            extra_readings[name] = values

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

    # Reuse the repository's own unit strings so the tooltip reads exactly as it
    # did when it showed measured values.
    for name, layer in surface.get("metrics", {}).items():
        layer["unit"] = repository._unit_for(name)

    response = {"metric_key": metric_key, **surface}

    if len(_SURFACE_CACHE) >= _SURFACE_CACHE_MAX_ENTRIES:
        _SURFACE_CACHE.pop(next(iter(_SURFACE_CACHE)))
    _SURFACE_CACHE[cache_key] = response

    return response


@router.post("/surface", response_model=interpolate_schemas.SurfaceResponse)
async def get_interpolated_surface(payload: interpolate_schemas.SurfaceRequest):
    """Ordinary-krige the supplied readings into a continuous value lattice.

    This is the surface the map draws. It takes its observations from the
    request rather than the database so that a running simulation - whose
    adjusted readings only exist in the browser - can be rendered the same way
    as saved data. Nothing is persisted.
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

    try:
        surface = krige_surface(
            [point.model_dump() for point in payload.points],
            rows=payload.rows,
            cols=payload.cols,
            bounds=payload.bounds,
            city=payload.city,
            buffer_deg=payload.boundary_buffer_deg,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"metric_key": payload.metric_key, **surface}


@router.post("/surfaces", response_model=interpolate_schemas.CitySurfacesResponse)
async def get_interpolated_city_surfaces(payload: interpolate_schemas.CitySurfacesRequest):
    """Krige one independent surface per city.

    Readings are partitioned by city rectangle and each city is fitted on its
    own readings alone. A city's surface is therefore generated from that city's
    data, not sliced out of a single wider fit - two cities with different heat
    regimes cannot flatten each other's detail.
    """
    validate_surface_metric(payload.metric_key)
    for city in payload.cities or []:
        validate_surface_city(city)

    if not payload.points:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="points cannot be empty.",
        )

    if payload.rows * payload.cols > SURFACE_MAX_RESOLUTION**2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"rows * cols cannot exceed {SURFACE_MAX_RESOLUTION**2}.",
        )

    surfaces, skipped = krige_city_surfaces(
        [point.model_dump() for point in payload.points],
        rows=payload.rows,
        cols=payload.cols,
        cities=payload.cities,
        buffer_deg=payload.boundary_buffer_deg,
    )

    return {
        "metric_key": payload.metric_key,
        "surfaces": [
            {"metric_key": payload.metric_key, **surface}
            for surface in surfaces.values()
        ],
        "skipped": skipped,
    }


# Update/when the user draws polygon/points the area of the polygon impacts these points
@router.put(
    "/update/{interpolated_id}",
    response_model=interpolate_schemas.InterpolatedPointResponse,
)
async def update_cell(
    interpolated_id: int,
    payload: interpolate_schemas.InterpolatedPointUpdate,
    db: Session = Depends(get_db),
):
    """Update an interpolated point."""
    point = get_interpolated_point_by_id(interpolated_id, db)

    if not point:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NOT FOUND",
        )

    return update_interpolated_point(point, payload, db)


# delete
@router.delete("/delete/{interpolated_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cell_id(interpolated_id: int, db: Session = Depends(get_db)):
    """Delete a specific interpolated point by its id."""
    point = get_interpolated_point_by_id(interpolated_id, db)
    if not point:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NOT FOUND",
        )

    delete_interpolated_point(point, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
