# %% [markdown]
# # Visitor data pipeline — Mac-local, memory-conscious version
#
# This notebook replaces the original Google Colab/Google Drive workflow.
# It is designed for this Mac (24 GB RAM) and uses DuckDB plus chunked
# PyArrow processing so the 130-million-row visits table is never loaded
# into Pandas all at once.
#
# Expected input layout:
#
# ```
# visitor_data/
# └── input/
#     ├── archive.zip
#     └── StoreVisit/
#         ├── *.parquet
#         └── ...
# ```
#
# Outputs are written to `visitor_data/output/`. Temporary spill files are
# written to `visitor_data/work/`, not Google Drive.
#
# Run the cells from top to bottom. If DuckDB is missing, first run:
#
# `%pip install duckdb`

# %%
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
import ast
import gc
import json
import shutil

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

try:
    import duckdb
except ImportError as exc:
    raise ImportError(
        "DuckDB is required. Run `%pip install duckdb`, restart the "
        "kernel if requested, and rerun this cell."
    ) from exc


PROJECT_ROOT = Path("/Users/rusli/Documents/GitHub/Rice-To-Meet-You")
DATA_ROOT = PROJECT_ROOT / "visitor_data"
INPUT_DIR = DATA_ROOT / "input"
OUTPUT_DIR = DATA_ROOT / "output"
WORK_DIR = DATA_ROOT / "work"

ARCHIVE_PATH = INPUT_DIR / "archive.zip"
STORE_VISIT_DIR = INPUT_DIR / "StoreVisit"

AGGREGATED_VISIT_FILE = OUTPUT_DIR / "store_visits_brand_market_daily.parquet"
MATCHED_VISIT_FILE = OUTPUT_DIR / "store_visits_core_poi_matched_with_average.parquet"
SPEND_LOOKUP_FILE = OUTPUT_DIR / "spend_lookup.parquet"
FINAL_FILE = OUTPUT_DIR / "store_visits_core_poi_spend_12m.parquet"

for directory in (INPUT_DIR, OUTPUT_DIR, WORK_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def sql_path(path: Path | str) -> str:
    """Return a path safely quoted for a DuckDB SQL string literal."""
    return str(path).replace("'", "''")


def connect_duckdb():
    """Create a disk-backed DuckDB connection capped below total Mac RAM."""
    database_path = WORK_DIR / "visitor_pipeline.duckdb"
    spill_path = WORK_DIR / "duckdb_spill"
    spill_path.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(database_path))
    connection.execute("SET memory_limit = '12GB'")
    connection.execute("SET threads = 4")
    connection.execute(
        f"SET temp_directory = '{sql_path(spill_path)}'"
    )
    return connection


visit_files = sorted(STORE_VISIT_DIR.glob("*.parquet"))
free_gb = shutil.disk_usage(PROJECT_ROOT).free / 1024**3

print(f"Local data directory: {DATA_ROOT}")
print(f"Free local disk: {free_gb:,.1f} GB")
print(f"Store-visit Parquet files found: {len(visit_files):,}")
print(f"Archive present: {ARCHIVE_PATH.exists()}")

if not ARCHIVE_PATH.exists():
    raise FileNotFoundError(
        f"Put archive.zip here:\n{ARCHIVE_PATH}"
    )

if not visit_files:
    raise FileNotFoundError(
        f"Put the store-visit Parquet files here:\n{STORE_VISIT_DIR}"
    )

if free_gb < 30:
    raise RuntimeError(
        "Less than 30 GB of local disk is free. Free more space or use "
        "an external SSD before running the pipeline."
    )

# %% [markdown]
# ## 1. Aggregate raw visits without loading them into Pandas
#
# DuckDB scans every Parquet file and spills to local disk when necessary.
# Unlike the original notebook, this does not create a 78 GB in-memory
# DataFrame or save an unnecessary copy of all raw visits.

# %%
visits_glob = STORE_VISIT_DIR / "*.parquet"
temporary_aggregate = AGGREGATED_VISIT_FILE.with_suffix(
    ".inprogress.parquet"
)

if temporary_aggregate.exists():
    temporary_aggregate.unlink()

con = connect_duckdb()

