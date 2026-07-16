"""
Stream 2 (Visitor Activity) modeling.

Compares regression models predicting a single store's visitor_count on a
single day, using data/visitor_daily_store_clean.csv.

Notes:
- Target is log1p(visitor_count) -- raw counts are heavily right-skewed
  (skew ~4.9, max 28,508) with 8.1% exact zeros. Metrics convert back via
  expm1 to stay readable as visitors/day.
- store_id_fk, brand_name_fk, category_fk are excluded from the feature
  set (see NON_FEATURE_COLUMNS in clean.py);
  category_grouped / brand_name_grouped stand in for the latter two.
- Train/test split is chronological (train 2020-2023, test 2024), not
  random -- also tests whether `year` helps or risks extrapolation, see
  run_year_ablation().
- The ~0.49% of rows missing lag/rolling history are dropped, not imputed.

Models: two baselines (mean, and naive "yesterday's market-average/store"
persistence), then Ridge, Lasso, RandomForest, HistGradientBoosting,
XGBoost, LightGBM, and CatBoost.
"""

from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from catboost import CatBoostRegressor
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Lasso, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from clean import NON_FEATURE_COLUMNS

CLEAN_PATH = Path("data/visitor_daily_store_clean.csv")
COMPARISON_PATH = Path("data/visitor_model_comparison.csv")
IMPORTANCE_PATH = Path("data/visitor_model_feature_importance.csv")

TARGET = "visitor_count"
TEST_YEAR = 2024  # holdout: everything from 2024 -- see module docstring

# Models with native pandas-categorical support -- build_model() below only
# knows how to construct these; Ridge/Lasso/RandomForest need the
# encoded_pipeline/ordinal_pipeline wrapping done inline in bakeoff().
NATIVE_CATEGORICAL_MODELS = ("HistGradientBoosting", "XGBoost", "LightGBM", "CatBoost")

CATEGORICAL_COLUMNS = ["state_fk", "market_fk", "day_of_week", "category_grouped", "brand_name_grouped"]
NUMERIC_COLUMNS = [
    "is_weekend",
    "is_hot_season",
    "is_covid_period",
    "is_federal_holiday",
    "month",
    "year",
    "visitors_lag_1",
    "visitors_lag_7",
    "visitors_rolling_7",
    "visitors_rolling_28",
    "visitors_rolling_7_std",
    "visitors_pct_change_1d",
    "visitors_rolling_7_vs_28",
    "stores_reporting_lag_1",
    "stores_reporting_rolling_7",
    "stores_reporting_change_1d",
    "visitors_per_reporting_store_lag_1",
    "has_foursquare_data",
    "foursquare_crowd_0_1km",
    "foursquare_crowd_1_2km",
    "foursquare_crowd_2_3km",
    "foursquare_crowd_3_5km",
    "foursquare_crowd_5km_plus",
    "foursquare_crowd_total",
    "foursquare_crowd_share_within_1km",
    "foursquare_heat_exposure_idw",
]
FEATURE_COLUMNS = CATEGORICAL_COLUMNS + NUMERIC_COLUMNS

assert not (set(FEATURE_COLUMNS) & set(NON_FEATURE_COLUMNS)), (
    "a column flagged NON_FEATURE_COLUMNS in clean.py snuck into the feature set"
)


def load_clean(path: Path = CLEAN_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["time_fk"])
    before = len(df)
    # visitors_pct_change_1d is a pct-change ratio, so a market-day total of
    # exactly 0 two days prior (a handful of small markets on quiet days)
    # divides to +-inf rather than NaN -- fold that into the same
    # "missing lag history" bucket sklearn would otherwise choke on.
    df[NUMERIC_COLUMNS] = df[NUMERIC_COLUMNS].replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=NUMERIC_COLUMNS + [TARGET]).reset_index(drop=True)
    print(f"Loaded {before} rows, dropped {before - len(df)} with missing/infinite lag-rolling history ({path})")
    return df


def chronological_split(df: pd.DataFrame, test_year: int = TEST_YEAR) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["year"] < test_year].copy()
    test = df[df["year"] == test_year].copy()
    return train, test


