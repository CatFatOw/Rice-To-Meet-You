"""Rectangular interpolation boundaries for the FIFA 2026 host cities.

The interpolated surface is a *city* product, not a national one: readings are
kriged over one city's rectangle and drawn only inside it, so the map never
paints a value over land that city's observations say nothing about.

Each city is one axis-aligned rectangle - a centre point plus a fixed half-span
in degrees. Deliberately not a municipal outline: the rectangle is the raster
extent, so the lattice, the boundary test and the drawn image are all the same
simple shape, and every lattice cell is inside it.

Reinstated from HOST_CITY_GRID_SPECS in app/routers/front_end_routes/heatmap.py
as of commit 949912a ("Add 3D heatmap experience and local data integration",
branch codex/3d-front-end-updated-backend-migrated-db-local), which built the
same per-city rasters with the same centres and the same 0.62 degree half-span.
Centres match frontend/src/data/hostCities.ts exactly, so the city the map
selects and the city the surface covers are always the same place.
"""
from typing import Any, Optional


# Half-width and half-height of every city rectangle, in degrees. Square in
# degrees rather than in kilometres, matching the original spec: 0.62 degrees is
# about 69 km north-south everywhere, and 60 km east-west at Houston's latitude
# narrowing to 46 km at Seattle's.
HALF_SPAN_DEGREES = 0.62


# (city, state, centre latitude, centre longitude)
HOST_CITY_GRID_SPECS: tuple[tuple[str, str, float, float], ...] = (
    ("Atlanta", "Georgia", 33.7490, -84.3880),
    ("Boston", "Massachusetts", 42.3601, -71.0589),
    ("Dallas", "Texas", 32.7767, -96.7970),
    ("Houston", "Texas", 29.7604, -95.3698),
    ("Kansas City", "Missouri", 39.0997, -94.5786),
    ("Los Angeles", "California", 34.0522, -118.2437),
    ("Miami", "Florida", 25.7617, -80.1918),
    ("New York", "New York", 40.7128, -74.0060),
    ("New Jersey", "New Jersey", 40.0583, -74.4057),
    ("Philadelphia", "Pennsylvania", 39.9526, -75.1652),
    ("Seattle", "Washington", 47.6062, -122.3321),
    ("San Francisco Bay Area", "California", 37.7749, -122.4194),
)


def _rectangle(center_lat: float, center_lon: float, half_span: float):
    """[minLon, minLat, maxLon, maxLat] for a centre and a half-span."""
    return [
        center_lon - half_span,
        center_lat - half_span,
        center_lon + half_span,
        center_lat + half_span,
    ]


def bounds_to_geojson(bounds) -> dict[str, Any]:
    """A [minLon, minLat, maxLon, maxLat] rectangle as a GeoJSON Polygon.

    Wound counter-clockwise and closed, so it can be drawn directly by the map's
    boundary layer.
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


# City name -> {state, center, bounds}. Built from the specs above so the
# rectangle and the centre can never drift apart.
CITY_BOUNDARIES: dict[str, dict[str, Any]] = {
    city: {
        "state": state,
        "center": [center_lon, center_lat],
        "bounds": _rectangle(center_lat, center_lon, HALF_SPAN_DEGREES),
    }
    for city, state, center_lat, center_lon in HOST_CITY_GRID_SPECS
}


# Alternate spellings that must resolve to the same rectangle. Covers the market
# codes the heatmap repository uses, the combined New York / New Jersey market,
# and the shorter names the frontend city list carries.
CITY_ALIASES: dict[str, str] = {
    "atlanta": "Atlanta",
    "boston": "Boston",
    "dallas": "Dallas",
    "houston": "Houston",
    "kansas city": "Kansas City",
    "kansas_city": "Kansas City",
    "los angeles": "Los Angeles",
    "los_angeles": "Los Angeles",
    "miami": "Miami",
    "new york": "New York",
    "new_york": "New York",
    "new york city": "New York",
    "nyc": "New York",
    "new jersey": "New Jersey",
    "new_jersey": "New Jersey",
    "newark": "New Jersey",
    "new york/new jersey": "New York",
    "new_york_nj": "New York",
    "philadelphia": "Philadelphia",
    "seattle": "Seattle",
    "san francisco": "San Francisco Bay Area",
    "san_francisco": "San Francisco Bay Area",
    "san francisco bay area": "San Francisco Bay Area",
}


def resolve_city_name(city: str) -> Optional[str]:
    """Map any accepted spelling of a city onto its CITY_BOUNDARIES key."""
    if not city:
        return None
    if city in CITY_BOUNDARIES:
        return city
    return CITY_ALIASES.get(city.strip().lower())


def get_city_boundary(city: str) -> Optional[dict[str, Any]]:
    """Return {state, center, bounds} for a city, or None if unknown."""
    resolved = resolve_city_name(city)
    return CITY_BOUNDARIES.get(resolved) if resolved else None


def get_city_bounds(city: str) -> Optional[list[float]]:
    """Return [minLon, minLat, maxLon, maxLat] for a city, or None."""
    boundary = get_city_boundary(city)
    return list(boundary["bounds"]) if boundary else None


def get_city_boundary_geojson(city: str) -> Optional[dict[str, Any]]:
    """Return the city's rectangle as a GeoJSON Polygon, or None."""
    bounds = get_city_bounds(city)
    return bounds_to_geojson(bounds) if bounds else None


def is_inside_city(city: str, longitude: float, latitude: float) -> bool:
    """Whether a coordinate falls inside a city's rectangle (edges included)."""
    bounds = get_city_bounds(city)
    if not bounds:
        return False
    min_lon, min_lat, max_lon, max_lat = bounds
    return min_lon <= longitude <= max_lon and min_lat <= latitude <= max_lat


def supported_cities() -> list[str]:
    """Every city with a rectangle, in display order."""
    return sorted(CITY_BOUNDARIES)
