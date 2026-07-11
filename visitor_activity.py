"""
Stream 2 (Visitor Activity) pipeline.

Reads real daily visitor data (2020-2024) for 9 US markets from
data/visitor_daily_store_raw.csv. Each row is one store's visit count for
one day.

Two things to know about this data:
1. It has no "city" column, only "market" -- a market can cover several
   cities (e.g. "New York/New Jersey" is one market).
2. The number of stores that report data changes a lot from day to day.
   So daily totals bounce around partly from real visitor changes, and
   partly just because more or fewer stores happened to report that day.
   To smooth over that noise, the forecasts below average the last several
   days together instead of trusting a single day's number.
"""

from __future__ import annotations

import calendar
from pathlib import Path

import pandas as pd

RAW_DAILY_PATH = Path("data/visitor_daily_store_raw.csv")
OUT_DIR = Path("data")

HOT_SEASON_MONTHS = {6, 7, 8}  # summer months: June, July, August

FORECAST_WINDOW_DAYS = 7  # how many past days we average to make a prediction


def load_daily_raw(path: Path = RAW_DAILY_PATH) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["time_fk"])


def audit_per_store_counts(df: pd.DataFrame) -> None:
    """Checks that visitor counts really differ store-by-store. An earlier
    version of this data had a bug where one state-wide number got copied
    onto every store -- this print statement confirms that's fixed."""
    grouped = df.groupby(["time_fk", "state_fk", "market_fk"])
    multi_store = grouped.filter(lambda g: g["store_id_fk"].nunique() > 1).groupby(
        ["time_fk", "state_fk", "market_fk"]
    )
    pct_still_constant = (multi_store["visitor_count"].nunique() == 1).mean()
    print(
        f"(audited {multi_store.ngroups} day/market groups with 2+ reporting stores: "
        f"{pct_still_constant:.1%} still show a single repeated visitor_count -- "
        f"should be near 0 now that the fix landed)"
    )


def aggregate_daily_market(df: pd.DataFrame) -> pd.DataFrame:
    """Adds up every store's visits for each (day, state, market), so we
    get one total number instead of one row per store. This is the most
    specific location grouping this data supports, since it has no city
    column."""
    agg = df.groupby(["time_fk", "state_fk", "market_fk"]).agg(
        daily_visitors=("visitor_count", "sum"),
        n_stores_reporting=("store_id_fk", "nunique"),
    ).reset_index()
    agg["is_hot_season"] = agg["time_fk"].dt.month.isin(HOT_SEASON_MONTHS)
    return agg.sort_values(["state_fk", "market_fk", "time_fk"]).reset_index(drop=True)


def compute_named_metrics(daily_market_df: pd.DataFrame, value_col: str = "daily_visitors") -> pd.DataFrame:
    """Calculates the key visitor numbers for each market: average day,
    busiest day, and how visits during hot months compare to the rest of
    the year. Works on both real past data and our future predictions --
    value_col just says which column holds the visitor numbers to use."""

    def agg(group: pd.DataFrame) -> pd.Series:
        hot = group[group["is_hot_season"]]
        cool = group[~group["is_hot_season"]]
        total = group[value_col].sum()
        return pd.Series(
            {
                "avg_daily_visitors_all_days": group[value_col].mean(),
                "peak_day_visitors": group[value_col].max(),
                "hot_window_avg_daily_visitors": hot[value_col].mean() if len(hot) else float("nan"),
                "cool_season_avg_daily_visitors": cool[value_col].mean() if len(cool) else float("nan"),
                "pct_total_visits_during_hot_season": (hot[value_col].sum() / total if total else float("nan")),
                "n_days_observed": len(group),
            }
        )

    return daily_market_df.groupby(["state_fk", "market_fk"]).apply(agg).reset_index()


