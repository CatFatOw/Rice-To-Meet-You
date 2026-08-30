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
    HeatmapPointsByDate,
)
from database import SessionLocal
from repository.heatmap_repository import HeatmapRepository
from services.simulation_services import run_diminishing_return_simulation

# --------------------------------------------------------------------------- #
# 1. Metric
# --------------------------------------------------------------------------- #
metric = "average_temperature_c"

# --------------------------------------------------------------------------- #
# 2. Heatmap Point Input
# --------------------------------------------------------------------------- #
heatmap_date = "2025-07-17"

# --------------------------------------------------------------------------- #
# 3. Base Placed Object Input (Street Tree in Vegetation Archetype)
# --------------------------------------------------------------------------- #


categorized_objects: BasePlacedObjectCategorized = {
    "Evaporative / water": [],
    "High-albedo surface": [
        {
            "activeFrom": "2025-07-01T00:00:00Z",
            "activeTo": "2025-07-31T00:00:00Z",
            "category": "High-albedo surface",
            "color": "#f8fafc",
            "geometry": {
                "kind": "polygon",
                "ring": [
                    [-80.263778485, 25.804666555],
                    [-80.263763532, 25.804387455],
                    [-80.263135519, 25.80439418],
                    [-80.263169163, 25.804676643],
                    [-80.263778485, 25.804666555]
                ]
            },
            "id": "66d4483e-01a7-418f-b751-369178fae5aa",
            "market_code": "miami",
            "name": "cool_roof",
            "params": {
                "deltaAlbedo": 0.45,
                "coverPct": 0.85,
            },
            "type": "cool_roof"
        }
    ],
    "Shade structure": [],
    "Vegetation": []
}

def test_sample_simulation():
    """Run diminishing return simulation with the sample test inputs."""
    with SessionLocal() as session:
        heatmap_result = HeatmapRepository(
            session
        ).getDataPointsForCityDateMetric(
            weather_date=heatmap_date,
            metric=metric,
            market_code="miami",
        )

    points_by_date: HeatmapPointsByDate = {
        heatmap_date: heatmap_result.get(heatmap_date, []),
    }

    result = run_diminishing_return_simulation(
        metric=metric,
        points_by_date=points_by_date,
        categorized_objects=categorized_objects,
        mode="standard",
    )

    heatmap_points = []
    for source_point, simulated_point in zip(
        points_by_date[heatmap_date], result.points_by_date[heatmap_date]
    ):
        difference = source_point["value"] - simulated_point["value"]
        if difference > 0:
            heatmap_points.append({**source_point, "value": difference})

    return {
        heatmap_date: heatmap_points,
        "heatmap_points_length": len(heatmap_points),
    }


if __name__ == "__main__":
    print(test_sample_simulation())
