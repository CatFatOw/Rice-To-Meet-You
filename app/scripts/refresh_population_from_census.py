"""Populate grid-cell population estimates from the 2024 ACS 5-year dataset.

Each Census tract's total population (B01003_001E) is apportioned to a grid
cell by the portion of its geographic area that intersects the cell. This is a
tract-area estimate, not a live population count. The script records that
provenance on every updated metric row.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape
from sqlalchemy import create_engine, text


ACS_YEAR = 2024
# Census Reporter mirrors the public Census ACS release and provides statewide
# tract results without an API key. The official Census API now requires one
# from this network.
CENSUS_REPORTER_URL = "https://api.censusreporter.org/1.0/data/show/latest"
# Generalized Census tract boundaries are much smaller than the full TIGER
# files and are accurate enough for a city-scale grid apportionment.
TIGER_URL = f"https://www2.census.gov/geo/tiger/GENZ{ACS_YEAR}/shp/cb_{ACS_YEAR}_us_tract_500k.zip"
STATES = {"Texas": "48", "Georgia": "13"}
SOURCE_NOTE = "2024 ACS 5-year total-population estimate (B01003_001E), accessed via Census Reporter and apportioned to the grid by Census-tract area overlap."


def fetch_acs_population(state_fips: str) -> pd.DataFrame:
    response = requests.get(
        CENSUS_REPORTER_URL,
        params={
            "table_ids": "B01003",
            "geo_ids": f"140|04000US{state_fips}",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    records = [
        {
            "GEOID": geoid.removeprefix("14000US"),
            "population": values["B01003"]["estimate"].get("B01003001"),
        }
        for geoid, values in payload["data"].items()
        if "B01003" in values and "estimate" in values["B01003"]
    ]
    frame = pd.DataFrame(records)
    frame["population"] = pd.to_numeric(frame["population"], errors="coerce")
    return frame[["GEOID", "population"]].dropna()


def download_tracts(state_fips: str, temp_dir: Path) -> gpd.GeoDataFrame:
    zip_path = temp_dir / f"cb_{ACS_YEAR}_us_tract_500k.zip"
    if not zip_path.exists():
        response = requests.get(TIGER_URL, timeout=180)
        response.raise_for_status()
        zip_path.write_bytes(response.content)
    return gpd.read_file(f"zip://{zip_path}", where=f"STATEFP = '{state_fips}'")[["GEOID", "geometry"]]


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set")

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as connection:
        rows = connection.execute(text("""
            SELECT metric.id AS metric_id, cell.state, cell.geometry
            FROM grid_cell_metrics AS metric
            JOIN grid_cell_geometry AS cell ON cell.id = metric.grid_cell_id
            WHERE cell.state IN ('Texas', 'Georgia')
              AND metric.timestamp >= TIMESTAMPTZ '2026-07-14'
        """)).mappings().all()

    grids = pd.DataFrame(rows)
    grids["geometry"] = grids["geometry"].map(lambda geometry: shape(geometry))
    grid_gdf = gpd.GeoDataFrame(grids, geometry="geometry", crs="EPSG:4326").to_crs("EPSG:3857")
    updates: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="census-tracts-") as temp:
        temp_dir = Path(temp)
        for state_name, state_fips in STATES.items():
            print(f"Preparing {state_name} Census tracts...", flush=True)
            state_grids = grid_gdf[grid_gdf["state"] == state_name][["metric_id", "geometry"]]
            population = fetch_acs_population(state_fips)
            tracts = download_tracts(state_fips, temp_dir).merge(population, on="GEOID", how="inner")
            tracts = gpd.GeoDataFrame(tracts, geometry="geometry", crs="EPSG:4269").to_crs("EPSG:3857")
            tracts["tract_area_m2"] = tracts.geometry.area

            overlaps = gpd.overlay(state_grids, tracts[["population", "tract_area_m2", "geometry"]], how="intersection")
            overlaps["estimated_population"] = overlaps["population"] * overlaps.geometry.area / overlaps["tract_area_m2"]
            estimates = overlaps.groupby("metric_id", as_index=False)["estimated_population"].sum()
            estimate_by_metric = dict(zip(estimates["metric_id"], estimates["estimated_population"]))

            for metric_id in state_grids["metric_id"]:
                value = estimate_by_metric.get(metric_id)
                updates.append({
                    "metric_id": int(metric_id),
                    "population": round(float(value), 2) if value is not None else None,
                    "source": SOURCE_NOTE if value is not None else "Placeholder: no Census tract overlap was available for this grid cell.",
                    "is_placeholder": value is None,
                })

    with engine.begin() as connection:
        connection.execute(text("""
            UPDATE grid_cell_metrics
            SET population = :population,
                population_metric_source = :source,
                population_metric_is_placeholder = :is_placeholder,
                population_color = CASE WHEN :is_placeholder THEN '#94A3B8' ELSE '#A855F7' END
            WHERE id = :metric_id
        """), updates)

    real_count = sum(not update["is_placeholder"] for update in updates)
    print(f"Updated {len(updates)} grid metrics: {real_count} Census estimates, {len(updates) - real_count} placeholders.", flush=True)


if __name__ == "__main__":
    main()
