"""File used to handle core processing logic for grid_geometry route"""
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from shapely.geometry import shape, box

def normalize_state(state: str):
    """Keep state names stored consistently."""
    return state.strip().title()

def normalize_city(city:str):
    """Keep city names stored consistanently"""
    return city.strip().title()

def grid_cells_to_geojson(cells):
    """Convert grid cell rows into a GeoJSON FeatureCollection."""
    features = []

    for cell in cells:
        features.append({
            "type": "Feature",
            "properties": {
                "id": cell.id,
                "cell_id": cell.cell_id,
                "row": cell.row,
                "col": cell.col,
                "centroid_lat": cell.grid_centroid_lat,
                "centroid_lon": cell.grid_centroid_lon,
                "state": cell.state,
            },
            "geometry": cell.geometry,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def get_city_polygon(city: str, state: str):
    """Get a city boundary from OpenStreetMap as a GeoJSON FeatureCollection.
    
    This function gets the actual shape of the city"""
    params = {
        "q": f"{city}, {state}",
        "format": "jsonv2",
        "polygon_geojson": 1,
        "limit": 1,
    }
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params=params,
        headers={"User-Agent": "rice_heat_safe"},
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()

    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CITY NOT FOUND",
        )

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": data[0].get("display_name"),
                    "place_id": data[0].get("place_id"),
                },
                "geometry": data[0]["geojson"],
            }
        ],
    }


def get_city_bbox(city: str, state: str):
    """Get a clean bounding box around a city boundary.This function creates a box"""
    city_geojson = get_city_polygon(city, state)
    city_geometry = shape(city_geojson["features"][0]["geometry"])
    min_lon, min_lat, max_lon, max_lat = city_geometry.bounds
    bbox_geometry = box(min_lon, min_lat, max_lon, max_lat)

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": city_geojson["features"][0]["properties"],
                "geometry": bbox_geometry.__geo_interface__,
            }
        ],
    }

