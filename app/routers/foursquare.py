"""Live Foursquare POI lookup routes for the map UI."""

import csv
from io import BytesIO, StringIO
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from requests.exceptions import RequestException
from starlette.responses import StreamingResponse

from schemas.foursquare_schemas import FoursquareLookupResponse
from services.foursquare_service import FoursquareConfigurationError, foursquare_lookup_payload, get_nearby_places

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


@router.post("/lookup-csv")
async def lookup_foursquare_places_from_csv(
    file: UploadFile = File(...),
    radius: int = Query(250, ge=1, le=100000),
    limit: int = Query(5, ge=1, le=50),
):
    """Look up every distinct CSV latitude/longitude pair and return POIs as CSV."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a CSV file.")
    try:
        text = (await file.read()).decode("utf-8-sig")
        reader = csv.DictReader(StringIO(text))
        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")
        latitude_key = "latitude" if "latitude" in reader.fieldnames else "lat"
        longitude_key = "longitude" if "longitude" in reader.fieldnames else "lon"
        if latitude_key not in reader.fieldnames or longitude_key not in reader.fieldnames:
            raise ValueError("CSV must include latitude/longitude or lat/lon columns.")
        coordinates = {(float(row[latitude_key]), float(row[longitude_key])) for row in reader if row.get(latitude_key) and row.get(longitude_key)}
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["query_latitude", "query_longitude", "fsq_place_id", "name", "latitude", "longitude", "category"])
    writer.writeheader()
    try:
        for latitude, longitude in sorted(coordinates):
            payload = get_nearby_places(latitude, longitude, radius, limit)
            for place in payload.get("results", []):
                categories = place.get("categories") or []
                writer.writerow({
                    "query_latitude": latitude, "query_longitude": longitude,
                    "fsq_place_id": place.get("fsq_place_id"), "name": place.get("name"),
                    "latitude": place.get("latitude"), "longitude": place.get("longitude"),
                    "category": categories[0].get("name") if categories else None,
                })
    except FoursquareConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except RequestException as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Foursquare request failed: {exc}")

    content = output.getvalue().encode("utf-8")
    return StreamingResponse(BytesIO(content), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=foursquare_lookup_results.csv"})
