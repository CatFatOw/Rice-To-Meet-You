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

Also folds in Foursquare heat exposure (crowd density near the store) as an
extra SARIMA/Prophet exog column and tree-model feature -- real signal only
for Dallas/Houston (~0.78 correlated with that market's visitor_count), a
constant 0 everywhere else (see clean.py's has_foursquare_data).

Three more additions ported over from Time_series_Analysis_fixed.ipynb's
exploratory work on this same Dallas/Houston series:
- weekday_dummies() gives SARIMA explicit day-of-week flags instead of
  leaning entirely on its seasonal_order=7 term to carry the weekly rhythm.
- fit_sarima_rolling_forecast() scores SARIMA one-step-ahead (predict a
  day, reveal its real actual, predict the next) instead of only the fully
  blind 366-day forecast above -- added as an EXTRA leaderboard row, not a
  replacement, since it's a genuinely easier task (real lags every day,
  like the tree models already get) and conflating the two would hide that
  the comparison isn't apples-to-apples anymore. See the new "evaluation"
  column on the combined leaderboard for which protocol scored which row.
- quantile_interval() adds P10/P50/P90 gradient-boosted quantile
  regression -- QUANTILE_MODEL_NAME's P50 slots into the main leaderboard
  like any other point forecast; the full interval doesn't fit that
  single-number shape, so it's written to its own CSV.

This is now the single home for Stream 2 model comparisons -- it absorbed
train.py's store-day bakeoff/month-ahead-forecast and
train_monthly.py's market-month bakeoff, both retired since they
tested different grains of the same question. run_month_ahead_comparison()
(ported from train.py) reuses this file's market-day features and
TREE_MODEL_BUILDERS rather than a separate model list, so there's one set
of candidates instead of three. predict_future.py (per-store recursive
forecasting) was retired too -- it depended on train.py's store-day model,
which no longer exists; this file only ever modeled at market grain.
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
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from statsmodels.tsa.statespace.sarimax import SARIMAX

from clean import HOT_SEASON_MONTHS

# SARIMAX convergence warnings are expected noise, not a broken fit -- see
# classical_ts.py.
warnings.filterwarnings("ignore")

TARGET = "visitor_count"
TEST_YEAR = 2024
CLEAN_PATH = Path("data/visitor_daily_store_clean.csv")
COMPARISON_PATH = Path("data/visitor_daily_market_classical_ts_comparison.csv")
FUTURE_HORIZON_DAYS = 7
FUTURE_PREDICTIONS_PATH = Path("data/visitor_daily_market_future_predictions.csv")
QUANTILE_MODEL_NAME = "GradientBoosting (quantile P50, daily, market grain)"
QUANTILE_INTERVAL_PATH = Path("data/visitor_daily_market_quantile_forecast.csv")
MONTH_BASELINES = ("baseline_trailing_7", "baseline_seasonal_365")
MONTH_COMPARISON_PATH = Path("data/visitor_month_ahead_model_comparison.csv")
MONTH_BACKTEST_PATH = Path("data/visitor_month_ahead_backtest_predictions.csv")
NEXT_MONTH_PATH = Path("data/visitor_next_month_predictions.csv")

# Restricted to Dallas/Houston for now -- other markets have visitor data
# too, add their market_fk values back here later.
MARKETS = ["Dallas / Houston"]

MARKET_KEY = ["state_fk", "market_fk"]
CATEGORICAL_COLUMNS = MARKET_KEY
NUMERIC_COLUMNS = [
    "month", "year", "day_of_month", "is_hot_season", "is_weekend", "is_federal_holiday",
    "visitors_lag_1", "visitors_lag_7", "visitors_lag_28", "visitors_lag_365",
    "visitors_rolling_7", "visitors_rolling_28",
    "foursquare_heat_exposure_idw",
]
FEATURE_COLUMNS = CATEGORICAL_COLUMNS + NUMERIC_COLUMNS


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


def build_market_day(clean: pd.DataFrame) -> pd.DataFrame:
    """Full daily series per market, reindexed over the complete date
    range and zero-filled where no store reported that day. Heat exposure
    reindexes to 0 the same way -- consistent with "no data" everywhere
    outside Dallas/Houston already meaning 0 in the source clean table."""
    totals = clean.groupby(MARKET_KEY + ["time_fk"]).agg(
        **{
            TARGET: (TARGET, "sum"),
            "foursquare_heat_exposure_idw": ("foursquare_heat_exposure_idw", "first"),
        }
    )
    full_range = pd.date_range(clean["time_fk"].min(), clean["time_fk"].max(), freq="D")

    filled = []
    for market_key, group in totals.groupby(level=MARKET_KEY):
        group = group.droplevel(MARKET_KEY).reindex(full_range, fill_value=0.0)
        frame = group.rename_axis("time_fk").reset_index()
        frame[MARKET_KEY[0]] = market_key[0]
        frame[MARKET_KEY[1]] = market_key[1]
        filled.append(frame)
    return pd.concat(filled, ignore_index=True)[
        MARKET_KEY + ["time_fk", TARGET, "foursquare_heat_exposure_idw"]
    ]


def add_features(market_day: pd.DataFrame) -> pd.DataFrame:
    df = market_day.sort_values(MARKET_KEY + ["time_fk"]).reset_index(drop=True)
    df["month"] = df["time_fk"].dt.month
    df["year"] = df["time_fk"].dt.year
    df["day_of_month"] = df["time_fk"].dt.day
    df["is_hot_season"] = df["month"].isin(HOT_SEASON_MONTHS)
    df["is_weekend"] = df["time_fk"].dt.weekday >= 5
    holidays = USFederalHolidayCalendar().holidays(start=df["time_fk"].min(), end=df["time_fk"].max())
    df["is_federal_holiday"] = df["time_fk"].isin(holidays)

    y = df.groupby(MARKET_KEY)[TARGET]
    df["visitors_lag_1"] = y.shift(1)
    df["visitors_lag_7"] = y.shift(7)
    df["visitors_lag_28"] = y.shift(28)  # month-ahead recursive forecast needs this lag
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
    rows.append({
        "model": "baseline_mean", "evaluation": "one-step-ahead",
        **score(test[TARGET].to_numpy(), dummy.predict(test[["month"]])),
    })

    persistence = test["visitors_lag_1"].to_numpy()
    rows.append({
        "model": "baseline_persistence (yesterday)", "evaluation": "one-step-ahead",
        **score(test[TARGET].to_numpy(), np.log1p(np.clip(persistence, 0, None))),
    })

    seasonal_naive = test["visitors_lag_365"].to_numpy()
    rows.append({
        "model": "baseline_seasonal_naive (same day last year)", "evaluation": "one-step-ahead",
        **score(test[TARGET].to_numpy(), np.log1p(np.clip(seasonal_naive, 0, None))),
    })
    return rows


def encoded_pipeline(estimator) -> Pipeline:
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLUMNS),
        ("num", StandardScaler(), NUMERIC_COLUMNS),
    ])
    return Pipeline([("pre", pre), ("model", estimator)])


