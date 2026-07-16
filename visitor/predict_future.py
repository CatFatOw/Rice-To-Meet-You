"""
Stream 2 (Visitor Activity) multi-day forecast.

Recursively rolls predict_tomorrow.py's next-day forecast forward
HORIZON_DAYS days: each day's prediction feeds back into the lag/rolling
feature history so the next day's forecast has a continuous trail --
there's no ground truth to look at for a date that hasn't happened yet.

The model is fit ONCE on real history before the loop starts and reused
for every horizon day -- only *features* roll forward on predictions,
never the *labels* a model is fit against. Retraining on the pipeline's
own forecasts each iteration would let day-1 errors get "confirmed" by
day-2 training and compound for reasons that have nothing to do with real
signal.

The output CSV carries every column clean_daily_store() produces, not just
identifiers + predicted_visitor_count, so downstream consumers (e.g.
HeatSafe risk scoring) don't have to re-derive calendar/lag/foursquare
features themselves. visitor_count is still the only modeled quantity.

Caveats, compounded by horizon:
- Foursquare crowd features have no future source and stay at whatever
  fallback the first forecast day used.
- Errors compound: a day's lag features depend on the *predicted* prior
  day, not an observed one.

Since there's no ground truth for the live dates, error is measured by
re-running the same recursive mechanic backdated over the last HORIZON_DAYS
already-observed days (run_backtest_rollout()), scored per horizon_day and
attached to the live output as backtest_mae / backtest_smape_pct.

The backtest predicts the REAL rows that reported on each held-out day,
not build_target_date_rows()'s "recently active" candidate universe the
live forecast uses (run_live_rollout()) -- most "recently active" stores
don't actually report on any given day (a store reports on only ~1.4 days
across 5 years), so comparing predictions for ~4800 candidates against
actuals from the ~50 that reported isn't a fair test. Predicting the exact
stores that DID report matches the population train.py's own
2024 holdout validates against.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from clean import FOURSQUARE_WIDE_PATH, RAW_PATH, RELEVANT_COLUMNS, clean_daily_store
from predict_tomorrow import build_target_date_rows, load_winner_name
from train import NUMERIC_COLUMNS, TARGET, build_model, native_categorical_frame, score

PREDICTIONS_PATH = Path("data/visitor_predictions_future.csv")
BACKTEST_PATH = Path("data/visitor_future_backtest_by_horizon.csv")

# How many days ahead to forecast, and how many already-observed trailing
# days to hold back for the matching backtest. Kept modest -- recursive lag
# features mean accuracy degrades with horizon (see module docstring).
HORIZON_DAYS = 7

OUTPUT_COLUMNS = [c for c in RELEVANT_COLUMNS if c != TARGET]


def fit_on_history(raw: pd.DataFrame, foursquare_wide: pd.DataFrame) -> tuple[object, pd.DataFrame]:
    """Fits the bake-off winner once on real historical data. `history` also
    anchors native_categorical_frame()'s categorical alignment for every
    horizon day, so predictions never see a category code the model wasn't
    fit on."""
    clean = clean_daily_store(raw, foursquare_wide)
    clean[NUMERIC_COLUMNS] = clean[NUMERIC_COLUMNS].replace([np.inf, -np.inf], np.nan)
    history = clean.dropna(subset=NUMERIC_COLUMNS + [TARGET]).reset_index(drop=True)

    winner_name = load_winner_name()
    print(f"Fitting bake-off winner ({winner_name}) once on {len(history)} historical rows")
    X_train, _ = native_categorical_frame(history, history)
    model = build_model(winner_name)
    model.fit(X_train, np.log1p(history[TARGET].to_numpy()))
    return model, history


def forecast_one_day(
    model,
    history: pd.DataFrame,
    raw_so_far: pd.DataFrame,
    foursquare_wide: pd.DataFrame,
    target_date: pd.Timestamp,
    target_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One recursive step: predicts visitor_count for target_rows (TARGET
    already NaN, time_fk == target_date) using lag/rolling history built
    from raw_so_far. Returns (feedback_rows, full_output_rows) --
    feedback_rows is RELEVANT_COLUMNS-shaped, for the next day's lag
    history; full_output_rows carries every derived column, for saving.
    Which stores land in target_rows is the caller's call -- see module
    docstring for why the live forecast and backtest use different ones."""
    combined = pd.concat([raw_so_far, target_rows], ignore_index=True)
    clean = clean_daily_store(combined, foursquare_wide)
    clean[NUMERIC_COLUMNS] = clean[NUMERIC_COLUMNS].replace([np.inf, -np.inf], np.nan)

    to_predict = clean[clean["time_fk"] == target_date].reset_index(drop=True)
    missing_history = to_predict[NUMERIC_COLUMNS].isna().any(axis=1)
    if missing_history.any():
        print(f"  Dropping {missing_history.sum()} store(s) with incomplete lag/rolling history")
    to_predict = to_predict[~missing_history].reset_index(drop=True)

    _, X_to_predict = native_categorical_frame(history, to_predict)
    predicted = np.clip(np.expm1(model.predict(X_to_predict)), 0, None)

    feedback_rows = to_predict[OUTPUT_COLUMNS].copy()
    feedback_rows[TARGET] = predicted

    full_output_rows = to_predict.drop(columns=[TARGET]).copy()
    full_output_rows["predicted_visitor_count"] = predicted
    return feedback_rows, full_output_rows


