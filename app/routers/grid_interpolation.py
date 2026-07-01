"""Routes and helpers for interpolating values onto generated grid cells.

Essentially the inital layer is grid cells + metrics which then we interpolate; however
the planner can then draw polygon masks over and whatever points that are intersected get impacted etc
"""

import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pykrige.ok import OrdinaryKriging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from database import get_db
from models import grid_cell_tables
from routers.grid_geometry import get_city_grid_cells, grid_cells_to_geojson
from schemas import interpolate_schemas
from fastapi.responses import Response

router = APIRouter(prefix="/grid_interpolation", tags=["grid_interpolation"])


INTERPOLATABLE_METRICS = {
    "heat_index",
    "heat_risk",
    "crowd_density",
    "population",
    "cooling_centers",
    "infrastructure_strain",
}


def heat_index_to_color(heat_index):
    """Sample Simple heat color ramp for polygon mesh rendering."""
    if heat_index is None:
        return "#BDBDBD"
    if heat_index >= 110:
        return "#8B0000"
    if heat_index >= 103:
        return "#FF4500"
    if heat_index >= 95:
        return "#FFA500"
    if heat_index >= 85:
        return "#FFD700"
    return "#00BFFF"


def metric_to_color(metric_key, value):
    """Return a frontend-friendly fill color for supported metrics."""
    if metric_key == "heat_index":
        return heat_index_to_color(value)
    if value is None:
        return "#BDBDBD"
    if value >= 0.8:
        return "#FF0000"
    if value >= 0.6:
        return "#FF6347"
    if value >= 0.4:
        return "#FFA500"
    if value >= 0.2:
        return "#FFD700"
    return "#00BFFF"


def _read_value(item, *keys):
    """Read the first available value from a dict or ORM-style object."""
    for key in keys:
        if isinstance(item, dict):
            if key in item:
                return item[key]
            properties = item.get("properties")
            if isinstance(properties, dict) and key in properties:
                return properties[key]
        elif hasattr(item, key):
            return getattr(item, key)
    return None


def _read_coordinates(item):
    """Return lon/lat from common grid, metric, and GeoJSON point shapes."""
    lon = _read_value(item, "centroid_lon", "grid_centroid_lon", "longitude", "lon")
    lat = _read_value(item, "centroid_lat", "grid_centroid_lat", "latitude", "lat")

    if lon is not None and lat is not None:
        return float(lon), float(lat)

    geometry = item.get("geometry") if isinstance(item, dict) else None
    if geometry and geometry.get("type") == "Point":
        coordinates = geometry.get("coordinates", [])
        if len(coordinates) >= 2:
            return float(coordinates[0]), float(coordinates[1])

    raise ValueError("Each interpolation point must include lon/lat or Point geometry.")


def _read_grid_cell_id(cell):
    return _read_value(cell, "id", "grid_cell_id")


def build_interpolation_result(cell, lon, lat, metric_key, value, variance=0):
    """Return one normalized interpolation result row."""
    return {
        "grid_cell_id": _read_grid_cell_id(cell),
        "cell_id": _read_value(cell, "cell_id"),
        "latitude": lat,
        "longitude": lon,
        metric_key: float(value),
        "variance": float(variance),
    }


def grid_metrics_to_known_points(grid_cells, timestamp, db: Session):
    """Use saved grid metrics as known points for interpolation."""
    cell_by_id = {cell.id: cell for cell in grid_cells}
    grid_cell_ids = list(cell_by_id.keys())

    if not grid_cell_ids:
        return [], {}

    metrics = (
        db.query(grid_cell_tables.GridCellMetrics)
        .filter(grid_cell_tables.GridCellMetrics.grid_cell_id.in_(grid_cell_ids))
        .filter(grid_cell_tables.GridCellMetrics.timestamp == timestamp)
        .all()
    )

    known_points = []
    exact_metrics_by_cell_id = {}

    for metric in metrics:
        cell = cell_by_id.get(metric.grid_cell_id)
        if not cell:
            continue

        values = {
            metric_key: getattr(metric, metric_key)
            for metric_key in INTERPOLATABLE_METRICS
            if getattr(metric, metric_key) is not None
        }

        if not values:
            continue

        exact_metrics_by_cell_id[metric.grid_cell_id] = values
        known_points.append(
            {
                "grid_cell_id": metric.grid_cell_id,
                "lon": cell.grid_centroid_lon,
                "lat": cell.grid_centroid_lat,
                **values,
            }
        )

    return known_points, exact_metrics_by_cell_id


