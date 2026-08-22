from pydantic import BaseModel

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# INPUT SCHEMA
class FinalVisitorDataCreate(BaseModel):
    city: str
    local_date: date
    avg_daily_visits: float
    location_name: str
    brand: str
    street_address: Optional[str] = None
    latitude: float
    longitude: float


# OUTPUT SCHEMA
class FinalVisitorDataResponse(BaseModel):
    id: int

    city: str
    local_date: date
    avg_daily_visits: float
    location_name: str
    brand: str
    street_address: Optional[str]
    latitude: float
    longitude: float

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)