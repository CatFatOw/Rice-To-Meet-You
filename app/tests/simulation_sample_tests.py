"""Sample test inputs and simulation execution for urban heat interventions."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the `app` root directory is on sys.path when running directly from `app/tests/`
APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from schemas.simulation_schemas import (
    BasePlacedObject,
    BasePlacedObjectCategorized,
    HeatmapMetricValue,
    HeatmapPointsByDate,
)
from services.simulation_services import run_diminishing_return_simulation

# --------------------------------------------------------------------------- #
# 1. Metric
# --------------------------------------------------------------------------- #
metric = "average_temperature_c"

# --------------------------------------------------------------------------- #
# 2. Heatmap Point Input
# --------------------------------------------------------------------------- #
heatmap_point: HeatmapMetricValue = {
    "value": 26.7246,
    "location_coordinates": (-80.34555866666666, 25.740390333333334),
    "individual_metrics": {
        "average_relative_humidity_pct": "82.9%",
        "average_wind_speed_knots": "5.2 mph",
        "precipitation_3d_sum_mm": "522 in",
        "average_temperature_c": "38°C",
    },
}

points_by_date: HeatmapPointsByDate = {
    "2025-07-17": [heatmap_point],
}

# --------------------------------------------------------------------------- #
# 3. Base Placed Object Input (Street Tree in Vegetation Archetype)
# --------------------------------------------------------------------------- #
placed_object: BasePlacedObject = {
    "id": "street-tree-1",
    "name": "Street Tree",
    "type": "street_tree",
    "category": "Vegetation",
    "color": "#22c55e",
    "market_code": "miami",
    "geometry": {
        "kind": "polygon",
        "ring": [
            (-80.349491, 25.746351),
            (-80.349181, 25.736851),
            (-80.338004, 25.737969),
            (-80.349491, 25.746351),
        ],
    },
    "params": {
        "canopyRadius_m": 5.0,
        "canopyHeight_m": 8.0,
        "lai": 4.0,
        "coverPct": 0.4,
        "irrigation": 0.6,
    },
    "activeFrom": "2024-12-31",
    "activeTo": "2025-01-10",
}

placed_object_2: BasePlacedObject = {
    "id": "street-tree-2",
    "name": "Street Tree",
    "type": "street_tree",
    "category": "Vegetation",
    "color": "#22c55e",
    "market_code": "miami",
    "geometry": {
        "kind": "polygon",
        "ring": [
            (-80.349200, 25.744100),
            (-80.341500, 25.743400),
            (-80.340900, 25.738000),
            (-80.346000, 25.736800),
            (-80.350100, 25.739500),
            (-80.349200, 25.744100),
        ],
    },
    "params": {
        "canopyRadius_m": 5.0,
        "canopyHeight_m": 8.0,
        "lai": 4.0,
        "coverPct": 0.4,
        "irrigation": 0.6,
    },
    "activeFrom": "2024-12-31",
    "activeTo": "2025-01-10",
}

placed_object_3: BasePlacedObject = {
    "id": "cool-roof-1",
    "name": "Cool Roof",
    "type": "cool_roof",
    "category": "High-albedo surface",
    "color": "#38bdf8",
    "market_code": "miami",
    "geometry": {
        "kind": "polygon",
        "ring": [
            (-80.349200, 25.744100),
            (-80.341500, 25.743400),
            (-80.340900, 25.738000),
            (-80.346000, 25.736800),
            (-80.350100, 25.739500),
            (-80.349200, 25.744100),
        ],
    },
    "params": {
        "albedo": 0.65,
        "deltaAlbedo": 0.45,
        "emissivity": 0.9,
        "coverPct": 0.85,
    },
    "activeFrom": "2024-12-31",
    "activeTo": "2025-01-10",
}

placed_object_4: BasePlacedObject = {
    "id": "cool-roof-2",
    "name": "Cool Roof",
    "type": "cool_roof",
    "category": "High-albedo surface",
    "color": "#38bdf8",
    "market_code": "miami",
    "geometry": {
        "kind": "polygon",
        "ring": [
            (-80.345500, 25.742000),
            (-80.342800, 25.741600),
            (-80.342900, 25.739000),
            (-80.345450, 25.738900),
            (-80.345500, 25.742000),
        ],
    },
    "params": {
        "albedo": 0.65,
        "deltaAlbedo": 0.45,
        "emissivity": 0.9,
        "coverPct": 0.85,
    },
    "activeFrom": "2024-12-31",
    "activeTo": "2025-01-10",
}

placed_object_5: BasePlacedObject = {
    "id": "misting-station-1",
    "name": "Misting Station",
    "type": "misting_station",
    "category": "Evaporative / water",
    "color": "#06b6d4",
    "market_code": "miami",
    "geometry": {
        "kind": "point",
        "longitude": -80.34555866666666,
        "latitude": 25.740399316333334,
    },
    "params": {
        "evapRateLpm": 3.0,
        "coverageRadiusM": 50.0,
        "activeFraction": 1.0,
    },
    "activeFrom": "2024-12-31",
    "activeTo": "2025-01-10",
}

categorized_objects: BasePlacedObjectCategorized = {'Vegetation': [], 'High-albedo surface': [{'id': '4d687ab1-cac3-43fb-a4f4-5d1c10e1003d', 'type': 'cool_roof', 'name': 'cool_roof', 'color': '#f8fafc', 'category': 'High-albedo surface', 'market_code': 'atlanta', 'geometry': {'kind': 'polygon', 'ring': [[-84.396384037, 33.789141641], [-84.396319531, 33.788713108], [-84.395457491, 33.788737457], [-84.395475083, 33.789248773], [-84.396384037, 33.789141641]]}, 'params': {'albedo': 0.65, 'emissivity': 0.9}, 'activeFrom': '2025-07-15T00:00:00Z', 'activeTo': '2025-07-18T00:00:00Z'}], 'Shade structure': [], 'Evaporative / water': []}


def test_sample_simulation():
    """Run diminishing return simulation with the sample test inputs."""
    result = run_diminishing_return_simulation(
        metric=metric,
        points_by_date=points_by_date,
        categorized_objects=categorized_objects,
        mode="standard",
    )
    print("Simulation result:", result)
    return result


if __name__ == "__main__":
    test_sample_simulation()
