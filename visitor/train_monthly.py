"""
Stream 2 (Visitor Activity) monthly-grain forecast.

Same target (visitor_count) and same log1p/expm1 handling as
train.py, but aggregated to market-month totals instead of
store-day rows. Why try this at all: predict_future.py's daily
recursive rollout compounds error fast, because every day's lag features
depend on the *previous predicted* day, not an observed one -- forecasting
a year out would mean ~365 chained predictions. Monthly grain sidesteps
most of that (a year out is only 12 recursive steps, each one averaging
over ~30 days of noise), and visitors_lag_12 (same calendar month one year
prior) is a direct match for the thing actually driving demand here --
the annual heat-season cycle -- in a way day-of-week/day-level lag
features can only approximate.

Aggregated to market (state_fk + market_fk), not store: a store reports on
~1.4 days across all 5 years (see clean.py's module
docstring) -- nowhere near enough for even a monthly per-store series.
Markets have near-daily coverage, so market-month totals are dense.

The seasonal_naive baseline (predict this month = same month last year) is
the real bar to clear: if a model can't beat "assume this year looks like
last year," it isn't adding anything over the seasonal cycle itself.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Lasso, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from clean import RAW_PATH
from train import score

CLEAN_PATH = Path("data/visitor_monthly_market_clean.csv")
COMPARISON_PATH = Path("data/visitor_monthly_model_comparison.csv")

TARGET = "visitors_total"
TEST_YEAR = 2024  # same holdout year as train.py, for comparability

MARKET_KEY = ["state_fk", "market_fk"]
HOT_SEASON_MONTHS = {6, 7, 8}  # matches clean.py

# Only 11 markets total -- one-hot is trivial here, no need for the
# native-categorical / high-cardinality handling train.py
# needs for ~190 brand groups.
CATEGORICAL_COLUMNS = ["state_fk", "market_fk"]
NUMERIC_COLUMNS = [
    "month",
    "year",
    "is_hot_season",
    "visitors_lag_1",
    "visitors_lag_12",
    "visitors_rolling_3",
    "visitors_rolling_12",
    "stores_reporting_lag_1",
]
FEATURE_COLUMNS = CATEGORICAL_COLUMNS + NUMERIC_COLUMNS


def build_market_month(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per (state_fk, market_fk, year, month): that month's total
    visitors plus lag/rolling history built from strictly earlier months.
    All lag/rolling values are shifted by 1 month first, so none leak the
    current month's own total."""
    raw = raw.copy()
    raw["year"] = raw["time_fk"].dt.year
    raw["month"] = raw["time_fk"].dt.month

    market_month = (
        raw.groupby(MARKET_KEY + ["year", "month"])
        .agg(visitors_total=("visitor_count", "sum"), stores_reporting=("store_id_fk", "nunique"))
        .reset_index()
        .sort_values(MARKET_KEY + ["year", "month"])
    )
    market_month["is_hot_season"] = market_month["month"].isin(HOT_SEASON_MONTHS)

    visitors = market_month.groupby(MARKET_KEY)["visitors_total"]
    market_month["visitors_lag_1"] = visitors.shift(1)
    market_month["visitors_lag_12"] = visitors.shift(12)  # same calendar month, one year prior
    market_month["visitors_rolling_3"] = visitors.transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    market_month["visitors_rolling_12"] = visitors.transform(lambda s: s.shift(1).rolling(12, min_periods=1).mean())

    stores = market_month.groupby(MARKET_KEY)["stores_reporting"]
    market_month["stores_reporting_lag_1"] = stores.shift(1)

    return market_month.drop(columns=["stores_reporting"])


def load_clean(path: Path = CLEAN_PATH) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    raw = pd.read_csv(RAW_PATH, parse_dates=["time_fk"])
    clean = build_market_month(raw)
    before = len(clean)
    clean = clean.dropna(subset=NUMERIC_COLUMNS + [TARGET]).reset_index(drop=True)
    print(f"Built {before} market-months, dropped {before - len(clean)} missing lag/rolling history "
          f"(first 12 months per market, needed for visitors_lag_12)")
    path.parent.mkdir(exist_ok=True)
    clean.to_csv(path, index=False)
    print(f"Wrote market-month table -> {path}")
    return clean


