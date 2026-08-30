"""Routes for heatmap data retrieval."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from repository.heatmap_repository import HeatmapRepository
from schemas.simulation_schemas import SimulationRequest

router = APIRouter(prefix="/heatmap", tags=["heatmap"])


@router.get(
    "/get-heatmap-points-by-city-date",
    status_code=status.HTTP_200_OK,
)
def get_heatmap_points_by_city_date(
    city: str,
    date: str,
):
    """Return heatmap points for a city and date."""

    db = SessionLocal()
    repository = HeatmapRepository(db)
    result = repository.getDataPointsForCityAndDate(
        weather_date=date,
        market_code=city,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO HEATMAP POINTS FOUND",
        )

    return result


@router.get(
    "/get-heatmap-points-by-city-date-metric",
    status_code=status.HTTP_200_OK,
)
def get_heatmap_points_by_city_date_metric(
    city: str,
    date: str,
    metric: str,
    additional_metrics: Optional[List[str]] = Query(default=None),
):
    """Return heatmap points for a city/date, restricted to one metric."""

    db = SessionLocal()
    repository = HeatmapRepository(db)
    try:
        result = repository.getDataPointsForCityDateMetric(
            market_code=city,
            weather_date=date,
            metric=metric,
            additional_metrics=additional_metrics,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO HEATMAP POINTS FOUND",
        )

    return result


@router.get(
    "/get-local-temperature-by-city-date",
    status_code=status.HTTP_200_OK,
)
def get_local_temperature_by_city_date(
    city: str,
    date: str,
    metric: Optional[str] = None,
    additional_metrics: Optional[List[str]] = Query(default=None),
    temperature_unit: str = "f",
):
    """Return per-point local temperatures for a city and date."""

    db = SessionLocal()
    repository = HeatmapRepository(db)
    try:
        result = repository.getLocalTemperatureByCityDate(
            weather_date=date,
            metric=metric,
            market_code=city,
            additional_metrics=additional_metrics,
            temperature_unit=temperature_unit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NO LOCAL TEMPERATURE POINTS FOUND",
        )

    return result


@router.post(
    "/get-simulated-point-by-date",
    status_code=status.HTTP_200_OK,
)
def get_simulated_point_by_date(
    payload: SimulationRequest,
):
    """Run intervention simulation and return simulated heatmap points."""
    db = SessionLocal()
    repository = HeatmapRepository(db)
    print("Simulation API Reached")
    try:
        result = repository.get_simulated_points_by_date(
            metric=payload.metric,
            points_by_date=payload.points_by_date,
            placed_objects=payload.placed_objects,
            mode=payload.mode,
        )
        print("Simulation Function Called")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return result


