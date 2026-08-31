"""
=============================================================================
Urban heat intervention simulation
=============================================================================

Estimates how planner-placed cooling interventions change pedestrian-level
temperature (and, where relevant, relative humidity) across a heatmap of point
readings grouped by date.

Four intervention archetypes are modelled, each with its own physics:
  1. Vegetation          — latent (transpiration) + shade cooling over a polygon
  2. High-albedo surface — reflects more solar over a polygon
  3. Shade structure     — blocks the direct solar beam over a polygon
  4. Evaporative/water   — misting/fountain plume from a point source

Shared shape of every model:
  - A weather-derived ceiling ΔT_max (the most cooling physically available
    under the current conditions).
  - A dimensionless intensity in [0, 1] derived from the planner's inputs.
  - delta_t = ΔT_max × intensity, applied to the initial temperature.

Sign convention (IMPORTANT): every model returns `final_temp` plus a SIGNED
`delta_t`, where negative means cooling. The internal magnitude computed before
the return is positive; the returned field negates it.

The public entry point is `get_simulated_points_by_date`, which delegates to
`run_diminishing_return_simulation` and returns just the readings.

Copy semantics: the baseline `points_by_date` is never mutated. Simulated
points are SHALLOW copies of their source, which is sufficient because every
write is a top-level key rebind -- `value` is reassigned and
`individual_metrics` is replaced with a freshly built dict, never mutated in
place. `location_coordinates` is only ever read. Points that no intervention
touches are copied but otherwise passed through unchanged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, NamedTuple

from schemas.simulation_schemas import (
    BasePlacedObject,
    BasePlacedObjectCategorized,
    Coordinates,
    Geometry,
    HeatmapMetricValue,
    HeatmapPointsByDate,
    Polygon,
)
from services.parsers import parse_percentage, parse_temperature


class CoolingResult(NamedTuple):
    """Return shape shared by all four cooling models."""

    final_temp: float  # °C after the intervention
    delta_t: float     # SIGNED change (negative = cooling)


# --- Vegetation cooling model ------------------------------------------------
# Estimates the pedestrian-level temperature drop from vegetation via two
# channels — latent (transpiration) and shade — combined into a 0–1 intensity
# and scaled to a ΔT. See derivation for the physics behind each step.


@dataclass(frozen=True)
class VegetationCoolingParams:
    """Planner-chosen inputs for a cell/archetype. All fractions are 0–1."""

    vegetated_coverage: float  # 0–1  fraction of ground with vegetation
    canopy_fraction: float     # 0–1  fraction of that vegetation under crown
    lai: float                 # ~0–6 Leaf Area Index (dimensionless)
    water_factor: float        # 0–1  water availability / irrigation gate


@dataclass(frozen=True)
class WeatherParams:
    """Environmental inputs that set the cooling ceiling (ΔT_max).

    Temperature and humidity drive the ET potential via VPD; solar and wind are
    held at 1 unless you have data to scale them.
    """

    temperature_c: float       # °C    air temperature
    relative_humidity: float   # 0–100 (percent) relative humidity
    f_solar: float = 1.0       # 0–1   insolation multiplier
    f_wind: float = 1.0        # 0–1   wind multiplier


# --- Model constants (the real calibration knobs) ---------------------------
# These encode model physics, not planner choices — point literature-fitting
# here rather than at the four inputs.
SHADE_DROUGHT_SURVIVAL = 0.8  # g: shade effect surviving water_factor=0 (~0.7–0.85)
WEIGHT_LATENT = 0.4           # w_L: relative weight of the latent/ET channel
WEIGHT_SHADE = 0.6            # w_S: relative weight of the shade channel (w_L + w_S = 1)
LAI_EXTINCTION = 0.5          # Beer–Lambert extinction coefficient in f_LAI
DELTA_T_MAX_ANCHOR = 5.0      # °C: cooling asymptote under hot-dry-sunny-calm conditions
VPD_REF = 4.5                 # kPa: peak-case VPD normalizing f_VPD (38 °C / 28% RH ≈ 4.8)


def saturation_vapor_pressure(temperature_c: float) -> float:
    """Saturation vapor pressure (kPa) from air temperature (°C) — Tetens.

    The maximum water vapor the air can hold at the given temperature; rises
    steeply with heat, which is why hot air has more evaporative "room".
    """
    return 0.6108 * math.exp((17.27 * temperature_c) / (temperature_c + 237.3))


def vapor_pressure_deficit(temperature_c: float, relative_humidity: float) -> float:
    """Vapor pressure deficit (kPa).

    The gap between how much moisture the air could hold and how much it
    currently holds. Larger VPD = drier air = more evaporative cooling
    potential.

    :param temperature_c:     air temperature (°C)
    :param relative_humidity: relative humidity (0–100)
    """
    return saturation_vapor_pressure(temperature_c) * (1 - relative_humidity / 100)


def delta_t_max_from_weather(weather: WeatherParams) -> float:
    """Weather-dependent cooling ceiling for vegetation.

        ΔT_max = 5 °C × f_VPD × f_solar × f_wind

    f_VPD scales the anchor by how dry the air is (capped at 1 at the reference
    VPD); f_solar and f_wind default to 1 unless real data is supplied.
    """
    vpd = vapor_pressure_deficit(weather.temperature_c, weather.relative_humidity)
    f_vpd = min(vpd / VPD_REF, 1.0)  # normalize to [0, 1] against the peak-case VPD

    return DELTA_T_MAX_ANCHOR * f_vpd * weather.f_solar * weather.f_wind


def vegetation_cooling(
    initial_temp: float,
    params: VegetationCoolingParams,
    delta_t_max: float | WeatherParams = DELTA_T_MAX_ANCHOR,
) -> CoolingResult:
    """Compute vegetation cooling for one cell.

    :param initial_temp: starting temperature at the cell (°C)
    :param params:       planner-chosen vegetation inputs
    :param delta_t_max:  either a fixed ceiling (°C) or WeatherParams to derive one
    :returns: CoolingResult — delta_t is SIGNED (negative = cooling).
    """
    # Accept a precomputed ceiling, or derive it from weather.
    delta_t_max_c = (
        delta_t_max
        if isinstance(delta_t_max, (int, float))
        else delta_t_max_from_weather(delta_t_max)
    )

    # Step 1 — saturating LAI transform (Beer–Lambert), not linear.
    # Extra leaf area gives diminishing returns as the canopy closes.
    f_lai = 1 - math.exp(-LAI_EXTINCTION * params.lai)

    # Step 2 — the two cooling channels.
    # Latent: transpiration, gated fully by water availability.
    latent = params.vegetated_coverage * f_lai * params.water_factor
    # Shade: canopy blocking sun; partly survives drought (leaves still cast
    # shade even when transpiration stops), per SHADE_DROUGHT_SURVIVAL.
    shade = (
        params.vegetated_coverage
        * params.canopy_fraction
        * f_lai
        * (SHADE_DROUGHT_SURVIVAL + (1 - SHADE_DROUGHT_SURVIVAL) * params.water_factor)
    )

    # Step 3 — combine into normalized intensity (0–1) via the channel weights.
    intensity = WEIGHT_LATENT * latent + WEIGHT_SHADE * shade

    # Step 4 — scale to a temperature drop, then apply to the initial temp.
    delta_t = delta_t_max_c * intensity  # positive magnitude
    final_temp = initial_temp - delta_t

    return CoolingResult(final_temp, -delta_t)  # negate so callers see cooling as < 0


# --- High-albedo (cool surface) cooling model -------------------------------
# Cool coatings/pavements reflect more solar: absorbed solar = (1 − albedo) ×
# irradiance, so raising albedo by Δalbedo cuts surface heating proportionally.


@dataclass(frozen=True)
class AlbedoCoolingParams:
    """Planner-chosen inputs for a high-albedo surface. All fractions are 0–1."""

    delta_albedo: float   # 0–1  increase in solar reflectance vs baseline
    area_coverage: float  # 0–1  treated fraction of the cell (linear)


@dataclass(frozen=True)
class AlbedoWeatherParams:
    """Environmental inputs — albedo cooling scales with SOLAR loading."""

    temperature_c: float  # °C   air temperature (solar-loading proxy)
    f_solar: float = 1.0  # 0–1  insolation multiplier


DELTA_T_MAX_ANCHOR_ALBEDO = 4.0  # °C: pedestrian-air cooling asymptote
DELTA_ALBEDO_REF = 0.7           # peak realistic albedo increase (→ f_albedo = 1)
SOLAR_PROXY_T_LOW = 20.0         # °C at/below which thermal loading ≈ minimal
SOLAR_PROXY_T_HIGH = 38.0        # °C at/above which thermal loading ≈ peak


def delta_t_max_from_weather_albedo(weather: AlbedoWeatherParams) -> float:
    """Weather ceiling for high-albedo surfaces.

        ΔT_max = 4 °C × f_thermal × f_solar

    There is no VPD term (reflectance doesn't depend on humidity); instead a
    temperature-based f_thermal ramps linearly from 0 at SOLAR_PROXY_T_LOW to 1
    at SOLAR_PROXY_T_HIGH, standing in for solar loading.
    """
    span = SOLAR_PROXY_T_HIGH - SOLAR_PROXY_T_LOW
    # Clamp the linear ramp to [0, 1].
    f_thermal = min(max((weather.temperature_c - SOLAR_PROXY_T_LOW) / span, 0.0), 1.0)

    return DELTA_T_MAX_ANCHOR_ALBEDO * f_thermal * weather.f_solar


def albedo_cooling(
    initial_temp: float,
    params: AlbedoCoolingParams,
    delta_t_max: float | AlbedoWeatherParams = DELTA_T_MAX_ANCHOR_ALBEDO,
) -> CoolingResult:
    """Compute high-albedo surface cooling for one cell.

    :param initial_temp: starting temperature at the cell (°C)
    :param params:       planner-chosen albedo inputs
    :param delta_t_max:  either a fixed ceiling (°C) or AlbedoWeatherParams
    :returns: CoolingResult — delta_t is SIGNED (negative = cooling).
    """
    delta_t_max_c = (
        delta_t_max
        if isinstance(delta_t_max, (int, float))
        else delta_t_max_from_weather_albedo(delta_t_max)
    )

    # Normalized reflectance gain (linear in Δalbedo, capped at 1).
    f_albedo = min(max(params.delta_albedo, 0.0) / DELTA_ALBEDO_REF, 1.0)

    # Intensity (0–1): reflectance gain scaled linearly by treated area.
    intensity = f_albedo * min(max(params.area_coverage, 0.0), 1.0)

    delta_t = delta_t_max_c * intensity
    final_temp = initial_temp - delta_t

    return CoolingResult(final_temp, -delta_t)


# --- Shade structure cooling model ------------------------------------------
# Blocks the direct solar beam over a footprint (no evaporation).


@dataclass(frozen=True)
class ShadeCoolingParams:
    """Planner-chosen inputs for a shade structure. All fractions are 0–1."""

    opacity: float          # 0–1  fraction of the direct beam blocked
    shaded_footprint: float # 0–1  shaded ground as a fraction of the cell (linear)


@dataclass(frozen=True)
class ShadeWeatherParams:
    """Environmental inputs — shade cooling scales with SOLAR loading."""

    temperature_c: float  # °C   air temperature (solar-loading proxy)
    f_solar: float = 1.0  # 0–1  insolation multiplier


DELTA_T_MAX_ANCHOR_SHADE = 5.0  # °C: pedestrian-air cooling asymptote
DIRECT_BEAM_FRACTION = 0.85     # max blockable share of global irradiance
SHADE_SOLAR_T_LOW = 20.0        # °C floor of the solar-proxy ramp
SHADE_SOLAR_T_HIGH = 38.0       # °C ceiling of the solar-proxy ramp


def delta_t_max_from_weather_shade(weather: ShadeWeatherParams) -> float:
    """Weather ceiling for shade structures.

        ΔT_max = 5 °C × f_thermal × f_solar × f_direct

    Like albedo, uses a temperature-based solar proxy (f_thermal). The extra
    DIRECT_BEAM_FRACTION caps the effect at the blockable (direct-beam) share of
    irradiance — diffuse sky radiation still reaches the ground under shade.
    """
    span = SHADE_SOLAR_T_HIGH - SHADE_SOLAR_T_LOW
    f_thermal = min(max((weather.temperature_c - SHADE_SOLAR_T_LOW) / span, 0.0), 1.0)
    return DELTA_T_MAX_ANCHOR_SHADE * f_thermal * weather.f_solar * DIRECT_BEAM_FRACTION


def shade_cooling(
    initial_temp: float,
    params: ShadeCoolingParams,
    delta_t_max: float | ShadeWeatherParams = DELTA_T_MAX_ANCHOR_SHADE * DIRECT_BEAM_FRACTION,
) -> CoolingResult:
    """Compute shade-structure cooling for one cell.

    :param initial_temp: starting temperature at the cell (°C)
    :param params:       planner-chosen shade inputs
    :param delta_t_max:  either a fixed ceiling (°C) or ShadeWeatherParams. The
                         numeric default already folds in DIRECT_BEAM_FRACTION.
    :returns: CoolingResult — delta_t is SIGNED (negative = cooling).
    """
    delta_t_max_c = (
        delta_t_max
        if isinstance(delta_t_max, (int, float))
        else delta_t_max_from_weather_shade(delta_t_max)
    )

    # Opacity is already the 0–1 blocked fraction — no normalization.
    f_shade = min(max(params.opacity, 0.0), 1.0)
    intensity = f_shade * min(max(params.shaded_footprint, 0.0), 1.0)

    delta_t = delta_t_max_c * intensity
    final_temp = initial_temp - delta_t
    return CoolingResult(final_temp, -delta_t)


# --- Evaporative / free-water cooling model ---------------------------------
# Misting + fountains: latent heat from evaporating free water. VPD-gated, and a
# point-source plume that falls off with distance.


@dataclass(frozen=True)
class EvaporativeCoolingParams:
    """Planner-chosen inputs for an evaporative source (misting/fountain)."""

    evap_rate_lpm: float      # L/min  effective evaporation
    coverage_radius_m: float  # m      plume reach — distance-falloff scale
    active_fraction: float    # 0–1    duty cycle


@dataclass(frozen=True)
class EvaporativeWeatherParams:
    """Environmental inputs — evaporation is VPD-gated and wind-dispersed."""

    temperature_c: float      # °C
    relative_humidity: float  # 0–100  drives VPD, like ET
    f_wind: float = 1.0       # 0–1    wind disperses the plume


LATENT_HEAT_VAPORIZATION = 2.45e6  # J/kg at ~25 °C
WATER_DENSITY_KG_PER_L = 1.0       # kg/L
EVAP_POWER_REF_W = 50000.0         # W: latent budget saturating i_source (calib knob)
DELTA_T_MAX_ANCHOR_EVAP = 8.0      # °C: peak-source cooling under hot, DRY conditions
VPD_REF_EVAP = 4.5                 # kPa: peak-case VPD normalizer


def delta_t_max_from_weather_evap(weather: EvaporativeWeatherParams) -> float:
    """Weather ceiling for evaporative sources.

        ΔT_max = 8 °C × f_VPD × f_wind

    VPD-gated like vegetation's latent channel; wind lowers the ceiling by
    dispersing the plume before it can cool the air.
    """
    vpd = vapor_pressure_deficit(weather.temperature_c, weather.relative_humidity)
    f_vpd = min(vpd / VPD_REF_EVAP, 1.0)
    return DELTA_T_MAX_ANCHOR_EVAP * f_vpd * weather.f_wind


def evaporative_cooling(
    initial_temp: float,
    params: EvaporativeCoolingParams,
    distance_m: float,
    delta_t_max: float | EvaporativeWeatherParams = DELTA_T_MAX_ANCHOR_EVAP,
) -> CoolingResult:
    """Evaporative cooling at a point `distance_m` from the source.

    Combines a source-strength term (how much latent power the emitter provides,
    saturating at EVAP_POWER_REF_W) with a linear distance falloff and a duty
    cycle. Points beyond the coverage radius receive nothing.

    :param initial_temp: starting temperature at the point (°C)
    :param params:       planner-chosen evaporative inputs
    :param distance_m:   distance from the source to this point (m)
    :param delta_t_max:  either a fixed ceiling (°C) or EvaporativeWeatherParams
    :returns: CoolingResult — delta_t is SIGNED (negative = cooling).
    """
    delta_t_max_c = (
        delta_t_max
        if isinstance(delta_t_max, (int, float))
        else delta_t_max_from_weather_evap(delta_t_max)
    )

    # Latent cooling power: P = ṁ · L_v  (kg/s × J/kg = W).
    mass_rate_kg_s = (max(params.evap_rate_lpm, 0.0) * WATER_DENSITY_KG_PER_L) / 60
    power_w = mass_rate_kg_s * LATENT_HEAT_VAPORIZATION
    i_source = min(power_w / EVAP_POWER_REF_W, 1.0)  # normalize to [0, 1]

    # Linear plume falloff: full at the source, 0 at/beyond the coverage radius.
    r = max(distance_m, 0.0)
    falloff = (
        max(1 - r / params.coverage_radius_m, 0.0)
        if params.coverage_radius_m > 0
        else 0.0
    )

    duty = min(max(params.active_fraction, 0.0), 1.0)  # fraction of time active

    delta_t = delta_t_max_c * i_source * duty * falloff
    final_temp = initial_temp - delta_t
    return CoolingResult(final_temp, -delta_t)


# --- Polygon spatial filtering ----------------------------------------------
# Helpers to decide which readings fall inside a drawn intervention footprint.


class BoundingBox(NamedTuple):
    """Axis-aligned lon/lat extent of a polygon — a cheap pre-filter."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


def get_bounding_box(polygon: Polygon) -> BoundingBox:
    """Compute the bounding box enclosing a polygon's vertices."""
    min_lon = min_lat = math.inf
    max_lon = max_lat = -math.inf

    for lon, lat in polygon:
        min_lon = min(min_lon, lon)
        min_lat = min(min_lat, lat)
        max_lon = max(max_lon, lon)
        max_lat = max(max_lat, lat)

    return BoundingBox(min_lon, min_lat, max_lon, max_lat)


def is_inside_bounding_box(lon: float, lat: float, bbox: BoundingBox) -> bool:
    """Fast rejection test: is (lon, lat) within the polygon's bounding box?"""
    return (
        bbox.min_lon <= lon <= bbox.max_lon and bbox.min_lat <= lat <= bbox.max_lat
    )


def point_in_polygon(lon: float, lat: float, polygon: Polygon) -> bool:
    """Ray-casting point-in-polygon test.

    Counts how many polygon edges a horizontal ray from the point crosses; an
    odd count means the point is inside.
    """
    inside = False
    count = len(polygon)

    # Walk each edge (i, j) where j trails i by one, wrapping at the end.
    for i in range(count):
        xi, yi = polygon[i]
        xj, yj = polygon[i - 1]  # -1 wraps to the last vertex on the first pass

        # Edge straddles the ray's latitude AND the crossing is to the right.
        # The first clause guarantees yi != yj, and `and` short-circuits, so the
        # division below can never hit a zero denominator.
        if ((yi > lat) != (yj > lat)) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside  # toggle on each crossing

    return inside


def is_point_inside_polygon(
    point: HeatmapMetricValue,
    polygon: Polygon,
    bbox: BoundingBox,
) -> bool:
    """True if a reading's coordinates fall inside the polygon.

    Applies the cheap bounding-box check first, then the exact ray-cast test.
    """
    lon, lat = point["location_coordinates"]
    if not is_inside_bounding_box(lon, lat, bbox):
        return False  # outside the box → cannot be inside the polygon
    return point_in_polygon(lon, lat, polygon)


def distance_meters(a: Coordinates, b: Coordinates) -> float:
    """Approximate distance in meters (equirectangular; fine at city scale).

    Projects lon/lat to local meters using the mean latitude, then Pythagoras.
    """
    lon1, lat1 = a
    lon2, lat2 = b
    mid_lat = math.radians((lat1 + lat2) / 2)
    dx = (lon2 - lon1) * math.cos(mid_lat) * 111320  # meters per degree lon here
    dy = (lat2 - lat1) * 110540                      # meters per degree lat
    return math.hypot(dx, dy)


def points_inside_polygon_by_date(
    points_by_date: HeatmapPointsByDate,
    polygon: Polygon,
) -> HeatmapPointsByDate:
    """Filter a by-date reading set down to the points inside `polygon`.

    Preserves the by-date grouping; dates with no interior points are dropped.
    The point objects are kept by reference so mutations propagate back.
    """
    bbox = get_bounding_box(polygon)  # compute once, reuse across all points
    result: HeatmapPointsByDate = {}

    for date, points in points_by_date.items():
        inside = [p for p in points if is_point_inside_polygon(p, polygon, bbox)]
        if inside:
            result[date] = inside

    return result


def geometry_anchor(geometry: Geometry) -> Coordinates:
    """Source anchor for radius-based archetypes.

    A point's own coords, or the centroid of a line/polygon. Used to locate the
    emitter for evaporative sources.
    """
    # A point geometry is its own anchor.
    if (
        geometry.get("kind") == "point"
        and geometry.get("longitude") is not None
        and geometry.get("latitude") is not None
    ):
        return (geometry["longitude"], geometry["latitude"])

    # Otherwise average the vertices (line coordinates or polygon ring).
    pts = geometry.get("coordinates") if geometry.get("kind") == "line" else geometry.get("ring")
    if not pts:
        return (0.0, 0.0)
    total_lng = sum(lng for lng, _ in pts)
    total_lat = sum(lat for _, lat in pts)
    return (total_lng / len(pts), total_lat / len(pts))


# --- Assumptions about the placed-object + reading shapes -------------------
# Category keys and param mappings that bridge the toolbox's placed objects to
# the physics models above. Adjust the *_CATEGORY strings to match your toolbox.

# Archetype key whose objects cool via ET/shade.
VEGETATION_CATEGORY = "Vegetation"

# Archetype key whose objects cool by raising solar reflectance.
HIGH_ALBEDO_CATEGORY = "High-albedo surface"  # ← set to your toolbox archetype key

# Archetype key whose objects cool by blocking the direct solar beam.
SHADE_CATEGORY = "Shade structure"  # ← set to your toolbox archetype key

# Archetype key whose objects cool by free-water evaporation.
EVAPORATIVE_CATEGORY = "Evaporative / water"  # ← set to your toolbox archetype key

# `change_in_temperature` points carry value 0 and no real temperature, so the
# weather-derived ceilings (especially the solar-proxy ones) would collapse. Use
# a representative hot-day temperature as a stopgap. The honest fix is to look
# up the co-located temperature reading and pass that instead.
CHANGE_IN_TEMP_ASSUMED_C = 34.0

# Canopy fraction default when the toolbox param omits it.
DEFAULT_CANOPY_FRACTION = 1.0


def get_object_polygon(geometry: Geometry | None) -> Polygon | None:
    """A placed object contributes a footprint only if it is a drawn polygon."""
    if not geometry:
        return None
    ring = geometry.get("ring")
    return ring if geometry.get("kind") == "polygon" and ring else None


def get_cooling_params(obj: BasePlacedObject) -> VegetationCoolingParams | None:
    """Map a placed object's toolbox params onto the vegetation model's inputs.

    Returns None if any required field is missing, so callers can skip the object.
    """
    p = obj.get("params")
    if not p or p.get("coverPct") is None or p.get("lai") is None or p.get("irrigation") is None:
        return None
    canopy = p.get("canopyFraction")
    return VegetationCoolingParams(
        vegetated_coverage=p["coverPct"],
        canopy_fraction=DEFAULT_CANOPY_FRACTION if canopy is None else canopy,
        lai=p["lai"],
        water_factor=p["irrigation"],
    )


def get_albedo_params(obj: BasePlacedObject) -> AlbedoCoolingParams | None:
    """Map a placed object's params onto the albedo model's inputs."""
    p = obj.get("params")
    if not p or p.get("deltaAlbedo") is None or p.get("coverPct") is None:
        return None
    return AlbedoCoolingParams(delta_albedo=p["deltaAlbedo"], area_coverage=p["coverPct"])


def get_shade_params(obj: BasePlacedObject) -> ShadeCoolingParams | None:
    """Map a placed shade object's params onto the shade model's inputs."""
    p = obj.get("params")
    if not p or p.get("opacity") is None or p.get("footprintFraction") is None:
        return None
    return ShadeCoolingParams(opacity=p["opacity"], shaded_footprint=p["footprintFraction"])


def get_evaporative_params(obj: BasePlacedObject) -> EvaporativeCoolingParams | None:
    """Map a placed object's params onto the evaporative model's inputs."""
    p = obj.get("params")
    if (
        not p
        or p.get("evapRateLpm") is None
        or p.get("coverageRadiusM") is None
        or p.get("activeFraction") is None
    ):
        return None
    return EvaporativeCoolingParams(
        evap_rate_lpm=p["evapRateLpm"],
        coverage_radius_m=p["coverageRadiusM"],
        active_fraction=p["activeFraction"],
    )


def metric_is_temperature(metric: str) -> bool:
    """This model only moves temperature; leave other metrics untouched."""
    return metric in ("average_temperature_c", "change_in_temperature")


def _to_epoch(value: str | None) -> float | None:
    """Parse an ISO date/datetime into epoch seconds, or None if unparseable.

    Naive values are treated as UTC, matching `new Date("2026-07-05")` on the
    TypeScript side.
    """
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def filter_by_active_window(
    points_by_date: HeatmapPointsByDate,
    active_from: str | None = None,
    active_to: str | None = None,
) -> HeatmapPointsByDate:
    """Keep only the dates within an intervention's [active_from, active_to].

    Either bound may be omitted → open-ended on that side. The point lists are
    kept by reference so downstream mutations propagate back to the caller.

    Retained for parity with the TypeScript module; the diminishing-returns path
    uses `is_active_on_date` per object instead.
    """
    start = _to_epoch(active_from)
    end = _to_epoch(active_to)
    start = -math.inf if start is None else start
    end = math.inf if end is None else end

    result: HeatmapPointsByDate = {}
    for date, points in points_by_date.items():
        t = _to_epoch(date)
        if t is not None and start <= t <= end:
            result[date] = points  # keep reference so mutations propagate
    return result


# --- Diminishing-returns composition ----------------------------------------

# The composition model used when several interventions affect one point.
SimulationMode = Literal["standard", "contextual"]


@dataclass
class SimulationFeedback:
    """Diagnostics describing how the interventions landed."""

    mode: SimulationMode = "standard"
    affected_points: int = 0
    overlap_points: int = 0
    max_objects_at_point: int = 0
    average_cooling_c: float = 0.0
    max_capacity_used: float = 0.0
    affected_locations: list[str] = field(default_factory=list)
    overlap_locations: list[str] = field(default_factory=list)
    contributing_interventions: list[str] = field(default_factory=list)
    interventions_without_effect: list[str] = field(default_factory=list)
    contextual_interactions: list[str] = field(default_factory=list)


class DiminishingSimulationResult(NamedTuple):
    points_by_date: HeatmapPointsByDate
    feedback: SimulationFeedback


@dataclass(frozen=True)
class ContextualInteraction:
    categories: tuple[str, str]
    factor: float
    label: str


CONTEXTUAL_INTERACTIONS: list[ContextualInteraction] = [
    ContextualInteraction(
        (VEGETATION_CATEGORY, EVAPORATIVE_CATEGORY),
        1.25,
        "Vegetation + water: irrigation and evapotranspiration reinforce cooling (+25%).",
    ),
    ContextualInteraction(
        (VEGETATION_CATEGORY, HIGH_ALBEDO_CATEGORY),
        0.82,
        "Vegetation + reflective concrete: overlapping benefits are less complementary (-18%).",
    ),
    ContextualInteraction(
        (VEGETATION_CATEGORY, SHADE_CATEGORY),
        0.86,
        "Vegetation + shade: shared solar blocking produces partial redundancy (-14%).",
    ),
    ContextualInteraction(
        (SHADE_CATEGORY, EVAPORATIVE_CATEGORY),
        0.92,
        "Shade + water: lower airflow modestly limits the evaporative plume (-8%).",
    ),
]


def clamp_simulation(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def is_active_on_date(obj: BasePlacedObject, date: str) -> bool:
    """True if the object's active window covers `date`."""
    time = _to_epoch(date)
    if time is None:
        return False
    start = _to_epoch(obj.get("activeFrom"))
    end = _to_epoch(obj.get("activeTo"))
    start = -math.inf if start is None else start
    end = math.inf if end is None else end
    return start <= time <= end


def cooling_ceiling_for_point(
    temperature_c: float,
    relative_humidity: float | None = None,
) -> float:
    """The largest ΔT_max any archetype could deliver at this point.

    Acts as the shared cooling budget that overlapping interventions draw down.
    """
    if relative_humidity is None:
        vegetation = DELTA_T_MAX_ANCHOR
        evaporative = DELTA_T_MAX_ANCHOR_EVAP
    else:
        vegetation = delta_t_max_from_weather(
            WeatherParams(temperature_c=temperature_c, relative_humidity=relative_humidity)
        )
        evaporative = delta_t_max_from_weather_evap(
            EvaporativeWeatherParams(
                temperature_c=temperature_c, relative_humidity=relative_humidity
            )
        )
    return max(
        vegetation,
        evaporative,
        delta_t_max_from_weather_albedo(AlbedoWeatherParams(temperature_c=temperature_c)),
        delta_t_max_from_weather_shade(ShadeWeatherParams(temperature_c=temperature_c)),
        0.1,
    )


def individual_cooling(
    category: str,
    obj: BasePlacedObject,
    point: HeatmapMetricValue,
    temperature_c: float,
    relative_humidity: float | None = None,
) -> float | None:
    """Standalone cooling magnitude (°C, positive) this object gives this point.

    Returns None when the object doesn't reach the point or lacks usable params.
    """
    if category == EVAPORATIVE_CATEGORY:
        evap_params = get_evaporative_params(obj)
        if not evap_params:
            return None
        distance = distance_meters(
            geometry_anchor(obj.get("geometry", {})), point["location_coordinates"]
        )
        if distance > evap_params.coverage_radius_m:
            return None
        if relative_humidity is None:
            result = evaporative_cooling(temperature_c, evap_params, distance)
        else:
            result = evaporative_cooling(
                temperature_c,
                evap_params,
                distance,
                EvaporativeWeatherParams(
                    temperature_c=temperature_c, relative_humidity=relative_humidity
                ),
            )
        return max(0.0, -result.delta_t)

    polygon = get_object_polygon(obj.get("geometry"))
    if not polygon or not is_point_inside_polygon(point, polygon, get_bounding_box(polygon)):
        return None

    if category == VEGETATION_CATEGORY:
        veg_params = get_cooling_params(obj)
        if not veg_params:
            return None
        if relative_humidity is None:
            result = vegetation_cooling(temperature_c, veg_params)
        else:
            result = vegetation_cooling(
                temperature_c,
                veg_params,
                WeatherParams(
                    temperature_c=temperature_c, relative_humidity=relative_humidity
                ),
            )
        return max(0.0, -result.delta_t)

    if category == HIGH_ALBEDO_CATEGORY:
        albedo_params = get_albedo_params(obj)
        if not albedo_params:
            return None
        result = albedo_cooling(
            temperature_c, albedo_params, AlbedoWeatherParams(temperature_c=temperature_c)
        )
        return max(0.0, -result.delta_t)

    if category == SHADE_CATEGORY:
        shade_params = get_shade_params(obj)
        if not shade_params:
            return None
        result = shade_cooling(
            temperature_c, shade_params, ShadeWeatherParams(temperature_c=temperature_c)
        )
        return max(0.0, -result.delta_t)

    return None


class _Contribution(NamedTuple):
    obj: BasePlacedObject
    category: str
    cooling: float


def run_diminishing_return_simulation(
    metric: str,
    points_by_date: HeatmapPointsByDate,
    categorized_objects: BasePlacedObjectCategorized,
    mode: SimulationMode = "standard",
) -> DiminishingSimulationResult:
    """Apply every active intervention against the same baseline.

    Contributions are combined with ``1 - product(1 - contribution / capacity)``,
    which prevents overlapping projects from unrealistically stacking their full
    cooling effect. Because every contribution is measured from the untouched
    baseline, the result is independent of iteration order.

    The baseline is never mutated. Returned points are shallow copies of their
    source: `value` and `individual_metrics` are rebound as whole keys, and
    `location_coordinates` is only read, so a deep copy is unnecessary. That
    does mean the returned points share their `location_coordinates` object with
    the input -- safe for serialization, but do not edit it in place downstream.

    :param metric:              the heatmap metric being simulated
    :param points_by_date:      baseline readings grouped by date (not mutated)
    :param categorized_objects: interventions grouped by archetype category
    :param mode:                'contextual' additionally applies the
                                cross-archetype interaction factors
    :returns: the simulated readings plus a feedback summary
    """

    feedback = SimulationFeedback(mode=mode)

    if not metric_is_temperature(metric):
        # Nothing is modified on this path, so fresh containers around the
        # existing point objects are enough.
        return DiminishingSimulationResult(
            {date: list(points) for date, points in points_by_date.items()}, feedback
        )

    is_change_metric = metric == "change_in_temperature"
    total_cooling = 0.0

    # dicts rather than sets: insertion order is preserved, matching the JS Set.
    affected_locations: dict[str, None] = {}
    overlap_locations: dict[str, None] = {}
    contributors: dict[str, None] = {}

    labels: dict[str, str] = {}
    for category, objects in categorized_objects.items():
        for obj in objects:
            label = obj.get("name")
            if label is None:
                label = obj.get("type")
            if label is None:
                label = category
            labels[obj["id"]] = label

    result: HeatmapPointsByDate = {}

    for date, points in points_by_date.items():
        simulated_points: list[HeatmapMetricValue] = []

        for index, source_point in enumerate(points):
            metrics = source_point.get("individual_metrics") or {}

            parsed_temperature = parse_temperature(metrics.get("average_temperature_c", ""))
            parsed_humidity = parse_percentage(
                metrics.get("average_relative_humidity_pct", "")
            )

            if is_change_metric:
                temperature_c = (
                    parsed_temperature
                    if parsed_temperature is not None
                    else CHANGE_IN_TEMP_ASSUMED_C
                )
            else:
                temperature_c = source_point["value"]
            relative_humidity = parsed_humidity

            ceiling = cooling_ceiling_for_point(temperature_c, relative_humidity)

            raw: list[_Contribution] = []
            for category, objects in categorized_objects.items():
                for obj in objects:
                    if not is_active_on_date(obj, date):
                        continue
                    cooling = individual_cooling(
                        category, obj, source_point, temperature_c, relative_humidity
                    )
                    if cooling is not None and cooling > 0:
                        raw.append(_Contribution(obj, category, cooling))

            if not raw:
                # Untouched: copy the container only, nothing to rewrite.
                simulated_points.append(dict(source_point))
                continue

            categories = {item.category for item in raw}
            interactions = (
                [
                    interaction
                    for interaction in CONTEXTUAL_INTERACTIONS
                    if interaction.categories[0] in categories
                    and interaction.categories[1] in categories
                ]
                if mode == "contextual"
                else []
            )
            factor = math.prod(interaction.factor for interaction in interactions)

            remaining = 1.0
            for item in raw:
                remaining *= 1 - clamp_simulation(item.cooling * factor / ceiling, 0.0, 1.0)
            impact = 1 - remaining

            cooling_c = ceiling * impact
            final_temperature = temperature_c - cooling_c

            feedback.affected_points += 1
            feedback.max_objects_at_point = max(feedback.max_objects_at_point, len(raw))
            feedback.max_capacity_used = max(feedback.max_capacity_used, impact * 100)
            total_cooling += cooling_c

            location = metrics.get("location_name") or f"Point {index + 1}"
            affected_locations[location] = None
            if len(raw) > 1:
                feedback.overlap_points += 1
                overlap_locations[location] = None

            for item in raw:
                contributors[item.obj["id"]] = None
            for interaction in interactions:
                if interaction.label not in feedback.contextual_interactions:
                    feedback.contextual_interactions.append(interaction.label)

            # Shallow copy: both writes below rebind top-level keys, and the
            # metrics spread builds a new dict rather than mutating the source.
            point = dict(source_point)
            point["value"] = -cooling_c if is_change_metric else final_temperature
            point["individual_metrics"] = {
                **metrics,
                "average_temperature_c": f"{final_temperature:.1f}°C",
                "simulation_cooling_c": f"{cooling_c:.2f}°C",
                "simulation_overlap_count": str(len(raw)),
                "simulation_capacity_used": f"{impact * 100:.0f}%",
            }
            simulated_points.append(point)

        result[date] = simulated_points

    feedback.average_cooling_c = (
        total_cooling / feedback.affected_points if feedback.affected_points else 0.0
    )
    feedback.affected_locations = list(affected_locations)
    feedback.overlap_locations = list(overlap_locations)
    feedback.contributing_interventions = [
        labels.get(object_id, object_id) for object_id in contributors
    ]
    feedback.interventions_without_effect = [
        label for object_id, label in labels.items() if object_id not in contributors
    ]

    return DiminishingSimulationResult(result, feedback)


def get_simulated_points_by_date(
    metric: str,
    points_by_date: HeatmapPointsByDate,
    placed_objects: BasePlacedObjectCategorized,
    mode: SimulationMode = "standard",
) -> HeatmapPointsByDate:
    """Run the intervention simulation for one metric and return the readings.

    Thin wrapper over `run_diminishing_return_simulation` for callers that don't
    need the feedback summary. The baseline `points_by_date` is never mutated.

    (The TypeScript version awaited a mock latency delay here purely so the
    frontend could exercise its loading states; there's nothing to simulate
    server-side, so it's dropped.)
    """
    return run_diminishing_return_simulation(
        metric, points_by_date, placed_objects, mode
    ).points_by_date