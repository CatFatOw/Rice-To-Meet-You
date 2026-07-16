"""
Stream 2 (Visitor Activity) classical time-series comparison.

Fits SARIMA and Prophet per market on the monthly market series
train_monthly.py uses (train 2020-2023, test 2024), and runs
that script's own tree bake-off alongside it, so both land in one combined
leaderboard/CSV.

SARIMA/Prophet skip the lag-feature engineering (and its first-year-per-
market drop), modeling the raw series directly -- slightly more training
history than the tree bake-off sees.

Fit per-market rather than pooled: both are univariate, and with only 11
markets a model per market is cheap.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from prophet import Prophet
from statsmodels.tsa.statespace.sarimax import SARIMAX

from clean import RAW_PATH
from train import score
from train_monthly import (
    MARKET_KEY,
    TARGET,
    TEST_YEAR,
    bakeoff,
    build_market_month,
    chronological_split,
    load_clean,
)

COMPARISON_PATH = Path("data/visitor_monthly_classical_ts_comparison.csv")

# SARIMAX convergence warnings ("non-invertible", "maxiter reached") are
# expected noise on ~4yr monthly series with a period-12 seasonal term --
# not indicative of a broken fit, just a short series for this model class.
warnings.filterwarnings("ignore")


def load_market_series(raw: pd.DataFrame) -> pd.DataFrame:
    """Full market-month series with no lag/rolling dropna -- SARIMA/Prophet
    don't need engineered lag columns, just (market, date, y)."""
    market_month = build_market_month(raw)
    market_month["date"] = pd.to_datetime(
        dict(year=market_month["year"], month=market_month["month"], day=1)
    )
    return market_month[MARKET_KEY + ["date", "year", TARGET]].rename(columns={TARGET: "y"})


def fit_sarima_forecast(train_y: pd.Series, horizon: int) -> np.ndarray:
    model = SARIMAX(
        train_y.to_numpy(), order=(1, 1, 1), seasonal_order=(1, 1, 1, 12),
        enforce_stationarity=False, enforce_invertibility=False,
    )
    fitted = model.fit(disp=False)
    return np.clip(fitted.forecast(horizon), 0, None)


def fit_prophet_forecast(train_dates: pd.Series, train_y: pd.Series, test_dates: pd.Series) -> np.ndarray:
    df = pd.DataFrame({"ds": train_dates, "y": train_y})
    # yearly_seasonality=4 (not Prophet's default 10) -- default fourier order
    # is tuned for daily data; with only 4 yearly cycles of monthly points to
    # fit it from, a lower order avoids an overfit wiggly seasonal curve.
    model = Prophet(yearly_seasonality=4, weekly_seasonality=False, daily_seasonality=False)
    model.fit(df)
    forecast = model.predict(pd.DataFrame({"ds": test_dates}))
    return np.clip(forecast["yhat"].to_numpy(), 0, None)


def classical_ts_bakeoff(series: pd.DataFrame) -> pd.DataFrame:
    sarima_actual, sarima_pred = [], []
    prophet_actual, prophet_pred = [], []

    for market_key, group in series.groupby(MARKET_KEY):
        group = group.sort_values("date").reset_index(drop=True)
        train = group[group["year"] < TEST_YEAR]
        test = group[group["year"] == TEST_YEAR]
        if len(test) == 0 or len(train) < 24:  # need at least ~2 full seasonal cycles
            print(f"Skipping {market_key}: insufficient history (train={len(train)}, test={len(test)})")
            continue

        print(f"Fitting {market_key}: train={len(train)} months, test={len(test)} months")

        sarima_fc = fit_sarima_forecast(train["y"], len(test))
        sarima_actual.extend(test["y"].to_numpy())
        sarima_pred.extend(sarima_fc)

        prophet_fc = fit_prophet_forecast(train["date"], train["y"], test["date"])
        prophet_actual.extend(test["y"].to_numpy())
        prophet_pred.extend(prophet_fc)

    return pd.DataFrame([
        {"model": "SARIMA (per-market)", **score(np.array(sarima_actual), np.log1p(np.array(sarima_pred)))},
        {"model": "Prophet (per-market)", **score(np.array(prophet_actual), np.log1p(np.array(prophet_pred)))},
    ])


def main() -> None:
    raw = pd.read_csv(RAW_PATH, parse_dates=["time_fk"])

    print("--- Tree bake-off (monthly, market grain) ---")
    clean = load_clean()
    train, test = chronological_split(clean)
    tree_results = bakeoff(train, test)
    print(tree_results.to_string(index=False))

    print("\n--- Classical time-series models (pooled across markets, same scoring as tree bake-off) ---")
    ts_results = classical_ts_bakeoff(load_market_series(raw))
    print(ts_results.to_string(index=False))

    combined = pd.concat(
        [tree_results[["model", "MAE", "RMSE", "sMAPE", "R2"]], ts_results], ignore_index=True
    ).sort_values("MAE").reset_index(drop=True)

    print("\n--- Combined leaderboard: tree models + classical time-series (monthly, market grain) ---")
    print(combined.to_string(index=False))
    COMPARISON_PATH.parent.mkdir(exist_ok=True)
    combined.to_csv(COMPARISON_PATH, index=False)
    print(f"\nWrote combined comparison table -> {COMPARISON_PATH}")


if __name__ == "__main__":
    main()
