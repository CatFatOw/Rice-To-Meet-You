"""Google Maps Platform traffic and area-insight helpers."""

import math
import os

import requests

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
AREA_INSIGHTS_URL = "https://areainsights.googleapis.com/v1:computeInsights"
REQUEST_TIMEOUT = 20


class GoogleMapsConfigurationError(RuntimeError):
    pass


def _api_key() -> str:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("VITE_GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise GoogleMapsConfigurationError("GOOGLE_MAPS_API_KEY is not configured on the server.")
    return api_key


def _duration_seconds(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and value.endswith("s"):
        try:
            return max(0, round(float(value[:-1])))
        except ValueError:
            return None
    return None


def _offset_coordinate(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    lat_delta = north_m / 111_320
    lon_delta = east_m / (111_320 * max(0.2, math.cos(math.radians(lat))))
    return lat + lat_delta, lon + lon_delta


def _traffic_status(score: int | None) -> str:
    if score is None:
        return "unavailable"
    if score < 15:
        return "light"
    if score < 35:
        return "moderate"
    if score < 65:
        return "heavy"
    return "severe"


def _category_to_google_type(category: str | None) -> str:
    if not category:
        return "point_of_interest"
    normalized = category.lower()
    if any(term in normalized for term in ["restaurant", "food", "coffee", "cafe", "bar"]):
        return "restaurant"
    if "hotel" in normalized:
        return "hotel"
    if any(term in normalized for term in ["store", "shop", "retail", "mall"]):
        return "store"
    if any(term in normalized for term in ["gallery", "museum", "attraction", "tour"]):
        return "tourist_attraction"
    if any(term in normalized for term in ["stadium", "concert", "theater", "venue"]):
        return "event_venue"
    if "park" in normalized:
        return "park"
    return "point_of_interest"


def _compute_route_sample(
    api_key: str,
    label: str,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> dict | None:
    response = requests.post(
        ROUTES_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "routes.duration,routes.staticDuration,routes.distanceMeters",
        },
        json={
            "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lon}}},
            "destination": {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lon}}},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
            "computeAlternativeRoutes": False,
            "languageCode": "en-US",
            "units": "IMPERIAL",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    routes = response.json().get("routes") or []
    if not routes:
        return None

    route = routes[0]
    duration = _duration_seconds(route.get("duration"))
    static_duration = _duration_seconds(route.get("staticDuration")) or duration
    if duration is None or static_duration is None:
        return None

    delay = max(0, duration - static_duration)
    congestion = 0 if static_duration == 0 else min(100, round((delay / static_duration) * 100))
    return {
        "label": label,
        "duration_seconds": duration,
        "static_duration_seconds": static_duration,
        "delay_seconds": delay,
        "distance_meters": route.get("distanceMeters"),
        "congestion_percent": congestion,
    }


def _nearby_place_count(api_key: str, lat: float, lon: float, category: str | None, radius_m: int) -> tuple[int | None, str, str | None]:
    google_type = _category_to_google_type(category)
    try:
        response = requests.post(
            AREA_INSIGHTS_URL,
            headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key},
            json={
                "insights": ["INSIGHT_COUNT"],
                "filter": {
                    "locationFilter": {
                        "circle": {
                            "latLng": {"latitude": lat, "longitude": lon},
                            "radius": radius_m,
                        }
                    },
                    "typeFilter": {"includedTypes": google_type},
                },
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("count"), google_type, None
    except requests.RequestException as exc:
        return None, google_type, f"Places Aggregate count unavailable: {exc}"


def google_poi_analytics_payload(
    venue_name: str,
    lat: float,
    lon: float,
    category: str | None = None,
    radius_m: int = 500,
) -> dict:
    api_key = _api_key()
    offsets = [
        ("North approach", 1000, 0),
        ("South approach", -1000, 0),
        ("East approach", 0, 1000),
        ("West approach", 0, -1000),
    ]
    samples = []
    notes = [
        "Google Places does not expose per-venue popular-times visitor counts through the standard Places Details API.",
        "Traffic score is estimated from Google Routes traffic-aware duration versus static duration around the POI.",
    ]

    for label, north_m, east_m in offsets:
        origin_lat, origin_lon = _offset_coordinate(lat, lon, north_m, east_m)
        try:
            sample = _compute_route_sample(api_key, label, origin_lat, origin_lon, lat, lon)
            if sample:
                samples.append(sample)
        except requests.RequestException as exc:
            notes.append(f"{label} unavailable: {exc}")

    traffic_score = None
    average_delay = None
    if samples:
        traffic_score = min(100, round(sum(sample["congestion_percent"] for sample in samples) / len(samples)))
        average_delay = round(sum(sample["delay_seconds"] for sample in samples) / len(samples))

    nearby_count, google_type, count_note = _nearby_place_count(api_key, lat, lon, category, radius_m)
    if count_note:
        notes.append(count_note)

    return {
        "venue_name": venue_name,
        "latitude": lat,
        "longitude": lon,
        "category": category,
        "radius_m": radius_m,
        "traffic_score": traffic_score,
        "traffic_status": _traffic_status(traffic_score),
        "average_delay_seconds": average_delay,
        "route_samples": samples,
        "nearby_place_count": nearby_count,
        "nearby_place_type": google_type,
        "visitor_analytics_available": False,
        "data_source": "google_routes_places_aggregate",
        "data_notes": notes,
    }
