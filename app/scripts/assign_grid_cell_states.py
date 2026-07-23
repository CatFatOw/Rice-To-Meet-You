"""Fill blank grid-cell states using U.S. Census cartographic boundaries."""

import os
import shutil
import urllib.request
from io import StringIO
from pathlib import Path

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text


GRID_CSV = Path("/Users/michaelwu/Downloads/grid_cell_geometry.csv")
BACKUP_CSV = GRID_CSV.with_suffix(".csv.before_state_backfill")
BOUNDARIES_ZIP = Path("/private/tmp/cb_2024_us_state_500k.zip")
BOUNDARIES_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_500k.zip"


def main():
    if not BOUNDARIES_ZIP.exists():
        urllib.request.urlretrieve(BOUNDARIES_URL, BOUNDARIES_ZIP)

    cells = pd.read_csv(GRID_CSV)
    states = gpd.read_file(f"zip://{BOUNDARIES_ZIP}").to_crs("EPSG:4326")[["NAME", "geometry"]]
    points = gpd.GeoDataFrame(
        cells[["id"]],
        geometry=gpd.points_from_xy(cells.grid_centroid_lon, cells.grid_centroid_lat),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(points, states, how="left", predicate="within")
    state_by_id = joined.groupby("id")["NAME"].first()
    cells["state"] = cells["id"].map(state_by_id).fillna("Unknown")

    if not BACKUP_CSV.exists():
        shutil.copy2(GRID_CSV, BACKUP_CSV)
    cells.to_csv(GRID_CSV, index=False)

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as connection:
        connection.execute(text("CREATE TEMP TABLE state_backfill (id INTEGER PRIMARY KEY, state TEXT NOT NULL) ON COMMIT DROP"))
        buffer = StringIO()
        cells[["id", "state"]].to_csv(buffer, index=False, header=False)
        raw = connection.connection.driver_connection
        with raw.cursor() as cursor:
            buffer.seek(0)
            cursor.copy_expert("COPY state_backfill (id, state) FROM STDIN WITH (FORMAT CSV)", buffer)
        connection.execute(text("UPDATE grid_cell_geometry g SET state = b.state FROM state_backfill b WHERE g.id = b.id"))

    print({"total": len(cells), "unknown": int((cells.state == "Unknown").sum()), "states": int(cells.state.nunique())})


if __name__ == "__main__":
    main()
