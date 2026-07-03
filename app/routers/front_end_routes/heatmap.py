"""Frontend-oriented heatmap routes.

These endpoints adapt existing backend polygon, metric, and interpolation data
into the shapes consumed directly by the React heatmap pages. They intentionally
reuse repository/service helpers instead of maintaining separate mock data paths.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database import get_db
from repository.grid_interpolation_repository import get_interpolated_points_query
from repository.grid_metrics_repository import (
    create_simulated_metrics_from_latest,
    get_latest_metrics_for_city,
    get_latest_metrics_for_grid_ids,
)
from repository.polygon_repository import get_polygons_for_city_state, create_new_polygon, create_impact_grids
from repository.polygon_repository import get_impacted_grid_cell_ids_by_polygon_id, get_key_pois, get_polygon_by_id
from schemas.front_end_schemas.heatmap_schemas import (
    HeatmapMetricPoint,
    LocationPOIResponse,
    SimulationApplyRequest,
    SimulationPolygonCreate,
)
from services.grid_interpolation_service import (
    INTERPOLATABLE_METRICS,
    interpolated_points_to_metric_layers,
)
from services.grid_metrics_services import (
    build_overall_statistics,
    build_poi_statistics,
    simulation_adjustments_from_objects,
)
from services.polygon_services import polygon_from_geojson
from schemas import polygon_schemas

router = APIRouter(prefix="/heatmap", tags=["heatmap"])


def validate_city_state_filter(city: str | None, state: str | None):
    """Require city and state to be supplied together for grid-backed filters."""
    if city or state:
        if not city or not state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="city and state must be provided together.",
            )


@router.get("/location-pois", response_model=list[LocationPOIResponse])
def get_location_pois(
    city: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    """Return saved polygon POIs in the frontend overlay format."""
    polygons = get_polygons_for_city_state(city, state, db)
    return [
        {
            "id": f"polygon-{polygon.id}",
            "name": polygon.name or f"Region {polygon.id}",
            "cityName": polygon.city_name or city or "Unknown",
            "stateName": polygon.state_name or state,
            "color": polygon.color or [34, 197, 94, 150],
            "polygon": polygon.geometry["coordinates"][0],
        }
        for polygon in polygons
    ]


@router.get("/metrics/points", response_model=dict[str, list[HeatmapMetricPoint]])
def get_heatmap_metric_points(
    city: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    """Return interpolated metric rows as city-keyed frontend heatmap layers."""
    validate_city_state_filter(city, state)
    interpolated_points = get_interpolated_points_query(db, city, state).all()
    if not interpolated_points:
        return {}

    return interpolated_points_to_metric_layers(interpolated_points, INTERPOLATABLE_METRICS)


@router.get("/statistics")
def get_statistics(
    city: str = "Nationally",
    state: str = "Texas",
    db: Session = Depends(get_db),
):
    """Return dashboard summary and POI table statistics for a city/state view."""
    latest_metrics = get_latest_metrics_for_city(city, state, db)
    pois = get_key_pois(None if city == "Nationally" else city, state, db)

    return {
        "overallStatistics": build_overall_statistics(city, latest_metrics),
        "poiStatistics": build_poi_statistics(city, pois, latest_metrics),
    }


@router.post("/simulation/polygon")
async def create_simulation_polygon(payload: SimulationPolygonCreate, db: Session = Depends(get_db)):
    """Function allows users to create their own polygons using tools in the front end"""
    ring = payload.polygon
    if ring[0] != ring[-1]:
        ring = [*ring, ring[0]]

    polygon_payload = polygon_schemas.PolygonGeometryCreate(
        name=payload.name,
        city_name=payload.cityName,
        state_name=payload.stateName,
        color=payload.color,
        geometry={"type": "Polygon", "coordinates": [ring]},
    )

    try:
        polygon_from_geojson(polygon_payload.geometry)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    polygon = create_new_polygon(polygon_payload, db)
    # Create the impact grids etc
    impacted_rows = create_impact_grids(
        polygon_id=polygon.id,
        polygon_points=polygon_payload,
        db=db,
        city=payload.cityName,
        state=payload.stateName,
        replace_existing=True,
    )
    # Get the specific grid ids that were impacted by the polygon the users drew on 
    impacted_ids = [row.grid_cell_id for row in impacted_rows]
    return {
        "id": f"polygon-{polygon.id}",
        "polygon_geometry_id": polygon.id,
        "name": polygon.name or f"Region {polygon.id}",
        "cityName": polygon.city_name or "Unknown",
        "stateName": polygon.state_name,
        "color": polygon.color or [34, 197, 94, 150],
        "polygon": polygon.geometry["coordinates"][0],
        "impacted_count": len(impacted_ids),
        "impacted_grid_cell_ids": impacted_ids,
    }



@router.get("/simulation/polygon/{polygon_id}")
async def get_specified_polygon(polygon_id: int, db: Session = Depends(get_db)):
    """function gets specific polygon by ID"""
    polygon = get_polygon_by_id(polygon_id, db)
    if not polygon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")

    return {
        "id": f"polygon-{polygon.id}",
        "polygon_geometry_id": polygon.id,
        "name": polygon.name or f"Region {polygon.id}",
        "cityName": polygon.city_name or "Unknown",
        "stateName": polygon.state_name,
        "color": polygon.color or [34, 197, 94, 150],
        "polygon": polygon.geometry["coordinates"][0],
    }


@router.post("/simulation/apply")
async def apply_simulation(payload: SimulationApplyRequest, db: Session = Depends(get_db)):
    """Apply placed simulation objects to impacted grid metrics."""
    if not payload.placedObjects:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="placedObjects cannot be empty.")

    impacted_grid_cell_ids = payload.impactedGridCellIds or []
    if not impacted_grid_cell_ids and payload.polygonGeometryId:
        impacted_grid_cell_ids = get_impacted_grid_cell_ids_by_polygon_id(payload.polygonGeometryId, db)

    if impacted_grid_cell_ids:
        latest_metrics = get_latest_metrics_for_grid_ids(impacted_grid_cell_ids, db)
    else:
        latest_metrics = get_latest_metrics_for_city(payload.cityName, payload.stateName, db)

    if not latest_metrics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NO METRICS FOUND")

    adjustments = simulation_adjustments_from_objects(payload.placedObjects)
    timestamp = payload.timestamp or datetime.now(timezone.utc)
    simulated_metrics = create_simulated_metrics_from_latest(latest_metrics, timestamp, adjustments, db)
    simulated_grid_cell_ids = [metric.grid_cell_id for metric in simulated_metrics]

    return {
        "timestamp": timestamp.isoformat(),
        "objects_applied": len(payload.placedObjects),
        "adjustments": adjustments,
        "metrics_created": len(simulated_metrics),
        "impacted_count": len(simulated_grid_cell_ids),
        "impacted_grid_cell_ids": simulated_grid_cell_ids,
    }