def quantile_gb(alpha: float) -> GradientBoostingRegressor:
    return GradientBoostingRegressor(
        loss="quantile", alpha=alpha, n_estimators=300, learning_rate=0.03,
        max_depth=3, min_samples_leaf=10, random_state=0,
    )


# Shared by tree_bakeoff and forecast_future_tree, so the future-forecast
# path always uses the exact estimator the bake-off scored, not a
# hand-copied duplicate of its hyperparameters. QUANTILE_MODEL_NAME's P50
# (the conditional median) is a legitimate point forecast alongside the
# other two -- its P10/P90 companions live in quantile_interval() instead,
# since they don't fit this dict's "one estimator -> one point forecast"
# shape.
TREE_MODEL_BUILDERS = {
    "RandomForest (daily, market grain)": lambda: RandomForestRegressor(
        n_estimators=300, max_depth=10, min_samples_leaf=3, n_jobs=-1, random_state=0
    ),
    "HistGradientBoosting (daily, market grain)": lambda: HistGradientBoostingRegressor(
        max_iter=300, random_state=0
    ),
    QUANTILE_MODEL_NAME: lambda: quantile_gb(0.50),
}


def tree_bakeoff(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    train = train.dropna(subset=NUMERIC_COLUMNS + [TARGET])
    test = test.dropna(subset=NUMERIC_COLUMNS + [TARGET])
    y_train = np.log1p(train[TARGET].to_numpy())
    y_test = test[TARGET].to_numpy()

    rows = fit_baselines(train, test)
    for name, build in TREE_MODEL_BUILDERS.items():
        model = encoded_pipeline(build())
        model.fit(train[FEATURE_COLUMNS], y_train)
        rows.append({"model": name, "evaluation": "one-step-ahead", **score(y_test, model.predict(test[FEATURE_COLUMNS]))})
    return pd.DataFrame(rows)


def quantile_interval(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """P10/P50/P90 interval alongside the point forecast tree_bakeoff
    already scores (QUANTILE_MODEL_NAME's P50) -- refits P50 here too
    rather than threading the fitted pipeline out of tree_bakeoff, to keep
    both functions simple and independent. Same one-step-ahead evaluation
    as the rest of tree_bakeoff: real lag/rolling values in test, not
    predicted ones.
    """
    train = train.dropna(subset=NUMERIC_COLUMNS + [TARGET])
    test = test.dropna(subset=NUMERIC_COLUMNS + [TARGET])
    y_train = np.log1p(train[TARGET].to_numpy())

    preds = {}
    for alpha in (0.10, 0.50, 0.90):
        pipeline = encoded_pipeline(quantile_gb(alpha))
        pipeline.fit(train[FEATURE_COLUMNS], y_train)
        preds[alpha] = np.expm1(pipeline.predict(test[FEATURE_COLUMNS]))

    # Independently fitted quantiles can cross -- sort each row so
    # p10 <= p50 <= p90 before reporting the interval.
    ordered = np.sort(np.column_stack([preds[0.10], preds[0.50], preds[0.90]]), axis=1)
    interval = test[MARKET_KEY + ["time_fk"]].reset_index(drop=True).copy()
    interval["p10"], interval["p50"], interval["p90"] = ordered[:, 0], ordered[:, 1], ordered[:, 2]

    actual = test[TARGET].to_numpy()
    coverage = ((actual >= interval["p10"].to_numpy()) & (actual <= interval["p90"].to_numpy())).mean()
    print(f"Quantile P10-P90 coverage: {coverage:.1%} (target: ~80%)")
    return interval


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


def weekday_dummies(dates: pd.DatetimeIndex) -> np.ndarray:
    """Explicit day-of-week exog columns (Tuesday..Sunday; Monday is the
    reference level dropped to avoid collinearity with the intercept) --
    lets SARIMA anchor to the weekly rhythm directly instead of leaning
    entirely on its seasonal_order=7 term to carry it."""
    dummies = pd.get_dummies(dates.dayofweek, dtype=float)
    dummies = dummies.reindex(columns=range(1, 7), fill_value=0.0)
    return dummies.to_numpy()


def sarima_exog(dates: pd.DatetimeIndex, heat: np.ndarray) -> np.ndarray:
    return np.column_stack([fourier_terms(dates), weekday_dummies(dates), heat])


def fit_sarima_forecast(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    # seasonal_order D=1 combined with regular d=1 over-differences this
    # series -- the model develops a near-unit-root and its deterministic
    # forecast trend diverges over a 366-day blind horizon (verified: drifts
    # from a sane ~6k/day up to 367k/day by the end). D=0 (weekly AR/MA terms
    # carry the week-of-cycle instead of a seasonal difference) is stable.
    #
    # Heat exposure rides along as an exog column next to the Fourier terms
    # and weekday dummies. test's heat values are real 2024 Foursquare
    # readings, not a forecast of them -- a fair backtest only to the extent
    # that reading would be available in near-real-time operationally,
    # unlike the Fourier/weekday columns (always knowable ahead of time from
    # the calendar alone).
    exog_train = sarima_exog(pd.DatetimeIndex(train["time_fk"]), train["foursquare_heat_exposure_idw"].to_numpy())
    exog_test = sarima_exog(pd.DatetimeIndex(test["time_fk"]), test["foursquare_heat_exposure_idw"].to_numpy())
    model = SARIMAX(
        train[TARGET].to_numpy(), order=(1, 1, 1), seasonal_order=(1, 0, 1, 7), exog=exog_train,
        enforce_stationarity=False, enforce_invertibility=False,
    )
    fitted = model.fit(disp=False)
    return np.clip(fitted.forecast(len(test), exog=exog_test), 0, None)


def fit_sarima_rolling_forecast(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """One-step-ahead rolling forecast: predict a day, then reveal that
    day's REAL actual to the model (a state update only -- refit=False, so
    no re-optimization, just the Kalman filter absorbing one more
    observation) before predicting the next. This is what an operational
    next-day forecast actually looks like, and it's the same one-step-ahead
    task tree_bakeoff already evaluates tree models on -- unlike
    fit_sarima_forecast's fully blind 366-day forecast, which doesn't see
    any 2024 actuals until scoring. NOT a valid stand-in for a genuine
    multi-day-ahead forecast, since those future actuals wouldn't exist yet
    (see forecast_future_ts, which falls back to the blind forecaster for
    real future dates for exactly this reason)."""
    exog_train = sarima_exog(pd.DatetimeIndex(train["time_fk"]), train["foursquare_heat_exposure_idw"].to_numpy())
    model = SARIMAX(
        train[TARGET].to_numpy(), order=(1, 1, 1), seasonal_order=(1, 0, 1, 7), exog=exog_train,
        enforce_stationarity=False, enforce_invertibility=False,
    )
    result = model.fit(disp=False)

    exog_test = sarima_exog(pd.DatetimeIndex(test["time_fk"]), test["foursquare_heat_exposure_idw"].to_numpy())
    predictions = []
    for i, actual in enumerate(test[TARGET].to_numpy()):
        exog_row = exog_test[[i]]
        one_step = result.get_forecast(steps=1, exog=exog_row).predicted_mean
        predictions.append(float(np.asarray(one_step).reshape(-1)[0]))
        result = result.append(endog=[actual], exog=exog_row, refit=False)
    return np.clip(np.array(predictions), 0, None)


def fit_prophet_forecast(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    df = pd.DataFrame({
        "ds": train["time_fk"], "y": train[TARGET], "heat": train["foursquare_heat_exposure_idw"],
    })
    model = Prophet(yearly_seasonality=6, weekly_seasonality=True, daily_seasonality=False)
    model.add_regressor("heat")
    model.fit(df)
    forecast = model.predict(pd.DataFrame({"ds": test["time_fk"], "heat": test["foursquare_heat_exposure_idw"]}))
    return np.clip(forecast["yhat"].to_numpy(), 0, None)


def classical_ts_bakeoff(market_day: pd.DataFrame) -> pd.DataFrame:
    sarima_actual, sarima_pred = [], []
    sarima_rolling_pred = []
    prophet_actual, prophet_pred = [], []

    for market_key, group in market_day.groupby(MARKET_KEY):
        group = group.sort_values("time_fk").reset_index(drop=True)
        train = group[group["time_fk"].dt.year < TEST_YEAR]
        test = group[group["time_fk"].dt.year == TEST_YEAR]
        print(f"Fitting {market_key}: train={len(train)} days, test={len(test)} days")

        sarima_fc = fit_sarima_forecast(train, test)
        sarima_actual.extend(test[TARGET].to_numpy())
        sarima_pred.extend(sarima_fc)

        print(f"  Rolling one-day-ahead SARIMA over {len(test)} test days...")
        sarima_rolling_pred.extend(fit_sarima_rolling_forecast(train, test))

        prophet_fc = fit_prophet_forecast(train, test)
        prophet_actual.extend(test[TARGET].to_numpy())
        prophet_pred.extend(prophet_fc)

    return pd.DataFrame([
        {
            "model": "SARIMA (daily, per-market, Fourier annual + weekly seasonal + heat exog)",
            "evaluation": "blind (366-day forecast)",
            **score(np.array(sarima_actual), np.log1p(np.array(sarima_pred))),
        },
        {
            "model": "SARIMA (daily, per-market, rolling one-day-ahead)",
            "evaluation": "one-step-ahead (rolling refit)",
            **score(np.array(sarima_actual), np.log1p(np.array(sarima_rolling_pred))),
        },
        {
            "model": "Prophet (daily, per-market, + heat exog)",
            "evaluation": "blind (366-day forecast)",
            **score(np.array(prophet_actual), np.log1p(np.array(prophet_pred))),
        },
    ])


def future_heat_estimate(heat_by_date: pd.Series, target_date: pd.Timestamp) -> float:
    """No real future Foursquare data -- assumes the same day-of-year crowd
    reading as 365 days earlier (the same seasonal-naive assumption
    visitors_lag_365 already relies on elsewhere in this file), not a real
    forecast of crowd density."""
    return heat_by_date.get(target_date - pd.Timedelta(days=365), 0.0)


def build_future_frame(market_day: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    """horizon_days future rows per market, continuing right after each
    market's last available date -- just time_fk + heat exog, what SARIMA/
    Prophet need to forecast forward (fit_sarima_forecast/fit_prophet_forecast
    don't touch TARGET on the frame they're handed as `test`)."""
    rows = []
    for market_key, group in market_day.groupby(MARKET_KEY):
        group = group.sort_values("time_fk").reset_index(drop=True)
        heat_by_date = group.set_index("time_fk")["foursquare_heat_exposure_idw"]
        future_dates = pd.date_range(group["time_fk"].iloc[-1] + pd.Timedelta(days=1), periods=horizon_days, freq="D")
        frame = pd.DataFrame({
            "time_fk": future_dates,
            "foursquare_heat_exposure_idw": [future_heat_estimate(heat_by_date, d) for d in future_dates],
        })
        frame[MARKET_KEY[0]] = market_key[0]
        frame[MARKET_KEY[1]] = market_key[1]
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def forecast_future_tree(estimator_name: str, market_day: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    """Recursively rolls the winning tree model forward horizon_days days
    per market: each day's prediction feeds the next day's lag/rolling
    features (visitors_lag_1 etc.), since there's no real value yet for a
    date that hasn't happened -- same recursive mechanic predict_future.py
    uses at store-day grain, just simpler here (one series per market, no
    store joins)."""
    fit_frame = add_features(market_day).dropna(subset=NUMERIC_COLUMNS + [TARGET])
    model = encoded_pipeline(TREE_MODEL_BUILDERS[estimator_name]())
    model.fit(fit_frame[FEATURE_COLUMNS], np.log1p(fit_frame[TARGET].to_numpy()))

    predictions = []
    for market_key, group in market_day.groupby(MARKET_KEY):
        series = group.sort_values("time_fk").reset_index(drop=True).copy()
        heat_by_date = series.set_index("time_fk")["foursquare_heat_exposure_idw"]

        for _ in range(horizon_days):
            next_date = series["time_fk"].iloc[-1] + pd.Timedelta(days=1)
            new_row = pd.DataFrame([{
                MARKET_KEY[0]: market_key[0],
                MARKET_KEY[1]: market_key[1],
                "time_fk": next_date,
                TARGET: np.nan,
                "foursquare_heat_exposure_idw": future_heat_estimate(heat_by_date, next_date),
            }])
            series = pd.concat([series, new_row], ignore_index=True)
            row = add_features(series).iloc[[-1]]
            predicted = max(float(np.expm1(model.predict(row[FEATURE_COLUMNS]))[0]), 0.0)
            series.loc[series.index[-1], TARGET] = predicted
            predictions.append({
                MARKET_KEY[0]: market_key[0], MARKET_KEY[1]: market_key[1],
                "time_fk": next_date, "predicted_visitor_count": predicted,
            })
    return pd.DataFrame(predictions)


def forecast_future_ts(estimator_name: str, market_day: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    """SARIMA/Prophet forecast horizon_days forward directly from exog --
    no recursion needed, unlike the tree path. The rolling-SARIMA variant
    also maps to fit_sarima_forecast: rolling only has an advantage when
    there's a real actual to reveal each step, which genuinely future dates
    never have, so it collapses back to the same blind forecast here."""
    fit_forecast = {
        "SARIMA (daily, per-market, Fourier annual + weekly seasonal + heat exog)": fit_sarima_forecast,
        "SARIMA (daily, per-market, rolling one-day-ahead)": fit_sarima_forecast,
        "Prophet (daily, per-market, + heat exog)": fit_prophet_forecast,
    }[estimator_name]
    future = build_future_frame(market_day, horizon_days)

    predictions = []
    for market_key, group in market_day.groupby(MARKET_KEY):
        group = group.sort_values("time_fk").reset_index(drop=True)
        future_group = future[
            (future[MARKET_KEY[0]] == market_key[0]) & (future[MARKET_KEY[1]] == market_key[1])
        ].reset_index(drop=True)
        forecast = fit_forecast(group, future_group)
        predictions.append(pd.DataFrame({
            MARKET_KEY[0]: market_key[0], MARKET_KEY[1]: market_key[1],
            "time_fk": future_group["time_fk"], "predicted_visitor_count": forecast,
        }))
    return pd.concat(predictions, ignore_index=True)


def forecast_future(winner_name: str, market_day: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    if winner_name in TREE_MODEL_BUILDERS:
        return forecast_future_tree(winner_name, market_day, horizon_days)
    return forecast_future_ts(winner_name, market_day, horizon_days)


def latest_complete_month(market_day: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return the start/end of the latest complete month in the data."""
    maximum = market_day["time_fk"].max().normalize()
    month_end = maximum + pd.offsets.MonthEnd(0)
    if maximum < month_end:
        period = maximum.to_period("M") - 1
    else:
        period = maximum.to_period("M")
    return period.start_time.normalize(), period.end_time.normalize()


def recursive_market_forecast(
    history: pd.DataFrame,
    forecast_dates: pd.DatetimeIndex,
    model_name: str,
    model: Pipeline | None,
) -> pd.DataFrame:
    """Forecast one day at a time and feed predictions into later lags.

    Never reads actual TARGET values on or after the first forecast date --
    the key difference from tree_bakeoff's one-step evaluation, where every
    test-set lag is a real historical value. Heat exposure isn't rolled
    forward the same way: future_heat_estimate() always looks 365 days back
    into `history`, which stays valid since a month-ahead horizon is far
    short of 365 days.
    """
    histories = {
        market_key: group.sort_values("time_fk")[TARGET].astype(float).tolist()
        for market_key, group in history.groupby(MARKET_KEY)
    }
    heat_by_market = {
        market_key: group.set_index("time_fk")["foursquare_heat_exposure_idw"]
        for market_key, group in history.groupby(MARKET_KEY)
    }
    holiday_dates = set(
        USFederalHolidayCalendar().holidays(start=forecast_dates.min(), end=forecast_dates.max())
    )
    output = []

    for forecast_date in forecast_dates:
        rows = []
        keys = []
        for market_key, values in histories.items():
            if len(values) < 365:
                raise ValueError(f"{market_key} has only {len(values)} history days; 365 are required")
            rows.append(
                {
                    "state_fk": market_key[0],
                    "market_fk": market_key[1],
                    "month": forecast_date.month,
                    "year": forecast_date.year,
                    "day_of_month": forecast_date.day,
                    "is_weekend": forecast_date.weekday() >= 5,
                    "is_hot_season": forecast_date.month in HOT_SEASON_MONTHS,
                    "is_federal_holiday": forecast_date in holiday_dates,
                    "visitors_lag_1": values[-1],
                    "visitors_lag_7": values[-7],
                    "visitors_lag_28": values[-28],
                    "visitors_lag_365": values[-365],
                    "visitors_rolling_7": float(np.mean(values[-7:])),
                    "visitors_rolling_28": float(np.mean(values[-28:])),
                    "foursquare_heat_exposure_idw": future_heat_estimate(
                        heat_by_market[market_key], forecast_date
                    ),
                }
            )
            keys.append(market_key)

        features = pd.DataFrame(rows)
        if model_name == "baseline_trailing_7":
            predicted = features["visitors_rolling_7"].to_numpy()
        elif model_name == "baseline_seasonal_365":
            predicted = features["visitors_lag_365"].to_numpy()
        else:
            if model is None:
                raise ValueError(f"{model_name} requires a fitted model")
            predicted = np.clip(np.expm1(model.predict(features[FEATURE_COLUMNS])), 0, None)

        for market_key, value in zip(keys, predicted):
            value = float(value)
            histories[market_key].append(value)
            output.append(
                {
                    "model": model_name,
                    "time_fk": forecast_date,
                    "state_fk": market_key[0],
                    "market_fk": market_key[1],
                    "predicted_visitor_count": value,
                }
            )
    return pd.DataFrame(output)


def run_month_ahead_comparison(market_day: pd.DataFrame) -> None:
    """Backtest every TREE_MODEL_BUILDERS candidate (plus the two recursive
    baselines) on one blind, fully-recursive month, then refit the winner on
    everything and forecast the following month. Reuses this file's own
    market-day features/model set instead of a separate model list, so
    there's one bake-off to read, not two.
    """
    backtest_start, backtest_end = latest_complete_month(market_day)
    history = market_day[market_day["time_fk"] < backtest_start].copy()
    actual = market_day[market_day["time_fk"].between(backtest_start, backtest_end)].copy()
    training = add_features(history).dropna(subset=NUMERIC_COLUMNS + [TARGET])
    forecast_dates = pd.date_range(backtest_start, backtest_end, freq="D")

    print(
        f"\nMonth-ahead backtest: train through {backtest_start.date() - pd.Timedelta(days=1)}, "
        f"forecast {backtest_start.date()} through {backtest_end.date()} "
        f"({len(forecast_dates)} recursive days, {len(actual)} market-days)"
    )

    y_train = np.log1p(training[TARGET].to_numpy())
    fitted: dict[str, Pipeline] = {}
    for name, build in TREE_MODEL_BUILDERS.items():
        print(f"Fitting {name}...")
        model = encoded_pipeline(build())
        model.fit(training[FEATURE_COLUMNS], y_train)
        fitted[name] = model

    prediction_frames = []
    comparison_rows = []
    for name in [*MONTH_BASELINES, *fitted]:
        print(f"Backtesting {name} across the full month...")
        predictions = recursive_market_forecast(history, forecast_dates, name, fitted.get(name))
        scored = predictions.merge(
            actual[MARKET_KEY + ["time_fk", TARGET]], on=MARKET_KEY + ["time_fk"], how="inner",
        )
        comparison_rows.append(
            {
                "model": name,
                "forecast_month": backtest_start.strftime("%Y-%m"),
                "n_market_days": len(scored),
                **score(scored[TARGET].to_numpy(), np.log1p(scored["predicted_visitor_count"].to_numpy())),
            }
        )
        prediction_frames.append(scored)

    comparison = pd.DataFrame(comparison_rows).sort_values("MAE").reset_index(drop=True)
    backtest_predictions = pd.concat(prediction_frames, ignore_index=True)
    print("\n--- Month-ahead recursive model comparison ---")
    print(comparison.to_string(index=False))

    MONTH_COMPARISON_PATH.parent.mkdir(exist_ok=True)
    comparison.to_csv(MONTH_COMPARISON_PATH, index=False)
    backtest_predictions.to_csv(MONTH_BACKTEST_PATH, index=False)

    winner_name = comparison.iloc[0]["model"]
    print(f"\nBest month-ahead model by MAE: {winner_name}")

    complete_training = add_features(market_day).dropna(subset=NUMERIC_COLUMNS + [TARGET])
    winner = None
    if winner_name not in MONTH_BASELINES:
        winner = encoded_pipeline(TREE_MODEL_BUILDERS[winner_name]())
        winner.fit(complete_training[FEATURE_COLUMNS], np.log1p(complete_training[TARGET].to_numpy()))

    next_month_start = backtest_end + pd.Timedelta(days=1)
    next_month_end = next_month_start + pd.offsets.MonthEnd(0)
    next_month_dates = pd.date_range(next_month_start, next_month_end, freq="D")
    next_month = recursive_market_forecast(market_day, next_month_dates, winner_name, winner)
    next_month.to_csv(NEXT_MONTH_PATH, index=False)

    print(f"Wrote month-ahead comparison -> {MONTH_COMPARISON_PATH}")
    print(f"Wrote month-ahead backtest predictions -> {MONTH_BACKTEST_PATH}")
    print(
        f"Wrote {len(next_month)} daily market forecasts for "
        f"{next_month_start.strftime('%B %Y')} -> {NEXT_MONTH_PATH}"
    )


def main() -> None:
    clean = pd.read_csv(CLEAN_PATH, parse_dates=["time_fk"])
    clean = clean[clean["market_fk"].isin(MARKETS)]
    market_day = add_features(build_market_day(clean))
    train, test = chronological_split(market_day)
    n_markets = market_day[MARKET_KEY].drop_duplicates().shape[0]
    print(f"Market-day series: train={len(train)} rows, test={len(test)} rows across {n_markets} markets")

    print("\n--- Tree bake-off (market-day grain, one-step-ahead: real lags in test) ---")
    tree_results = tree_bakeoff(train, test)
    print(tree_results.to_string(index=False))

    print("\n--- Classical time-series (market-day grain: blind 366-day forecast + rolling one-day-ahead) ---")
    ts_results = classical_ts_bakeoff(market_day)
    print(ts_results.to_string(index=False))

    print("\n--- Quantile interval (P10/P50/P90, market-day grain, one-step-ahead) ---")
    interval = quantile_interval(train, test)
    QUANTILE_INTERVAL_PATH.parent.mkdir(exist_ok=True)
    interval.to_csv(QUANTILE_INTERVAL_PATH, index=False)
    print(interval.head().to_string(index=False))
    print(f"Wrote -> {QUANTILE_INTERVAL_PATH}")

    combined = pd.concat([tree_results, ts_results], ignore_index=True).sort_values("MAE").reset_index(drop=True)
    COMPARISON_PATH.parent.mkdir(exist_ok=True)
    combined.to_csv(COMPARISON_PATH, index=False)
    print("\n--- Combined leaderboard (bigger, daily-grain dataset) ---")
    print("NOTE: 'evaluation' differs by row -- one-step-ahead rows get real")
    print("lag/actual values every day, blind rows forecast the full test")
    print("period with none. Lower MAE on an easier evaluation isn't a")
    print("like-for-like win; see the module docstring.")
    print(combined[["model", "evaluation", "MAE", "RMSE", "sMAPE", "R2"]].to_string(index=False))
    print(f"\nWrote -> {COMPARISON_PATH}")

    winner_name = combined["model"].iloc[0]
    print(f"\n--- Forecasting {FUTURE_HORIZON_DAYS} days beyond available data (bake-off winner: {winner_name}) ---")
    future = forecast_future(winner_name, market_day, FUTURE_HORIZON_DAYS)
    FUTURE_PREDICTIONS_PATH.parent.mkdir(exist_ok=True)
    future.to_csv(FUTURE_PREDICTIONS_PATH, index=False)
    print(future.to_string(index=False))
    print(f"\nWrote -> {FUTURE_PREDICTIONS_PATH}")

    print("\n--- Month-ahead recursive forecast (formerly train.py) ---")
    run_month_ahead_comparison(market_day)


if __name__ == "__main__":
    main()
