from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Request schemas
# ============================================================

WeatherTimeline = Literal["current", "hourly", "daily"]


class Coordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class OpenMeteoForecastRequest(Coordinates):
    current: list[str] | None = None
    hourly: list[str] | None = None
    daily: list[str] | None = None

    forecast_days: int = Field(default=7, ge=1, le=16)
    timezone: str = "auto"

    temperature_unit: Literal["celsius", "fahrenheit"] = "celsius"
    wind_speed_unit: Literal["kmh", "ms", "mph", "kn"] = "kmh"
    precipitation_unit: Literal["mm", "inch"] = "mm"


# ============================================================
# Current-weather response
# ============================================================

class OpenMeteoCurrentUnits(BaseModel):
    model_config = ConfigDict(extra="allow")

    time: str | None = None
    interval: str | None = None

    temperature_2m: str | None = None
    relative_humidity_2m: str | None = None
    apparent_temperature: str | None = None
    is_day: str | None = None

    precipitation: str | None = None
    rain: str | None = None
    showers: str | None = None
    snowfall: str | None = None

    weather_code: str | None = None
    cloud_cover: str | None = None

    pressure_msl: str | None = None
    surface_pressure: str | None = None

    wind_speed_10m: str | None = None
    wind_direction_10m: str | None = None
    wind_gusts_10m: str | None = None


class OpenMeteoCurrent(BaseModel):
    model_config = ConfigDict(extra="allow")

    time: str
    interval: int | None = None

    temperature_2m: float | None = None
    relative_humidity_2m: float | None = None
    apparent_temperature: float | None = None
    is_day: int | None = None

    precipitation: float | None = None
    rain: float | None = None
    showers: float | None = None
    snowfall: float | None = None

    weather_code: int | None = None
    cloud_cover: float | None = None

    pressure_msl: float | None = None
    surface_pressure: float | None = None

    wind_speed_10m: float | None = None
    wind_direction_10m: float | None = None
    wind_gusts_10m: float | None = None


# ============================================================
# Hourly response
# ============================================================

class OpenMeteoHourlyUnits(BaseModel):
    """
    Open-Meteo unit values are strings such as °C, %, mm, km/h, and W/m².

    extra="allow" means newly requested or newly introduced Open-Meteo
    variables will not break response validation.
    """

    model_config = ConfigDict(extra="allow")

    time: str | None = None

    temperature_2m: str | None = None
    relative_humidity_2m: str | None = None
    dew_point_2m: str | None = None
    apparent_temperature: str | None = None
    wet_bulb_temperature_2m: str | None = None

    precipitation_probability: str | None = None
    precipitation: str | None = None
    rain: str | None = None
    showers: str | None = None
    snowfall: str | None = None
    snow_depth: str | None = None

    weather_code: str | None = None
    is_day: str | None = None

    pressure_msl: str | None = None
    surface_pressure: str | None = None

    cloud_cover: str | None = None
    cloud_cover_low: str | None = None
    cloud_cover_mid: str | None = None
    cloud_cover_high: str | None = None
    visibility: str | None = None

    evapotranspiration: str | None = None
    et0_fao_evapotranspiration: str | None = None
    vapour_pressure_deficit: str | None = None

    wind_speed_10m: str | None = None
    wind_speed_80m: str | None = None
    wind_speed_120m: str | None = None
    wind_speed_180m: str | None = None

    wind_direction_10m: str | None = None
    wind_direction_80m: str | None = None
    wind_direction_120m: str | None = None
    wind_direction_180m: str | None = None
    wind_gusts_10m: str | None = None

    temperature_80m: str | None = None
    temperature_120m: str | None = None
    temperature_180m: str | None = None

    soil_temperature_0cm: str | None = None
    soil_temperature_6cm: str | None = None
    soil_temperature_18cm: str | None = None
    soil_temperature_54cm: str | None = None

    soil_moisture_0_to_1cm: str | None = None
    soil_moisture_1_to_3cm: str | None = None
    soil_moisture_3_to_9cm: str | None = None
    soil_moisture_9_to_27cm: str | None = None
    soil_moisture_27_to_81cm: str | None = None

    uv_index: str | None = None
    uv_index_clear_sky: str | None = None
    sunshine_duration: str | None = None

    total_column_integrated_water_vapour: str | None = None
    cape: str | None = None
    lifted_index: str | None = None
    convective_inhibition: str | None = None

    freezing_level_height: str | None = None
    boundary_layer_height: str | None = None

    shortwave_radiation: str | None = None
    direct_radiation: str | None = None
    diffuse_radiation: str | None = None
    direct_normal_irradiance: str | None = None
    global_tilted_irradiance: str | None = None
    terrestrial_radiation: str | None = None

    shortwave_radiation_instant: str | None = None
    direct_radiation_instant: str | None = None
    diffuse_radiation_instant: str | None = None
    direct_normal_irradiance_instant: str | None = None
    global_tilted_irradiance_instant: str | None = None
    terrestrial_radiation_instant: str | None = None


