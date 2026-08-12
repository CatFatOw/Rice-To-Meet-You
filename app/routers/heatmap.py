"""Routes for heatmap data retrieval."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from repository.heatmap_repository import HeatmapRepository

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
