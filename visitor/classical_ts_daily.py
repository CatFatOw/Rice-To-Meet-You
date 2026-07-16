"""
Stream 2 (Visitor Activity) daily-grain, bigger-dataset comparison.

Same question as classical_ts.py (can SARIMA/Prophet
compete with lag-feature tree models?), retried on ~30x more data per
market: a full daily series (train ~1461 days, test 366 days in 2024)
instead of monthly totals (train ~48 months). The monthly comparison's
SARIMA/Prophet losses were plausibly a small-sample problem -- univariate
models fit to only 48 points per market -- so this checks whether more
history per series changes the outcome.

Grain change requires two adjustments from the monthly script:
- SARIMA's native seasonal_order period=365 (annual cycle at daily grain)
  is computationally impractical for a state-space model -- the standard
  workaround (used here) is a period=7 (weekly) seasonal_order plus Fourier
  sin/cos-of-day-of-year terms passed in as exog regressors for the annual
  cycle, rather than a literal 365-length seasonal term.
- Prophet needs no such workaround -- daily data with yearly_seasonality is
  its native use case (unlike being forced onto monthly points last time).

Also runs a matching tree bake-off at the SAME market-day grain (not the
store-day grain train.py uses), so this stays apples-to-
apples: same target rows, same train/test split, same score() function.
Like every other bake-off in this project, the tree model's test
predictions use REAL historical lag values (one-step-ahead evaluation),
while SARIMA/Prophet forecast the entire 366-day test period blind from
train data alone -- a genuinely harder task. That asymmetry favors the
tree model; it isn't eliminated here, just flagged.

Some markets have real reporting gaps (Kansas City/KS is missing ~1/3 of
days) -- build_market_day() zero-fills them ("no store reported that day"),
so every market gets a complete, evenly-spaced series, which the period=7
seasonal term requires to mean anything.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from prophet import Prophet
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from statsmodels.tsa.statespace.sarimax import SARIMAX

from clean import RAW_PATH
from train import score
from train_monthly import HOT_SEASON_MONTHS, MARKET_KEY

# SARIMAX convergence warnings are expected noise, not a broken fit -- see
# classical_ts.py.
warnings.filterwarnings("ignore")

TARGET = "visitor_count"
TEST_YEAR = 2024
COMPARISON_PATH = Path("data/visitor_daily_market_classical_ts_comparison.csv")

CATEGORICAL_COLUMNS = MARKET_KEY
NUMERIC_COLUMNS = [
    "month", "year", "is_hot_season", "is_weekend", "is_federal_holiday",
    "visitors_lag_1", "visitors_lag_7", "visitors_lag_365",
    "visitors_rolling_7", "visitors_rolling_28",
]
FEATURE_COLUMNS = CATEGORICAL_COLUMNS + NUMERIC_COLUMNS


def build_market_day(raw: pd.DataFrame) -> pd.DataFrame:
    """Full daily series per market, reindexed over the complete date
    range and zero-filled where no store reported that day."""
    totals = raw.groupby(MARKET_KEY + ["time_fk"])["visitor_count"].sum()
    full_range = pd.date_range(raw["time_fk"].min(), raw["time_fk"].max(), freq="D")

    filled = []
    for market_key, series in totals.groupby(level=MARKET_KEY):
        series = series.droplevel(MARKET_KEY).reindex(full_range, fill_value=0.0)
        frame = series.rename(TARGET).rename_axis("time_fk").reset_index()
        frame[MARKET_KEY[0]] = market_key[0]
        frame[MARKET_KEY[1]] = market_key[1]
        filled.append(frame)
    return pd.concat(filled, ignore_index=True)[MARKET_KEY + ["time_fk", TARGET]]


def add_features(market_day: pd.DataFrame) -> pd.DataFrame:
    df = market_day.sort_values(MARKET_KEY + ["time_fk"]).reset_index(drop=True)
    df["month"] = df["time_fk"].dt.month
    df["year"] = df["time_fk"].dt.year
    df["is_hot_season"] = df["month"].isin(HOT_SEASON_MONTHS)
    df["is_weekend"] = df["time_fk"].dt.weekday >= 5
    holidays = USFederalHolidayCalendar().holidays(start=df["time_fk"].min(), end=df["time_fk"].max())
    df["is_federal_holiday"] = df["time_fk"].isin(holidays)

    y = df.groupby(MARKET_KEY)[TARGET]
    df["visitors_lag_1"] = y.shift(1)
    df["visitors_lag_7"] = y.shift(7)
    df["visitors_lag_365"] = y.shift(365)  # ~1yr prior -- the daily-grain seasonal-naive signal
    df["visitors_rolling_7"] = y.transform(lambda s: s.shift(1).rolling(7, min_periods=1).mean())
    df["visitors_rolling_28"] = y.transform(lambda s: s.shift(1).rolling(28, min_periods=1).mean())
    return df


def chronological_split(df: pd.DataFrame, test_year: int = TEST_YEAR) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["year"] < test_year].copy()
    test = df[df["year"] == test_year].copy()
    return train, test


def fit_baselines(train: pd.DataFrame, test: pd.DataFrame) -> list[dict]:
    rows = []
    dummy = DummyRegressor(strategy="mean").fit(train[["month"]], np.log1p(train[TARGET]))
    rows.append({"model": "baseline_mean", **score(test[TARGET].to_numpy(), dummy.predict(test[["month"]]))})

    persistence = test["visitors_lag_1"].to_numpy()
    rows.append({
        "model": "baseline_persistence (yesterday)",
        **score(test[TARGET].to_numpy(), np.log1p(np.clip(persistence, 0, None))),
    })

    seasonal_naive = test["visitors_lag_365"].to_numpy()
    rows.append({
        "model": "baseline_seasonal_naive (same day last year)",
        **score(test[TARGET].to_numpy(), np.log1p(np.clip(seasonal_naive, 0, None))),
    })
    return rows


def encoded_pipeline(estimator) -> Pipeline:
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLUMNS),
        ("num", StandardScaler(), NUMERIC_COLUMNS),
    ])
    return Pipeline([("pre", pre), ("model", estimator)])


def tree_bakeoff(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    train = train.dropna(subset=NUMERIC_COLUMNS + [TARGET])
    test = test.dropna(subset=NUMERIC_COLUMNS + [TARGET])
    y_train = np.log1p(train[TARGET].to_numpy())
    y_test = test[TARGET].to_numpy()

    models = {
        "RandomForest (daily, market grain)": encoded_pipeline(
            RandomForestRegressor(n_estimators=300, max_depth=10, min_samples_leaf=3, n_jobs=-1, random_state=0)
        ),
        "HistGradientBoosting (daily, market grain)": encoded_pipeline(
            HistGradientBoostingRegressor(max_iter=300, random_state=0)
        ),
    }
    rows = fit_baselines(train, test)
    for name, model in models.items():
        model.fit(train[FEATURE_COLUMNS], y_train)
        rows.append({"model": name, **score(y_test, model.predict(test[FEATURE_COLUMNS]))})
    return pd.DataFrame(rows)


def fourier_terms(dates: pd.DatetimeIndex, period: float = 365.25, order: int = 2) -> np.ndarray:
    """Annual-cycle exog regressors for SARIMAX -- a literal seasonal_order
    period of 365 is computationally impractical for a daily state-space
    model, so the annual cycle goes in as sin/cos harmonics instead."""
    day_of_year = np.asarray(dates.dayofyear, dtype=float)
    terms = []
    for k in range(1, order + 1):
        terms.append(np.sin(2 * np.pi * k * day_of_year / period))
        terms.append(np.cos(2 * np.pi * k * day_of_year / period))
    return np.column_stack(terms)


def fit_sarima_forecast(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    # seasonal_order D=1 combined with regular d=1 over-differences this
    # series -- the model develops a near-unit-root and its deterministic
    # forecast trend diverges over a 366-day blind horizon (verified: drifts
    # from a sane ~6k/day up to 367k/day by the end). D=0 (weekly AR/MA terms
    # carry the week-of-cycle instead of a seasonal difference) is stable.
    exog_train = fourier_terms(pd.DatetimeIndex(train["time_fk"]))
    exog_test = fourier_terms(pd.DatetimeIndex(test["time_fk"]))
    model = SARIMAX(
        train[TARGET].to_numpy(), order=(1, 1, 1), seasonal_order=(1, 0, 1, 7), exog=exog_train,
        enforce_stationarity=False, enforce_invertibility=False,
    )
    fitted = model.fit(disp=False)
    return np.clip(fitted.forecast(len(test), exog=exog_test), 0, None)


def fit_prophet_forecast(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    df = pd.DataFrame({"ds": train["time_fk"], "y": train[TARGET]})
    model = Prophet(yearly_seasonality=6, weekly_seasonality=True, daily_seasonality=False)
    model.fit(df)
    forecast = model.predict(pd.DataFrame({"ds": test["time_fk"]}))
    return np.clip(forecast["yhat"].to_numpy(), 0, None)


def classical_ts_bakeoff(market_day: pd.DataFrame) -> pd.DataFrame:
    sarima_actual, sarima_pred = [], []
    prophet_actual, prophet_pred = [], []

    for market_key, group in market_day.groupby(MARKET_KEY):
        group = group.sort_values("time_fk").reset_index(drop=True)
        train = group[group["time_fk"].dt.year < TEST_YEAR]
        test = group[group["time_fk"].dt.year == TEST_YEAR]
        print(f"Fitting {market_key}: train={len(train)} days, test={len(test)} days")

        sarima_fc = fit_sarima_forecast(train, test)
        sarima_actual.extend(test[TARGET].to_numpy())
        sarima_pred.extend(sarima_fc)

        prophet_fc = fit_prophet_forecast(train, test)
        prophet_actual.extend(test[TARGET].to_numpy())
        prophet_pred.extend(prophet_fc)

    return pd.DataFrame([
        {
            "model": "SARIMA (daily, per-market, Fourier annual + weekly seasonal)",
            **score(np.array(sarima_actual), np.log1p(np.array(sarima_pred))),
        },
        {
            "model": "Prophet (daily, per-market)",
            **score(np.array(prophet_actual), np.log1p(np.array(prophet_pred))),
        },
    ])


def main() -> None:
    raw = pd.read_csv(RAW_PATH, parse_dates=["time_fk"])
    market_day = add_features(build_market_day(raw))
    train, test = chronological_split(market_day)
    n_markets = market_day[MARKET_KEY].drop_duplicates().shape[0]
    print(f"Market-day series: train={len(train)} rows, test={len(test)} rows across {n_markets} markets")

    print("\n--- Tree bake-off (market-day grain, one-step-ahead: real lags in test) ---")
    tree_results = tree_bakeoff(train, test)
    print(tree_results.to_string(index=False))

    print("\n--- Classical time-series (market-day grain, true 366-day blind forecast) ---")
    ts_results = classical_ts_bakeoff(market_day)
    print(ts_results.to_string(index=False))

    combined = pd.concat([tree_results, ts_results], ignore_index=True).sort_values("MAE").reset_index(drop=True)
    COMPARISON_PATH.parent.mkdir(exist_ok=True)
    combined.to_csv(COMPARISON_PATH, index=False)
    print("\n--- Combined leaderboard (bigger, daily-grain dataset) ---")
    print(combined[["model", "MAE", "RMSE", "sMAPE", "R2"]].to_string(index=False))
    print(f"\nWrote -> {COMPARISON_PATH}")


if __name__ == "__main__":
    main()
