from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GoogleTrafficRouteSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    duration_seconds: int = Field(ge=0)
    static_duration_seconds: int = Field(ge=0)
    delay_seconds: int = Field(ge=0)
    distance_meters: int | None = Field(default=None, ge=0)
    congestion_percent: int = Field(ge=0, le=100)


class GooglePoiAnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue_name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category: str | None = None
    radius_m: int = Field(ge=100, le=5000)
    traffic_score: int | None = Field(default=None, ge=0, le=100)
    traffic_status: Literal["unavailable", "light", "moderate", "heavy", "severe"]
    average_delay_seconds: int | None = Field(default=None, ge=0)
    route_samples: list[GoogleTrafficRouteSample] = Field(default_factory=list)
    nearby_place_count: int | None = Field(default=None, ge=0)
    nearby_place_type: str | None = None
    visitor_analytics_available: bool = False
    data_source: Literal["google_routes_places_aggregate"]
    data_notes: list[str] = Field(default_factory=list)
