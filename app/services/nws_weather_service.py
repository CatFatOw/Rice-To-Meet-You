"""Client helpers for National Weather Service API data.

Keep external API request/response logic here. FastAPI route modules should
call this service instead of putting HTTP request code directly in routers or
SQLAlchemy model files.


NWS resolves around the following URL: https://api.weather.gov
Every endpoint returns JSON file 

"""

import threading
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
import geopandas as gpd
from shapely.geometry import box 
from urllib3.util.retry import Retry

from repository.weather_repository import (
    bulk_upsert_nws_observations,
    get_existing_observation_cell_ids,
    upsert_nws_observation,
)

headers = {
    "User-Agent": "RiceHeatSafe (michaelwufluffy@gmail.com)",
    "Accept": "application/geo+json",
}

BASE_URL = "https://api.weather.gov"
REQUEST_TIMEOUT = 20
METADATA_CACHE_TTL = timedelta(days=30)
HTTP_RETRY_COUNT = 3
HTTP_BACKOFF_FACTOR = 0.6
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
_thread_local = threading.local()


def get_http_session():
    """Return one retry-enabled HTTP session per worker thread."""
    session = getattr(_thread_local, "session", None)
    if session is not None:
        return session

    retry = Retry(
        total=HTTP_RETRY_COUNT,
        connect=HTTP_RETRY_COUNT,
        read=HTTP_RETRY_COUNT,
        status=HTTP_RETRY_COUNT,
        backoff_factor=HTTP_BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=40, pool_maxsize=40)
    session = requests.Session()
    session.headers.update(headers)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    _thread_local.session = session
    return session


def get_json(url: str, **kwargs):
    """GET JSON from an external API with timeout, headers, pooling, and retries."""
    response = get_http_session().get(url, timeout=REQUEST_TIMEOUT, **kwargs)
    response.raise_for_status()
    return response.json()

# Get the point metadata 
def get_point_metadata(lat:float, lon:float):
    """Given a specified latitude/longitude it returns the NWS metadata and returns it in json format"""
    point_url = f"{BASE_URL}/points/{lat},{lon}"
    return get_json(point_url)


# Get Hourly
def get_hourly_forecast(lat:float, lon:float):
    """Function returns a json format of all possible days and their hourly forcasts in json format
    If a specific time or day is desired, the fastapi route can do such task"""
    # Returns the metadata NWS 
    point_data = get_point_metadata(lat, lon)
    hourly_url = point_data["properties"]["forecastHourly"]
    return get_json(hourly_url)


def get_hourly_forecast_by_url(hourly_url: str):
    """Fetch an hourly forecast from an NWS forecastHourly URL."""
    return get_json(hourly_url)

# latitude = 29.7604
# longitude = -95.3698
#print(get_hourly_forecast(29.7604, -95.3698))


# Get grid forcast
# This returns a GEO JSON which can be queried into the application (city BBOX)
def get_grid_forecast(lat:float, lon:float):
    """Function gets the NWS raw gridded forecast data and returns more detailed forecast variables (temp, humidity, dew, heat index, wind) over time"""
    point_data = get_point_metadata(lat, lon)
    grid_url = point_data["properties"]["forecastGridData"]
    return get_json(grid_url)

#print(get_grid_forecast(29.7604, -95.3698))


# Get the state bbox


def get_state_bbox(
    full_state_name: str,
    format="jsonv2",
    polygon_geojson=1,
    limit=1,
):
    """Return a state's GeoJSON polygon."""

    payload = {
        "q": full_state_name,
        "format": format,
        "polygon_geojson": polygon_geojson,
        "limit": limit,
    }

    data = get_json(
        "https://nominatim.openstreetmap.org/search",
        params=payload,
    )

    if not data:
        raise ValueError(f"State '{full_state_name}' not found.")
    # Geojson format
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": data[0]["display_name"],
                    "place_id": data[0]["place_id"],
                },
                "geometry": data[0]["geojson"],
            }
        ],
    }
    return geojson

