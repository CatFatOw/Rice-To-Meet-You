from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

# INPUT SCHEMAS
class WeatherObservationCreate(BaseModel):
    grid_cell_id: int

    timestamp: datetime

    temperature: Optional[float] = None
    humidity: Optional[float] = None
    dewpoint: Optional[float] = None

    wind_direction: Optional[str] = None

    precipitation_prob: Optional[float] = None

    detailed_forecast: Optional[str] = None

    source: str = "NWS"


# RESPONSE SCHEMAS
class WeatherObservationResponse(BaseModel):
    id: int

    grid_cell_id: int

    timestamp: datetime

    temperature: Optional[float]
    humidity: Optional[float]
    dewpoint: Optional[float]

    wind_direction: Optional[str]

    precipitation_prob: Optional[float]

    detailed_forecast: Optional[str]

    source: str

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
