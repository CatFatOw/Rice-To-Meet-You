from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FoursquarePlaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fsq_place_id: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    category: str | None = None
    address: str | None = None
    distance_m: int = Field(ge=0)
    visitor_count: int | None = None
    visitor_count_status: Literal["unavailable_free_places"]


class FoursquareLookupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requested_time: datetime | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: int = Field(ge=1, le=100000)
    fetched_at: datetime
    historical_visitor_counts_available: bool = False
    places: list[FoursquarePlaceResponse]