def _forecast_month_for_group(hist: pd.DataFrame, target_month_start: pd.Timestamp, window: int) -> pd.DataFrame:
    """Predicts one market's visitor counts for one future month.

    How it works: take the average of the last `window` real days as a
    baseline number (the "level"). Then nudge each day of the forecast
    month up or down based on what that market's Mondays, Saturdays, etc.
    usually look like in the real data (the "shape") -- e.g. if Saturdays
    are normally busier, the forecasted Saturdays come out a bit higher.

    `hist` must only contain days before `target_month_start` -- the
    caller makes sure of this so the forecast never peeks at the days
    it's trying to predict. Used by both forecast_month_ahead (predicting
    a real future month) and backtest_month_ahead (checking accuracy
    against real past months), so both use identical logic.
    """
    level = hist["daily_visitors"].tail(window).mean()

    n_days = calendar.monthrange(target_month_start.year, target_month_start.month)[1]
    dates = pd.date_range(target_month_start, periods=n_days, freq="D")

    market_mean = hist["daily_visitors"].mean()
    profile = (
        (hist["daily_visitors"] / market_mean).groupby(hist["time_fk"].dt.weekday).mean()
    )
    raw_mult = pd.Series(dates.weekday, index=dates).map(profile).fillna(1.0)
    mult = raw_mult / raw_mult.mean()  # rescale so the shaped days still average back to `level`

    return pd.DataFrame({"date": dates, "forecast_daily_visitors": (level * mult).values})


def forecast_month_ahead(daily_market_df: pd.DataFrame, window: int = FORECAST_WINDOW_DAYS) -> pd.DataFrame:
    """Predicts every day of the calendar month right after each market's
    last real day of data.

    This is a simple guess, not a smart trend-following model. Read it as
    "assume next month looks like last week did, just shaped by which
    days of the week are usually busier" -- it won't catch things like an
    upcoming holiday or a new trend starting.
    """
    rows = []
    for (state, market), g in daily_market_df.sort_values("time_fk").groupby(["state_fk", "market_fk"]):
        last_date = g["time_fk"].iloc[-1]
        month_start = pd.Timestamp(last_date.year, last_date.month, 1) + pd.DateOffset(months=1)
        fc = _forecast_month_for_group(g, month_start, window)

        for d, v in zip(fc["date"], fc["forecast_daily_visitors"]):
            rows.append(
                {
                    "state_fk": state,
                    "market_fk": market,
                    "as_of_date": last_date,
                    "time_fk": d,
                    "forecast_daily_visitors": v,
                    "is_hot_season": d.month in HOT_SEASON_MONTHS,
                    "forecast_method": f"trailing_{window}day_level_x_real_weekday_profile",
                }
            )
    return pd.DataFrame(rows)


def backtest_month_ahead(daily_market_df: pd.DataFrame, window: int = FORECAST_WINDOW_DAYS) -> pd.DataFrame:
    """Checks how good the month-ahead prediction actually is.

    For every real month we have data for, this pretends we're standing
    right before that month started, makes a prediction using only the
    data from before then, and compares it to what really happened. Doing
    this across every past month gives an honest accuracy score, since
    each prediction is tested only against days it never got to see
    ahead of time.
    """
    rows = []
    for (state, market), g in daily_market_df.sort_values("time_fk").groupby(["state_fk", "market_fk"]):
        g = g.reset_index(drop=True)
        for period in sorted(g["time_fk"].dt.to_period("M").unique()):
            month_start = period.start_time
            hist = g[g["time_fk"] < month_start]
            if len(hist) < window:
                continue
            actual_month = g[
                (g["time_fk"] >= month_start) & (g["time_fk"] < month_start + pd.DateOffset(months=1))
            ]
            if actual_month.empty:
                continue

            fc = _forecast_month_for_group(hist, month_start, window)
            merged = actual_month.merge(fc, left_on="time_fk", right_on="date", how="inner")
            for _, r in merged.iterrows():
                actual = r["daily_visitors"]
                predicted = r["forecast_daily_visitors"]
                rows.append(
                    {
                        "state_fk": state,
                        "market_fk": market,
                        "month": str(period),
                        "date": r["time_fk"],
                        "predicted": predicted,
                        "actual": actual,
                        "abs_error": abs(actual - predicted),
                        "pct_error": abs(actual - predicted) / actual if actual else float("nan"),
                    }
                )
    return pd.DataFrame(rows)


def forecast_trailing_avg(daily_market_df: pd.DataFrame, window: int = FORECAST_WINDOW_DAYS) -> pd.DataFrame:
    """Predicts tomorrow's visitors for each market: just the average of
    the last `window` real days.

    Why an average instead of just using yesterday's number? Because how
    many stores report data changes a lot day to day (see the module
    docstring at the top), so yesterday alone can be a noisy, unreliable
    guess. Averaging several days smooths that out.
    """
    rows = []
    for (state, market), g in daily_market_df.sort_values("time_fk").groupby(["state_fk", "market_fk"]):
        last_date = g["time_fk"].iloc[-1]
        trailing = g["daily_visitors"].tail(window)
        forecast_date = last_date + pd.Timedelta(days=1)
        rows.append(
            {
                "state_fk": state,
                "market_fk": market,
                "as_of_date": last_date,
                "forecast_date": forecast_date,
                "forecast_daily_visitors": trailing.mean(),
                "forecast_is_hot_season": forecast_date.month in HOT_SEASON_MONTHS,
                "forecast_method": f"trailing_{window}day_average",
                "n_days_in_window": len(trailing),
            }
        )
    return pd.DataFrame(rows)