aggregate_sql = f"""
COPY (
    SELECT
        CAST(BRAND AS VARCHAR) AS BRAND,
        CAST(MARKET AS VARCHAR) AS MARKET,
        CAST(LOCAL_DATE AS DATE) AS LOCAL_DATE,
        SUM(TRY_CAST(DAILY_VISITS AS DOUBLE)) AS TOTAL_DAILY_VISITS,
        COUNT(*)::BIGINT AS SOURCE_ROW_COUNT
    FROM read_parquet(
        '{sql_path(visits_glob)}',
        union_by_name = true
    )
    WHERE BRAND IS NOT NULL
      AND MARKET IS NOT NULL
      AND TRY_CAST(LOCAL_DATE AS DATE) IS NOT NULL
      AND TRY_CAST(DAILY_VISITS AS DOUBLE) IS NOT NULL
    GROUP BY BRAND, MARKET, LOCAL_DATE
) TO '{sql_path(temporary_aggregate)}'
  (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
"""

con.execute(aggregate_sql)
con.close()
temporary_aggregate.replace(AGGREGATED_VISIT_FILE)

aggregate_metadata = pq.ParquetFile(AGGREGATED_VISIT_FILE)
print(
    f"Saved {aggregate_metadata.metadata.num_rows:,} aggregated rows to:\n"
    f"{AGGREGATED_VISIT_FILE}"
)

# %% [markdown]
# ## 2. Prepare branded POIs
#
# The POI table is much smaller than the visits table. Only branded POIs
# that can participate in the join are retained in memory.

# %%
CORE_TABLE = "core-poi-geometry-rice"


def normalize_text(series: pd.Series) -> pd.Series:
    result = (
        series.astype("string")
        .str.normalize("NFKC")
        .str.strip()
        .str.casefold()
        .str.replace(r"[^a-z0-9]+", "", regex=True)
    )
    return result.mask(result.eq(""))


def extract_safegraph_brand_names(value) -> list[str]:
    if pd.isna(value):
        return []

    text = str(value).strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return [text]

    names = []

    def search(obj):
        if isinstance(obj, dict):
            name = obj.get("safegraph_brand_name")
            if isinstance(name, list):
                names.extend(str(item) for item in name if pd.notna(item))
            elif pd.notna(name):
                names.append(str(name))

            for nested_value in obj.values():
                if isinstance(nested_value, (dict, list, tuple)):
                    search(nested_value)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                search(item)

    search(parsed)
    return list(dict.fromkeys(names))


core_parts = []

with ZipFile(ARCHIVE_PATH) as archive:
    core_files = sorted(
        (
            entry
            for entry in archive.infolist()
            if not entry.is_dir()
            and entry.filename.lower().endswith(".csv")
            and PurePosixPath(entry.filename).parent.name == CORE_TABLE
        ),
        key=lambda entry: entry.filename,
    )

    if not core_files:
        raise FileNotFoundError(f"No files found for {CORE_TABLE}")

    for number, entry in enumerate(core_files, start=1):
        print(f"Reading POI partition {number}/{len(core_files)}")
        with archive.open(entry) as source:
            core_parts.append(pd.read_csv(source, low_memory=False))

core_poi = pd.concat(core_parts, ignore_index=True, copy=False)
del core_parts
gc.collect()

unique_brand_values = core_poi["BRANDS"].dropna().unique()
brand_mapping = {
    value: extract_safegraph_brand_names(value)
    for value in unique_brand_values
}

core_poi["_SAFEGRAPH_BRAND_NAME"] = core_poi["BRANDS"].map(brand_mapping)
core_poi_for_join = core_poi.explode("_SAFEGRAPH_BRAND_NAME").copy()
core_poi_for_join["_brand_key"] = normalize_text(
    core_poi_for_join["_SAFEGRAPH_BRAND_NAME"]
)
core_poi_for_join["_market_key"] = normalize_text(
    core_poi_for_join["MARKET"]
)

core_poi_for_join = (
    core_poi_for_join.dropna(
        subset=["_brand_key", "_market_key", "PLACEKEY"]
    )
    .drop_duplicates(
        subset=["PLACEKEY", "_brand_key", "_market_key"],
        keep="first",
    )
    .reset_index(drop=True)
)

