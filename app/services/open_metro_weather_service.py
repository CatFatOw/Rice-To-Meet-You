"""Business logic for fetching and storing Open-Meteo forecasts."""

import csv
import io
from typing import Any

import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from repository.grid_geometry_repository import get_all_cells
from repository.open_metro_weather_repository import (
    add_value,
    delete_value,
    get_all_values,
    get_values_for_export,
    get_values_by_id,
    update_value,
)
from schemas.open_metro_weather_schemas import OpenMeteoForecastCreate, OpenMeteoForecastRequest


def get_weather_api(request: OpenMeteoForecastRequest) -> dict[str, Any]:
    """Fetch one forecast from Open-Meteo using the requested weather variables."""
    params: dict[str, Any] = {
        "latitude": request.latitude,
        "longitude": request.longitude,
        "timezone": request.timezone,
        "temperature_unit": request.temperature_unit,
        "wind_speed_unit": request.wind_speed_unit,
        "precipitation_unit": request.precipitation_unit,
    }
    for timeline in ("current", "hourly", "daily"):
        requested_variables = getattr(request, timeline)
        if requested_variables:
            params[timeline] = ",".join(requested_variables)
    if request.daily:
        params["forecast_days"] = request.forecast_days

    try:
        response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Open-Meteo forecast request failed.",
        ) from exc
    return response.json()


def get_all_data(db: Session):
    """Return every saved Open-Meteo forecast, newest first."""
    return get_all_values(db)


def export_forecasts_csv(limit: int, timeline: str, db: Session) -> str:
    """Export Open-Meteo response values as one clean row per selected time."""
    forecasts = get_values_for_export(limit, db)
    rows = [
        row
        for forecast in forecasts
        for row in _unpack_forecast_response(forecast.response_data)
        if timeline == "all" or row["timeline"] == timeline
    ]
    fields = sorted({key for row in rows for key in row})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _unpack_forecast_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Align Open-Meteo arrays by time, producing spreadsheet-friendly rows."""
    metadata = {
        key: data.get(key)
        for key in ("latitude", "longitude", "elevation", "generationtime_ms", "utc_offset_seconds", "timezone", "timezone_abbreviation")
    }
    rows = []
    for timeline_name in ("current", "hourly", "daily"):
        values = data.get(timeline_name) or {}
        units = data.get(f"{timeline_name}_units") or {}
        if timeline_name == "current" and values:
            rows.append({
                **metadata,
                "timeline": timeline_name,
                **values,
                **{f"{key}_unit": value for key, value in units.items()},
            })
            continue
        times = values.get("time") or []
        for index, value_time in enumerate(times):
            row = {**metadata, "timeline": timeline_name, "time": value_time}
            for key, series in values.items():
                if key == "time":
                    continue
                row[key] = series[index] if isinstance(series, list) and index < len(series) else series
            for key, value in units.items():
                row[f"{key}_unit"] = value
            rows.append(row)
    return rows


def get_forecast_by_id(forecast_id: int, db: Session):
    """Return one saved forecast or a consistent 404 response."""
    forecast = get_values_by_id(forecast_id, db)
    if not forecast:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FORECAST NOT FOUND")
    return forecast


def build_forecast_payload(
    request: OpenMeteoForecastRequest, weather_data: dict[str, Any]
) -> OpenMeteoForecastCreate:
    """Translate an Open-Meteo response into the persistence schema."""
    return OpenMeteoForecastCreate(
        latitude=weather_data["latitude"],
        longitude=weather_data["longitude"],
        elevation=weather_data.get("elevation"),
        timezone=weather_data.get("timezone"),
        timezone_abbreviation=weather_data.get("timezone_abbreviation"),
        utc_offset_seconds=weather_data.get("utc_offset_seconds"),
        generation_time_ms=weather_data.get("generationtime_ms"),
        response_data=weather_data,
        requested_current=request.current,
        requested_hourly=request.hourly,
        requested_daily=request.daily,
        forecast_days=request.forecast_days if request.daily else None,
    )


def fetch_and_add_new_data(request: OpenMeteoForecastRequest, db: Session):
    """Fetch a forecast and save the raw response for later use and provenance."""
    return add_value(build_forecast_payload(request, get_weather_api(request)), db)


def update_by_id(forecast_id: int, request: OpenMeteoForecastRequest, db: Session):
    """Refresh a saved forecast with a new Open-Meteo request."""
    forecast = get_forecast_by_id(forecast_id, db)
    return update_value(forecast, build_forecast_payload(request, get_weather_api(request)), db)


def delete_data(forecast_id: int, db: Session) -> None:
    """Delete a saved forecast."""
    delete_value(get_forecast_by_id(forecast_id, db), db)


def get_weather_all_grid_cells(request: OpenMeteoForecastRequest, db: Session):
    """Fetch and persist one forecast for every saved grid-cell centroid."""
    grid_cells = get_all_cells(db)
    if not grid_cells:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NO GRID CELLS FOUND")

    forecasts = []
    for cell in grid_cells:
        cell_request = request.model_copy(
            update={"latitude": cell.grid_centroid_lat, "longitude": cell.grid_centroid_lon}
        )
        forecasts.append(fetch_and_add_new_data(cell_request, db))
    return forecasts