def apply_exact_grid_metrics(results, exact_metrics_by_cell_id):
    """Prefer saved metrics when the target grid cell already has them."""
    for result in results:
        exact_values = exact_metrics_by_cell_id.get(result["grid_cell_id"], {})
        for metric_key, value in exact_values.items():
            result[metric_key] = value


def interpolate_grid_centroids(grid_cells, known_points, metric_key: str = "heat_index"):
    """Interpolate a numeric metric from known points onto grid cell centroids.

    grid_cells can be SQLAlchemy GridCellGeometry rows or dicts with centroid
    coordinates. known_points can be dicts or GeoJSON features containing
    centroid/point coordinates and the metric_key value.
    """
    if not grid_cells:
        raise ValueError("grid_cells cannot be empty.")
    if not known_points:
        raise ValueError("known_points cannot be empty.")

    # known weather observations 
    known_rows = []
    for point in known_points:
        value = _read_value(point, metric_key)
        if value is None:
            continue
        lon, lat = _read_coordinates(point)
        known_rows.append((lon, lat, float(value)))

    if len(known_rows) < 2:
        raise ValueError(f"At least two known points with {metric_key} are required.")

    exact_values_by_cell_id = {}
    for point in known_points:
        grid_cell_id = _read_value(point, "grid_cell_id")
        value = _read_value(point, metric_key)
        if grid_cell_id is not None and value is not None:
            exact_values_by_cell_id[int(grid_cell_id)] = float(value)

    target_coordinates = [_read_coordinates(cell) for cell in grid_cells]
    exact_results = []
    cells_to_predict = []
    coordinates_to_predict = []

    for cell, (lon, lat) in zip(grid_cells, target_coordinates):
        grid_cell_id = _read_grid_cell_id(cell)
        if grid_cell_id in exact_values_by_cell_id:
            exact_results.append(
                build_interpolation_result(
                    cell,
                    lon,
                    lat,
                    metric_key,
                    exact_values_by_cell_id[grid_cell_id],
                    variance=0,
                )
            )
            continue

        cells_to_predict.append(cell)
        coordinates_to_predict.append((lon, lat))

    if not cells_to_predict:
        return exact_results

    x = np.array([row[0] for row in known_rows], dtype=float)
    y = np.array([row[1] for row in known_rows], dtype=float)
    z = np.array([row[2] for row in known_rows], dtype=float)

    target_x = np.array([coord[0] for coord in coordinates_to_predict], dtype=float)
    target_y = np.array([coord[1] for coord in coordinates_to_predict], dtype=float)

    if np.allclose(z, z[0]):
        interpolated_values = np.full(len(cells_to_predict), z[0], dtype=float)
        variance = np.zeros(len(cells_to_predict), dtype=float)
    else:
        # Use ordinary kriging to predict values at unsampled centroid locations.
        kriging = OrdinaryKriging(
            x,
            y,
            z,
            variogram_model="linear",
            verbose=False,
            enable_plotting=False,
        )

        interpolated_values, variance = kriging.execute(
            "points", target_x, target_y
        )

    results = list()

    for cell, value, var, (lon, lat) in zip(
        cells_to_predict,
        interpolated_values,
        variance,
        coordinates_to_predict,
    ):
        results.append(
            build_interpolation_result(cell, lon, lat, metric_key, value, variance=var)
        )

    return [*exact_results, *results]


def merge_interpolated_metric(base_results, metric_results, metric_key: str):
    """Add one interpolated metric result set onto the base result rows."""
    metric_by_cell_id = {
        result["grid_cell_id"]: result[metric_key]
        for result in metric_results
    }

    for result in base_results:
        if result["grid_cell_id"] in metric_by_cell_id:
            result[metric_key] = metric_by_cell_id[result["grid_cell_id"]]


def fill_missing_metrics(results):
    """Keep unsupported metrics explicit as null in the response/database."""
    for result in results:
        for metric_key in INTERPOLATABLE_METRICS:
            result.setdefault(metric_key, None)


def get_known_metric_count(known_points, metric_key: str):
    """Count known points that include a value for this metric."""
    return sum(1 for point in known_points if _read_value(point, metric_key) is not None)


def interpolate_available_metrics(grid_cells, known_points, requested_metric_key: str):
    """Interpolate every metric with enough known values."""
    metric_order = [
        requested_metric_key,
        *sorted(INTERPOLATABLE_METRICS - {requested_metric_key}),
    ]
    metric_keys = [
        metric_key
        for metric_key in metric_order
        if get_known_metric_count(known_points, metric_key) >= 2
    ]

    if not metric_keys:
        raise ValueError(
            "At least two known points for one interpolatable metric are required."
        )

    def interpolate_metric(metric_key):
        return metric_key, interpolate_grid_centroids(
            grid_cells,
            known_points,
            metric_key=metric_key,
        )

    max_workers = min(len(metric_keys), len(INTERPOLATABLE_METRICS))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        metric_result_sets = list(executor.map(interpolate_metric, metric_keys))

    results = None
    for metric_key, metric_results in metric_result_sets:
        if results is None:
            results = metric_results
        else:
            merge_interpolated_metric(results, metric_results, metric_key)

    fill_missing_metrics(results)
    return results


