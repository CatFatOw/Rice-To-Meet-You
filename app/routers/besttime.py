"""On-demand BestTime traffic-score route for selected Foursquare POIs."""

from fastapi import APIRouter, HTTPException, Query, status
from requests.exceptions import RequestException

from schemas.besttime_schemas import BestTimeTrafficResponse
from services.besttime_service import (
    BestTimeConfigurationError,
    BestTimeUnavailableError,
    besttime_traffic_payload,
)

router = APIRouter(prefix="/besttime", tags=["besttime"])


@router.get("/traffic", response_model=BestTimeTrafficResponse)
async def get_besttime_traffic(
    venue_name: str = Query(..., min_length=1),
    venue_address: str = Query(..., min_length=1),
):
    """Return a relative live/forecast traffic score; never an absolute visitor count."""
    try:
        return besttime_traffic_payload(venue_name, venue_address)
    except BestTimeUnavailableError:
        return {
            "venue_name": venue_name,
            "venue_address": venue_address,
            "traffic_score": None,
            "forecast_traffic_score": None,
            "live_available": False,
            "score_source": "besttime_unavailable",
            "status": "unavailable",
            "best_time_label": None,
            "worst_time_label": None,
            "current_hour": None,
            "busiest_hour": None,
            "quietest_hour": None,
            "today_profile": [],
            "week_peak_windows": [],
            "data_notes": ["BestTime has no traffic forecast for this venue."],
        }
    except BestTimeConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except RequestException as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"BestTime request failed: {exc}")
