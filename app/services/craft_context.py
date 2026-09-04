"""Context crafting for the urban-heat intervention chat bot.

craftContext() folds the three raw sources

    B. craftCurrentScenarios(city, date)                    -> planned interventions
    C. queryVisitorRowsWithGeometryByCityDate(...)          -> top heat-risk destinations
    D. getAllMetricsByCityDate(weather_date, market_code)   -> daily weather context

into one prompt-ready briefing that mirrors the simulation model spec: archetypes,
psychrometrics, per-archetype ΔT_max ceilings for today's weather, spatial reach,
time windows, diminishing-returns composition and contextual interactions.
"""

from __future__ import annotations

import math
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Spec constants (§3-§7, §10, §11)
# ---------------------------------------------------------------------------

ANCHOR_VEG = 5.0
ANCHOR_ALBEDO = 4.0
ANCHOR_SHADE = 5.0
ANCHOR_EVAP = 8.0

VPD_REF = 4.5
LAI_EXTINCTION = 0.5
WEIGHT_LATENT = 0.4
WEIGHT_SHADE = 0.6
SHADE_DROUGHT_SURVIVAL = 0.8

DELTA_ALBEDO_REF = 0.7
T_LOW = 20.0
T_HIGH = 38.0
DIRECT_BEAM_FRACTION = 0.85

L_V = 2.45e6
RHO_WATER = 1.0
EVAP_POWER_REF_W = 50000.0

MIN_CEILING = 0.1
CHANGE_IN_TEMP_ASSUMED_C = 34.0

VEGETATION = "Vegetation"
ALBEDO = "High-albedo surface"
SHADE = "Shade structure"
EVAPORATIVE = "Evaporative / water"

# toolbox param -> model field, plus which params the model refuses to run without (§2)
ARCHETYPES: Dict[str, Dict[str, Any]] = {
	VEGETATION: {
		"fields": {
			"coverPct": "vegetated_coverage",
			"canopyFraction": "canopy_fraction",
			"lai": "lai",
			"irrigation": "water_factor",
		},
		"required": ("coverPct", "lai", "irrigation"),
		"defaults": {"canopyFraction": 1.0},
		"geometry": "polygon",
		"anchor": ANCHOR_VEG,
	},
	ALBEDO: {
		"fields": {"deltaAlbedo": "delta_albedo", "coverPct": "area_coverage"},
		"required": ("deltaAlbedo", "coverPct"),
		"defaults": {},
		"geometry": "polygon",
		"anchor": ANCHOR_ALBEDO,
	},
	SHADE: {
		"fields": {"opacity": "opacity", "footprintFraction": "shaded_footprint"},
		"required": ("opacity", "footprintFraction"),
		"defaults": {},
		"geometry": "polygon",
		"anchor": ANCHOR_SHADE,
	},
	EVAPORATIVE: {
		"fields": {
			"evapRateLpm": "evap_rate_lpm",
			"coverageRadiusM": "coverage_radius_m",
			"activeFraction": "active_fraction",
		},
		"required": ("evapRateLpm", "coverageRadiusM", "activeFraction"),
		"defaults": {},
		"geometry": "point",
		"anchor": ANCHOR_EVAP,
	},
}

INTERACTIONS: List[Tuple[frozenset, float, str]] = [
	(frozenset({VEGETATION, EVAPORATIVE}), 1.25, "irrigation + ET reinforce"),
	(frozenset({VEGETATION, ALBEDO}), 0.82, "less complementary"),
	(frozenset({VEGETATION, SHADE}), 0.86, "shared solar blocking"),
	(frozenset({SHADE, EVAPORATIVE}), 0.92, "lower airflow limits plume"),
]

CATEGORY_ALIASES = {
	"vegetation": VEGETATION,
	"veg": VEGETATION,
	"trees": VEGETATION,
	"green": VEGETATION,
	"high-albedo surface": ALBEDO,
	"high albedo surface": ALBEDO,
	"albedo": ALBEDO,
	"cool roof": ALBEDO,
	"shade structure": SHADE,
	"shade": SHADE,
	"evaporative / water": EVAPORATIVE,
	"evaporative": EVAPORATIVE,
	"water": EVAPORATIVE,
	"misting": EVAPORATIVE,
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, low: float, high: float) -> float:
	return max(low, min(high, value))


