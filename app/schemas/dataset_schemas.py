from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _unknown_if_empty(value):
    """Keep required text columns non-null when source datasets omit labels."""
    if value is None:
        return "Unknown"
    if isinstance(value, str) and value.strip() == "":
        return "Unknown"
    return value


def _empty_dict_if_missing(value):
    if value is None:
        return {}
    return value


def _empty_list_if_missing(value):
    if value is None:
        return []
    return value


# -----------------------INPUT SCHEMA----------------------
class CorePoiGeometryCreate(BaseModel):
    brands: Optional[list[dict[str, Any]]] = None
    category_tags: Optional[list[str]] = None
    city: str
    closed_on: Optional[date] = None
    domains: Optional[list[str]] = None

    enclosed: bool
    geometry_type: str
    includes_parking_lot: bool
    iso_country_code: str
    is_synthetic: bool

    latitude: float
    location_name: str
    longitude: float
    market: str

    naics_code: Optional[int] = None
    naics_code_2022: Optional[int] = None
    opened_on: Optional[date] = None
    open_hours: Optional[dict[str, Any]] = None

    parent_placekey: Optional[str] = None
    phone_number: Optional[str] = None
    placekey: str

    polygon_class: str
    polygon_wkt: str
    postal_code: str
    region: str
    safegraph_place_id: str
    store_id: Optional[str] = None
    street_address: str
    sub_category: str = "Unknown"
    sub_category_2022: str = "Unknown"
    top_category: str = "Unknown"
    top_category_2022: str = "Unknown"
    tracking_closed_since: Optional[date] = None
    website: Optional[str] = None
    wkt_area_sq_meters: float

    _category_defaults = field_validator(
        "sub_category",
        "sub_category_2022",
        "top_category",
        "top_category_2022",
        mode="before",
    )(_unknown_if_empty)


class DailySpendBrandStateCreate(BaseModel):
    brand_id: int
    brand_name: str
    market: str
    spend_amount: float
    state_abbr: str
    trans_count: float
    trans_date: date
    version: str

class DailyWeatherRiceCreate(BaseModel):
    average_dew_point_f: float
    average_relative_humidity: float
    average_sea_level_pressure_millibars: float
    average_temperature_c: float
    average_visibility_km: float
    average_wind_speed_knots: float
    city_location_identifier: str
    cooling_degree_days_c: float
    heating_degree_days_c: float
    max_temperature_c: float
    min_temperature_c: float
    precipitation: int
    valid_date: date



class SpendPatternsRiceCreate(BaseModel):
    brands: str | None = None

    bucketed_customer_frequency: dict[str, Any]
    bucketed_customer_incomes: dict[str, Any]

    city: str
    customer_home_city: dict[str, Any]
    day_counts: dict[str, Any]

    iso_country_code: str

    latitude: float
    longitude: float
    location_name: str
    market: str

    mean_spend_per_customer_by_frequency: dict[str, Any]
    mean_spend_per_customer_by_income: dict[str, Any]

    median_spend_per_customer: float
    median_spend_per_transaction: float

    naics_code: int

    online_spend: float
    online_transactions: float

    parent_placekey: Optional[str] = None
    placekey: str

    postal_code: str

    raw_num_customers: float
    raw_num_transactions: float
    raw_total_spend: float

    region: str

    related_buynowpaylater_service_pct: Optional[dict[str, Any]] = None
    related_cross_shopping_local_brands_pct: Optional[dict[str, Any]] = None
    related_cross_shopping_online_merchants_pct: Optional[dict[str, Any]] = None
    related_cross_shopping_physical_brands_pct: Optional[dict[str, Any]] = None
    related_cross_shopping_same_category_brands_pct: Optional[dict[str, Any]] = None
    related_delivery_service_pct: Optional[dict[str, Any]] = None
    related_payment_platform_pct: Optional[dict[str, Any]] = None
    related_rideshare_service_pct: Optional[dict[str, Any]] = None
    related_streaming_cable_pct: Optional[dict[str, Any]] = None
    related_wireless_carrier_pct: Optional[dict[str, Any]] = None

    spend_by_day: list[float | int | None]
    spend_by_day_of_week: dict[str, Any]
    spend_by_transaction_intermediary: Optional[dict[str, Any]] = None

    spend_per_transaction_by_day: list[float | int | None]
    spend_date_range_start: date
    spend_date_range_end: date

    spend_pct_change_vs_prev_month: Optional[float] = None
    spend_pct_change_vs_prev_year: Optional[float] = None

    spend_per_transaction_percentiles: dict[str, Any]

    street_address: str
    sub_category: str = "Unknown"
    top_category: str = "Unknown"

    transaction_intermediary: Optional[dict[str, Any]] = None

    _category_defaults = field_validator(
        "sub_category",
        "top_category",
        mode="before",
    )(_unknown_if_empty)
    _required_dict_defaults = field_validator(
        "bucketed_customer_frequency",
        "bucketed_customer_incomes",
        "customer_home_city",
        "day_counts",
        "mean_spend_per_customer_by_frequency",
        "mean_spend_per_customer_by_income",
        "spend_by_day_of_week",
        "spend_per_transaction_percentiles",
        mode="before",
    )(_empty_dict_if_missing)
    _required_list_defaults = field_validator(
        "spend_by_day",
        "spend_per_transaction_by_day",
        mode="before",
    )(_empty_list_if_missing)


