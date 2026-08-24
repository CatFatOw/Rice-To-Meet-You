"""File handles the core logic behind the grid interpolation routes"""
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from pykrige.ok import OrdinaryKriging
from data.city_boundaries import (
    get_city_bounds,
    get_city_boundary_geojson,
    resolve_city_name,
    supported_cities,
)


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


def _walk_positions(coordinates):
    """Yield every [lon, lat] pair from nested GeoJSON coordinate arrays."""
    if not coordinates:
        return
    if isinstance(coordinates[0], (int, float)):
        yield coordinates
        return
    for nested in coordinates:
        yield from _walk_positions(nested)


def _grid_cell_bounds(cells):
    """Return [min_lon, min_lat, max_lon, max_lat] across cell polygon geometry."""
    min_lon = min_lat = float("inf")
    max_lon = max_lat = float("-inf")

    for cell in cells:
        geometry = cell.geometry or {}
        for position in _walk_positions(geometry.get("coordinates", [])):
            lon, lat = position[0], position[1]
            min_lon = min(min_lon, lon)
            max_lon = max(max_lon, lon)
            min_lat = min(min_lat, lat)
            max_lat = max(max_lat, lat)

    if min_lon == float("inf"):
        raise ValueError("Grid cells have no polygon geometry to derive bounds from.")
    return [min_lon, min_lat, max_lon, max_lat]


