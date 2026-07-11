"""
Cleans data/visitor_daily_store_raw.csv down to the columns with real
visitor-activity signal, adds calendar + market-level history features,
merges in Foursquare heat-exposure crowd density, and writes the result to
data/visitor_daily_store_clean.csv.

Dropped: source_row_id (internal DB id) and the time_state*_fk columns
(pipe-joined concatenations of columns already kept -- reconstructable via
string concat if ever needed, nothing reads them as-is).

Market-level history (visitors_lag_*, visitors_rolling_*,
stores_reporting_*) is aggregated to state_fk+market_fk, not store_id_fk:
an individual store reports on only ~1.4 days on average across 5 years,
too sparse to trail on its own, while a market has near-daily coverage. All
lag/rolling values are shifted by 1 first, so none leak the current day's
own total.

category_grouped / brand_name_grouped fold rare values into "Other"
(thresholds: MIN_CATEGORY_GROUP_COUNT / MIN_BRAND_GROUP_COUNT) because
store_id_fk, brand_name_fk, and category_fk are too high-cardinality to
one-hot/target-encode directly -- most values appear in only a handful of
rows, so raw encodings would just memorize individual rows instead of
learning a real pattern. Brand's threshold is also capped by
HistGradientBoostingRegressor's 255-category-per-feature limit downstream.
store_id_fk itself is left un-bucketed (kept only for joining/grouping --
see NON_FEATURE_COLUMNS for what a training script should drop).

Foursquare crowd density by heat-sensor distance (foursquare_crowd_0_1km
... foursquare_crowd_total, has_foursquare_data; from
bucket_foursquare_heat_exposure.py, run that first) only covers the
"Dallas / Houston" market -- 0 elsewhere, flagged via has_foursquare_data
rather than left NaN so it doesn't get dropped by a training script's
dropna.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

RAW_PATH = Path("data/visitor_daily_store_raw.csv")
CLEAN_PATH = Path("data/visitor_daily_store_clean.csv")

# Produced by bucket_foursquare_heat_exposure.py -- run that first. Only
# covers the "Dallas / Houston" market (state_fk="TX"); every other
# market/date gets 0 via the fillna in merge_foursquare_crowd_density below,
# flagged by has_foursquare_data so a model can tell "0 coverage" from
# "0 crowd".
FOURSQUARE_WIDE_PATH = Path("data/foursquare_heat_bucket_market_wide.csv")
FOURSQUARE_CROWD_COLUMNS = [
    "foursquare_crowd_0_1km",
    "foursquare_crowd_1_2km",
    "foursquare_crowd_2_3km",
    "foursquare_crowd_3_5km",
    "foursquare_crowd_5km_plus",
    "foursquare_crowd_total",
]

HOT_SEASON_MONTHS = {6, 7, 8}  # June, July, August -- matches visitor_activity.py
COVID_PERIOD_START = pd.Timestamp("2020-03-01")  # US national emergency declared 2020-03-13
COVID_PERIOD_END = pd.Timestamp("2022-12-30")  # approx. widespread reopening / vaccine rollout (edited)

RELEVANT_COLUMNS = [
    "time_fk",
    "state_fk",
    "market_fk",
    "store_id_fk",
    "brand_name_fk",
    "category_fk",
    "visitor_count",
]

MARKET_KEY = ["state_fk", "market_fk"]
ROLLING_WINDOWS = (7, 28)

# Below this many rows, a category/brand value gets folded into "Other" in
# the *_grouped columns -- see "Overfitting guardrails" in the module
# docstring for how these thresholds were picked.
MIN_CATEGORY_GROUP_COUNT = 100
# 50 kept 355 brand groups, which is fine for most models but breaks
# sklearn's HistGradientBoostingRegressor (hard cap of 255 categories per
# feature) -- 100 keeps 190 groups (56.8% of rows keep their own brand
# label, the rest fold into "Other"), safely under that limit.
MIN_BRAND_GROUP_COUNT = 100

# Kept in the output for joining/grouping/traceability, but too sparse to
# feed a model directly -- see "Overfitting guardrails" above. A training
# script should do something like:
#   X = clean.drop(columns=NON_FEATURE_COLUMNS + ["time_fk", "visitor_count"])
NON_FEATURE_COLUMNS = ["store_id_fk", "brand_name_fk", "category_fk"]


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["day_of_week"] = df["time_fk"].dt.day_name()
    df["is_weekend"] = df["time_fk"].dt.weekday >= 5
    df["month"] = df["time_fk"].dt.month
    df["year"] = df["time_fk"].dt.year
    df["is_hot_season"] = df["month"].isin(HOT_SEASON_MONTHS)
    df["is_covid_period"] = df["time_fk"].between(COVID_PERIOD_START, COVID_PERIOD_END)

    holidays = USFederalHolidayCalendar().holidays(start=df["time_fk"].min(), end=df["time_fk"].max())
    df["is_federal_holiday"] = df["time_fk"].isin(holidays)
    return df


def bucket_rare_values(series: pd.Series, min_count: int) -> pd.Series:
    """Folds values that appear fewer than min_count times into "Other", so
    a one-hot/target-encoded version of this column doesn't end up with
    columns backed by only a handful of rows -- the classic
    high-cardinality-categorical overfitting trap (see module docstring)."""
    counts = series.value_counts()
    rare_values = counts[counts < min_count].index
    return series.where(~series.isin(rare_values), "Other")


def build_market_history(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per (state_fk, market_fk, time_fk) carrying that day's
    market-level lag/rolling features, all built from days strictly
    before it."""
    market_day = (
        raw.groupby(MARKET_KEY + ["time_fk"])
        .agg(visitors_total=("visitor_count", "sum"), stores_reporting=("store_id_fk", "nunique"))
        .reset_index()
        .sort_values(MARKET_KEY + ["time_fk"])
    )

    visitors = market_day.groupby(MARKET_KEY)["visitors_total"]
    visitors_lag_2 = visitors.shift(2)  # only used to build visitors_pct_change_1d below
    market_day["visitors_lag_1"] = visitors.shift(1)
    market_day["visitors_lag_7"] = visitors.shift(7)
    for window in ROLLING_WINDOWS:
        market_day[f"visitors_rolling_{window}"] = visitors.transform(
            lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean()
        )
    market_day["visitors_rolling_7_std"] = visitors.transform(
        lambda s: s.shift(1).rolling(7, min_periods=1).std()
    )
    # Change between the two most recent known days (t-2 -> t-1) -- the most
    # recent 1-day momentum available without looking at today's own total.
    market_day["visitors_pct_change_1d"] = (market_day["visitors_lag_1"] - visitors_lag_2) / visitors_lag_2
    market_day["visitors_rolling_7_vs_28"] = (
        market_day["visitors_rolling_7"] / market_day["visitors_rolling_28"]
    )

    stores = market_day.groupby(MARKET_KEY)["stores_reporting"]
    stores_lag_2 = stores.shift(2)
    market_day["stores_reporting_lag_1"] = stores.shift(1)
    market_day["stores_reporting_rolling_7"] = stores.transform(
        lambda s: s.shift(1).rolling(7, min_periods=1).mean()
    )
    market_day["stores_reporting_change_1d"] = market_day["stores_reporting_lag_1"] - stores_lag_2

    market_day["visitors_per_reporting_store_lag_1"] = (
        market_day["visitors_lag_1"] / market_day["stores_reporting_lag_1"]
    )

    return market_day.drop(columns=["visitors_total", "stores_reporting"])


