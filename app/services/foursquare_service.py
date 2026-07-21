"""Client helpers for Foursquare Places API data."""

import os
from datetime import datetime, timezone

import requests

BASE_URL = "https://places-api.foursquare.com/places/search"
API_VERSION = "2025-06-17"
REQUEST_TIMEOUT = 20


class FoursquareConfigurationError(RuntimeError):
    """Raised when the service is enabled without a server-side API key."""


def get_nearby_places(lat: float, lon: float, radius: int, limit: int) -> dict:
    """Return current POIs near a coordinate without exposing the API key to clients."""
    api_key = os.getenv("FOURSQUARE_API_KEY")
    if not api_key:
        raise FoursquareConfigurationError("FOURSQUARE_API_KEY is not configured on the server.")
    response = requests.get(
        BASE_URL,
        params={"ll": f"{lat},{lon}", "radius": radius, "sort": "DISTANCE", "limit": limit},
        headers={"Authorization": f"Bearer {api_key}", "X-Places-Api-Version": API_VERSION, "Accept": "application/json"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def foursquare_lookup_payload(lat: float, lon: float, radius: int, limit: int, requested_time=None) -> dict:
    """Adapt Foursquare's current-POI response to the app's visitor-metric contract."""
    payload = get_nearby_places(lat, lon, radius, limit)
    places = []
    for place in payload.get("results", []):
        categories = place.get("categories") or []
        location = place.get("location") or {}
        if place.get("latitude") is None or place.get("longitude") is None:
            continue
        places.append({
            "fsq_place_id": place["fsq_place_id"], "name": place["name"],
            "latitude": place["latitude"], "longitude": place["longitude"],
            "category": categories[0].get("name") if categories else None,
            "address": location.get("formatted_address"),
            "distance_m": int(place.get("distance", 0)),
            "visitor_count": None,
            "visitor_count_status": "unavailable_free_places",
        })
    return {
        "requested_time": requested_time, "latitude": lat, "longitude": lon,
        "radius_m": radius, "fetched_at": datetime.now(timezone.utc),
        "historical_visitor_counts_available": False, "place_count": len(places),
    }
