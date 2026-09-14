"""Fetch Neon usage metrics and store them for Grafana."""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import text

from app.database import engine

CONSUMPTION_URL = (
    "https://console.neon.tech/api/v2/"
    "consumption_history/v2/projects"
)

METRICS = [
    "compute_unit_seconds",
    "root_branch_bytes_month",
    "child_branch_bytes_month",
    "instant_restore_bytes_month",
    "public_network_transfer_bytes",
    "private_network_transfer_bytes",
]


def get_usage(hours):
    """gets the usage of the neon db"""
    neon_api_key = os.getenv("NEON_API_KEY")
    neon_org_id = os.getenv("NEON_ORG_ID")

    if not neon_api_key or not neon_org_id:
        raise RuntimeError(
            "NEON_API_KEY and NEON_ORG_ID must be set in .env."
        )

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)
    # send a response to the neon DB
    response = requests.get(
        CONSUMPTION_URL,
        headers={"Authorization": f"Bearer {neon_api_key}"},
        params={
            "org_id": neon_org_id,
            "from": start_time.isoformat().replace("+00:00", "Z"),
            "to": end_time.isoformat().replace("+00:00", "Z"),
            "granularity": "hourly",
            "metrics": ",".join(METRICS),
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()

def save_usage(payload: dict) -> int:
    inserted_rows = 0

    for project in payload.get("projects", []):
        for period in project.get("periods", []):
            for timeframe in period.get("consumption", []):
                timeframe_end = timeframe["timeframe_end"]

                for metric in timeframe.get("metrics", []):
                    with engine.begin() as connection:
                        connection.execute(
                            text(
                                """
                                INSERT INTO neon_usage_hourly (
                                    timeframe_end,
                                    metric_name,
                                    value
                                )
                                VALUES (
                                    :timeframe_end,
                                    :metric_name,
                                    :value
                                )
                                ON CONFLICT (timeframe_end, metric_name)
                                DO UPDATE SET value = EXCLUDED.value
                                """
                            ),
                            {
                                "timeframe_end": timeframe_end,
                                "metric_name": metric["metric_name"],
                                "value": metric["value"],
                            },
                        )

                    inserted_rows += 1

    return inserted_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="How many previous hours of usage to fetch.",
    )
    args = parser.parse_args()

    print(f"Fetching Neon usage for the last {args.hours} hours...")
    payload = get_usage(args.hours)
    #import json

    #print("Top-level keys:", list(payload.keys()))
    #print(json.dumps(payload, indent=2)[:5000])
    saved = save_usage(payload)
    print(f"Saved or updated {saved} Neon usage metric rows.")


if __name__ == "__main__":
    main()