#print(get_state_bbox("texas"))


# THe nxn splitting logic 
def split_bbox_into_cell(state_geojson, output_path=None, n=100, download=False):
    """Given an entire mask (geojson format), it splits it into smaller grid cells"""
    # Load the state mask (geojson equivalent of pandas)
    if isinstance(state_geojson, dict):
        state = gpd.GeoDataFrame.from_features(state_geojson["features"], crs="EPSG:4326")
    else:
        state = gpd.read_file(state_geojson)
    # converts data into Coordinate Reference System.EPSG is the lat/lon 
    state = state.to_crs("EPSG:4326")
    # Get the bounding box since a bbox is essentially a rectangle
    min_lon, min_lat, max_lon, max_lat = state.total_bounds
    
    # Core logic to create nxn cells 
    lon_step = (max_lon - min_lon) / n
    lat_step = (max_lat - min_lat) / n

    cells = list()

    for row in range(n):
        for col in range(n):
            # starting point+ (how many columns over) × (width of one column)
            left = min_lon + col * lon_step
            right =min_lon + (col+1) * lon_step 
            bottom = min_lat + row * lat_step 
            top = min_lat + (row+1) * lat_step 
            # Create 1 rectanglular grid. box function creates the correct polygon format
            cell = box(left, bottom, right, top)
            
            cells.append({
                "cell_id":f"{row}_{col}",
                "row":row,
                "col":col,
                "geometry":cell
            })
    # convert to geodataframe
    grid = gpd.GeoDataFrame(cells, crs="EPSG:4326")
    
    # The grid may exceed the state, so clip anything outside the state boundary.
    clipped_grid = gpd.clip(grid, state)
    clipped_grid = clipped_grid.to_crs("EPSG:3857")

    # We want each grid to act like its own "simulation cell" thus we can find the centroid for each one 
    centroid_projected = clipped_grid.geometry.centroid

    # We need the centroids in lat/lon for the pipline 
    # 1 column
    # EPSG:3857 is distance while EPSG:4326 is lat/lon
    centroids_latlon = gpd.GeoSeries(
        centroid_projected,
        crs="EPSG:3857"
    ).to_crs("EPSG:4326")

    clipped_grid["centroid_lon"] = centroids_latlon.x 
    clipped_grid["centroid_lat"] = centroids_latlon.y
    clipped_grid = clipped_grid.to_crs("EPSG:4326")

    # download for demo/quick visualize
    if download:
        if not output_path:
            raise ValueError("output_path is required when download=True")
        clipped_grid.to_file(output_path, driver="GeoJSON")
        return f"FINISHED EXPORTING TO: {output_path} "
    #don't download for bsackend process
    return clipped_grid




    


def hourly_forecast_to_weather_summary(
    hourly: dict,
    target_time: str | None = None,
):
    """Convert NWS hourly forecast JSON into the smaller weather summary we store."""
    periods = hourly["properties"]["periods"]

    # Default to the first (current) forecast period
    if target_time is None:
        period = periods[0]
    else:
        target = datetime.fromisoformat(target_time)

        period = min(
            periods,
            key=lambda p: abs(
                datetime.fromisoformat(p["startTime"]) - target
            ),
        )

    return {
        "time": period["startTime"],
        "end_time": period["endTime"],
        "daytime": period["isDaytime"],

        "temperature": {
            "value": period["temperature"],
            "unit": period["temperatureUnit"],
            "trend": period["temperatureTrend"],
        },

        "humidity": period["relativeHumidity"]["value"],

        "dewpoint_c": period["dewpoint"]["value"],

        "wind": {
            "speed": period["windSpeed"],
            "direction": period["windDirection"],
        },

        "precipitation_probability": period["probabilityOfPrecipitation"]["value"],

        "forecast": {
            "short": period["shortForecast"],
            "detailed": period["detailedForecast"],
        },

        "icon": period["icon"],
    }