class OpenMeteoHourly(BaseModel):
    model_config = ConfigDict(extra="allow")

    time: list[str]

    temperature_2m: list[float | None] | None = None
    relative_humidity_2m: list[float | None] | None = None
    dew_point_2m: list[float | None] | None = None
    apparent_temperature: list[float | None] | None = None
    wet_bulb_temperature_2m: list[float | None] | None = None

    precipitation_probability: list[int | None] | None = None
    precipitation: list[float | None] | None = None
    rain: list[float | None] | None = None
    showers: list[float | None] | None = None
    snowfall: list[float | None] | None = None
    snow_depth: list[float | None] | None = None

    weather_code: list[int | None] | None = None
    is_day: list[int | None] | None = None

    pressure_msl: list[float | None] | None = None
    surface_pressure: list[float | None] | None = None

    cloud_cover: list[float | None] | None = None
    cloud_cover_low: list[float | None] | None = None
    cloud_cover_mid: list[float | None] | None = None
    cloud_cover_high: list[float | None] | None = None
    visibility: list[float | None] | None = None

    evapotranspiration: list[float | None] | None = None
    et0_fao_evapotranspiration: list[float | None] | None = None
    vapour_pressure_deficit: list[float | None] | None = None

    wind_speed_10m: list[float | None] | None = None
    wind_speed_80m: list[float | None] | None = None
    wind_speed_120m: list[float | None] | None = None
    wind_speed_180m: list[float | None] | None = None

    wind_direction_10m: list[float | None] | None = None
    wind_direction_80m: list[float | None] | None = None
    wind_direction_120m: list[float | None] | None = None
    wind_direction_180m: list[float | None] | None = None
    wind_gusts_10m: list[float | None] | None = None

    temperature_80m: list[float | None] | None = None
    temperature_120m: list[float | None] | None = None
    temperature_180m: list[float | None] | None = None

    soil_temperature_0cm: list[float | None] | None = None
    soil_temperature_6cm: list[float | None] | None = None
    soil_temperature_18cm: list[float | None] | None = None
    soil_temperature_54cm: list[float | None] | None = None

    soil_moisture_0_to_1cm: list[float | None] | None = None
    soil_moisture_1_to_3cm: list[float | None] | None = None
    soil_moisture_3_to_9cm: list[float | None] | None = None
    soil_moisture_9_to_27cm: list[float | None] | None = None
    soil_moisture_27_to_81cm: list[float | None] | None = None

    uv_index: list[float | None] | None = None
    uv_index_clear_sky: list[float | None] | None = None
    sunshine_duration: list[float | None] | None = None

    total_column_integrated_water_vapour: list[float | None] | None = None
    cape: list[float | None] | None = None
    lifted_index: list[float | None] | None = None
    convective_inhibition: list[float | None] | None = None

    freezing_level_height: list[float | None] | None = None
    boundary_layer_height: list[float | None] | None = None

    shortwave_radiation: list[float | None] | None = None
    direct_radiation: list[float | None] | None = None
    diffuse_radiation: list[float | None] | None = None
    direct_normal_irradiance: list[float | None] | None = None
    global_tilted_irradiance: list[float | None] | None = None
    terrestrial_radiation: list[float | None] | None = None

    shortwave_radiation_instant: list[float | None] | None = None
    direct_radiation_instant: list[float | None] | None = None
    diffuse_radiation_instant: list[float | None] | None = None
    direct_normal_irradiance_instant: list[float | None] | None = None
    global_tilted_irradiance_instant: list[float | None] | None = None
    terrestrial_radiation_instant: list[float | None] | None = None