def merge_foursquare_crowd_density(clean: pd.DataFrame, foursquare_wide: pd.DataFrame) -> pd.DataFrame:
    clean = clean.merge(foursquare_wide, on=MARKET_KEY + ["time_fk"], how="left")
    clean["has_foursquare_data"] = clean["foursquare_crowd_total"].notna()
    clean[FOURSQUARE_CROWD_COLUMNS] = clean[FOURSQUARE_CROWD_COLUMNS].fillna(0.0)
    return clean


def clean_daily_store(raw: pd.DataFrame, foursquare_wide: pd.DataFrame) -> pd.DataFrame:
    clean = raw[RELEVANT_COLUMNS].copy()
    clean = add_calendar_features(clean)
    clean["category_grouped"] = bucket_rare_values(clean["category_fk"], MIN_CATEGORY_GROUP_COUNT)
    clean["brand_name_grouped"] = bucket_rare_values(clean["brand_name_fk"], MIN_BRAND_GROUP_COUNT)
    clean = clean.merge(build_market_history(raw), on=MARKET_KEY + ["time_fk"], how="left")
    clean = merge_foursquare_crowd_density(clean, foursquare_wide)
    return clean.sort_values(["market_fk", "time_fk", "store_id_fk"]).reset_index(drop=True)


def main() -> None:
    raw = pd.read_csv(RAW_PATH, parse_dates=["time_fk"])
    foursquare_wide = pd.read_csv(FOURSQUARE_WIDE_PATH, parse_dates=["time_fk"])
    clean = clean_daily_store(raw, foursquare_wide)

    dropped = [c for c in raw.columns if c not in RELEVANT_COLUMNS]
    added = [c for c in clean.columns if c not in RELEVANT_COLUMNS]
    clean.to_csv(CLEAN_PATH, index=False)

    print(f"Loaded {len(raw)} rows, {len(raw.columns)} columns from {RAW_PATH}")
    print(f"Dropped columns: {dropped}")
    print(f"Added columns:   {added}")
    print(f"Wrote {len(clean)} rows, {len(clean.columns)} columns -> {CLEAN_PATH}")


if __name__ == "__main__":
    main()
