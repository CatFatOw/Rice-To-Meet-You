"""Open-Meteo forecast endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from schemas.open_metro_weather_schemas import OpenMeteoForecastRecordResponse, OpenMeteoForecastRequest
from services.open_metro_weather_service import (
    delete_data,
    export_forecasts_csv,
    fetch_and_add_new_data,
    get_all_data,
    get_forecast_by_id,
    get_weather_all_grid_cells,
    update_by_id,
)

router = APIRouter(prefix="/open_metro", tags=["open_metro"])


@router.get("/", response_model=list[OpenMeteoForecastRecordResponse])
async def get_all(db: Session = Depends(get_db)):
    """List saved Open-Meteo forecasts."""
    return get_all_data(db)


@router.post("/fetch", status_code=status.HTTP_201_CREATED, response_model=OpenMeteoForecastRecordResponse)
async def add_weather(payload: OpenMeteoForecastRequest, db: Session = Depends(get_db)):
    """Fetch Open-Meteo weather and persist the raw API response."""
    return fetch_and_add_new_data(payload, db)


@router.get("/export.csv", response_class=Response)
async def export_csv(
    limit: int = Query(default=150, ge=1, le=5_000),
    timeline: Literal["hourly", "daily", "current", "all"] = "hourly",
    db: Session = Depends(get_db),
):
    """Download a selected Open-Meteo timeline as CSV (hourly by default)."""
    return Response(
        content=export_forecasts_csv(limit, timeline, db),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=open_meteo_{timeline}_forecasts.csv"},
    )


@router.post(
    "/all_grid_weather",
    response_model=list[OpenMeteoForecastRecordResponse],
    status_code=status.HTTP_201_CREATED,
)
async def get_weather_all(payload: OpenMeteoForecastRequest, db: Session = Depends(get_db)):
    """Fetch and persist weather for every saved grid-cell centroid."""
    return get_weather_all_grid_cells(payload, db)


@router.get("/{forecast_id}", response_model=OpenMeteoForecastRecordResponse)
async def get_by_id(forecast_id: int, db: Session = Depends(get_db)):
    """Get a saved forecast by ID."""
    return get_forecast_by_id(forecast_id, db)


@router.put("/update/{forecast_id}", response_model=OpenMeteoForecastRecordResponse)
async def update_by_id_route(
    forecast_id: int,
    payload: OpenMeteoForecastRequest,
    db: Session = Depends(get_db),
):
    """Refresh one saved forecast."""
    return update_by_id(forecast_id, payload, db)


@router.delete("/delete/{forecast_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_by_id(forecast_id: int, db: Session = Depends(get_db)):
    """Delete one saved forecast."""
    delete_data(forecast_id, db)
