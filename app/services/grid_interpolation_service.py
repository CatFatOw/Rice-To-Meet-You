"""Ordinary kriging of metric readings onto the map's continuous surfaces."""
import numpy as np
from pykrige.ok import OrdinaryKriging
from data.city_boundaries import (
    get_city_bounds,
    resolve_city_name,
)


# The frontend draws a dense, regular lattice as one continuous image. That
# surface is derived data - it is never stored, so it works for simulated
# readings that exist only in the browser.

# Metrics the surface endpoint accepts: every metric the map can display except
# avg_daily_visits and heat_risk_score.
#
# Two metrics are excluded on purpose, and both for the same reason: they are
# per-POI records rather than samples of a field that exists between the POIs,
# so kriging one would invent a value for empty ground. avg_daily_visits is a
# footfall count, and heat_risk_score is scored per POI and carries that POI's
# name, brand and address - text a coordinate between two POIs cannot have.
# Both keep the point-density heatmap.
SURFACE_METRICS = {
    "average_temperature_c",
    "average_temperature_f",
    "heat_index_c",
    "heat_index_f",
    "average_relative_humidity_pct",
    "local_temperature_c",
    "local_temperature_f",
    # The urban-heat-island reading itself. Unlike the two excluded metrics
    # below, it IS a sample of a field -- heat island intensity is defined
    # everywhere in the city, not just where a reading was taken -- so the
    # value kriged for empty ground is a real estimate rather than an invention.
    # The public name of the metric, whatever the reflected heat table spells
    # the column: see HeatmapRepository.UHI_CANDIDATES.
    "urban_heat_index",
    "change_in_temperature",
    "change_in_average_temperature_c",
    "change_in_average_temperature_f",
    "change_in_local_temperature_c",
    "change_in_local_temperature_f",
}

# Lattice resolution bounds. Kriging cost grows with the number of predicted
# points, so the ceiling keeps a single request bounded.
SURFACE_MIN_RESOLUTION = 8
SURFACE_MAX_RESOLUTION = 128

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
        # Secondary metrics on this same lattice, for the tooltip.
        "metrics": metric_layers,
    }