def _as_float(value: Any) -> Optional[float]:
	if value is None or isinstance(value, bool):
		return None
	if isinstance(value, Decimal):
		return float(value)
	if isinstance(value, (int, float)):
		return float(value)
	text = str(value).strip().replace("%", "").replace("°C", "").replace("°F", "")
	try:
		return float(text)
	except ValueError:
		return None


def _fmt(value: Optional[float], digits: int = 2, suffix: str = "") -> str:
	if value is None:
		return "n/a"
	return f"{value:.{digits}f}{suffix}"


def _row_to_dict(row: Any) -> Dict[str, Any]:
	"""Accept SQLAlchemy Rows, ORM objects, mappings, or plain dicts."""
	if isinstance(row, dict):
		return dict(row)
	mapping = getattr(row, "_mapping", None)
	if mapping is not None:
		return {key: value for key, value in mapping.items()}
	if hasattr(row, "__dict__"):
		return {k: v for k, v in vars(row).items() if not k.startswith("_")}
	return {}


def _records(value: Any) -> List[Dict[str, Any]]:
	if value is None:
		return []
	if isinstance(value, dict):
		return [value]
	if isinstance(value, (list, tuple, set)):
		return [_row_to_dict(item) for item in value if item is not None]
	if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
		return [_row_to_dict(item) for item in value if item is not None]
	return [_row_to_dict(value)]


def _pick(mapping: Dict[str, Any], *keys: str) -> Any:
	lowered = {str(k).lower(): v for k, v in mapping.items()}
	for key in keys:
		if key.lower() in lowered and lowered[key.lower()] is not None:
			return lowered[key.lower()]
	return None


def _normalize_category(raw: Any) -> Optional[str]:
	if raw is None:
		return None
	text = str(raw).strip()
	if text in ARCHETYPES:
		return text
	return CATEGORY_ALIASES.get(text.lower())


def _coerce_date(value: Any) -> Optional[date_type]:
	if value is None:
		return None
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date_type):
		return value
	try:
		return date_type.fromisoformat(str(value).strip()[:10])
	except ValueError:
		return None


# ---------------------------------------------------------------------------
# Psychrometrics and per-archetype ceilings (§3-§7, §10)
# ---------------------------------------------------------------------------

def _es_kpa(temp_c: float) -> float:
	return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def _vpd_kpa(temp_c: float, rh_pct: float) -> float:
	return _es_kpa(temp_c) * (1.0 - rh_pct / 100.0)


def _ceilings(
	temp_c: Optional[float],
	rh_pct: Optional[float],
	f_solar: float = 1.0,
	f_wind: float = 1.0,
) -> Dict[str, Any]:
	"""ΔT_max per archetype for the day's weather, plus the shared budget ceiling."""
	vpd = None
	if temp_c is not None and rh_pct is not None:
		vpd = _vpd_kpa(temp_c, rh_pct)

	if vpd is not None:
		vpd_factor = min(vpd / VPD_REF, 1.0)
		veg = ANCHOR_VEG * vpd_factor * f_solar * f_wind
		evap = ANCHOR_EVAP * vpd_factor * f_wind
	else:
		# §10: RH unknown -> fall back to the fixed anchors
		veg = ANCHOR_VEG
		evap = ANCHOR_EVAP

	if temp_c is not None:
		f_thermal = _clamp((temp_c - T_LOW) / (T_HIGH - T_LOW), 0.0, 1.0)
	else:
		f_thermal = 1.0
	albedo = ANCHOR_ALBEDO * f_thermal * f_solar
	shade = ANCHOR_SHADE * f_thermal * f_solar * DIRECT_BEAM_FRACTION

	return {
		"vpd_kpa": vpd,
		"f_thermal": f_thermal,
		"delta_t_max": {VEGETATION: veg, ALBEDO: albedo, SHADE: shade, EVAPORATIVE: evap},
		"ceiling": max(veg, evap, albedo, shade, MIN_CEILING),
	}


# ---------------------------------------------------------------------------
# Geometry (§8)
# ---------------------------------------------------------------------------

def _ring(geometry: Dict[str, Any]) -> List[Sequence[float]]:
	ring = _pick(geometry, "ring", "coordinates", "coords", "points")
	if isinstance(ring, (list, tuple)) and ring and isinstance(ring[0], (list, tuple)):
		if ring[0] and isinstance(ring[0][0], (list, tuple)):  # GeoJSON [[[lon,lat],...]]
			ring = ring[0]
		return [p for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2]
	return []