def _fill_metric_grid_with_kriging(values, bounds, rows, cols, cell_by_pos, metric_key):
    """Krige values onto lattice positions that have no saved metric value.

    Positions without a stored grid cell (no metric row at all) get a synthetic
    centroid from the regular bbox split, matching how the grid was generated.
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    lon_step = (max_lon - min_lon) / cols
    lat_step = (max_lat - min_lat) / rows

    def centroid(row, col):
        cell = cell_by_pos.get((row, col))
        if cell is not None:
            return cell.grid_centroid_lon, cell.grid_centroid_lat
        return min_lon + (col + 0.5) * lon_step, min_lat + (row + 0.5) * lat_step

    known_points = []
    target_cells = []
    for row in range(rows):
        for col in range(cols):
            lon, lat = centroid(row, col)
            position_id = row * cols + col
            value = values[row][col]
            if value is not None:
                known_points.append(
                    {"grid_cell_id": position_id, "lon": lon, "lat": lat, metric_key: float(value)}
                )
            else:
                target_cells.append({"id": position_id, "lon": lon, "lat": lat})

    if not target_cells or len(known_points) < 2:
        return

    results = interpolate_grid_centroids(target_cells, known_points, metric_key=metric_key)
    for result in results:
        position_id = result["grid_cell_id"]
        values[position_id // cols][position_id % cols] = round(float(result[metric_key]), 2)


def grid_metrics_to_city_grids(metrics, metric_keys=None):
    """Convert latest grid metric rows into city-keyed raster value grids.

    Each city becomes a rows x cols lattice (row 0 = southernmost) of metric
    values at grid cell centroids, with kriging filling any cells that have no
    saved value, so the frontend can render a continuous surface and sample the
    interpolated value at any coordinate.
    """
    metric_keys = sorted(metric_keys or INTERPOLATABLE_METRICS)
    metrics_by_city = {}
    for metric in metrics:
        grid_cell = getattr(metric, "grid_cell", None)
        if not grid_cell or grid_cell.row is None or grid_cell.col is None:
            continue
        city_name = city_name_from_interpolated_point(metric)
        metrics_by_city.setdefault(city_name, []).append(metric)

    city_grids = {}
    for city_name, city_metrics in metrics_by_city.items():
        cells = [metric.grid_cell for metric in city_metrics]
        rows = max(cell.row for cell in cells) + 1
        cols = max(cell.col for cell in cells) + 1
        bounds = _grid_cell_bounds(cells)
        cell_by_pos = {(cell.row, cell.col): cell for cell in cells}

        metric_grids = {}
        for metric_key in metric_keys:
            values = [[None] * cols for _ in range(rows)]
            for metric in city_metrics:
                value = getattr(metric, metric_key, None)
                if value is not None:
                    cell = metric.grid_cell
                    values[cell.row][cell.col] = float(value)

            flat_known = [value for row in values for value in row if value is not None]
            if not flat_known:
                continue

            _fill_metric_grid_with_kriging(values, bounds, rows, cols, cell_by_pos, metric_key)

            flat = [value for row in values for value in row if value is not None]
            metric_grids[metric_key] = {
                "min": min(flat),
                "max": max(flat),
                "values": values,
            }

        if not metric_grids:
            continue

        city_grids[city_name] = {
            "state": cells[0].state,
            "bounds": bounds,
            "rows": rows,
            "cols": cols,
            "timestamp": max(metric.timestamp for metric in city_metrics).isoformat(),
            "metrics": metric_grids,
        }

    return city_grids


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


# ---------------------------------------------------------------------------
# Continuous kriged surfaces
# ---------------------------------------------------------------------------
# The routes above interpolate onto saved grid-cell centroids and persist the
# result. The frontend needs something different: a dense, regular lattice it
# can draw as one continuous image. That surface is derived data — it is never
# stored, so it works for simulated readings that exist only in the browser.

# Metrics the surface endpoint accepts. These are weather-model metrics, not the
# stored grid metrics in INTERPOLATABLE_METRICS, and they are deliberately kept
# separate: nothing about a surface request touches grid_cell_metrics.
SURFACE_METRICS = {
    "average_temperature_c",
    "change_in_temperature",
}

# Lattice resolution bounds. Kriging cost grows with the number of predicted
# points, so the ceiling keeps a single request bounded.
SURFACE_MIN_RESOLUTION = 8
SURFACE_MAX_RESOLUTION = 128
SURFACE_DEFAULT_RESOLUTION = 48

# Padding applied to the observation bounding box, as a fraction of its span,
# so the drawn surface extends slightly past the outermost reading instead of
# ending exactly on it.
SURFACE_BOUNDS_PADDING = 0.05

# Minimum degrees of span for a bounding box. Guards the degenerate cases of a
# single observation, or several that share a latitude or longitude.
SURFACE_MIN_SPAN = 0.01


def surface_bounds_for_city(city: str):
    """The city's rectangle as [minLon, minLat, maxLon, maxLat], or None.

    The rectangle is used unpadded and unmodified: it is simultaneously the
    lattice extent, the set of readings that feed the fit, and the drawn image,
    so all three agree by construction. The same city therefore renders at the
    same extent on every date, however many readings a particular day has.
    """
    return get_city_bounds(city)


def surface_bounds(points):
    """Padded [minLon, minLat, maxLon, maxLat] covering every observation.

    The fallback extent, used only when no city is given. Prefer
    surface_bounds_for_city.
    """
    longitudes = [float(point["longitude"]) for point in points]
    latitudes = [float(point["latitude"]) for point in points]

    min_lon, max_lon = min(longitudes), max(longitudes)
    min_lat, max_lat = min(latitudes), max(latitudes)

    lon_span = max(max_lon - min_lon, SURFACE_MIN_SPAN)
    lat_span = max(max_lat - min_lat, SURFACE_MIN_SPAN)

    # Re-centre a degenerate axis on its single value rather than growing it
    # in one direction only.
    lon_centre = (min_lon + max_lon) / 2
    lat_centre = (min_lat + max_lat) / 2
    min_lon, max_lon = lon_centre - lon_span / 2, lon_centre + lon_span / 2
    min_lat, max_lat = lat_centre - lat_span / 2, lat_centre + lat_span / 2

    lon_pad = lon_span * SURFACE_BOUNDS_PADDING
    lat_pad = lat_span * SURFACE_BOUNDS_PADDING

    return [min_lon - lon_pad, min_lat - lat_pad, max_lon + lon_pad, max_lat + lat_pad]


# Variogram models tried in order. Spherical leads because it saturates, which
# fits a bounded urban heat field: semivariance climbs with distance and then
# levels off. A linear model cannot fit that shape - least squares drives its
# slope to zero, the model degenerates to pure nugget, and kriging then returns
# the global mean at every location (a flat surface). Gaussian is excluded
# outright: on this data it produces wild over/undershoot.
SURFACE_VARIOGRAM_MODELS = ("spherical", "exponential", "power")

# A fitted model is rejected when the predicted surface varies by less than
# this fraction of the observed spread - the signature of the degenerate
# pure-nugget fit described above.
SURFACE_DEGENERATE_RATIO = 0.05

# Kriging may extrapolate past the observed range, which is legitimate, but an
# ill-conditioned fit can overshoot by orders of magnitude. Predictions are
# clamped to the observed range widened by this fraction of its own spread.
SURFACE_OVERSHOOT_MARGIN = 0.25


# Ordinary kriging is cubic in the number of observations: pykrige builds the
# full O(N^2) pairwise distance matrix when it fits, then by default solves
# against every observation for every predicted cell. Measured on a 48x48
# lattice, that is 0.24s at N=1000 but 15.5s and 1.8GB at N=8000.
#
# Two bounds keep it interactive, and both were measured against a known field:
# subsampling to 1000 and using a 32-point local neighbourhood took an 8000
# point fit from 18.8s to 0.15s while RMSE against the true field moved only
# 0.087 -> 0.094, and the recovered value range was unchanged.
SURFACE_MAX_FIT_POINTS = 1000
SURFACE_KRIGING_NEIGHBOURS = 32


def subsample_points(points, max_points: int = SURFACE_MAX_FIT_POINTS, seed: int = 0):
    """Randomly thin readings to at most `max_points`.

    Random selection, deliberately not averaging into bins: bin-averaging is
    faster still but smooths the extremes away - on the same test field it
    flattened a 34.9 degree peak to 33.3 and cost 7x the error. Dropping whole
    readings at random leaves the surviving values, and so the peaks, intact.

    Seeded so repeated requests for the same data return the same surface.
    """
    if len(points) <= max_points:
        return points
    rng = np.random.default_rng(seed)
    keep = rng.choice(len(points), max_points, replace=False)
    keep.sort()  # preserve input order, which keeps the result easy to compare
    return [points[i] for i in keep]


def _fit_and_execute(x, y, z, target_lons, target_lats, model: str):
    """Run one ordinary-kriging fit; returns (values, variance)."""
    kriging = OrdinaryKriging(
        x,
        y,
        z,
        variogram_model=model,
        verbose=False,
        enable_plotting=False,
    )
    # "grid" evaluates the full lat x lon outer product in one call, which is
    # what makes a dense lattice affordable. n_closest_points restricts each
    # cell's solve to its nearest observations; it requires the loop backend.
    values, variance = kriging.execute(
        "grid",
        target_lons,
        target_lats,
        backend="loop",
        n_closest_points=min(SURFACE_KRIGING_NEIGHBOURS, len(x)),
    )
    return np.asarray(values, dtype=float), np.asarray(variance, dtype=float)


# Readings are matched to a city by its outline. A non-zero buffer (in degrees)
# widens that test, trading strictness for stability: kriging near the edge of a
# point cloud has little data on one side, so a small buffer pulls in the
# neighbouring readings that steady it. The default is strict - a city's surface
# is fitted only on readings that fall inside that city.
SURFACE_BOUNDARY_BUFFER_DEG = 0.0

# Ordinary kriging needs at least two distinct observations to fit a variogram.
# A city with fewer gets no surface rather than a fabricated one.
SURFACE_MIN_POINTS = 2


def points_inside_city(points, city: str, buffer_deg: float = SURFACE_BOUNDARY_BUFFER_DEG):
    """Return only the readings that fall inside a city's rectangle.

    This is what makes each city's surface its own: the variogram is fitted on
    one city's readings alone, so a neighbouring city's heat pattern cannot
    influence it. Returns every point unchanged when the city is unknown.
    """
    bounds = get_city_bounds(city) if city else None
    if not bounds or not points:
        return list(points)

    min_lon, min_lat, max_lon, max_lat = bounds
    if buffer_deg:
        min_lon -= buffer_deg
        min_lat -= buffer_deg
        max_lon += buffer_deg
        max_lat += buffer_deg

    return [
        point
        for point in points
        if min_lon <= float(point["longitude"]) <= max_lon
        and min_lat <= float(point["latitude"]) <= max_lat
    ]


def group_points_by_city(points, cities=None, buffer_deg: float = SURFACE_BOUNDARY_BUFFER_DEG):
    """Partition readings by the city rectangle that contains them.

    Cities with no readings are omitted, and a reading outside every rectangle
    is dropped - there is no city surface it belongs to.

    Some host-city rectangles genuinely overlap (New York and New Jersey share
    0.84 x 0.59 degrees, and both overlap Philadelphia), so a reading in an
    overlap feeds every rectangle containing it. That is correct for building
    each city's surface independently, but it means two surfaces can cover the
    same ground - callers that draw the result should pass `cities` to name the
    one city they want rather than rendering all of them on top of each other.
    """
    target_cities = list(cities) if cities else supported_cities()
    grouped = {}

    for city in target_cities:
        resolved = resolve_city_name(city)
        if not resolved:
            continue
        city_points = points_inside_city(points, resolved, buffer_deg=buffer_deg)
        if city_points:
            grouped[resolved] = city_points

    return grouped


def krige_city_surfaces(
    points,
    rows: int,
    cols: int,
    cities=None,
    variogram_model=None,
    buffer_deg: float = SURFACE_BOUNDARY_BUFFER_DEG,
):
    """Krige one independent surface per city.

    Each city is fitted and predicted on its own readings only, so the result is
    a set of separate surfaces rather than slices of a single national one.
    Returns (surfaces_by_city, skipped), where `skipped` explains every city
    that could not produce a surface.
    """
    grouped = group_points_by_city(points, cities=cities, buffer_deg=buffer_deg)
    surfaces = {}
    skipped = {}

    for city, city_points in grouped.items():
        if len(city_points) < SURFACE_MIN_POINTS:
            skipped[city] = (
                f"only {len(city_points)} reading(s) inside the city outline; "
                f"{SURFACE_MIN_POINTS} are required"
            )
            continue
        try:
            surfaces[city] = krige_surface(
                city_points,
                rows=rows,
                cols=cols,
                city=city,
                variogram_model=variogram_model,
                buffer_deg=buffer_deg,
            )
        except ValueError as exc:
            skipped[city] = str(exc)

    return surfaces, skipped


def _krige_values(x, y, z, target_lons, target_lats, rows, cols, variogram_model=None):
    """Krige one value field onto a fixed lattice; returns (values, variance, model).

    Split out of krige_surface so the secondary metrics shown in the tooltip can
    be interpolated onto exactly the same lattice as the drawn surface, through
    exactly the same fitting and safeguards.
    """
    observed_min = float(np.min(z))
    observed_max = float(np.max(z))
    observed_spread = observed_max - observed_min

    # A constant field has no variogram to fit, and pykrige raises on one. It is
    # also a legitimate input: change_in_temperature is all zeros until an
    # intervention is placed, and a market-level metric carries one value across
    # the whole city.
    if len(z) < 2 or observed_spread == 0:
        return (
            np.full((rows, cols), z[0], dtype=float),
            np.zeros((rows, cols), dtype=float),
            "constant",
        )

    candidates = (variogram_model,) if variogram_model else SURFACE_VARIOGRAM_MODELS
    values = None
    variance = None
    model_used = None
    last_error = None

    for candidate in candidates:
        try:
            fitted_values, fitted_variance = _fit_and_execute(
                x, y, z, target_lons, target_lats, candidate
            )
        except Exception as exc:  # noqa: BLE001 - try the next model instead
            last_error = exc
            continue

        values, variance, model_used = fitted_values, fitted_variance, candidate

        # Accept the first model whose surface carries real structure.
        spread = float(np.nanmax(fitted_values) - np.nanmin(fitted_values))
        if spread >= observed_spread * SURFACE_DEGENERATE_RATIO:
            break

    if values is None:
        raise ValueError(f"Kriging failed for every variogram model: {last_error}")

    # Guard against an ill-conditioned fit overshooting the data.
    margin = observed_spread * SURFACE_OVERSHOOT_MARGIN
    return (
        np.clip(values, observed_min - margin, observed_max + margin),
        variance,
        model_used,
    )


def krige_surface(
    points,
    rows: int,
    cols: int,
    bounds=None,
    variogram_model=None,
    city=None,
    buffer_deg: float = SURFACE_BOUNDARY_BUFFER_DEG,
    extra_points_by_metric=None,
):
    """Ordinary-krige observations onto a regular rows x cols lattice.

    `points` are dicts carrying longitude, latitude and value. The returned
    lattice is row-major with row 0 at the southern edge, matching the raster
    renderer's expectation, and each cell holds the value at its centroid.

    Pass `city` to make this a city surface. The readings are first *filtered*
    to that city's rectangle and the variogram is fitted on those alone, so the
    surface is generated from the city's own data rather than sliced out of a
    wider fit. The lattice then spans exactly the same rectangle, so every cell
    holds a value - there is nothing to clip.

    Models are tried in order until one produces a surface that actually varies,
    because a variogram that fits badly degenerates into a flat mean rather than
    raising.

    `extra_points_by_metric` maps a metric name to its own readings. Each is
    kriged onto the *same* lattice and returned under `metrics`. These are the
    values the tooltip reports alongside the drawn metric: they are never
    coloured, but they are interpolated rather than snapped to the nearest
    reading, so the tooltip describes the exact point under the cursor.
    """
    if not points:
        raise ValueError("At least one known point is required.")

    # Fit on this city's readings only. Doing it here, before anything else,
    # is what separates "a surface for this city" from "the national surface,
    # cropped".
    if city:
        points = points_inside_city(points, city, buffer_deg=buffer_deg)
        if len(points) < SURFACE_MIN_POINTS:
            raise ValueError(
                f"Only {len(points)} reading(s) fall inside {resolve_city_name(city)}; "
                f"{SURFACE_MIN_POINTS} are required to fit a variogram."
            )

    # Bound the cost before any fitting happens. A city rectangle can hold many
    # more readings than a 48x48 lattice can express.
    points = subsample_points(points)

    rows = int(max(SURFACE_MIN_RESOLUTION, min(SURFACE_MAX_RESOLUTION, rows)))
    cols = int(max(SURFACE_MIN_RESOLUTION, min(SURFACE_MAX_RESOLUTION, cols)))

    # Explicit bounds win; otherwise the city outline defines the extent, and
    # only a request with no city at all falls back to the observations' bbox.
    resolved_bounds = (
        (list(bounds) if bounds else None)
        or (surface_bounds_for_city(city) if city else None)
        or surface_bounds(points)
    )
    min_lon, min_lat, max_lon, max_lat = (float(value) for value in resolved_bounds)

    # Cell centroids, so the lattice describes cell centres and not corners.
    lon_step = (max_lon - min_lon) / cols
    lat_step = (max_lat - min_lat) / rows
    target_lons = np.array(
        [min_lon + (col + 0.5) * lon_step for col in range(cols)], dtype=float
    )
    target_lats = np.array(
        [min_lat + (row + 0.5) * lat_step for row in range(rows)], dtype=float
    )

    x = np.array([float(point["longitude"]) for point in points], dtype=float)
    y = np.array([float(point["latitude"]) for point in points], dtype=float)
    z = np.array([float(point["value"]) for point in points], dtype=float)

    values, variance, model_used = _krige_values(
        x, y, z, target_lons, target_lats, rows, cols, variogram_model
    )

    # Secondary metrics: same lattice, same fitting path, own variogram. Each is
    # filtered and thinned exactly like the primary, and one that cannot be
    # fitted is skipped rather than failing the whole surface - a missing
    # tooltip row is a far smaller loss than a missing map.
    metric_layers = {}
    for metric_name, metric_points in (extra_points_by_metric or {}).items():
        if city:
            metric_points = points_inside_city(metric_points, city, buffer_deg=buffer_deg)
        metric_points = subsample_points(metric_points)
        if len(metric_points) < SURFACE_MIN_POINTS:
            continue
        try:
            layer_values, _, layer_model = _krige_values(
                np.array([float(p["longitude"]) for p in metric_points], dtype=float),
                np.array([float(p["latitude"]) for p in metric_points], dtype=float),
                np.array([float(p["value"]) for p in metric_points], dtype=float),
                target_lons,
                target_lats,
                rows,
                cols,
                variogram_model,
            )
        except ValueError:
            continue
        metric_layers[metric_name] = {
            "values": [[float(v) for v in row] for row in layer_values],
            "min": float(np.nanmin(layer_values)),
            "max": float(np.nanmax(layer_values)),
            "source_count": len(metric_points),
            "variogram_model": layer_model,
        }

    # No clipping step: the lattice spans exactly the city rectangle, so every
    # cell is inside the boundary by construction and carries a real value.
    resolved_city = resolve_city_name(city) if city else None

    return {
        "bounds": [min_lon, min_lat, max_lon, max_lat],
        "rows": rows,
        "cols": cols,
        "values": [[float(value) for value in row] for row in values],
        "min": float(np.nanmin(values)),
        "max": float(np.nanmax(values)),
        "variance_mean": float(np.nanmean(variance)),
        # Readings that fed this city's fit, after the rectangle filter.
        "source_count": len(points),
        "variogram_model": model_used,
        "city": resolved_city,
        # The same rectangle as `bounds`, as GeoJSON, so the map can stroke it.
        "boundary": get_city_boundary_geojson(city) if resolved_city else None,
        # Secondary metrics on this same lattice, for the tooltip.
        "metrics": metric_layers,
    }