def get_detailed_weather_summary(
    lat: float,
    lon: float,
    target_time: str | None = None,
):
    """
    Returns a detailed weather summary.

    Parameters
    ----------
    lat : float
    lon : float
    target_time : str | None
        ISO 8601 datetime, e.g.
        "2026-06-28T15:00:00-05:00"

        If None, returns the current forecast period.
    """

    hourly = get_hourly_forecast(lat, lon)
    return hourly_forecast_to_weather_summary(hourly, target_time)

#print(get_detailed_weather_summary(29.7604, -95.3698))


def fetch_nws_metadata_for_cell(cell_data: dict):
    """Fetch NWS point metadata for one grid-cell centroid."""
    point_data = get_point_metadata(cell_data["lat"], cell_data["lon"])
    properties = point_data["properties"]
    return {
        **cell_data,
        "nws_grid_id": properties["gridId"],
        "nws_grid_x": properties["gridX"],
        "nws_grid_y": properties["gridY"],
        "forecast_hourly": properties["forecastHourly"],
        "nws_metadata_checked_at": datetime.now(timezone.utc),
        "metadata_source": "fetched",
    }


def cached_nws_metadata_for_cell(cell):
    """Return cached NWS point metadata when the grid-cell row has a fresh mapping."""
    forecast_hourly = getattr(cell, "forecast_hourly", None)
    checked_at = getattr(cell, "nws_metadata_checked_at", None)

    if not all((
        getattr(cell, "nws_grid_id", None),
        getattr(cell, "nws_grid_x", None) is not None,
        getattr(cell, "nws_grid_y", None) is not None,
        forecast_hourly,
        checked_at,
    )):
        return None

    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) - checked_at > METADATA_CACHE_TTL:
        return None

    return {
        "grid_cell_id": cell.id,
        "cell_id": cell.cell_id,
        "lat": cell.grid_centroid_lat,
        "lon": cell.grid_centroid_lon,
        "nws_grid_id": cell.nws_grid_id,
        "nws_grid_x": cell.nws_grid_x,
        "nws_grid_y": cell.nws_grid_y,
        "forecast_hourly": forecast_hourly,
        "nws_metadata_checked_at": checked_at,
        "metadata_source": "cache",
    }


def update_cell_nws_metadata(cell_by_id: dict[int, object], metadata_rows: list[dict]):
    """Persist newly fetched NWS point metadata on grid-cell rows."""
    for metadata in metadata_rows:
        if metadata.get("metadata_source") != "fetched":
            continue

        cell = cell_by_id.get(metadata["grid_cell_id"])
        if cell is None:
            continue

        cell.nws_grid_id = metadata["nws_grid_id"]
        cell.nws_grid_x = metadata["nws_grid_x"]
        cell.nws_grid_y = metadata["nws_grid_y"]
        cell.forecast_hourly = metadata["forecast_hourly"]
        cell.nws_metadata_checked_at = metadata["nws_metadata_checked_at"]


def fetch_weather_observation_for_cell(cell_data: dict):
    """Fetch the current NWS weather data for one grid cell without using the DB session."""
    return {
        "grid_cell_id": cell_data["grid_cell_id"],
        "cell_id": cell_data["cell_id"],
        "observation_data": get_detailed_weather_summary(cell_data["lat"], cell_data["lon"]),
    }


def save_weather_observation_for_cell(cell, db):
    """Create or update the latest NWS weather row for one grid cell."""
    fetched = fetch_weather_observation_for_cell({
        "grid_cell_id": cell.id,
        "cell_id": cell.cell_id,
        "lat": cell.grid_centroid_lat,
        "lon": cell.grid_centroid_lon,
    })
    return upsert_nws_observation(fetched["grid_cell_id"], fetched["observation_data"], db)