def backtest_trailing_avg(daily_market_df: pd.DataFrame, window: int = FORECAST_WINDOW_DAYS) -> pd.DataFrame:
    """Checks how good the 1-day-ahead prediction actually is: for every
    real day (after the first `window` days), predict it using only the
    average of the days before it, then compare to what really happened.
    Same idea as backtest_month_ahead, just one day at a time instead of
    a whole month.
    """
    rows = []
    for (state, market), g in daily_market_df.sort_values("time_fk").groupby(["state_fk", "market_fk"]):
        g = g.reset_index(drop=True)
        for i in range(window, len(g)):
            trailing = g["daily_visitors"].iloc[i - window : i]
            predicted = trailing.mean()
            actual = g["daily_visitors"].iloc[i]
            rows.append(
                {
                    "state_fk": state,
                    "market_fk": market,
                    "date": g["time_fk"].iloc[i],
                    "predicted": predicted,
                    "actual": actual,
                    "abs_error": abs(actual - predicted),
                    "pct_error": abs(actual - predicted) / actual if actual else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def format_for_stream3(df: pd.DataFrame, value_col: str, is_forecast: bool) -> pd.DataFrame:
    """Reshapes our numbers to look like the same columns Stream 2 itself
    received as input (time_fk, state_fk, market_fk, visitor_count, plus
    the pipe-joined key columns), instead of our own working column
    names. Stream 3 expects everything handed to it in one consistent
    shape, so this is the last step before writing the handoff file --
    used for both the real numbers and the forecast numbers, with
    `is_forecast` marking which is which.
    """
    out = pd.DataFrame(
        {
            "time_fk": pd.to_datetime(df["time_fk"]).dt.strftime("%Y-%m-%d"),
            "state_fk": df["state_fk"],
            "market_fk": df["market_fk"],
            "visitor_count": df[value_col],
        }
    )
    out["time_state_fk"] = out["time_fk"] + "|" + out["state_fk"]
    out["time_state_market_fk"] = out["time_state_fk"] + "|" + out["market_fk"]
    out["is_forecast"] = is_forecast
    return out


def main() -> None:
    daily_raw = load_daily_raw()
    print(f"Loaded {len(daily_raw)} real per-store rows from {RAW_DAILY_PATH}")
    print(f"Date range: {daily_raw['time_fk'].min().date()} -> {daily_raw['time_fk'].max().date()}")
    print(f"Markets: {sorted(daily_raw['market_fk'].unique())}")

    audit_per_store_counts(daily_raw)

    daily_market = aggregate_daily_market(daily_raw)
    metrics = compute_named_metrics(daily_market)
    forecast = forecast_trailing_avg(daily_market)
    backtest = backtest_trailing_avg(daily_market)
    month_forecast = forecast_month_ahead(daily_market)
    month_forecast_metrics = compute_named_metrics(month_forecast, value_col="forecast_daily_visitors")
    month_backtest = backtest_month_ahead(daily_market)

    stream3_real = format_for_stream3(daily_market, value_col="daily_visitors", is_forecast=False)
    stream3_forecast = format_for_stream3(month_forecast, value_col="forecast_daily_visitors", is_forecast=True)
    stream3_handoff = pd.concat([stream3_real, stream3_forecast], ignore_index=True)

    OUT_DIR.mkdir(exist_ok=True)
    paths = {
        "daily totals (real, per market)": OUT_DIR / "visitor_activity_daily_real.csv",
        "named metrics (real)": OUT_DIR / "visitor_activity_named_metrics.csv",
        "forecast (trailing avg, next day)": OUT_DIR / "visitor_activity_forecast_daily.csv",
        "backtest (walk-forward, 1 day)": OUT_DIR / "visitor_activity_backtest_trailing_avg.csv",
        "forecast (month ahead, daily)": OUT_DIR / "visitor_activity_forecast_month_ahead.csv",
        "named metrics (month-ahead forecast)": OUT_DIR / "visitor_activity_forecast_month_ahead_metrics.csv",
        "backtest (walk-forward, month ahead)": OUT_DIR / "visitor_activity_backtest_month_ahead.csv",
        "STREAM 3 HANDOFF (current + forecast)": OUT_DIR / "visitor_activity_stream3_handoff.csv",
    }
    daily_market.to_csv(paths["daily totals (real, per market)"], index=False)
    metrics.to_csv(paths["named metrics (real)"], index=False)
    forecast.to_csv(paths["forecast (trailing avg, next day)"], index=False)
    backtest.to_csv(paths["backtest (walk-forward, 1 day)"], index=False)
    month_forecast.to_csv(paths["forecast (month ahead, daily)"], index=False)
    month_forecast_metrics.to_csv(paths["named metrics (month-ahead forecast)"], index=False)
    month_backtest.to_csv(paths["backtest (walk-forward, month ahead)"], index=False)
    stream3_handoff.to_csv(paths["STREAM 3 HANDOFF (current + forecast)"], index=False)

    print()
    for label, path in paths.items():
        print(f"Wrote {label:36s} -> {path}")

    print("\n--- Stream 3 handoff file, same column shape as our own input data ---")
    print(stream3_handoff.head(3).to_string(index=False))
    print("...")
    print(stream3_handoff.tail(3).to_string(index=False))
    print(
        f"{len(stream3_real)} real rows + {len(stream3_forecast)} forecast rows "
        f"= {len(stream3_handoff)} total rows"
    )

    print("\n--- Named metrics, real (top 10 by avg_daily_visitors_all_days) ---")
    print(metrics.sort_values("avg_daily_visitors_all_days", ascending=False).head(10).to_string(index=False))

    print(f"\n--- Walk-forward backtest ({len(backtest)} scored days across all markets) ---")
    smape = (
        2 * backtest["abs_error"] / (backtest["actual"].abs() + backtest["predicted"].abs())
    ).mean() * 100
    print(f"MAE:         {backtest['abs_error'].mean():.1f} visitors/day  (typical size of the miss)")
    print(f"Mean MAPE:   {backtest['pct_error'].mean() * 100:.1f}%  (misleading average -- see note below)")
    print(f"Median MAPE: {backtest['pct_error'].median() * 100:.1f}%  (typical error %, middle value)")
    print(f"sMAPE:       {smape:.1f}%  (error %, but not thrown off by tiny real numbers)")
    print(
        "NOTE: the average error % above looks huge mostly because of a "
        "few days where the real number was tiny (like 3 visitors) while "
        "the prediction wasn't -- one day like that skews the average a "
        "lot, even though most days aren't nearly that off. The median "
        "and sMAPE numbers aren't fooled by those outliers, so trust "
        "those instead."
    )
    print("Per-market median pct_error:")
    print((backtest.groupby("market_fk")["pct_error"].median() * 100).round(1).sort_values().to_string())

    print("\n--- Forecast: next day per market ---")
    print(
        forecast.sort_values("forecast_daily_visitors", ascending=False)
        [["state_fk", "market_fk", "forecast_date", "forecast_daily_visitors", "forecast_is_hot_season"]]
        .to_string(index=False)
    )

    target_month = month_forecast["time_fk"].iloc[0].strftime("%B %Y")
    print(f"\n--- Forecast: {target_month}, named metrics per market ---")
    print(
        month_forecast_metrics.sort_values("avg_daily_visitors_all_days", ascending=False).to_string(index=False)
    )

    print(f"\n--- Walk-forward backtest of the MONTH-AHEAD model ({len(month_backtest)} scored days) ---")
    month_smape = (
        2 * month_backtest["abs_error"] / (month_backtest["actual"].abs() + month_backtest["predicted"].abs())
    ).mean() * 100
    print(f"MAE:         {month_backtest['abs_error'].mean():.1f} visitors/day")
    print(f"Median MAPE: {month_backtest['pct_error'].median() * 100:.1f}%")
    print(f"sMAPE:       {month_smape:.1f}%")
    print("Per-market median pct_error (month-ahead model):")
    print((month_backtest.groupby("market_fk")["pct_error"].median() * 100).round(1).sort_values().to_string())
    print(
        "Compare to the 1-day model's per-market median pct_error above -- "
        "this tells you how much accuracy is actually lost going from a "
        "1-day to a 1-month horizon on this data."
    )


if __name__ == "__main__":
    main()
