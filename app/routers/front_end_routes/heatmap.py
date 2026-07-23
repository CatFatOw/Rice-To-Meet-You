"""Frontend-oriented heatmap routes.

These endpoints adapt existing backend polygon, metric, and interpolation data
into the shapes consumed directly by the React heatmap pages. They intentionally
reuse repository/service helpers instead of maintaining separate mock data paths.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone
from math import cos, radians

from database import get_db
from repository.grid_metrics_repository import (
    create_simulated_metrics_from_latest,
    get_latest_metrics_for_city,
    get_latest_metrics_for_grid_ids,
)
from repository.polygon_repository import get_polygons_for_city_state, create_new_polygon, create_impact_grids
from repository.polygon_repository import get_impacted_grid_cell_ids_by_polygon_id, get_key_pois, get_polygon_by_id
from repository.poi_polygon_repository import get_poi_by_id, get_poi_polygons_for_city_state
from schemas.front_end_schemas.heatmap_schemas import (
    CityMetricGrid,
    HeatmapMetricPoint,
    LocationPOIResponse,
    SimulationApplyRequest,
    SimulationPolygonCreate,
)
from services.grid_interpolation_service import (
    INTERPOLATABLE_METRICS,
    grid_metrics_to_city_grids,
    grid_metrics_to_metric_layers,
)
from services.grid_metrics_services import (
    build_overall_statistics,
    build_poi_statistics,
    simulation_adjustments_from_objects,
)
from services.polygon_services import polygon_from_geojson
from services.poi_polygon_services import poi_to_frontend_polygon
from schemas import polygon_schemas

router = APIRouter(prefix="/heatmap", tags=["heatmap"])


# The UI's selectable host-city names. Detailed weather points are spatially
# interpolated onto a small raster around each host city, rather than relying
# on the old nullable legacy metric columns.
HOST_CITY_GRID_SPECS = (
    ("Atlanta", "Georgia", 33.7490, -84.3880),
    ("Boston", "Massachusetts", 42.3601, -71.0589),
    ("Dallas", "Texas", 32.7767, -96.7970),
    ("Houston", "Texas", 29.7604, -95.3698),
    ("Kansas City", "Missouri", 39.0997, -94.5786),
    ("Los Angeles", "California", 34.0522, -118.2437),
    ("Miami", "Florida", 25.7617, -80.1918),
    ("New York", "New York", 40.7128, -74.0060),
    ("New Jersey", "New Jersey", 40.0583, -74.4057),
    ("Philadelphia", "Pennsylvania", 39.9526, -75.1652),
    ("Seattle", "Washington", 47.6062, -122.3321),
    ("San Francisco Bay Area", "California", 37.7749, -122.4194),
)


def _idw(points, latitude: float, longitude: float) -> float:
    """Inverse-distance interpolation for one metric at one map coordinate."""
    weighted_total = 0.0
    weight_sum = 0.0
    longitude_scale = cos(radians(latitude))
    for point_lat, point_lon, value in points:
        distance_sq = (point_lat - latitude) ** 2 + ((point_lon - longitude) * longitude_scale) ** 2
        if distance_sq < 1e-12:
            return float(value)
        weight = 1.0 / distance_sq
        weighted_total += weight * float(value)
        weight_sum += weight
    return weighted_total / weight_sum


def detailed_metrics_to_city_grids(db: Session, year: int | None = None, month: int | None = None, season: str | None = None) -> dict:
    """Build frontend rasters directly from production.grid_cell_metrics_detailed.

    The detailed table is the canonical local source. Its engineered weather
    records are sparse station/grid observations, so this produces an IDW
    interpolated grid for every host city without using mock values or the
    old nullable ``grid_cell_metrics`` display columns.
    """
    if year or month or season:
        season_months = {"winter": [12, 1, 2], "spring": [3, 4, 5], "summer": [6, 7, 8], "fall": [9, 10, 11]}
        filters, params = ["m.date IS NOT NULL"], {}
        if year:
            filters.append("EXTRACT(YEAR FROM m.date) = :year"); params["year"] = year
        if month:
            filters.append("EXTRACT(MONTH FROM m.date) = :month"); params["month"] = month
        if season:
            filters.append("EXTRACT(MONTH FROM m.date) = ANY(:months)"); params["months"] = season_months[season]
        rows = db.execute(text(f"""
            WITH period_metrics AS (
              SELECT g.grid_centroid_lat AS latitude, g.grid_centroid_lon AS longitude, g.state,
                max(m.timestamp) AS latest_metric_timestamp,
                avg(m.avg_temperature_c) AS avg_temperature_c,
                avg(m.visitor_count) AS visitor_activity,
                avg(m.uhi) AS uhi, avg(m.relative_humidity) AS relative_humidity,
                avg(m.wind_speed_knots) * 0.514444 AS wind_speed_mps
              FROM production.grid_cell_metrics m
              JOIN production.grid_cell_geometry g ON g.id = m.grid_cell_id
              WHERE {' AND '.join(filters)}
              GROUP BY g.id, g.grid_centroid_lat, g.grid_centroid_lon, g.state
              HAVING avg(m.avg_temperature_c) IS NOT NULL OR avg(m.visitor_count) IS NOT NULL
            ), comfort AS (
              SELECT *, CASE WHEN avg_temperature_c IS NOT NULL AND relative_humidity IS NOT NULL THEN
                avg_temperature_c * atan(0.151977 * sqrt(relative_humidity + 8.313659))
                + atan(avg_temperature_c + relative_humidity)
                - atan(relative_humidity - 1.676331)
                + 0.00391838 * power(relative_humidity, 1.5) * atan(0.023101 * relative_humidity)
                - 4.686035 END AS wet_bulb_temperature_c
              FROM period_metrics
            ), scores AS (
              SELECT *,
                CASE WHEN wet_bulb_temperature_c IS NOT NULL THEN least(100.0, greatest(0.0, 100.0 * (wet_bulb_temperature_c - 18) / 12)) END AS wet_bulb_score,
                CASE WHEN wind_speed_mps IS NOT NULL THEN least(100.0, greatest(0.0, 100.0 * (3.5 - wind_speed_mps) / 3.5)) END AS low_wind_score,
                CASE WHEN uhi IS NOT NULL THEN least(100.0, greatest(0.0, 100.0 * (uhi - 1) / 10)) END AS uhi_score
              FROM comfort
            )
            SELECT latitude, longitude, state, latest_metric_timestamp,
              avg_temperature_c * 9 / 5 + 32 AS heat_index,
              CASE WHEN wet_bulb_score IS NULL OR low_wind_score IS NULL OR uhi_score IS NULL THEN NULL
                   ELSE .60 * wet_bulb_score + .20 * low_wind_score + .20 * uhi_score END AS heat_risk,
              CASE WHEN wet_bulb_score IS NULL OR low_wind_score IS NULL OR uhi_score IS NULL THEN NULL
                   ELSE 100 - (.60 * wet_bulb_score + .20 * low_wind_score + .20 * uhi_score) END AS football_playability_index,
              CASE WHEN wet_bulb_score IS NULL OR low_wind_score IS NULL OR uhi_score IS NULL THEN NULL
                   ELSE .60 * wet_bulb_score + .20 * low_wind_score + .20 * uhi_score END AS football_playability_risk_score,
              visitor_activity, visitor_activity AS visitor_density,
              uhi, relative_humidity, wind_speed_mps
            FROM scores
        """), params).mappings().all()
    else:
        rows = db.execute(
        text(
            """
            SELECT latitude, longitude, state, latest_metric_timestamp,
                   latest_avg_temperature_c * 9 / 5 + 32 AS heat_index,
                   football_playability_risk_score AS heat_risk,
                   football_playability_index,
                   football_playability_risk_score,
                   COALESCE(latest_visitor_count, visitor_avg) AS visitor_activity,
                   COALESCE(latest_visitor_count, visitor_avg) AS visitor_density,
                   latest_uhi AS uhi,
                   latest_relative_humidity AS relative_humidity,
                   wind_speed_mps
            FROM production.grid_cell_metrics_detailed
            WHERE latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND (
                latest_avg_temperature_c IS NOT NULL
                OR football_playability_risk_score IS NOT NULL
                OR football_playability_index IS NOT NULL
                OR latest_visitor_count IS NOT NULL
                OR visitor_avg IS NOT NULL
                OR latest_uhi IS NOT NULL
                OR latest_relative_humidity IS NOT NULL
                OR wind_speed_mps IS NOT NULL
              )
            """
        )
        ).mappings().all()

    if not rows:
        return {}

    grids = {}
    grid_size = 25
    half_span_degrees = 0.62
    for city, state, center_lat, center_lon in HOST_CITY_GRID_SPECS:
        state_rows = [row for row in rows if row["state"] == state]

        min_lon, max_lon = center_lon - half_span_degrees, center_lon + half_span_degrees
        min_lat, max_lat = center_lat - half_span_degrees, center_lat + half_span_degrees
        metric_grids = {}
        for metric_key in (
            "heat_index",
            "heat_risk",
            "football_playability_index",
            "football_playability_risk_score",
            "visitor_activity",
            "visitor_density",
            "uhi",
            "relative_humidity",
            "wind_speed_mps",
        ):
            state_points = [
                (row["latitude"], row["longitude"], row[metric_key])
                for row in state_rows
                if row[metric_key] is not None
            ]
            all_points = [
                (row["latitude"], row["longitude"], row[metric_key])
                for row in rows
                if row[metric_key] is not None
            ]
            source_points = state_points if len(state_points) >= 2 else all_points
            if len(source_points) < 2:
                continue
            # A bounded nearest-neighbor set keeps the live endpoint fast even
            # for dense visitor data (tens of thousands of observations), while
            # still using real detailed-table observations for each city.
            source_points = sorted(
                source_points,
                key=lambda point: (point[0] - center_lat) ** 2 + ((point[1] - center_lon) * cos(radians(center_lat))) ** 2,
            )[:80]

            values = []
            for row_index in range(grid_size):
                latitude = min_lat + (max_lat - min_lat) * row_index / (grid_size - 1)
                value_row = []
                for column_index in range(grid_size):
                    longitude = min_lon + (max_lon - min_lon) * column_index / (grid_size - 1)
                    value_row.append(round(_idw(source_points, latitude, longitude), 2))
                values.append(value_row)
            metric_grids[metric_key] = {
                "min": min(value for row in values for value in row),
                "max": max(value for row in values for value in row),
                "values": values,
            }

        if not metric_grids:
            continue

        timestamp_rows = state_rows if state_rows else rows
        source_times = [row["latest_metric_timestamp"] for row in timestamp_rows if row["latest_metric_timestamp"]]
        timestamp = max(source_times).isoformat() if source_times else datetime.now(timezone.utc).isoformat()
        grids[city] = {
            "state": state,
            "bounds": [min_lon, min_lat, max_lon, max_lat],
            "rows": grid_size,
            "cols": grid_size,
            "timestamp": timestamp,
            "metrics": metric_grids,
        }
    return grids


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
    include_core_pois: bool = True,
    core_poi_limit: int = 250,
    db: Session = Depends(get_db),
):
    """Return saved polygon and core dataset POIs in the frontend overlay format."""
    polygons = get_polygons_for_city_state(city, state, db)
    saved_polygons = [
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

    if not include_core_pois:
        return saved_polygons

    pois = get_poi_polygons_for_city_state(
        None if city == "Nationally" else city,
        state,
        db,
        limit=core_poi_limit,
    )
    return [*saved_polygons, *[poi_to_frontend_polygon(poi) for poi in pois]]


@router.get("/core-pois", response_model=list[LocationPOIResponse])
def get_core_pois(
    city: str | None = None,
    state: str | None = None,
    category: str | None = None,
    limit: int = 250,
    db: Session = Depends(get_db),
):
    """Return core POI footprints in the frontend overlay format."""
    pois = get_poi_polygons_for_city_state(
        None if city == "Nationally" else city,
        state,
        db,
        category=category,
        limit=limit,
    )
    return [poi_to_frontend_polygon(poi) for poi in pois]


@router.get("/core-pois/{poi_id}", response_model=LocationPOIResponse)
def get_core_poi_details(poi_id: int, db: Session = Depends(get_db)):
    """Return one core POI polygon with click-panel metadata and statistics."""
    poi = get_poi_by_id(poi_id, db)
    if not poi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POI not found")
    if not poi.polygon_wkt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POI has no polygon")
    return poi_to_frontend_polygon(poi)


@router.get("/metrics/points", response_model=dict[str, list[HeatmapMetricPoint]])
def get_heatmap_metric_points(
    city: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    """Return latest grid metrics as city-keyed frontend heatmap layers."""
    validate_city_state_filter(city, state)
    try:
        latest_metrics = get_latest_metrics_for_city(city, state, db)
    except SQLAlchemyError:
        return {}
    if not latest_metrics:
        return {}

    return grid_metrics_to_metric_layers(latest_metrics, INTERPOLATABLE_METRICS)


@router.get("/metrics/grid", response_model=dict[str, CityMetricGrid])
def get_heatmap_metric_grid(
    city: str | None = None,
    state: str | None = None,
    year: int | None = None,
    month: int | None = None,
    season: str | None = None,
    db: Session = Depends(get_db),
):
    """Return latest grid metrics as city-keyed interpolated raster grids.

    Each city's response carries the full rows x cols value lattice (kriging
    fills cells without saved metrics), so the frontend can render a continuous
    surface over the grid area and sample interpolated values at any coordinate.
    """
    try:
        if season not in (None, "winter", "spring", "summer", "fall"):
            raise HTTPException(status_code=400, detail="season must be winter, spring, summer, or fall")
        city_grids = detailed_metrics_to_city_grids(db, year, month, season)
    except SQLAlchemyError:
        return {}
    if city and state:
        return {city: city_grids[city]} if city in city_grids else {}
    return city_grids


@router.get("/statistics")
def get_statistics(
    city: str = "Nationally",
    state: str = "Texas",
    db: Session = Depends(get_db),
):
    """Return dashboard summary and POI table statistics for a city/state view."""
    try:
        latest_metrics = get_latest_metrics_for_city(city, state, db)
        pois = get_key_pois(None if city == "Nationally" else city, state, db)
    except SQLAlchemyError:
        latest_metrics = []
        pois = []

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