def chronological_split(df: pd.DataFrame, test_year: int = TEST_YEAR) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["year"] < test_year].copy()
    test = df[df["year"] == test_year].copy()
    return train, test


def fit_baselines(train: pd.DataFrame, test: pd.DataFrame) -> list[dict]:
    rows = []

    dummy = DummyRegressor(strategy="mean").fit(train[["month"]], np.log1p(train[TARGET]))
    pred_log = dummy.predict(test[["month"]])
    rows.append({"model": "baseline_mean", **score(test[TARGET].to_numpy(), pred_log)})

    persistence = test["visitors_lag_1"].to_numpy()
    rows.append({
        "model": "baseline_persistence (last month)",
        **score(test[TARGET].to_numpy(), np.log1p(np.clip(persistence, 0, None))),
    })

    seasonal_naive = test["visitors_lag_12"].to_numpy()
    rows.append({
        "model": "baseline_seasonal_naive (same month last year)",
        **score(test[TARGET].to_numpy(), np.log1p(np.clip(seasonal_naive, 0, None))),
    })
    return rows


def encoded_pipeline(estimator) -> Pipeline:
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLUMNS),
        ("num", StandardScaler(), NUMERIC_COLUMNS),
    ])
    return Pipeline([("pre", pre), ("model", estimator)])


def bakeoff(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    y_train = np.log1p(train[TARGET].to_numpy())
    y_test = test[TARGET].to_numpy()

    models = {
        "Ridge": encoded_pipeline(Ridge(alpha=1.0, random_state=0)),
        "Lasso": encoded_pipeline(Lasso(alpha=0.001, random_state=0, max_iter=5000)),
        "RandomForest": encoded_pipeline(
            RandomForestRegressor(n_estimators=300, max_depth=8, min_samples_leaf=2, n_jobs=-1, random_state=0)
        ),
        "HistGradientBoosting": encoded_pipeline(
            HistGradientBoostingRegressor(max_iter=200, max_depth=4, random_state=0)
        ),
    }

    rows = fit_baselines(train, test)
    for name, model in models.items():
        model.fit(train[FEATURE_COLUMNS], y_train)
        test_pred_log = model.predict(test[FEATURE_COLUMNS])
        train_pred_log = model.predict(train[FEATURE_COLUMNS])
        test_scores = score(y_test, test_pred_log)
        train_scores = score(train[TARGET].to_numpy(), train_pred_log)
        rows.append({
            "model": name,
            **test_scores,
            "train_R2": train_scores["R2"],
            "overfit_gap_R2": train_scores["R2"] - test_scores["R2"],
        })

    return pd.DataFrame(rows).sort_values("MAE").reset_index(drop=True)


def main() -> None:
    df = load_clean()
    train, test = chronological_split(df)
    print(f"Train: {len(train)} market-months (2021-{TEST_YEAR - 1})  |  Test: {len(test)} market-months ({TEST_YEAR})")
    print("(2020 is dropped entirely -- visitors_lag_12 needs a full prior year of history)")

    print("\n--- Monthly model bake-off (chronological holdout) ---")
    results = bakeoff(train, test)
    print(results.to_string(index=False))
    COMPARISON_PATH.parent.mkdir(exist_ok=True)
    results.to_csv(COMPARISON_PATH, index=False)
    print(f"\nWrote comparison table -> {COMPARISON_PATH}")

    naive_mae = results.loc[results["model"].str.contains("seasonal_naive"), "MAE"].iloc[0]
    best_row = results.iloc[0]
    if best_row["model"].startswith("baseline"):
        print("\nNo model beat the baselines -- at this grain/sample size (11 markets), "
              "the seasonal cycle itself may already be most of the signal.")
    else:
        skill_vs_seasonal = (1 - best_row["MAE"] / naive_mae) * 100
        print(f"\nBest model ({best_row['model']}) beats seasonal_naive by {skill_vs_seasonal:.1f}% MAE")


if __name__ == "__main__":
    main()