def native_categorical_frame(
    train: pd.DataFrame, test: pd.DataFrame, feature_columns: list[str] = FEATURE_COLUMNS
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Feature frames for models with built-in categorical support
    (HistGradientBoosting, XGBoost, LightGBM, CatBoost): categorical
    columns become pandas `category` dtype, with test categories aligned
    to train's so an unseen 2024 value becomes a missing code instead of a
    new one the model never learned a split for."""
    X_train = train[feature_columns].copy()
    X_test = test[feature_columns].copy()
    for col in CATEGORICAL_COLUMNS:
        cats = pd.Categorical(X_train[col]).categories
        X_train[col] = pd.Categorical(X_train[col], categories=cats)
        X_test[col] = pd.Categorical(X_test[col], categories=cats)
    return X_train, X_test


def encoded_pipeline(estimator) -> Pipeline:
    """ColumnTransformer + estimator for models without native categorical
    support (Ridge, Lasso, RandomForest) -- one-hot needs scaling alongside
    it so regularization treats every feature fairly."""
    pre = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLUMNS),
            ("num", StandardScaler(), NUMERIC_COLUMNS),
        ]
    )
    return Pipeline([("pre", pre), ("model", estimator)])


def ordinal_pipeline(estimator) -> Pipeline:
    """RandomForest doesn't need scaling, and one-hot would blow up split
    search over ~440 sparse dummy columns for no benefit -- plain ordinal
    codes are the standard tree-model shortcut."""
    pre = ColumnTransformer(
        [
            ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CATEGORICAL_COLUMNS),
            ("num", "passthrough", NUMERIC_COLUMNS),
        ]
    )
    return Pipeline([("pre", pre), ("model", estimator)])


def smape(actual: np.ndarray, predicted: np.ndarray) -> float:
    denom = np.abs(actual) + np.abs(predicted)
    ratio = np.where(denom == 0, 0.0, 2 * np.abs(actual - predicted) / np.where(denom == 0, 1, denom))
    return float(np.mean(ratio)) * 100


def score(actual: np.ndarray, predicted_log: np.ndarray) -> dict:
    predicted = np.clip(np.expm1(predicted_log), 0, None)  # visitor counts can't be negative
    resid = actual - predicted
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((actual - actual.mean()) ** 2))
    return {
        "MAE": float(np.mean(np.abs(resid))),
        "RMSE": float(np.sqrt(np.mean(resid**2))),
        "sMAPE": smape(actual, predicted),
        "R2": 1 - ss_res / ss_tot,
    }


def fit_baselines(train: pd.DataFrame, test: pd.DataFrame) -> list[dict]:
    rows = []

    dummy = DummyRegressor(strategy="mean").fit(train[["month"]], np.log1p(train[TARGET]))
    pred_log = dummy.predict(test[["month"]])
    rows.append({"model": "baseline_mean", **score(test[TARGET].to_numpy(), pred_log)})

    persistence_pred = test["visitors_per_reporting_store_lag_1"].to_numpy()
    rows.append({
        "model": "baseline_persistence (yesterday's market avg/store)",
        **score(test[TARGET].to_numpy(), np.log1p(np.clip(persistence_pred, 0, None))),
    })
    return rows


def bakeoff(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    y_train = np.log1p(train[TARGET].to_numpy())
    y_test = test[TARGET].to_numpy()

    X_train_native, X_test_native = native_categorical_frame(train, test)

    models = {
        "Ridge": encoded_pipeline(Ridge(alpha=1.0, random_state=0)),
        "Lasso": encoded_pipeline(Lasso(alpha=0.001, random_state=0, max_iter=5000)),
        "RandomForest": ordinal_pipeline(
            RandomForestRegressor(n_estimators=300, max_depth=14, min_samples_leaf=5, n_jobs=-1, random_state=0)
        ),
        "HistGradientBoosting": HistGradientBoostingRegressor(
            categorical_features="from_dtype", max_iter=400, random_state=0
        ),
        "XGBoost": xgb.XGBRegressor(
            n_estimators=400, max_depth=6, learning_rate=0.05, tree_method="hist",
            enable_categorical=True, random_state=0,
        ),
        "LightGBM": lgb.LGBMRegressor(n_estimators=400, max_depth=-1, learning_rate=0.05, random_state=0, verbosity=-1),
        "CatBoost": CatBoostRegressor(
            iterations=400, depth=8, learning_rate=0.05, cat_features=CATEGORICAL_COLUMNS,
            random_state=0, verbose=False,
        ),
    }

    rows = fit_baselines(train, test)
    fitted = {}
    for name, model in models.items():
        if name in NATIVE_CATEGORICAL_MODELS:
            model.fit(X_train_native, y_train)
            train_pred_log = model.predict(X_train_native)
            test_pred_log = model.predict(X_test_native)
        else:
            model.fit(train[FEATURE_COLUMNS], y_train)
            train_pred_log = model.predict(train[FEATURE_COLUMNS])
            test_pred_log = model.predict(test[FEATURE_COLUMNS])

        fitted[name] = model
        test_scores = score(y_test, test_pred_log)
        train_scores = score(train[TARGET].to_numpy(), train_pred_log)
        rows.append({
            "model": name,
            **test_scores,
            "train_R2": train_scores["R2"],
            "overfit_gap_R2": train_scores["R2"] - test_scores["R2"],
        })

    results = pd.DataFrame(rows).sort_values("MAE").reset_index(drop=True)
    return results, fitted


def build_model(name: str):
    """Fresh estimator with the bake-off's hyperparameters -- year ablation,
    walk-forward, and predict_tomorrow.py all need their own
    freshly-fit copy of the winning model type."""
    if name == "XGBoost":
        return xgb.XGBRegressor(n_estimators=400, max_depth=6, learning_rate=0.05,
                                 tree_method="hist", enable_categorical=True, random_state=0)
    if name == "LightGBM":
        return lgb.LGBMRegressor(n_estimators=400, learning_rate=0.05, random_state=0, verbosity=-1)
    if name == "CatBoost":
        return CatBoostRegressor(iterations=400, depth=8, learning_rate=0.05,
                                  cat_features=CATEGORICAL_COLUMNS, random_state=0, verbose=False)
    if name == "HistGradientBoosting":
        return HistGradientBoostingRegressor(categorical_features="from_dtype", max_iter=400, random_state=0)
    raise ValueError(f"no native-categorical builder for {name!r} -- one of {NATIVE_CATEGORICAL_MODELS}")


def run_year_ablation(train: pd.DataFrame, test: pd.DataFrame, winner_name: str) -> pd.DataFrame:
    """Direct test of the extrapolation concern flagged for `year` in
    clean.py: refit the winning model type with and
    without `year` in the feature set and compare test-set accuracy. The
    2024 holdout is exactly the "unseen year" case a live forecast would
    face, so this isn't a synthetic check."""
    cols_with_year = FEATURE_COLUMNS
    cols_without_year = [c for c in FEATURE_COLUMNS if c != "year"]
    y_train = np.log1p(train[TARGET].to_numpy())
    y_test = test[TARGET].to_numpy()

    rows = []
    for label, cols in [("with_year", cols_with_year), ("without_year", cols_without_year)]:
        X_train, X_test = native_categorical_frame(train, test, feature_columns=cols)
        model = build_model(winner_name)
        model.fit(X_train, y_train)
        rows.append({"variant": label, **score(y_test, model.predict(X_test))})
    return pd.DataFrame(rows)


def run_walk_forward(df: pd.DataFrame, winner_name: str) -> pd.DataFrame:
    """Repeats the holdout at earlier year boundaries (train <2022 -> test
    2022, train <2023 -> test 2023, train <2024 -> test 2024) so the
    headline result isn't just one lucky split -- same walk-forward
    discipline visitor_activity.py already uses for its own backtests."""
    rows = []
    for test_year in (2022, 2023, 2024):
        train, test = chronological_split(df, test_year=test_year)
        X_train, X_test = native_categorical_frame(train, test)
        model = build_model(winner_name)
        model.fit(X_train, np.log1p(train[TARGET].to_numpy()))
        s = score(test[TARGET].to_numpy(), model.predict(X_test))
        rows.append({"test_year": test_year, "n_train": len(train), "n_test": len(test), **s})
    return pd.DataFrame(rows)


def feature_importance(model, name: str) -> pd.DataFrame:
    if name == "CatBoost":
        imp = model.get_feature_importance()
        names = FEATURE_COLUMNS
    elif hasattr(model, "feature_importances_"):
        imp = model.feature_importances_
        names = FEATURE_COLUMNS
    else:
        return pd.DataFrame(columns=["feature", "importance"])
    return (
        pd.DataFrame({"feature": names, "importance": imp})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


def main() -> None:
    df = load_clean()
    train, test = chronological_split(df)
    print(f"Train: {len(train)} rows (2020-{TEST_YEAR - 1})  |  Test: {len(test)} rows ({TEST_YEAR})")

    print("\n--- Model bake-off (chronological holdout, metrics on raw visitor_count scale) ---")
    results, fitted = bakeoff(train, test)
    print(results.to_string(index=False))
    COMPARISON_PATH.parent.mkdir(exist_ok=True)
    results.to_csv(COMPARISON_PATH, index=False)
    print(f"\nWrote comparison table -> {COMPARISON_PATH}")

    trained_names = [n for n in results["model"] if n in fitted]
    winner_name = trained_names[0]
    winner = fitted[winner_name]
    print(f"\nBest model by test MAE: {winner_name}")

    print(f"\n--- Feature importance: {winner_name} ---")
    importance = feature_importance(winner, winner_name)
    if not importance.empty:
        print(importance.head(15).to_string(index=False))
        importance.to_csv(IMPORTANCE_PATH, index=False)
        print(f"Wrote feature importance -> {IMPORTANCE_PATH}")

    if winner_name in NATIVE_CATEGORICAL_MODELS:
        print(f"\n--- year ablation on {winner_name} (does the model need `year` to generalize to 2024?) ---")
        ablation = run_year_ablation(train, test, winner_name)
        print(ablation.to_string(index=False))

        print(f"\n--- walk-forward stability of {winner_name} (train <Y, test Y, for Y in 2022/2023/2024) ---")
        walk_forward = run_walk_forward(df, winner_name)
        print(walk_forward.to_string(index=False))
    else:
        print(f"\n(skipping year ablation / walk-forward -- {winner_name} isn't one of the native-categorical models)")


if __name__ == "__main__":
    main()