def _geometry_anchor(geometry: Optional[Dict[str, Any]]) -> Tuple[float, float]:
	"""point -> its own (lon,lat); line/polygon -> centroid of coordinates; else (0,0)."""
	if not isinstance(geometry, dict):
		return (0.0, 0.0)
	kind = str(_pick(geometry, "kind", "type") or "").lower()
	if kind == "point":
		coords = _pick(geometry, "coordinates", "coords", "point")
		if isinstance(coords, (list, tuple)) and len(coords) >= 2:
			return (float(coords[0]), float(coords[1]))
		lon = _as_float(_pick(geometry, "lon", "lng", "longitude"))
		lat = _as_float(_pick(geometry, "lat", "latitude"))
		if lon is not None and lat is not None:
			return (lon, lat)
		return (0.0, 0.0)
	points = _ring(geometry)
	if not points:
		return (0.0, 0.0)
	return (
		sum(float(p[0]) for p in points) / len(points),
		sum(float(p[1]) for p in points) / len(points),
	)


def _distance_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
	mean_lat = math.radians((lat1 + lat2) / 2.0)
	dx = (lon2 - lon1) * math.cos(mean_lat) * 111320.0
	dy = (lat2 - lat1) * 110540.0
	return math.hypot(dx, dy)


def _point_in_ring(lon: float, lat: float, ring: Sequence[Sequence[float]]) -> bool:
	if len(ring) < 3:
		return False
	xs = [float(p[0]) for p in ring]
	ys = [float(p[1]) for p in ring]
	if lon < min(xs) or lon > max(xs) or lat < min(ys) or lat > max(ys):
		return False  # bbox pre-filter
	inside = False
	count = len(ring)
	j = count - 1
	for i in range(count):
		xi, yi = float(ring[i][0]), float(ring[i][1])
		xj, yj = float(ring[j][0]), float(ring[j][1])
		if (yi > lat) != (yj > lat):
			x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
			if lon < x_cross:
				inside = not inside
		j = i
	return inside


# ---------------------------------------------------------------------------
# Scenario normalization (§2, §4-§7, §9)
# ---------------------------------------------------------------------------

def _scenario_objects(currentScenarios: Any) -> List[Dict[str, Any]]:
	if isinstance(currentScenarios, dict):
		for key in ("scenarios", "objects", "projects", "interventions", "features", "items"):
			value = currentScenarios.get(key)
			if isinstance(value, (list, tuple)):
				return [_row_to_dict(item) for item in value if item is not None]
		if _normalize_category(_pick(currentScenarios, "category", "archetype", "type")):
			return [dict(currentScenarios)]
		return []
	return _records(currentScenarios)


def _intensity(category: str, params: Dict[str, float]) -> Optional[float]:
	"""Standalone intensity ∈ [0,1] (evaporative excludes the spatial falloff)."""
	if category == VEGETATION:
		cover = _clamp(params["vegetated_coverage"], 0.0, 1.0)
		canopy = _clamp(params.get("canopy_fraction", 1.0), 0.0, 1.0)
		water = _clamp(params["water_factor"], 0.0, 1.0)
		f_lai = 1.0 - math.exp(-LAI_EXTINCTION * max(params["lai"], 0.0))
		latent = cover * f_lai * water
		shade = cover * canopy * f_lai * (SHADE_DROUGHT_SURVIVAL + 0.2 * water)
		return WEIGHT_LATENT * latent + WEIGHT_SHADE * shade
	if category == ALBEDO:
		f_albedo = min(max(params["delta_albedo"], 0.0) / DELTA_ALBEDO_REF, 1.0)
		return f_albedo * _clamp(params["area_coverage"], 0.0, 1.0)
	if category == SHADE:
		return _clamp(params["opacity"], 0.0, 1.0) * _clamp(params["shaded_footprint"], 0.0, 1.0)
	if category == EVAPORATIVE:
		mass_rate = max(params["evap_rate_lpm"], 0.0) * RHO_WATER / 60.0
		i_source = min(mass_rate * L_V / EVAP_POWER_REF_W, 1.0)
		return i_source * _clamp(params["active_fraction"], 0.0, 1.0)
	return None


