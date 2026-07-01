"""Routes for interpolating metrics onto generated grid cells."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
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
from routers.grid_geometry import get_city_grid_cells
from schemas import interpolate_schemas
from services.grid_geometry_services import grid_cells_to_geojson
from services.grid_interpolation_service import (
    INTERPOLATABLE_METRICS,
    add_relative_confidence,
    apply_exact_grid_metrics,
    grid_metrics_to_known_points,
    interpolate_available_metrics,
    interpolated_points_to_geojson,
    interpolated_points_to_heatmap_geojson,
    interpolated_points_to_polygon_geojson,
)

router = APIRouter(prefix="/grid_interpolation", tags=["grid_interpolation"])


def validate_metric_key(metric_key: str, field_name: str = "metric_key"):
    """Raise a 400 if a requested metric is not interpolatable."""
    if metric_key not in INTERPOLATABLE_METRICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be one of: {sorted(INTERPOLATABLE_METRICS)}",
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