def assign_weather_for_cells(cells, db, max_workers: int, skip_existing: bool, limit: int | None):
    """Fetch NWS data concurrently, reusing repeated forecast URLs within this run."""
    created_count = 0
    updated_count = 0
    failed = []
    skipped_existing = 0
    max_workers = max(1, min(max_workers, 12))

    if skip_existing:
        cell_ids = [cell.id for cell in cells]
        existing_cell_ids = get_existing_observation_cell_ids(cell_ids, db)
        skipped_existing = len(existing_cell_ids)
        cells = [cell for cell in cells if cell.id not in existing_cell_ids]

    if limit is not None:
        cells = cells[:max(0, limit)]

    # A full-state NWS refresh can spend several minutes outside the database.
    # Keep the already-loaded cell fields available, but release Neon before the
    # network work so its pooled SSL connection cannot go stale mid-refresh.
    db.expire_on_commit = False
    db.commit()

    cell_by_id = {cell.id: cell for cell in cells}
    cached_metadata = []
    cells_needing_metadata = []

    for cell in cells:
        metadata = cached_nws_metadata_for_cell(cell)
        if metadata:
            cached_metadata.append(metadata)
        else:
            cells_needing_metadata.append({
                "grid_cell_id": cell.id,
                "cell_id": cell.cell_id,
                "lat": cell.grid_centroid_lat,
                "lon": cell.grid_centroid_lon,
            })

    fetched_metadata = []
    metadata_workers = min(max_workers, 6)
    with ThreadPoolExecutor(max_workers=metadata_workers) as executor:
        futures = {
            executor.submit(fetch_nws_metadata_for_cell, cell): cell
            for cell in cells_needing_metadata
        }
        for future in as_completed(futures):
            cell = futures[future]
            try:
                fetched_metadata.append(future.result())
            except RequestException as exc:
                failed.append({"grid_cell_id": cell["grid_cell_id"], "cell_id": cell["cell_id"], "error": str(exc)})

    metadata_rows = cached_metadata + fetched_metadata
    update_cell_nws_metadata(cell_by_id, fetched_metadata)

    # Persist metadata and return the connection to the pool before fetching
    # forecasts. The next database operation will then check out a fresh,
    # pre-pinged connection instead of reusing an idle SSL socket.
    db.commit()

    cells_by_forecast_url = {}
    for metadata in metadata_rows:
        cells_by_forecast_url.setdefault(metadata["forecast_hourly"], []).append(metadata)

    forecast_by_url = {}
    forecast_workers = min(max_workers, 8)
    with ThreadPoolExecutor(max_workers=forecast_workers) as executor:
        futures = {
            executor.submit(get_hourly_forecast_by_url, forecast_url): forecast_url
            for forecast_url in cells_by_forecast_url
        }
        for future in as_completed(futures):
            forecast_url = futures[future]
            try:
                forecast_by_url[forecast_url] = hourly_forecast_to_weather_summary(future.result())
            except RequestException as exc:
                for cell in cells_by_forecast_url[forecast_url]:
                    failed.append({
                        "grid_cell_id": cell["grid_cell_id"],
                        "cell_id": cell["cell_id"],
                        "nws_grid": f"{cell['nws_grid_id']} {cell['nws_grid_x']},{cell['nws_grid_y']}",
                        "error": str(exc),
                    })

    # Database writes stay in this request thread because SQLAlchemy sessions are not thread-safe.
    observation_assignments = []
    for forecast_url, grouped_cells in cells_by_forecast_url.items():
        observation_data = forecast_by_url.get(forecast_url)
        if not observation_data:
            continue

        for cell in grouped_cells:
            observation_assignments.append((cell["grid_cell_id"], observation_data))

    created_count, updated_count = bulk_upsert_nws_observations(observation_assignments, db)
    db.commit()
    return {
        "created": created_count,
        "updated": updated_count,
        "skipped_existing": skipped_existing,
        "failed": len(failed),
        "failures": failed[:10],
        "count": created_count + updated_count,
        "requested": len(cells),
        "metadata_cache_hits": len(cached_metadata),
        "metadata_requests": len(cells_needing_metadata),
        "forecast_requests": len(cells_by_forecast_url),
        "db_upsert_rows": len(observation_assignments),
    }