def add_relative_confidence(results):
    """Score each result from 0 to 1 based on variance within this run."""
    variances = [max(result["variance"], 0) for result in results]
    if not variances:
        return

    min_variance = min(variances)
    max_variance = max(variances)

    if min_variance == max_variance:
        for result in results:
            result["confidence"] = 1.0
        return

    for result, variance in zip(results, variances):
        uncertainty = (variance - min_variance) / (max_variance - min_variance)
        result["confidence"] = 1 - uncertainty


def interpolated_points_to_geojson(points):
    """Convert interpolated point rows into a GeoJSON FeatureCollection."""
    features = []

    for point in points:
        features.append({
            "type": "Feature",
            "properties": {
                "id": point.id,
                "grid_cell_id": point.grid_cell_id,
                "timestamp": point.timestamp.isoformat(),
                "heat_index": point.heat_index,
                "heat_risk": point.heat_risk,
                "crowd_density": point.crowd_density,
                "population": point.population,
                "cooling_centers": point.cooling_centers,
                "infrastructure_strain": point.infrastructure_strain,
                "interpolation_method": point.interpolation_method,
                "source_count": point.source_count,
                "confidence": point.confidence,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [point.longitude, point.latitude],
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def metric_value_range(points, metric_key):
    """Return the min/max for a metric across available interpolated points."""
    values = [
        getattr(point, metric_key)
        for point in points
        if getattr(point, metric_key) is not None
    ]
    if not values:
        return None, None
    return min(values), max(values)


def metric_to_intensity(value, min_value, max_value):
    """Normalize a metric value into the 0-1 range used by heatmap layers."""
    if value is None:
        return 0
    if min_value is None or max_value is None:
        return 0
    if min_value == max_value:
        return 1
    return (value - min_value) / (max_value - min_value)


def interpolated_points_to_heatmap_geojson(interpolated_points, metric_key="heat_index"):
    """Convert interpolated points into heatmap-friendly point GeoJSON."""
    min_value, max_value = metric_value_range(interpolated_points, metric_key)
    features = []

    for point in interpolated_points:
        value = getattr(point, metric_key, None)
        intensity = metric_to_intensity(value, min_value, max_value)
        features.append({
            "type": "Feature",
            "properties": {
                "id": point.id,
                "grid_cell_id": point.grid_cell_id,
                "timestamp": point.timestamp.isoformat(),
                "metric": metric_key,
                "value": value,
                "intensity": intensity,
                "confidence": point.confidence,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [point.longitude, point.latitude],
            },
        })

    return {
        "type": "FeatureCollection",
        "properties": {
            "metric": metric_key,
            "min": min_value,
            "max": max_value,
        },
        "features": features,
    }



def interpolated_points_to_polygon_geojson(interpolated_points, color_metric="heat_index"):
    """Convert interpolated point rows into polygon GeoJSON for mesh rendering."""
    features = []

    for point in interpolated_points:
        cell = point.grid_cell
        if not cell or not cell.geometry:
            continue

        fill_color = metric_to_color(color_metric, getattr(point, color_metric, None))
        features.append({
            "type": "Feature",
            "geometry": cell.geometry,
            "properties": {
                "id": point.id,
                "grid_cell_id": cell.id,
                "cell_id": cell.cell_id,
                "row": cell.row,
                "col": cell.col,
                "timestamp": point.timestamp.isoformat(),
                "heat_index": point.heat_index,
                "heat_risk": point.heat_risk,
                "crowd_density": point.crowd_density,
                "population": point.population,
                "cooling_centers": point.cooling_centers,
                "infrastructure_strain": point.infrastructure_strain,
                "interpolation_method": point.interpolation_method,
                "source_count": point.source_count,
                "confidence": point.confidence,
                "color_metric": color_metric,
                "fillColor": fill_color,
                "fill": fill_color,
                "stroke": False,
                "color": fill_color,
                "weight": 0,
                "opacity": 0,
                "fillOpacity": 0.78,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def get_interpolated_points_query(db, city=None, state=None, timestamp=None):
    """Build a filtered interpolated-points query."""
    query = (
        db.query(grid_cell_tables.InterpolatedPoint)
        .options(joinedload(grid_cell_tables.InterpolatedPoint.grid_cell))
    )

    if city and state:
        grid_cells = get_city_grid_cells(city, state, db)
        grid_cell_ids = [cell.id for cell in grid_cells]
        query = query.filter(grid_cell_tables.InterpolatedPoint.grid_cell_id.in_(grid_cell_ids))
    elif city or state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="city and state must be provided together.",
        )

    if timestamp:
        query = query.filter(grid_cell_tables.InterpolatedPoint.timestamp == timestamp)

    return query



# Get the grid cells (geojson format)
@router.get("/grid_cells_city")
async def get_grid_cells_city(city: str, state: str, db: Session = Depends(get_db)):
    """Route gets all grid cells related with the city"""
    all_cells = get_city_grid_cells(city, state, db)
    cells_geojson = grid_cells_to_geojson(all_cells)
    return cells_geojson


# Route to actually interpolate
@router.post("/interpolate", response_model=list[interpolate_schemas.InterpolatedPointResponse])
async def interpolate(
    payload: interpolate_schemas.InterpolationRunRequest,
    db: Session = Depends(get_db),
):
    """Interpolate known points onto city grid centroids and save the results."""
    if payload.metric_key not in INTERPOLATABLE_METRICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"metric_key must be one of: {sorted(INTERPOLATABLE_METRICS)}",
        )

    grid_cells = get_city_grid_cells(payload.city, payload.state, db)
    grid_metric_points, exact_metrics_by_cell_id = grid_metrics_to_known_points(
        grid_cells,
        payload.timestamp,
        db,
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
        (
            db.query(grid_cell_tables.InterpolatedPoint)
            .filter(grid_cell_tables.InterpolatedPoint.grid_cell_id.in_(result_grid_cell_ids))
            .filter(grid_cell_tables.InterpolatedPoint.timestamp == payload.timestamp)
            .delete(synchronize_session=False)
        )
        db.flush()

    interpolated_points = []
    # Update / add all points for the interpolated points
    for result in results:
        point = grid_cell_tables.InterpolatedPoint(
            grid_cell_id=result["grid_cell_id"],
            timestamp=payload.timestamp,
            latitude=result["latitude"],
            longitude=result["longitude"],
            interpolation_method="kriging",
            source_count=len(known_points),
            confidence=result["confidence"],
        )
        for metric_key in INTERPOLATABLE_METRICS:
            setattr(point, metric_key, result[metric_key])
        interpolated_points.append(point)

    db.add_all(interpolated_points)
    db.commit()

    return (
        db.query(grid_cell_tables.InterpolatedPoint)
        .filter(grid_cell_tables.InterpolatedPoint.grid_cell_id.in_(result_grid_cell_ids))
        .filter(grid_cell_tables.InterpolatedPoint.timestamp == payload.timestamp)
        .all()
    )




# Get all interpolated values 
@router.get("/all")
async def get_all(db: Session = Depends(get_db)):
    """function gets all interpolated points and returns them in geojson format"""
    data = db.query(grid_cell_tables.InterpolatedPoint).all()
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
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
    if color_metric not in INTERPOLATABLE_METRICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"color_metric must be one of: {sorted(INTERPOLATABLE_METRICS)}",
        )

    query = get_interpolated_points_query(db, city, state, timestamp)
    data = query.all()
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
    if metric_key not in INTERPOLATABLE_METRICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"metric_key must be one of: {sorted(INTERPOLATABLE_METRICS)}",
        )

    query = get_interpolated_points_query(db, city, state, timestamp)
    data = query.all()
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")

    return interpolated_points_to_heatmap_geojson(data, metric_key=metric_key)


# Update/hen the user draws polygon/points the area of the polygon impacts these points 
@router.put(
    "/update/{interpolated_id}",
    response_model=interpolate_schemas.InterpolatedPointResponse
)
async def update_cell(
    interpolated_id: int,
    payload: interpolate_schemas.InterpolatedPointUpdate,
    db: Session = Depends(get_db)
):
    """Update an interpolated point."""

    point = (
        db.query(grid_cell_tables.InterpolatedPoint)
        .filter(grid_cell_tables.InterpolatedPoint.id == interpolated_id)
        .first()
    )

    if not point:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NOT FOUND"
        )
    # update the values
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(point, key, value)

    db.commit()
    db.refresh(point)

    return point


# delete
@router.delete("/delete/{interpolated_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cell_id(interpolated_id: int, db: Session = Depends(get_db)):
    """function deletes a specific interpolated point by its id"""
    data = (
        db.query(grid_cell_tables.InterpolatedPoint)
        .filter(grid_cell_tables.InterpolatedPoint.id == interpolated_id)
        .first()
    )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NOT FOUND"
        )
    db.delete(data)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