def _summarize_scenario(index: int, raw: Dict[str, Any], as_of: Optional[date_type]) -> Dict[str, Any]:
	category = _normalize_category(_pick(raw, "category", "archetype", "type", "kind"))
	name = _pick(raw, "name", "label", "title", "id") or f"object #{index}"
	geometry = _pick(raw, "geometry", "geom", "shape")
	geometry = geometry if isinstance(geometry, dict) else None
	source_params = _pick(raw, "params", "parameters", "inputs", "properties")
	source_params = source_params if isinstance(source_params, dict) else raw

	summary: Dict[str, Any] = {
		"name": str(name),
		"category": category,
		"raw_category": _pick(raw, "category", "archetype", "type", "kind"),
		"geometry": geometry,
		"geometry_kind": str(_pick(geometry or {}, "kind", "type") or "unknown").lower(),
		"anchor": _geometry_anchor(geometry),
		"ring": _ring(geometry) if geometry else [],
		"params": {},
		"missing": [],
		"intensity": None,
		"active": True,
		"skipped_reason": None,
		"active_from": _coerce_date(_pick(raw, "activeFrom", "active_from", "start_date")),
		"active_to": _coerce_date(_pick(raw, "activeTo", "active_to", "end_date")),
	}

	if category is None:
		summary["skipped_reason"] = "unknown archetype"
		return summary

	spec = ARCHETYPES[category]
	values: Dict[str, float] = {}
	for toolbox_key, model_field in spec["fields"].items():
		value = _as_float(_pick(source_params, toolbox_key, model_field))
		if value is None and toolbox_key in spec["defaults"]:
			value = spec["defaults"][toolbox_key]
		if value is None:
			if toolbox_key in spec["required"]:
				summary["missing"].append(toolbox_key)
			continue
		values[model_field] = value
	summary["params"] = values

	if summary["missing"]:
		summary["skipped_reason"] = "missing " + ", ".join(summary["missing"]) + " (model returns None)"
		return summary

	if spec["geometry"] == "polygon" and summary["geometry_kind"] != "polygon":
		summary["skipped_reason"] = f"needs a polygon footprint, geometry is '{summary['geometry_kind']}'"
	elif spec["geometry"] == "polygon" and not summary["ring"]:
		summary["skipped_reason"] = "polygon ring is empty"

	# §9 time window, bounds inclusive, missing bound = open ended
	if as_of is not None:
		if summary["active_from"] and as_of < summary["active_from"]:
			summary["active"] = False
		if summary["active_to"] and as_of > summary["active_to"]:
			summary["active"] = False

	summary["intensity"] = _intensity(category, values)
	return summary


def _reaches(scenario: Dict[str, Any], lon: float, lat: float) -> Tuple[bool, float, str]:
	"""(reaches?, falloff, human note) for a destination point."""
	if scenario["category"] == EVAPORATIVE:
		radius = scenario["params"].get("coverage_radius_m", 0.0)
		anchor_lon, anchor_lat = scenario["anchor"]
		distance = max(_distance_meters(anchor_lon, anchor_lat, lon, lat), 0.0)
		if radius <= 0:
			return (False, 0.0, "coverage radius is 0")
		falloff = max(1.0 - distance / radius, 0.0)
		return (falloff > 0, falloff, f"{distance:.0f} m from source, radius {radius:.0f} m")
	if _point_in_ring(lon, lat, scenario["ring"]):
		return (True, 1.0, "point inside footprint")
	return (False, 0.0, "point outside footprint")


def _compose(
	contributions: List[Dict[str, Any]],
	ceiling: float,
	mode: str,
) -> Dict[str, Any]:
	"""§10 diminishing returns + §11 contextual factor."""
	categories = {c["category"] for c in contributions}
	factor = 1.0
	applied: List[str] = []
	if mode == "contextual":
		for pair, multiplier, reason in INTERACTIONS:
			if pair <= categories:
				factor *= multiplier
				applied.append(f"{' + '.join(sorted(pair))} ×{multiplier} ({reason})")

	remaining = 1.0
	for contribution in contributions:
		remaining *= 1.0 - _clamp(contribution["cooling_c"] * factor / ceiling, 0.0, 1.0)
	impact = 1.0 - remaining
	return {
		"factor": factor,
		"interactions": applied,
		"capacity_used": impact,
		"cooling_c": ceiling * impact,
	}


