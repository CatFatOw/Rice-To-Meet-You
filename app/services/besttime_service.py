"""Client helpers for BestTime relative venue-busyness data."""

import os
from datetime import datetime

import requests
from requests.exceptions import RequestException

LIVE_URL = "https://besttime.app/api/v1/forecasts/live"
FORECAST_URL = "https://besttime.app/api/v1/forecasts"
REQUEST_TIMEOUT = 25
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class BestTimeConfigurationError(RuntimeError):
    pass


class BestTimeUnavailableError(RuntimeError):
    pass


def _api_key() -> str:
    api_key = os.getenv("BESTTIME_API_KEY")
    if not api_key:
        raise BestTimeConfigurationError("BESTTIME_API_KEY is not configured on the server.")
    return api_key


def _post_besttime(url: str, venue_name: str, venue_address: str) -> dict:
    api_key = _api_key()
    response = requests.post(
        url,
        params={"api_key_private": api_key, "venue_name": venue_name, "venue_address": venue_address},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code == 404:
        raise BestTimeUnavailableError("BestTime has no traffic forecast for this venue.")
    response.raise_for_status()
    return response.json()


def get_live_traffic(venue_name: str, venue_address: str) -> dict:
    return _post_besttime(LIVE_URL, venue_name, venue_address)


def get_forecast_traffic(venue_name: str, venue_address: str) -> dict:
    return _post_besttime(FORECAST_URL, venue_name, venue_address)


def _clamp_score(value) -> int | None:
    if value is None:
        return None
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return None


def _hour_label(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour}:00 {suffix}"


def _day_name(index: int) -> str:
    if 0 <= index < len(DAY_NAMES):
        return DAY_NAMES[index]
    return f"Day {index + 1}"


def _hour_score(day_index: int, hour: int, score: int) -> dict:
    return {
        "day": _day_name(day_index),
        "hour": hour,
        "hour_label": _hour_label(hour),
        "score": score,
    }


def _extract_week_raw(payload: dict) -> list[list[int]]:
    analysis = payload.get("analysis") or {}
    candidates = [
        payload.get("week_raw"),
        payload.get("forecast_week"),
        analysis.get("week_raw"),
        analysis.get("forecast_week"),
    ]
    for candidate in candidates:
        if not isinstance(candidate, list) or not candidate:
            continue
        week_profile: list[list[int]] = []
        for day in candidate[:7]:
            if not isinstance(day, list):
                week_profile = []
                break
            scores = [_clamp_score(score) for score in day[:24]]
            if len(scores) == 24 and all(score is not None for score in scores):
                week_profile.append([score for score in scores if score is not None])
        if week_profile:
            return week_profile
    return []


def _extract_peak_windows(payload: dict, week_profile: list[list[int]]) -> list[dict]:
    analysis = payload.get("analysis") or {}
    raw_windows = analysis.get("busy_hours") or payload.get("busy_hours") or []
    windows: list[dict] = []

    if isinstance(raw_windows, list):
        for day_index, day_windows in enumerate(raw_windows[:7]):
            if not isinstance(day_windows, list):
                continue
            for window in day_windows[:2]:
                if not isinstance(window, list) or len(window) < 2:
                    continue
                start_hour = max(0, min(23, int(window[0])))
                end_hour = max(start_hour + 1, min(24, int(window[1])))
                day_scores = week_profile[day_index] if day_index < len(week_profile) else []
                score_values = day_scores[start_hour:end_hour]
                score = round(sum(score_values) / len(score_values)) if score_values else 0
                windows.append({
                    "day": _day_name(day_index),
                    "start_hour": start_hour,
                    "end_hour": end_hour,
                    "start_label": _hour_label(start_hour),
                    "end_label": _hour_label(end_hour % 24),
                    "score": score,
                })

    if windows or not week_profile:
        return windows[:8]

    for day_index, day_scores in enumerate(week_profile[:7]):
        best_hour = max(range(len(day_scores)), key=lambda hour: day_scores[hour])
        end_hour = min(24, best_hour + 2)
        score_values = day_scores[best_hour:end_hour]
        windows.append({
            "day": _day_name(day_index),
            "start_hour": best_hour,
            "end_hour": end_hour,
            "start_label": _hour_label(best_hour),
            "end_label": _hour_label(end_hour % 24),
            "score": round(sum(score_values) / len(score_values)),
        })
    return sorted(windows, key=lambda window: window["score"], reverse=True)[:8]


def besttime_traffic_payload(venue_name: str, venue_address: str) -> dict:
    live_payload = get_live_traffic(venue_name, venue_address)
    try:
        forecast_payload = get_forecast_traffic(venue_name, venue_address)
    except (BestTimeUnavailableError, RequestException):
        forecast_payload = {}

    analysis = live_payload.get("analysis") or {}
    live_available = bool(analysis.get("venue_live_busyness_available"))
    live_score = _clamp_score(analysis.get("venue_live_busyness")) if live_available else None
    forecast_score = _clamp_score(analysis.get("venue_forecasted_busyness"))
    week_profile = _extract_week_raw(forecast_payload or live_payload)
    today_index = datetime.now().weekday()
    today_scores = week_profile[today_index] if today_index < len(week_profile) else []
    today_profile = [_hour_score(today_index, hour, score) for hour, score in enumerate(today_scores)]
    current_hour = None
    if today_scores:
        hour = datetime.now().hour
        current_hour = _hour_score(today_index, hour, today_scores[hour])
        busiest_hour = _hour_score(today_index, max(range(24), key=lambda index: today_scores[index]), max(today_scores))
        quietest_hour = _hour_score(today_index, min(range(24), key=lambda index: today_scores[index]), min(today_scores))
    else:
        busiest_hour = None
        quietest_hour = None

    notes = [
        "BestTime scores are relative busyness percentages, not absolute visitor counts.",
    ]
    if not week_profile:
        notes.append("Hourly best-time forecast was not available for this venue.")

    return {
        "venue_name": venue_name,
        "venue_address": venue_address,
        "traffic_score": live_score if live_score is not None else forecast_score,
        "forecast_traffic_score": forecast_score,
        "live_available": live_available,
        "score_source": "besttime_live" if live_score is not None else "besttime_forecast",
        "status": "available",
        "best_time_label": (
            f"{busiest_hour['day']} at {busiest_hour['hour_label']}"
            if busiest_hour else None
        ),
        "worst_time_label": (
            f"{quietest_hour['day']} at {quietest_hour['hour_label']}"
            if quietest_hour else None
        ),
        "current_hour": current_hour,
        "busiest_hour": busiest_hour,
        "quietest_hour": quietest_hour,
        "today_profile": today_profile,
        "week_peak_windows": _extract_peak_windows(forecast_payload or live_payload, week_profile),
        "data_notes": notes,
    }
