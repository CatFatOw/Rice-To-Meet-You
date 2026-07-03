"""File handles the core logic behind the grid interpolation routes"""
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from pykrige.ok import OrdinaryKriging


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


def grid_metrics_to_known_points(grid_cells, metrics):
    """Use saved grid metrics as known points for interpolation."""
    cell_by_id = {cell.id: cell for cell in grid_cells}
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


def city_name_from_interpolated_point(point):
    """Infer the display city name from the generated grid cell id.

    Interpolated points do not store city directly. Generated grid cell ids use
    a city_state_row_col style prefix, so this keeps the frontend heatmap route
    grouped by city without adding another database column.
    """
    grid_cell = getattr(point, "grid_cell", None)
    cell_id = getattr(grid_cell, "cell_id", None)
    state = getattr(grid_cell, "state", None)
    if not cell_id:
        return "Unknown"

    parts = cell_id.split("_")
    if state:
        normalized_state = str(state).lower().replace(" ", "_")
        state_index = "_".join(parts).find(f"_{normalized_state}_")
        if state_index > 0:
            return cell_id[:state_index].replace("_", " ").title()

    if len(parts) >= 3:
        return parts[0].replace("_", " ").title()
    return "Unknown"


def interpolated_points_to_metric_layers(interpolated_points, metric_keys=None):
    """Convert interpolated rows into the frontend heatmap metric layer shape.

    The lower-level interpolation endpoint returns GeoJSON. The React heatmap
    component expects a city-keyed dictionary of metric layers, with each layer
    containing normalized 0-100 weighted points. This adapter keeps that frontend
    contract while reusing the saved interpolation rows as the source of truth.
    """
    metric_keys = sorted(metric_keys or INTERPOLATABLE_METRICS)
    ranges = {
        metric_key: metric_value_range(interpolated_points, metric_key)
        for metric_key in metric_keys
    }
    layers_by_city = {}

    for metric_key in metric_keys:
        min_value, max_value = ranges[metric_key]
        for point in interpolated_points:
            raw_value = getattr(point, metric_key, None)
            if raw_value is None:
                continue

            city_name = city_name_from_interpolated_point(point)
            city_layers = layers_by_city.setdefault(
                city_name,
                {key: {"metric": key, "points": []} for key in metric_keys},
            )
            grid_cell = getattr(point, "grid_cell", None)
            location_name = getattr(grid_cell, "cell_id", None) or f"Grid Cell {point.grid_cell_id}"
            individual_metrics = {
                key: getattr(point, key, None)
                for key in metric_keys
            }

            city_layers[metric_key]["points"].append({
                "value": metric_to_intensity(raw_value, min_value, max_value) * 100,
                "location_name": location_name,
                "location_coordinates": [point.longitude, point.latitude],
                "individual_metrics": individual_metrics,
            })

    return {
        city_name: [layer for layer in city_layers.values() if layer["points"]]
        for city_name, city_layers in layers_by_city.items()
    }


def grid_metrics_to_metric_layers(metrics, metric_keys=None):
    """Convert latest grid metric rows into the frontend heatmap layer shape.

    This uses the saved grid cell centroid as the rendered point location, so
    the frontend can display a varied heatmap without requiring separate
    interpolated point rows for every demo dataset refresh.
    """
    metric_keys = sorted(metric_keys or INTERPOLATABLE_METRICS)
    ranges = {
        metric_key: metric_value_range(metrics, metric_key)
        for metric_key in metric_keys
    }
    layers_by_city = {}

    for metric_key in metric_keys:
        min_value, max_value = ranges[metric_key]
        for metric in metrics:
            raw_value = getattr(metric, metric_key, None)
            if raw_value is None:
                continue

            grid_cell = getattr(metric, "grid_cell", None)
            if not grid_cell:
                continue

            city_name = city_name_from_interpolated_point(metric)
            city_layers = layers_by_city.setdefault(
                city_name,
                {key: {"metric": key, "points": []} for key in metric_keys},
            )
            individual_metrics = {
                key: getattr(metric, key, None)
                for key in metric_keys
            }

            city_layers[metric_key]["points"].append({
                "value": metric_to_intensity(raw_value, min_value, max_value) * 100,
                "location_name": grid_cell.cell_id or f"Grid Cell {metric.grid_cell_id}",
                "location_coordinates": [grid_cell.grid_centroid_lon, grid_cell.grid_centroid_lat],
                "individual_metrics": individual_metrics,
            })

    return {
        city_name: [layer for layer in city_layers.values() if layer["points"]]
        for city_name, city_layers in layers_by_city.items()
    }
