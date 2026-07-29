"""
Most Foursquare POIs can't be tied to one specific store -- a brand+market
often has several candidate locations sharing one internal visitor total,
with no address data to tell them apart (match_status ==
"exact_brand_market_ambiguous", 94% of rows). Rather than guess which store,
this attributes visitors to a nearest_heat_distance_km bucket instead, which
is all HeatSafe's crowd-density feature actually needs. Ambiguous groups
split their total across buckets in proportion to candidate count per
bucket (assumes visitors spread evenly across a brand's locations --
unverified, no ground truth to check it against). Unique-match rows already
know their bucket for certain and pass through unsplit.

Outputs:
  data/foursquare_heat_bucket_estimates.csv -- per (date, market, brand,
    heat_distance_bucket), tagged certain vs split_estimate.
  data/foursquare_heat_bucket_daily_market.csv -- summed across brands, per
    (date, market, heat_distance_bucket): the shape GridCellMetrics wants.
  data/foursquare_heat_bucket_market_wide.csv -- Dallas + Houston pooled back
    into visitor_daily_store_raw.csv's single combined "Dallas / Houston"
    (state_fk="TX") market, one column per bucket, keyed on
    (state_fk, market_fk, time_fk) so clean_visitor_daily_store.py can merge
    it straight onto the market-day history it already builds.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_PATH = Path("data/foursquare_visitor_metrics_cohesive.csv")
ESTIMATES_PATH = Path("data/foursquare_heat_bucket_estimates.csv")
DAILY_MARKET_PATH = Path("data/foursquare_heat_bucket_daily_market.csv")
MARKET_WIDE_PATH = Path("data/foursquare_heat_bucket_market_wide.csv")

GROUP_KEY = ["market", "name", "date"]

HEAT_DISTANCE_BINS = [0, 1, 2, 3, 5, float("inf")]
HEAT_DISTANCE_LABELS = ["0-1km", "1-2km", "2-3km", "3-5km", "5km+"]
# Column-name-safe versions of the labels above, for the pivoted wide table.
HEAT_DISTANCE_COLUMN_SUFFIXES = {"0-1km": "0_1km", "1-2km": "1_2km", "2-3km": "2_3km", "3-5km": "3_5km", "5km+": "5km_plus"}

# visitor_daily_store_raw.csv's market_fk/state_fk for this combined market --
# both Dallas and Houston in the Foursquare data roll up to this one raw market.
RAW_STATE_FK = "TX"
RAW_MARKET_FK = "Dallas / Houston"

UNIQUE_STATUS = "exact_brand_market_unique"
AMBIGUOUS_STATUS = "exact_brand_market_ambiguous"


def add_heat_distance_bucket(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["heat_distance_bucket"] = pd.cut(
        df["nearest_heat_distance_km"], bins=HEAT_DISTANCE_BINS, labels=HEAT_DISTANCE_LABELS, right=False
    )
    return df


def certain_estimates(df: pd.DataFrame) -> pd.DataFrame:
    unique = df[df["match_status"] == UNIQUE_STATUS].copy()
    unique["allocated_visitor_count"] = unique["visitor_count"]
    unique["n_pois_in_bucket"] = 1
    unique["n_candidates_in_group"] = 1
    unique["confidence"] = "certain"
    return unique


def split_estimates(df: pd.DataFrame) -> pd.DataFrame:
    ambiguous = df[df["match_status"] == AMBIGUOUS_STATUS].copy()

    group_sizes = ambiguous.groupby(GROUP_KEY)["fsq_place_id"].transform("size")
    bucket_sizes = ambiguous.groupby(GROUP_KEY + ["heat_distance_bucket"], observed=True)["fsq_place_id"].transform(
        "size"
    )

    ambiguous["n_candidates_in_group"] = group_sizes
    ambiguous["n_pois_in_bucket"] = bucket_sizes
    ambiguous["allocated_visitor_count"] = (
        ambiguous["market_brand_visitor_count_total"] * bucket_sizes / group_sizes
    )
    ambiguous["confidence"] = "split_estimate"

    # One row per (group, bucket) -- every POI sharing a bucket has identical values above.
    dedup_cols = GROUP_KEY + ["heat_distance_bucket"]
    return ambiguous.drop_duplicates(subset=dedup_cols)


def build_estimates(raw: pd.DataFrame) -> pd.DataFrame:
    df = add_heat_distance_bucket(raw)
    combined = pd.concat([certain_estimates(df), split_estimates(df)], ignore_index=True)
    columns = GROUP_KEY + [
        "heat_distance_bucket",
        "allocated_visitor_count",
        "n_pois_in_bucket",
        "n_candidates_in_group",
        "confidence",
    ]
    return combined[columns].sort_values(GROUP_KEY + ["heat_distance_bucket"]).reset_index(drop=True)


def build_daily_market(estimates: pd.DataFrame) -> pd.DataFrame:
    return (
        estimates.groupby(["date", "market", "heat_distance_bucket"], observed=True)
        .agg(
            allocated_visitor_count=("allocated_visitor_count", "sum"),
            n_brands=("allocated_visitor_count", "size"),
        )
        .reset_index()
        .sort_values(["date", "market", "heat_distance_bucket"])
        .reset_index(drop=True)
    )


def build_market_wide(estimates: pd.DataFrame) -> pd.DataFrame:
    pooled = estimates.groupby(["date", "heat_distance_bucket"], observed=True)["allocated_visitor_count"].sum()
    wide = pooled.unstack("heat_distance_bucket", fill_value=0.0)
    wide = wide.rename(columns=lambda bucket: f"foursquare_crowd_{HEAT_DISTANCE_COLUMN_SUFFIXES[bucket]}")
    wide["foursquare_crowd_total"] = wide.sum(axis=1)

    wide = wide.reset_index().rename(columns={"date": "time_fk"})
    wide.insert(0, "state_fk", RAW_STATE_FK)
    wide.insert(1, "market_fk", RAW_MARKET_FK)
    return wide


def main() -> None:
    raw = pd.read_csv(RAW_PATH)
    n_before = (raw["match_status"] == UNIQUE_STATUS).sum()

    estimates = build_estimates(raw)
    n_after = len(estimates)

    ESTIMATES_PATH.parent.mkdir(exist_ok=True)
    estimates.to_csv(ESTIMATES_PATH, index=False)

    daily_market = build_daily_market(estimates)
    daily_market.to_csv(DAILY_MARKET_PATH, index=False)

    market_wide = build_market_wide(estimates)
    market_wide.to_csv(MARKET_WIDE_PATH, index=False)

    print(f"Loaded {len(raw)} rows from {RAW_PATH}")
    print(f"Store-level certain rows before: {n_before} ({n_before / len(raw):.1%} of total)")
    print(f"Bucket-level estimated rows after: {n_after} ({n_after / len(raw):.1%} of total)")
    print(estimates["confidence"].value_counts())
    print(f"\nWrote {len(estimates)} rows -> {ESTIMATES_PATH}")
    print(f"Wrote {len(daily_market)} rows -> {DAILY_MARKET_PATH}")
    print(f"Wrote {len(market_wide)} rows -> {MARKET_WIDE_PATH}")


if __name__ == "__main__":
    main()
