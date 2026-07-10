from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# Heat Data ML Schemas
# =========================================================

class HeatDataMLBase(BaseModel):
    """Shared fields for creating and returning heat ML data."""

    date: Optional[datetime] = None

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    avg_temp_c: float
    relative_humidity: float = Field(..., ge=0, le=100)
    wind_speed_knots: float = Field(..., ge=0)
    urban_heat_idx: float

    source: str = "interpolated"

    distance_nearest_station_km: Optional[float] = Field(
        default=0.0,
        ge=0,
    )
    passed_threshold: Optional[bool] = True


class HeatDataMLCreate(HeatDataMLBase):
    """Schema used when creating a heat-data record."""

    pass


class HeatDataMLResponse(HeatDataMLBase):
    """Schema returned from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int


# =========================================================
# Visitor Data ML Schemas
# =========================================================

class VisitorDataMLBase(BaseModel):
    """Shared fields for creating and returning visitor ML data."""

    date: Optional[datetime] = None

    market: str = Field(..., min_length=1)
    source_market: Optional[str] = None

    fsq_place_id: Optional[str] = None
    name: Optional[str] = None

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    category: Optional[str] = None

    visitor_count: Optional[int] = Field(default=None, ge=0)
    visitor_count_source: Optional[str] = None

    market_brand_visitor_count_total: Optional[int] = Field(
        default=None,
        ge=0,
    )
    candidate_foursquare_poi_count: Optional[int] = Field(
        default=None,
        ge=0,
    )

    match_status: Optional[str] = None
    visitor_categories: Optional[str] = None

    nearest_heat_distance_km: Optional[float] = Field(
        default=None,
        ge=0,
    )
    query_center_distance_m: Optional[float] = Field(
        default=None,
        ge=0,
    )

    google_maps_congestion: Optional[float] = Field(
        default=None,
        ge=0,
    )


class VisitorDataMLCreate(VisitorDataMLBase):
    """Schema used when creating a visitor-data record."""

    pass


class VisitorDataMLResponse(VisitorDataMLBase):
    """Schema returned from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class PredictionModelCsvImportResponse(BaseModel):
    """Response returned after importing prediction-model rows from CSV."""

    filename: str
    imported_count: int
    error_count: int
    errors: list[str] = []