# ---------------------------------------------------------------------------
# Weather context (D)
# ---------------------------------------------------------------------------

_METRIC_NAME_KEYS = ("metric", "metric_name", "metric_key", "name", "key")
_METRIC_VALUE_KEYS = ("value", "metric_value", "val", "amount")


def _flatten_metrics(allMetricsByCityDate: Any) -> Dict[str, Any]:
	flat: Dict[str, Any] = {}
	for record in _records(allMetricsByCityDate):
		if not isinstance(record, dict):
			continue
		nested = record.get("individual_metrics")
		if isinstance(nested, dict):
			flat.update({str(k).lower(): v for k, v in nested.items()})
		metric_name = _pick(record, *_METRIC_NAME_KEYS)
		metric_value = _pick(record, *_METRIC_VALUE_KEYS)
		if metric_name is not None and metric_value is not None:
			flat[str(metric_name).lower()] = metric_value
		else:
			flat.update({str(k).lower(): v for k, v in record.items()})
	return flat


def _weather_context(allMetricsByCityDate: Any) -> Dict[str, Any]:
	flat = _flatten_metrics(allMetricsByCityDate)

	temp_c = _as_float(_pick(flat, "average_temperature_c", "local_temperature_c", "temperature_c"))
	temp_source = "average_temperature_c"
	if temp_c is None:
		temp_f = _as_float(_pick(flat, "average_temperature_f", "local_temperature_f", "temperature_f"))
		if temp_f is not None:
			temp_c = (temp_f - 32.0) * 5.0 / 9.0
			temp_source = "converted from °F"
		else:
			temp_source = f"assumed {CHANGE_IN_TEMP_ASSUMED_C:.1f}°C (CHANGE_IN_TEMP_ASSUMED_C)"

	humidity = _as_float(_pick(flat, "average_relative_humidity_pct", "relative_humidity_pct", "humidity_pct"))
	effective_temp = temp_c if temp_c is not None else CHANGE_IN_TEMP_ASSUMED_C

	return {
		"metrics": flat,
		"temperature_c": temp_c,
		"temperature_source": temp_source,
		"effective_temperature_c": effective_temp,
		"humidity_pct": humidity,
		"ceilings": _ceilings(effective_temp, humidity),
	}


# ---------------------------------------------------------------------------
# Destinations (C)
# ---------------------------------------------------------------------------

