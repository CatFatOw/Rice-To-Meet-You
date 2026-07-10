"""Google-backed POI traffic and area analytics routes."""

from fastapi import APIRouter, HTTPException, Query, status
from requests.exceptions import RequestException

from schemas.google_analytics_schemas import GooglePoiAnalyticsResponse
from services.google_analytics_service import (
    GoogleMapsConfigurationError,
    google_poi_analytics_payload,
)

router = APIRouter(prefix="/google", tags=["google"])


@router.get("/poi-analytics", response_model=GooglePoiAnalyticsResponse)
async def get_google_poi_analytics(
    venue_name: str = Query(..., min_length=1),
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    category: str | None = None,
    radius_m: int = Query(500, ge=100, le=5000),
):
    try:
        return google_poi_analytics_payload(venue_name, lat, lon, category, radius_m)
    except GoogleMapsConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except RequestException as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Google request failed: {exc}")