core_poi_for_join["CORE_POI_MATCH_COUNT"] = (
    core_poi_for_join.groupby(
        ["_brand_key", "_market_key"],
        dropna=False,
    )["PLACEKEY"]
    .transform("nunique")
    .astype("Int64")
)

print(f"Prepared branded POI rows: {len(core_poi_for_join):,}")

del core_poi, unique_brand_values, brand_mapping
gc.collect()

# %% [markdown]
# ## 3. Join visits to POIs in chunks
#
# Only matched POI rows are saved. For ambiguous brand-market matches,
# total visits are divided evenly across the matching locations.

# %%
ROWS_PER_CHUNK = 50_000
temporary_matched = MATCHED_VISIT_FILE.with_suffix(
    ".inprogress.parquet"
)

if temporary_matched.exists():
    temporary_matched.unlink()

input_parquet = pq.ParquetFile(AGGREGATED_VISIT_FILE)
total_input_rows = input_parquet.metadata.num_rows

writer = None
output_schema = None
processed_rows = 0
matched_source_rows = 0
matched_output_rows = 0
next_row_id = 0

try:
    for chunk_number, batch in enumerate(
        input_parquet.iter_batches(batch_size=ROWS_PER_CHUNK),
        start=1,
    ):
        visits = batch.to_pandas()
        chunk_rows = len(visits)

        visits["_brand_key"] = normalize_text(visits["BRAND"])
        visits["_market_key"] = normalize_text(visits["MARKET"])
        visits["_aggregate_visit_row_id"] = range(
            next_row_id, next_row_id + chunk_rows
        )
        next_row_id += chunk_rows

        joined = visits.merge(
            core_poi_for_join,
            how="left",
            on=["_brand_key", "_market_key"],
            suffixes=("_VISIT", "_CORE"),
            sort=False,
        )

        matched_mask = joined["PLACEKEY"].notna()
        matched_source_rows += joined.loc[
            matched_mask, "_aggregate_visit_row_id"
        ].nunique()

        matched = joined.loc[matched_mask].copy()
        matched["MATCHED_CORE_POI"] = True
        matched["MATCH_STATUS"] = "unique_brand_market_match"
        matched.loc[
            matched["CORE_POI_MATCH_COUNT"].gt(1),
            "MATCH_STATUS",
        ] = "ambiguous_brand_market_match"
        matched["AVERAGE_DAILY_VISITS"] = (
            pd.to_numeric(
                matched["TOTAL_DAILY_VISITS"], errors="coerce"
            )
            / pd.to_numeric(
                matched["CORE_POI_MATCH_COUNT"], errors="coerce"
            )
        )

        if not matched.empty:
            table = pa.Table.from_pandas(
                matched, preserve_index=False
            ).replace_schema_metadata(None)

            if writer is None:
                output_schema = table.schema
                writer = pq.ParquetWriter(
                    temporary_matched,
                    output_schema,
                    compression="zstd",
                )
            elif not table.schema.equals(
                output_schema, check_metadata=False
            ):
                table = table.cast(output_schema)

            writer.write_table(table)
            matched_output_rows += len(matched)

        processed_rows += chunk_rows

        if chunk_number == 1 or chunk_number % 25 == 0:
            print(
                f"Processed {processed_rows:,}/{total_input_rows:,} "
                f"aggregated rows"
            )

        del visits, joined, matched
        if "table" in locals():
            del table
        gc.collect()
finally:
    if writer is not None:
        writer.close()

if writer is None:
    raise RuntimeError("No visit rows matched the POI table.")

if processed_rows != total_input_rows:
    raise RuntimeError(
        f"Processed {processed_rows:,} of {total_input_rows:,} rows. "
        f"Incomplete output remains at {temporary_matched}"
    )

temporary_matched.replace(MATCHED_VISIT_FILE)

print(f"Matched source rows: {matched_source_rows:,}")
print(f"Matched location-date rows: {matched_output_rows:,}")
print(f"Saved matched visits to:\n{MATCHED_VISIT_FILE}")

del core_poi_for_join
gc.collect()

# %% [markdown]
# ## 4. Create an out-of-core spending lookup
#
# Spend CSV partitions are extracted to local temporary storage and converted
# directly to a compact Parquet lookup. They are not concatenated in Pandas.

