from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BestTimeHourScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: str
    hour: int = Field(ge=0, le=23)
    hour_label: str
    score: int = Field(ge=0, le=100)


class BestTimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: str
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=24)
    start_label: str
    end_label: str
    score: int = Field(ge=0, le=100)


class BestTimeTrafficResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue_name: str
    venue_address: str
    traffic_score: int | None = Field(default=None, ge=0)
    forecast_traffic_score: int | None = Field(default=None, ge=0, le=100)
    live_available: bool = False
    score_source: Literal["besttime_live", "besttime_forecast", "besttime_unavailable"]
    status: Literal["available", "unavailable"]
    best_time_label: str | None = None
    worst_time_label: str | None = None
    current_hour: BestTimeHourScore | None = None
    busiest_hour: BestTimeHourScore | None = None
    quietest_hour: BestTimeHourScore | None = None
    today_profile: list[BestTimeHourScore] = Field(default_factory=list)
    week_peak_windows: list[BestTimeWindow] = Field(default_factory=list)
    data_notes: list[str] = Field(default_factory=list)