class StoreVisitsCreate(BaseModel):
    brand: str
    category: str
    daily_visits: int
    local_date: date
    market: str
    naics_code: int
    business_name: str
    state: str
    stock_exchange: Optional[str] = None
    stock_symbol: Optional[str] = None
    store_id: str
    sub_category: str = "Unknown"
    version_id: int

    _category_defaults = field_validator("sub_category", mode="before")(_unknown_if_empty)


class UrbanHeatIndexCreate(BaseModel):
    latitude: float
    longitude: float
    market: str
    point_geometry: str
    uhi: int


#----------------------END OF INPUT SCHEMA------------------


# ----------------------RESPONSE SCHEMA-----------------------
class CorePoiGeometryResponse(BaseModel):
    id: int

    brands: Optional[list[dict[str, Any]]] = None
    category_tags: Optional[list[str]] = None
    city: str
    closed_on: Optional[date] = None
    domains: Optional[list[str]] = None

    enclosed: bool
    geometry_type: str
    includes_parking_lot: bool
    iso_country_code: str
    is_synthetic: bool

    latitude: float
    location_name: str
    longitude: float
    market: str

    naics_code: Optional[int] = None
    naics_code_2022: Optional[int] = None
    opened_on: Optional[date] = None
    open_hours: Optional[dict[str, Any]] = None

    parent_placekey: Optional[str] = None
    phone_number: Optional[str] = None
    placekey: str

    polygon_class: str
    polygon_wkt: str
    postal_code: str
    region: str
    safegraph_place_id: str
    store_id: Optional[str] = None
    street_address: str
    sub_category: str
    sub_category_2022: str
    top_category: str
    top_category_2022: str
    tracking_closed_since: Optional[date] = None
    website: Optional[str] = None
    wkt_area_sq_meters: float

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailySpendBrandStateResponse(BaseModel):
    id: int

    brand_id: int
    brand_name: str
    market: str
    spend_amount: float
    state_abbr: str
    trans_count: float
    trans_date: date
    version: str

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DailyWeatherRiceResponse(BaseModel):
    id: int

    average_dew_point_f: float
    average_relative_humidity: float
    average_sea_level_pressure_millibars: float
    average_temperature_c: float
    average_visibility_km: float
    average_wind_speed_knots: float
    city_location_identifier: str
    cooling_degree_days_c: float
    heating_degree_days_c: float
    max_temperature_c: float
    min_temperature_c: float
    precipitation: int
    valid_date: date

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpendPatternsRiceResponse(BaseModel):
    id: int

    brands: str | None = None

    bucketed_customer_frequency: dict[str, Any]
    bucketed_customer_incomes: dict[str, Any]

    city: str
    customer_home_city: dict[str, Any]
    day_counts: dict[str, Any]

    iso_country_code: str

    latitude: float
    longitude: float
    location_name: str
    market: str

    mean_spend_per_customer_by_frequency: dict[str, Any]
    mean_spend_per_customer_by_income: dict[str, Any]

    median_spend_per_customer: float
    median_spend_per_transaction: float

    naics_code: int

    online_spend: float
    online_transactions: float

    parent_placekey: Optional[str] = None
    placekey: str

    postal_code: str

    raw_num_customers: float
    raw_num_transactions: float
    raw_total_spend: float

    region: str

    related_buynowpaylater_service_pct: Optional[dict[str, Any]] = None
    related_cross_shopping_local_brands_pct: Optional[dict[str, Any]] = None
    related_cross_shopping_online_merchants_pct: Optional[dict[str, Any]] = None
    related_cross_shopping_physical_brands_pct: Optional[dict[str, Any]] = None
    related_cross_shopping_same_category_brands_pct: Optional[dict[str, Any]] = None
    related_delivery_service_pct: Optional[dict[str, Any]] = None
    related_payment_platform_pct: Optional[dict[str, Any]] = None
    related_rideshare_service_pct: Optional[dict[str, Any]] = None
    related_streaming_cable_pct: Optional[dict[str, Any]] = None
    related_wireless_carrier_pct: Optional[dict[str, Any]] = None

    spend_by_day: list[float | int | None]
    spend_by_day_of_week: dict[str, Any]
    spend_by_transaction_intermediary: Optional[dict[str, Any]] = None

    spend_per_transaction_by_day: list[float | int | None]

    spend_date_range_start: date
    spend_date_range_end: date

    spend_pct_change_vs_prev_month: Optional[float] = None
    spend_pct_change_vs_prev_year: Optional[float] = None

    spend_per_transaction_percentiles: dict[str, Any]

    street_address: str
    sub_category: str
    top_category: str

    transaction_intermediary: Optional[dict[str, Any]] = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class StoreVisitsResponse(BaseModel):
    id: int

    brand: str
    category: str
    daily_visits: int
    local_date: date
    market: str
    naics_code: int
    business_name: str
    state: str
    stock_exchange: Optional[str] = None
    stock_symbol: Optional[str] = None
    store_id: str
    sub_category: str
    version_id: int

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UrbanHeatIndexResponse(BaseModel):
    id: int

    latitude: float
    longitude: float
    market: str
    point_geometry: str
    uhi: int

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetCsvImportResponse(BaseModel):
    dataset: str
    inserted_count: int
    errors: list[str] = Field(default_factory=list)