def run_live_rollout(raw: pd.DataFrame, foursquare_wide: pd.DataFrame, anchor_date: pd.Timestamp) -> pd.DataFrame:
    """Fits on all real history, then recursively forecasts HORIZON_DAYS
    days for build_target_date_rows()'s "recently active" candidate
    universe -- there's no way to know which stores will actually report
    on a future date."""
    model, history = fit_on_history(raw, foursquare_wide)

    raw_so_far = raw.copy()
    all_predictions = []
    for horizon_day in range(1, HORIZON_DAYS + 1):
        target_date = anchor_date + pd.Timedelta(days=horizon_day - 1)
        print(f"  Forecasting horizon_day {horizon_day} ({target_date.date()})")
        target_rows = build_target_date_rows(raw_so_far, target_date)
        feedback_rows, full_output_rows = forecast_one_day(
            model, history, raw_so_far, foursquare_wide, target_date, target_rows
        )

        full_output_rows["horizon_day"] = horizon_day
        all_predictions.append(full_output_rows)

        # Feeds this day's predictions back in as next day's "known" history
        # -- see module docstring: features roll forward, labels never do.
        raw_so_far = pd.concat([raw_so_far, feedback_rows], ignore_index=True)

    return pd.concat(all_predictions, ignore_index=True)


def run_backtest_rollout(raw: pd.DataFrame, foursquare_wide: pd.DataFrame, anchor_date: pd.Timestamp) -> pd.DataFrame:
    """Same mechanic as run_live_rollout, backdated into already-observed
    history: fits before anchor_date, then predicts the REAL rows that
    reported each held-out day (not the candidate universe -- see module
    docstring). Predictions still feed back into raw_so_far as next-day
    lag history, so this measures how much predicted (not observed) lag
    history degrades accuracy by horizon -- exactly what the live rollout
    experiences but can't self-score."""
    train_raw = raw[raw["time_fk"] < anchor_date].reset_index(drop=True)
    model, history = fit_on_history(train_raw, foursquare_wide)

    raw_so_far = train_raw.copy()
    all_predictions = []
    for horizon_day in range(1, HORIZON_DAYS + 1):
        target_date = anchor_date + pd.Timedelta(days=horizon_day - 1)
        real_rows = raw[raw["time_fk"] == target_date].reset_index(drop=True)
        print(f"  Forecasting horizon_day {horizon_day} ({target_date.date()}), {len(real_rows)} stores really reported")
        target_rows = real_rows.copy()
        target_rows[TARGET] = np.nan

        feedback_rows, full_output_rows = forecast_one_day(
            model, history, raw_so_far, foursquare_wide, target_date, target_rows
        )
        full_output_rows["horizon_day"] = horizon_day
        full_output_rows = full_output_rows.merge(
            real_rows[["store_id_fk", "time_fk", TARGET]].rename(columns={TARGET: "actual_visitor_count"}),
            on=["store_id_fk", "time_fk"], how="left",
        )
        all_predictions.append(full_output_rows)

        # Feeds this day's PREDICTIONS back in, not the real values -- see
        # docstring above.
        raw_so_far = pd.concat([raw_so_far, feedback_rows], ignore_index=True)

    return pd.concat(all_predictions, ignore_index=True)