# %%
SPEND_TABLE = "spend-patterns-rice"
SPEND_EXTRACT_DIR = WORK_DIR / "spend_csv"
SPEND_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

with ZipFile(ARCHIVE_PATH) as archive:
    spend_entries = sorted(
        (
            entry
            for entry in archive.infolist()
            if not entry.is_dir()
            and entry.filename.lower().endswith(".csv")
            and PurePosixPath(entry.filename).parent.name == SPEND_TABLE
        ),
        key=lambda entry: entry.filename,
    )

    if not spend_entries:
        raise FileNotFoundError(f"No files found for {SPEND_TABLE}")

    for number, entry in enumerate(spend_entries, start=1):
        destination = SPEND_EXTRACT_DIR / PurePosixPath(entry.filename).name
        if not destination.exists() or destination.stat().st_size != entry.file_size:
            print(f"Extracting spend partition {number}/{len(spend_entries)}")
            with archive.open(entry) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target, length=8 * 1024 * 1024)

spend_glob = SPEND_EXTRACT_DIR / "*.csv"
temporary_spend = SPEND_LOOKUP_FILE.with_suffix(".inprogress.parquet")

if temporary_spend.exists():
    temporary_spend.unlink()

con = connect_duckdb()

spend_sql = f"""
COPY (
    SELECT
        NULLIF(TRIM(PLACEKEY), '') AS PLACEKEY,
        TRY_CAST(SPEND_DATE_RANGE_START AS DATE)
            AS SPEND_DATE_RANGE_START,
        TRY_CAST(SPEND_DATE_RANGE_END AS DATE)
            AS SPEND_DATE_RANGE_END,
        TRY_CAST(RAW_TOTAL_SPEND AS DOUBLE)
            AS SPEND_RAW_TOTAL_SPEND,
        TRY_CAST(RAW_NUM_CUSTOMERS AS DOUBLE)
            AS SPEND_RAW_NUM_CUSTOMERS,
        TRY_CAST(RAW_NUM_TRANSACTIONS AS DOUBLE)
            AS SPEND_RAW_NUM_TRANSACTIONS,
        TRY_CAST(MEDIAN_SPEND_PER_CUSTOMER AS DOUBLE)
            AS SPEND_MEDIAN_SPEND_PER_CUSTOMER,
        TRY_CAST(MEDIAN_SPEND_PER_TRANSACTION AS DOUBLE)
            AS SPEND_MEDIAN_SPEND_PER_TRANSACTION,
        TRY_CAST(ONLINE_SPEND AS DOUBLE)
            AS SPEND_ONLINE_SPEND,
        TRY_CAST(ONLINE_TRANSACTIONS AS DOUBLE)
            AS SPEND_ONLINE_TRANSACTIONS,
        TRY_CAST(SPEND_PCT_CHANGE_VS_PREV_MONTH AS DOUBLE)
            AS SPEND_PCT_CHANGE_VS_PREV_MONTH,
        TRY_CAST(SPEND_PCT_CHANGE_VS_PREV_YEAR AS DOUBLE)
            AS SPEND_PCT_CHANGE_VS_PREV_YEAR,
        TRY_CAST(SPEND_DATE_RANGE_END AS DATE) + INTERVAL 14 DAY
            AS SPEND_AVAILABLE_DATE,
        TRY_CAST(SPEND_DATE_RANGE_END AS DATE)
            + INTERVAL 14 DAY + INTERVAL 12 MONTH
            AS SPEND_TARGET_ELIGIBLE_DATE
    FROM read_csv_auto(
        '{sql_path(spend_glob)}',
        header = true,
        union_by_name = true,
        all_varchar = true
    )
    WHERE NULLIF(TRIM(PLACEKEY), '') IS NOT NULL
      AND TRY_CAST(SPEND_DATE_RANGE_START AS DATE) IS NOT NULL
      AND TRY_CAST(SPEND_DATE_RANGE_END AS DATE) IS NOT NULL
) TO '{sql_path(temporary_spend)}'
  (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
"""

con.execute(spend_sql)

duplicate_spend_keys = con.execute(
    f"""
    SELECT COUNT(*)
    FROM (
        SELECT PLACEKEY, SPEND_TARGET_ELIGIBLE_DATE
        FROM read_parquet('{sql_path(temporary_spend)}')
        GROUP BY PLACEKEY, SPEND_TARGET_ELIGIBLE_DATE
        HAVING COUNT(*) > 1
    )
    """
).fetchone()[0]

