"""
Stream 2 (Visitor Activity) next-day forecast.

Predicts tomorrow's visitor_count -- "tomorrow" meaning the day after the
last date in data/visitor_daily_store_raw.csv -- for every store that
reported at least once in the RECENT_WINDOW_DAYS before it, using the exact
same feature pipeline as clean.py (train/serve parity)
and the current bake-off winner from train.py, refit on the
full historical dataset (no holdout -- there's no reason to hold back 2024
once you're forecasting past the end of it).

Why not a classical per-store time-series model (ARIMA / exponential
smoothing / Prophet): an individual store reports on only ~1.4 days on
average across 5 years (see clean.py's module
docstring) -- nowhere near enough history to fit a univariate model per
store. The lag/rolling features already feeding the winning tabular model
(visitors_lag_1, visitors_rolling_7/28, etc., aggregated to market level,
where daily coverage is dense) are themselves a time-series forecasting
technique -- gradient-boosted trees over engineered lag features -- and
that architecture is already validated by the existing bake-off and the
multi-city generalization study, so this reuses it rather than bolting on a
second, weaker method that the data can't actually support.

Foursquare crowd columns have no live/future source in this dataset, so
tomorrow naturally falls back to the same has_foursquare_data=False,
crowd=0 handling clean.py already uses for
out-of-coverage markets -- an honest limitation, not a bug: Foursquare
features simply won't help sharpen tomorrow's forecast the way they help
explain historical Dallas/Houston rows.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from clean import FOURSQUARE_WIDE_PATH, RAW_PATH, RELEVANT_COLUMNS, clean_daily_store
from train import (
    COMPARISON_PATH,
    FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    TARGET,
    build_model,
    native_categorical_frame,
)

PREDICTIONS_PATH = Path("data/visitor_predictions_tomorrow.csv")

# A store must have reported at least once in this window before the
# forecast date to get a forecast -- stores are far too sparse overall
# (~1.4 reporting days/5yr) to forecast for ones that haven't shown up
# recently; this is the operational stand-in for "stores we'd expect to
# possibly report tomorrow."
RECENT_WINDOW_DAYS = 90


def build_target_date_rows(raw: pd.DataFrame, target_date: pd.Timestamp) -> pd.DataFrame:
    """One synthetic row per recently-active store for target_date, with
    visitor_count left NaN (that's what we're predicting) and every other
    column copied from that store's most recent known report."""
    cutoff = target_date - pd.Timedelta(days=RECENT_WINDOW_DAYS)
    recent = raw[raw["time_fk"] > cutoff]
    latest_per_store = recent.sort_values("time_fk").groupby("store_id_fk", as_index=False).tail(1).copy()

    latest_per_store["time_fk"] = target_date
    latest_per_store["visitor_count"] = np.nan
    return latest_per_store[RELEVANT_COLUMNS]


def load_winner_name(path: Path = COMPARISON_PATH) -> str:
    """Whatever the bake-off's best model was last time train.py
    ran, by MAE (results.csv is already sorted that way)."""
    results = pd.read_csv(path)
    return results["model"].iloc[0]


def main() -> None:
    raw = pd.read_csv(RAW_PATH, parse_dates=["time_fk"])
    foursquare_wide = pd.read_csv(FOURSQUARE_WIDE_PATH, parse_dates=["time_fk"])

    target_date = raw["time_fk"].max() + pd.Timedelta(days=1)
    target_rows = build_target_date_rows(raw, target_date)
    print(
        f"Forecasting {target_date.date()} for {len(target_rows)} stores that reported at least once "
        f"in the last {RECENT_WINDOW_DAYS} days"
    )

    combined_raw = pd.concat([raw, target_rows], ignore_index=True)
    clean = clean_daily_store(combined_raw, foursquare_wide)
    clean[NUMERIC_COLUMNS] = clean[NUMERIC_COLUMNS].replace([np.inf, -np.inf], np.nan)

    history = clean[clean["time_fk"] < target_date].dropna(subset=NUMERIC_COLUMNS + [TARGET]).reset_index(drop=True)
    to_predict = clean[clean["time_fk"] == target_date].reset_index(drop=True)
    missing_history = to_predict[NUMERIC_COLUMNS].isna().any(axis=1)
    if missing_history.any():
        print(f"Dropping {missing_history.sum()} store(s) with incomplete lag/rolling history")
    to_predict = to_predict[~missing_history].reset_index(drop=True)

    winner_name = load_winner_name()
    print(f"Refitting bake-off winner ({winner_name}) on all {len(history)} historical rows")
    X_train, X_test = native_categorical_frame(history, to_predict)
    model = build_model(winner_name)
    model.fit(X_train, np.log1p(history[TARGET].to_numpy()))

    predicted = np.clip(np.expm1(model.predict(X_test)), 0, None)
    output = to_predict[["time_fk", "state_fk", "market_fk", "store_id_fk", "brand_name_fk", "category_fk"]].copy()
    output["predicted_visitor_count"] = predicted
    output = output.sort_values("predicted_visitor_count", ascending=False).reset_index(drop=True)

    PREDICTIONS_PATH.parent.mkdir(exist_ok=True)
    output.to_csv(PREDICTIONS_PATH, index=False)
    print(f"Wrote {len(output)} store forecasts -> {PREDICTIONS_PATH}")

    print("\n--- Top 10 predicted stores ---")
    print(output.head(10).to_string(index=False))

    print("\n--- Predicted market totals (sanity check) ---")
    market_totals = (
        output.groupby(["state_fk", "market_fk"])["predicted_visitor_count"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    print(market_totals.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
