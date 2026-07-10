"""Live Foursquare POI lookup routes for the map UI."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from requests.exceptions import RequestException

from schemas.foursquare_schemas import FoursquareLookupResponse
from services.foursquare_service import FoursquareConfigurationError, foursquare_lookup_payload

router = APIRouter(prefix="/foursquare", tags=["foursquare"])


@router.get("/lookup", response_model=FoursquareLookupResponse)
async def lookup_nearby_foursquare_places(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    time: datetime | None = None,
    radius: int = Query(1000, ge=1, le=100000),
    limit: int = Query(20, ge=1, le=50),
):
    """Return current POIs for a coordinate; free Foursquare has no visit history."""
    try:
        return foursquare_lookup_payload(lat, lon, radius, limit, time)
    except FoursquareConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except RequestException as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Foursquare request failed: {exc}")