def score_by_horizon(backtest_predictions: pd.DataFrame) -> pd.DataFrame:
    """MAE/RMSE/sMAPE/R2 per horizon_day, store-day grain, on the real
    matched rows run_backtest_rollout() already attached actual_visitor_count
    to."""
    rows = []
    for horizon_day, group in backtest_predictions.groupby("horizon_day"):
        s = score(group["actual_visitor_count"].to_numpy(), np.log1p(group["predicted_visitor_count"].to_numpy()))
        rows.append({"horizon_day": horizon_day, "n_stores": len(group), **s})
    return pd.DataFrame(rows)


def main() -> None:
    raw = pd.read_csv(RAW_PATH, parse_dates=["time_fk"])[RELEVANT_COLUMNS]
    foursquare_wide = pd.read_csv(FOURSQUARE_WIDE_PATH, parse_dates=["time_fk"])
    max_date = raw["time_fk"].max()

    print(f"--- Backtest: recursive rollout over the last {HORIZON_DAYS} already-observed days ---")
    backtest_anchor = max_date - pd.Timedelta(days=HORIZON_DAYS - 1)
    backtest_predictions = run_backtest_rollout(raw, foursquare_wide, backtest_anchor)
    backtest_scores = score_by_horizon(backtest_predictions)
    print(backtest_scores.to_string(index=False))
    BACKTEST_PATH.parent.mkdir(exist_ok=True)
    backtest_scores.to_csv(BACKTEST_PATH, index=False)
    print(f"Wrote backtest-by-horizon table -> {BACKTEST_PATH}")

    print(f"\n--- Live forecast: recursive rollout over the next {HORIZON_DAYS} days ---")
    anchor_date = max_date + pd.Timedelta(days=1)
    output = run_live_rollout(raw, foursquare_wide, anchor_date)

    output = output.merge(
        backtest_scores[["horizon_day", "MAE", "sMAPE"]].rename(
            columns={"MAE": "backtest_mae", "sMAPE": "backtest_smape_pct"}
        ),
        on="horizon_day", how="left",
    )
    output = output.sort_values(
        ["horizon_day", "predicted_visitor_count"], ascending=[True, False]
    ).reset_index(drop=True)

    PREDICTIONS_PATH.parent.mkdir(exist_ok=True)
    output.to_csv(PREDICTIONS_PATH, index=False)
    print(f"\nWrote {len(output)} store-day forecasts across {HORIZON_DAYS} days -> {PREDICTIONS_PATH}")
    print("(backtest_mae/backtest_smape_pct on each row is that horizon_day's error measured on the "
          f"last {HORIZON_DAYS} already-observed days, recursively forecast the same way -- see backtest above)")

    print("\n--- Predicted market totals, top 3 markets per horizon day ---")
    market_totals = (
        output.groupby(["horizon_day", "state_fk", "market_fk"])["predicted_visitor_count"]
        .sum()
        .reset_index()
        .sort_values(["horizon_day", "predicted_visitor_count"], ascending=[True, False])
    )
    print(market_totals.groupby("horizon_day").head(3).to_string(index=False))


if __name__ == "__main__":
    main()