con.close()

if duplicate_spend_keys:
    raise RuntimeError(
        f"Found {duplicate_spend_keys:,} duplicate spend lookup keys."
    )

temporary_spend.replace(SPEND_LOOKUP_FILE)
spend_rows = pq.ParquetFile(SPEND_LOOKUP_FILE).metadata.num_rows
print(f"Saved {spend_rows:,} spend rows to:\n{SPEND_LOOKUP_FILE}")

# %% [markdown]
# ## 5. Add leakage-safe spending features
#
# For each store-date row, the ASOF join selects the latest spending record
# whose publication date was already known at the one-year forecast origin.
# The row count remains unchanged.

# %%
temporary_final = FINAL_FILE.with_suffix(".inprogress.parquet")

if temporary_final.exists():
    temporary_final.unlink()

con = connect_duckdb()

final_sql = f"""
COPY (
    SELECT
        v.*,
        v.LOCAL_DATE - INTERVAL 12 MONTH AS FORECAST_ORIGIN,
        s.SPEND_MEDIAN_SPEND_PER_CUSTOMER,
        s.SPEND_MEDIAN_SPEND_PER_TRANSACTION,
        s.SPEND_ONLINE_SPEND,
        s.SPEND_ONLINE_TRANSACTIONS,
        s.SPEND_RAW_NUM_CUSTOMERS,
        s.SPEND_RAW_NUM_TRANSACTIONS,
        s.SPEND_RAW_TOTAL_SPEND,
        s.SPEND_DATE_RANGE_END,
        s.SPEND_DATE_RANGE_START,
        s.SPEND_PCT_CHANGE_VS_PREV_MONTH,
        s.SPEND_PCT_CHANGE_VS_PREV_YEAR,
        s.SPEND_AVAILABLE_DATE,
        s.SPEND_TARGET_ELIGIBLE_DATE,
        s.PLACEKEY IS NOT NULL AS MATCHED_SPEND_PATTERN,
        DATE_DIFF(
            'day',
            s.SPEND_AVAILABLE_DATE,
            v.LOCAL_DATE - INTERVAL 12 MONTH
        ) AS SPEND_DATA_AGE_DAYS
    FROM read_parquet('{sql_path(MATCHED_VISIT_FILE)}') AS v
    ASOF LEFT JOIN read_parquet('{sql_path(SPEND_LOOKUP_FILE)}') AS s
      ON v.PLACEKEY = s.PLACEKEY
     AND v.LOCAL_DATE >= s.SPEND_TARGET_ELIGIBLE_DATE
) TO '{sql_path(temporary_final)}'
  (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
"""

con.execute(final_sql)
con.close()
temporary_final.replace(FINAL_FILE)

# %% [markdown]
# ## 6. Validate and preview the final result

# %%
con = connect_duckdb()

validation = con.execute(
    f"""
    SELECT
        COUNT(*) AS total_rows,
        COUNT(DISTINCT (PLACEKEY, LOCAL_DATE)) AS unique_store_dates,
        COUNT_IF(MATCHED_SPEND_PATTERN) AS matched_spend_rows,
        ROUND(
            100.0 * COUNT_IF(MATCHED_SPEND_PATTERN) / COUNT(*),
            2
        ) AS spend_match_percentage,
        COUNT_IF(
            MATCHED_SPEND_PATTERN
            AND SPEND_AVAILABLE_DATE > FORECAST_ORIGIN
        ) AS leakage_violations
    FROM read_parquet('{sql_path(FINAL_FILE)}')
    """
).df()

sample = con.execute(
    f"""
    SELECT
        BRAND,
        MARKET_VISIT,
        LOCAL_DATE,
        PLACEKEY,
        STREET_ADDRESS,
        AVERAGE_DAILY_VISITS,
        MATCHED_SPEND_PATTERN,
        SPEND_RAW_TOTAL_SPEND
    FROM read_parquet('{sql_path(FINAL_FILE)}')
    LIMIT 10
    """
).df()

con.close()

display(validation)
display(sample)
print(f"Final table:\n{FINAL_FILE}")
