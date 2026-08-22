"""Integration test for HeatmapRepository."""

import argparse
import json
from typing import Any, Dict

from database import SessionLocal
from repository.heatmap_repository import HeatmapRepository


def validate_result(result: Dict[str, Any], requested_date: str) -> None:
    """Validate the basic HeatmapPointsByDate response structure."""
    assert isinstance(result, dict), "Repository result must be a dictionary"

    if not result:
        print(
            f"No heatmap records found for {requested_date}. "
            "Check that the date and market exist in the database."
        )
        return

    assert requested_date in result, (
        f"Expected date key {requested_date!r}, "
        f"but received {list(result.keys())}"
    )

    points = result[requested_date]
    assert isinstance(points, list), "Points for a date must be a list"

    for index, point in enumerate(points):
        assert "location_coordinates" in point, (
            f"Point {index} is missing location_coordinates"
        )

        coordinates = point["location_coordinates"]
        assert isinstance(coordinates, list), (
            f"Point {index} coordinates must be a list"
        )
        assert len(coordinates) == 2, (
            f"Point {index} must contain [longitude, latitude]"
        )
        assert all(isinstance(value, (int, float)) for value in coordinates), (
            f"Point {index} contains non-numeric coordinates"
        )

        assert isinstance(point.get("individual_metrics"), dict), (
            f"Point {index} individual_metrics must be a dictionary"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Test HeatmapRepository")
    parser.add_argument(
        "--date",
        default="2020-01-01",
        help="Weather date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--market",
        default="dallas",
        help="Market code, such as dallas or houston",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=3,
        help="Number of returned points to print",
    )
    args = parser.parse_args()

    session = SessionLocal()

    try:
        repository = HeatmapRepository(session)

        result = repository.getDataPointsForCityAndDate(
            weather_date=args.date,
            market_code=args.market,
        )

        validate_result(result, args.date)

        points = result.get(args.date, [])
        print(f"Retrieved {len(points):,} points")
        print(
            json.dumps(
                {args.date: points[: args.preview]},
                indent=2,
                default=str,
            )
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()