def _destination_point(row: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
	lon = _as_float(_pick(row, "longitude", "lon", "lng", "x"))
	lat = _as_float(_pick(row, "latitude", "lat", "y"))
	if lon is not None and lat is not None:
		return (lon, lat)
	geometry = _pick(row, "geometry", "geom", "shape", "location")
	if isinstance(geometry, dict):
		anchor_lon, anchor_lat = _geometry_anchor(geometry)
		if (anchor_lon, anchor_lat) != (0.0, 0.0):
			return (anchor_lon, anchor_lat)
	return (None, None)


def _destination_baseline(row: Dict[str, Any], fallback_c: float) -> float:
	value = _as_float(_pick(row, "value", "average_temperature_c", "local_temperature_c", "temperature_c"))
	if value is not None:
		return value
	value_f = _as_float(_pick(row, "average_temperature_f", "local_temperature_f", "temperature_f"))
	if value_f is not None:
		return (value_f - 32.0) * 5.0 / 9.0
	return fallback_c


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

MODEL_RULES = """MODEL RULES (for reasoning about any what-if the user asks)
- Every archetype: delta_t = ΔT_max(weather) × intensity(planner inputs ∈ [0,1]); returned
  delta_t is signed, negative means cooling; final_temp = initial_temp − |delta_t|.
- Vegetation ΔT_max = 5.0 × min(VPD/4.5,1); intensity = 0.4×latent + 0.6×shade,
  f_LAI = 1 − exp(−0.5×LAI), shade keeps 0.8 of its effect with no irrigation.
- High-albedo ΔT_max = 4.0 × clamp((T−20)/18,0,1) (no VPD term);
  intensity = min(Δalbedo/0.7,1) × coverage.
- Shade ΔT_max = 5.0 × clamp((T−20)/18,0,1) × 0.85 (diffuse sky still reaches the ground);
  intensity = opacity × shaded footprint.
- Evaporative ΔT_max = 8.0 × min(VPD/4.5,1) × f_wind (wind LOWERS the ceiling);
  intensity = min(ṁ·L_v/50 kW,1) × duty × max(1 − r/radius, 0). Beyond the radius: nothing.
- Reach: polygons apply only to points inside the ring; misting falls off linearly from
  the geometry anchor. Objects only count on dates inside [activeFrom, activeTo] (inclusive).
- Composition is NOT additive: a shared per-point budget
  ceiling = max(ΔT_max of the four archetypes, 0.1), remaining = Π(1 − c_i×factor/ceiling),
  cooling = ceiling × (1 − remaining). Each c_i is computed standalone against the untouched
  baseline, so results are order-independent and overlapping projects never stack fully.
- Contextual mode multiplies every contribution by each interaction whose BOTH categories are
  present: veg+water ×1.25, veg+albedo ×0.82, veg+shade ×0.86, shade+water ×0.92."""


def craftContext(
	currentScenarios: Any,
	topHeatRiskDestinations: Any,
	allMetricsByCityDate: Any,
	mode: str = "standard",
) -> str:
	"""Assemble the chat-bot briefing from the three context sources.

	Returns a prompt-ready string: day/weather framing with the ΔT_max ceilings that
	today's air temperature and humidity allow, the planned interventions with their
	normalized model fields and standalone intensities, the contextual interactions in
	play, and the top heat-risk destinations annotated with which interventions actually
	reach them and the composed cooling that results.
	"""
	scenarios_dict = currentScenarios if isinstance(currentScenarios, dict) else {}
	city = _pick(scenarios_dict, "city", "market_code", "market") or "unknown city"
	as_of = _coerce_date(_pick(scenarios_dict, "date", "weather_date", "day"))
	date_label = as_of.isoformat() if as_of else str(_pick(scenarios_dict, "date") or "unknown date")

	weather = _weather_context(allMetricsByCityDate)
	ceilings = weather["ceilings"]
	delta_t_max = ceilings["delta_t_max"]

	raw_objects = _scenario_objects(currentScenarios)
	scenarios = [_summarize_scenario(i + 1, raw, as_of) for i, raw in enumerate(raw_objects, start=0)]
	usable = [s for s in scenarios if s["category"] and s["active"] and not s["skipped_reason"]]

	lines: List[str] = []
	lines.append(f"URBAN HEAT CONTEXT — {city} — {date_label} — mode: {mode}")
	lines.append("")

	# --- weather -----------------------------------------------------------
	lines.append("1. DAILY WEATHER CONTEXT")
	lines.append(
		f"   Air temperature: {_fmt(weather['temperature_c'], 1, '°C')} ({weather['temperature_source']})"
	)
	lines.append(f"   Relative humidity: {_fmt(weather['humidity_pct'], 0, '%')}")
	if ceilings["vpd_kpa"] is not None:
		lines.append(
			f"   VPD (Tetens): {_fmt(ceilings['vpd_kpa'], 2, ' kPa')}"
			f"  |  VPD/VPD_REF = {min(ceilings['vpd_kpa'] / VPD_REF, 1.0):.2f}"
		)
	else:
		lines.append("   VPD: unavailable (no humidity) — vegetation/evaporative fall back to anchors 5.0 / 8.0°C")
	lines.append(f"   f_thermal (T−20)/18: {ceilings['f_thermal']:.2f}")
	lines.append("   ΔT_max the weather allows today:")
	for category in (VEGETATION, ALBEDO, SHADE, EVAPORATIVE):
		lines.append(f"     - {category}: {delta_t_max[category]:.2f}°C")
	lines.append(f"   Shared per-point ceiling: {ceilings['ceiling']:.2f}°C")
	other = {
		key: _json_value(value)
		for key, value in weather["metrics"].items()
		if key not in {"average_temperature_c", "average_relative_humidity_pct"}
	}
	if other:
		lines.append("   Other metrics passed through untouched: " + ", ".join(sorted(other)))
	lines.append("")

	# --- scenarios ---------------------------------------------------------
	lines.append(f"2. CURRENT SCENARIO — {len(scenarios)} object(s), {len(usable)} contributing")
	if not scenarios:
		lines.append("   No interventions placed for this city/date.")
	for index, scenario in enumerate(scenarios, start=1):
		category = scenario["category"] or f"unrecognized ({scenario['raw_category']})"
		head = f"   [{index}] {scenario['name']} — {category}"
		if scenario["skipped_reason"]:
			head += f"  ⚠ SKIPPED: {scenario['skipped_reason']}"
		elif not scenario["active"]:
			head += "  ⚠ outside its active window on this date"
		lines.append(head)
		if scenario["params"]:
			lines.append(
				"       fields: "
				+ ", ".join(f"{k}={v:g}" for k, v in sorted(scenario["params"].items()))
			)
		window = "open-ended"
		if scenario["active_from"] or scenario["active_to"]:
			window = f"{scenario['active_from'] or '−inf'} → {scenario['active_to'] or '+inf'} (inclusive)"
		lines.append(f"       geometry: {scenario['geometry_kind']}, anchor "
					 f"({scenario['anchor'][0]:.5f}, {scenario['anchor'][1]:.5f}); window: {window}")
		if scenario["intensity"] is not None and not scenario["skipped_reason"]:
			standalone = delta_t_max[scenario["category"]] * scenario["intensity"]
			lines.append(
				f"       intensity: {scenario['intensity']:.3f} → standalone cooling "
				f"{standalone:.2f}°C at full reach"
			)
	lines.append("")

	# --- interactions ------------------------------------------------------
	present = {s["category"] for s in usable}
	lines.append("3. CONTEXTUAL INTERACTIONS")
	if mode != "contextual":
		lines.append("   Mode is 'standard' → factor = 1 (no interaction multipliers applied).")
	pairs = [f"   {' + '.join(sorted(pair))} ×{mult} ({reason})"
			 for pair, mult, reason in INTERACTIONS if pair <= present]
	if pairs:
		lines.append("   Category pairs co-present in the scenario:")
		lines.extend(pairs)
	else:
		lines.append("   No interacting category pairs are co-present.")
	lines.append("")

	# --- destinations ------------------------------------------------------
	destinations = _records(topHeatRiskDestinations)
	lines.append(f"4. TOP HEAT-RISK DESTINATIONS ({len(destinations)}, hottest/most exposed first)")
	if not destinations:
		lines.append("   No visitor rows returned for this city/date.")
	for rank, row in enumerate(destinations, start=1):
		name = _pick(row, "name", "destination", "poi_name", "location_name", "id") or f"row {rank}"
		lon, lat = _destination_point(row)
		baseline = _destination_baseline(row, weather["effective_temperature_c"])
		visitors = _pick(row, "visitors", "visitor_count", "visits", "footfall")
		head = f"   {rank}. {name} — baseline {baseline:.1f}°C"
		if visitors is not None:
			head += f", visitors {_json_value(visitors)}"
		if lon is None or lat is None:
			lines.append(head + " — no coordinates, coverage cannot be evaluated")
			continue
		lines.append(head + f" @ ({lon:.5f}, {lat:.5f})")

		contributions: List[Dict[str, Any]] = []
		for scenario in usable:
			reaches, falloff, note = _reaches(scenario, lon, lat)
			if not reaches:
				continue
			cooling = delta_t_max[scenario["category"]] * scenario["intensity"] * falloff
			contributions.append({
				"name": scenario["name"],
				"category": scenario["category"],
				"cooling_c": cooling,
				"note": note,
			})
		if not contributions:
			lines.append("       covered by: nothing — this location gets 0.00°C of cooling")
			continue
		composed = _compose(contributions, ceilings["ceiling"], mode)
		for contribution in contributions:
			lines.append(
				f"       + {contribution['name']} ({contribution['category']}): standalone "
				f"{contribution['cooling_c']:.2f}°C — {contribution['note']}"
			)
		if composed["interactions"]:
			lines.append(
				f"       contextual factor {composed['factor']:.3f}: " + "; ".join(composed["interactions"])
			)
		lines.append(
			f"       = composed cooling {composed['cooling_c']:.2f}°C "
			f"({composed['capacity_used'] * 100:.0f}% of the {ceilings['ceiling']:.2f}°C ceiling, "
			f"overlap {len(contributions)}) → final {baseline - composed['cooling_c']:.1f}°C"
		)
	lines.append("")

	lines.append(MODEL_RULES)
	return "\n".join(lines)


def _json_value(value: Any) -> Any:
	if isinstance(value, Decimal):
		return float(value)
	if isinstance(value, (datetime, date_type)):
		return value.isoformat()
	return value