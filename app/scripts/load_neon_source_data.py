"""Create source-data tables and load the supplied POI, grid, and metric extracts."""

import csv
import json
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values


ROOT = Path("/Users/michaelwu/Downloads")
POI_FILE = ROOT / "core_poi_geometry.csv"
GRID_FILE = ROOT / "grid_cell_geometry.csv"
METRICS_FILE = ROOT / "grid_cell_metrics.json"

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS core_poi_geometry (
    id INTEGER PRIMARY KEY, brands JSONB, category_tags JSONB, city TEXT, closed_on DATE,
    domains JSONB, enclosed BOOLEAN, geometry_type TEXT, includes_parking_lot BOOLEAN,
    iso_country_code TEXT, is_synthetic BOOLEAN, latitude DOUBLE PRECISION, location_name TEXT,
    longitude DOUBLE PRECISION, market TEXT, naics_code INTEGER, naics_code_2022 INTEGER,
    opened_on DATE, open_hours JSONB, parent_placekey TEXT, phone_number TEXT, placekey TEXT,
    polygon_class TEXT, polygon_wkt TEXT, postal_code TEXT, region TEXT, safegraph_place_id TEXT,
    store_id TEXT, street_address TEXT, sub_category TEXT, sub_category_2022 TEXT,
    top_category TEXT, top_category_2022 TEXT, tracking_closed_since DATE, website TEXT,
    wkt_area_sq_meters DOUBLE PRECISION, created_at TIMESTAMPTZ, user_id INTEGER
);
CREATE INDEX IF NOT EXISTS ix_core_poi_geometry_city ON core_poi_geometry (city);
CREATE INDEX IF NOT EXISTS ix_core_poi_geometry_placekey ON core_poi_geometry (placekey);

CREATE TABLE IF NOT EXISTS grid_cell_geometry (
    id INTEGER PRIMARY KEY, cell_id TEXT NOT NULL UNIQUE, row INTEGER NOT NULL, col INTEGER NOT NULL,
    grid_centroid_lat DOUBLE PRECISION NOT NULL, grid_centroid_lon DOUBLE PRECISION NOT NULL,
    geometry JSONB NOT NULL, state TEXT, created_at TIMESTAMPTZ, nws_grid_id TEXT,
    nws_grid_x INTEGER, nws_grid_y INTEGER, forecast_hourly TEXT, nws_metadata_checked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_grid_cell_geometry_state ON grid_cell_geometry (state);

CREATE TABLE IF NOT EXISTS grid_cell_metrics (
    id INTEGER PRIMARY KEY, grid_cell_id INTEGER NOT NULL REFERENCES grid_cell_geometry(id) ON DELETE CASCADE,
    date DATE NOT NULL, created_at TIMESTAMPTZ, latitude DOUBLE PRECISION NOT NULL, longitude DOUBLE PRECISION NOT NULL,
    metric_source_kind TEXT NOT NULL, avg_temperature_c DOUBLE PRECISION, relative_humidity DOUBLE PRECISION,
    wind_speed_knots DOUBLE PRECISION, uhi DOUBLE PRECISION, source TEXT,
    distance_to_nearest_station_km DOUBLE PRECISION, passed_threshold BOOLEAN, market TEXT,
    source_market TEXT, fsq_place_id TEXT, placekey TEXT, name TEXT, category TEXT,
    visitor_count DOUBLE PRECISION, visitor_count_source TEXT, source_period_start TIMESTAMPTZ,
    source_period_end TIMESTAMPTZ, heat_index_color TEXT, heat_risk_color TEXT, crowd_density_color TEXT,
    population_color TEXT, cooling_centers_color TEXT, infrastructure_strain_color TEXT, overall_risk_color TEXT
);
CREATE INDEX IF NOT EXISTS ix_grid_cell_metrics_grid_date ON grid_cell_metrics (grid_cell_id, date);
CREATE INDEX IF NOT EXISTS ix_grid_cell_metrics_source_kind ON grid_cell_metrics (metric_source_kind);
"""

JSON_COLUMNS = {"brands", "category_tags", "domains", "open_hours", "geometry"}


def null(value):
    return None if value == "" else value


def load_csv(cursor, table, path):
    with path.open(newline="") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames
        rows = []
        for record in reader:
            row = []
            for column in columns:
                value = null(record[column])
                if value is not None and column in JSON_COLUMNS:
                    value = Json(json.loads(value))
                row.append(value)
            rows.append(tuple(row))
            if len(rows) == 1_000:
                execute_values(cursor, f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s", rows, page_size=1_000)
                rows.clear()
        if rows:
            execute_values(cursor, f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s", rows, page_size=1_000)


def load_metrics(cursor):
    rows = []
    columns = [
        "id", "grid_cell_id", "date", "created_at", "latitude", "longitude", "metric_source_kind",
        "avg_temperature_c", "relative_humidity", "wind_speed_knots", "uhi", "source",
        "distance_to_nearest_station_km", "passed_threshold", "market", "source_market", "fsq_place_id",
        "placekey", "name", "category", "visitor_count", "visitor_count_source", "source_period_start",
        "source_period_end", "heat_index_color", "heat_risk_color", "crowd_density_color", "population_color",
        "cooling_centers_color", "infrastructure_strain_color", "overall_risk_color",
    ]
    with METRICS_FILE.open() as source:
        for record in json.load(source):
            rows.append(tuple(record.get(column) for column in columns))
            if len(rows) == 1_000:
                execute_values(cursor, f"INSERT INTO grid_cell_metrics ({', '.join(columns)}) VALUES %s", rows, page_size=1_000)
                rows.clear()
    if rows:
        execute_values(cursor, f"INSERT INTO grid_cell_metrics ({', '.join(columns)}) VALUES %s", rows, page_size=1_000)


def main():
    database_url = os.environ["DATABASE_URL"]
    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLES)
            for table in ("grid_cell_metrics", "core_poi_geometry", "grid_cell_geometry"):
                cursor.execute(f"TRUNCATE TABLE {table} CASCADE")
            load_csv(cursor, "core_poi_geometry", POI_FILE)
            load_csv(cursor, "grid_cell_geometry", GRID_FILE)
            load_metrics(cursor)
            for table in ("core_poi_geometry", "grid_cell_geometry", "grid_cell_metrics"):
                cursor.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1), true)")
            cursor.execute("SELECT (SELECT count(*) FROM core_poi_geometry), (SELECT count(*) FROM grid_cell_geometry), (SELECT count(*) FROM grid_cell_metrics)")
            print("loaded counts:", cursor.fetchone())


if __name__ == "__main__":
    main()