# ============================================================
# Daily response
# ============================================================

class OpenMeteoDailyUnits(BaseModel):
    model_config = ConfigDict(extra="allow")

    time: str | None = None
    weather_code: str | None = None

    temperature_2m_max: str | None = None
    temperature_2m_min: str | None = None

    apparent_temperature_max: str | None = None
    apparent_temperature_min: str | None = None

    sunrise: str | None = None
    sunset: str | None = None
    daylight_duration: str | None = None
    sunshine_duration: str | None = None

    uv_index_max: str | None = None
    uv_index_clear_sky_max: str | None = None

    precipitation_sum: str | None = None
    rain_sum: str | None = None
    showers_sum: str | None = None
    snowfall_sum: str | None = None

    precipitation_hours: str | None = None
    precipitation_probability_max: str | None = None

    wind_speed_10m_max: str | None = None
    wind_gusts_10m_max: str | None = None
    wind_direction_10m_dominant: str | None = None

    shortwave_radiation_sum: str | None = None
    et0_fao_evapotranspiration: str | None = None


class OpenMeteoDaily(BaseModel):
    model_config = ConfigDict(extra="allow")

    time: list[str]

    weather_code: list[int | None] | None = None

    temperature_2m_max: list[float | None] | None = None
    temperature_2m_min: list[float | None] | None = None

    apparent_temperature_max: list[float | None] | None = None
    apparent_temperature_min: list[float | None] | None = None

    sunrise: list[str | None] | None = None
    sunset: list[str | None] | None = None
    daylight_duration: list[float | None] | None = None
    sunshine_duration: list[float | None] | None = None

    uv_index_max: list[float | None] | None = None
    uv_index_clear_sky_max: list[float | None] | None = None

    precipitation_sum: list[float | None] | None = None
    rain_sum: list[float | None] | None = None
    showers_sum: list[float | None] | None = None
    snowfall_sum: list[float | None] | None = None

    precipitation_hours: list[float | None] | None = None
    precipitation_probability_max: list[int | None] | None = None

    wind_speed_10m_max: list[float | None] | None = None
    wind_gusts_10m_max: list[float | None] | None = None
    wind_direction_10m_dominant: list[float | None] | None = None

    shortwave_radiation_sum: list[float | None] | None = None
    et0_fao_evapotranspiration: list[float | None] | None = None


# ============================================================
# Complete Open-Meteo response
# ============================================================

class OpenMeteoForecastResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Location metadata returned by Open-Meteo
    latitude: float
    longitude: float
    elevation: float | None = None

    generationtime_ms: float | None = None
    utc_offset_seconds: int | None = None
    timezone: str | None = None
    timezone_abbreviation: str | None = None

    # Included only when requested
    current_units: OpenMeteoCurrentUnits | None = None
    current: OpenMeteoCurrent | None = None

    hourly_units: OpenMeteoHourlyUnits | None = None
    hourly: OpenMeteoHourly | None = None

    daily_units: OpenMeteoDailyUnits | None = None
    daily: OpenMeteoDaily | None = None



class OpenMeteoForecastCreate(BaseModel):
    """Internal persistence payload for a fetched Open-Meteo response."""

    latitude: float
    longitude: float
    elevation: float | None = None
    timezone: str | None = None
    timezone_abbreviation: str | None = None
    utc_offset_seconds: int | None = None
    generation_time_ms: float | None = None
    response_data: dict[str, Any]
    requested_current: list[str] | None = None
    requested_hourly: list[str] | None = None
    requested_daily: list[str] | None = None
    forecast_days: int | None = None


class OpenMeteoForecastRecordResponse(BaseModel):
    """Saved forecast metadata plus the original Open-Meteo response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    latitude: float
    longitude: float
    elevation: float | None = None
    timezone: str | None = None
    timezone_abbreviation: str | None = None
    utc_offset_seconds: int | None = None
    generation_time_ms: float | None = None
    response_data: dict[str, Any]
    requested_current: list[str] | None = None
    requested_hourly: list[str] | None = None
    requested_daily: list[str] | None = None
    forecast_days: int | None = None
    source: str
    fetched_at: datetime
    created_at: datetime
