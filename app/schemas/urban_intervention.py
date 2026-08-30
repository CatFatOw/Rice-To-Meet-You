from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID

from typing_extensions import NotRequired, TypedDict


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

GeometryKind = Literal["point", "line", "polygon"]

InterventionType = Literal[
    "cool_roof",
    "misting_station",
    "street_tree",
    "shade_structure",
    "cool_pavement",
]

InterventionStatus = Literal[
    "planned",
    "active",
    "inactive",
    "retired",
]

ArchetypeCode = Literal[
    "vegetation",
    "high_albedo_surface",
    "shade_structure",
    "evaporative_water",
]

Coordinate: TypeAlias = tuple[float, float]
Polygon: TypeAlias = list[Coordinate]


# ---------------------------------------------------------------------------
# Geometry input types
# ---------------------------------------------------------------------------

class PointGeometry(TypedDict):
    kind: Literal["point"]
    longitude: float
    latitude: float


class LineGeometry(TypedDict):
    kind: Literal["line"]
    coordinates: list[Coordinate]


class PolygonGeometry(TypedDict):
    kind: Literal["polygon"]
    ring: Polygon


Geometry: TypeAlias = (
    PointGeometry
    | LineGeometry
    | PolygonGeometry
)


# ---------------------------------------------------------------------------
# Intervention parameter types
#
# These keys are read verbatim by the simulation's `get_*_params` functions.
# Each of those returns None if a required key is missing, and the object is
# then skipped with no error raised — it just appears in
# `feedback.interventions_without_effect`. So a rename here doesn't break a
# request, it breaks the result, silently. Keep these in step with
# `simulation.py` and with the toolbox definitions on the frontend.
#
# The keys are camelCase while the rest of the schema is snake_case. That's
# deliberate: the simulation indexes the stored `parameters` blob directly, so
# these have to match its literals rather than the column convention.
#
# All fractions are 0–1, not percentages. `coverPct` is named "Pct" but feeds a
# 0–1 intensity term. TypedDict gives no runtime validation, so ranges are
# enforced by REQUIRED_PARAM_KEYS / PARAM_BOUNDS below, not by these classes.
# ---------------------------------------------------------------------------

class CoolRoofParams(TypedDict):
    """High-albedo surface — read by `get_albedo_params`."""

    # The reflectance GAIN over the surface being replaced, NOT the finished
    # albedo. The model divides this by DELTA_ALBEDO_REF = 0.7, so passing a
    # finished 0.65 where the true gain is 0.50 overstates cooling by ~30%.
    deltaAlbedo: float  # 0–1  -> delta_albedo
    coverPct: float     # 0–1  -> area_coverage (treated fraction, linear)

    # `emissivity` was dropped: the model has no thermal-emission term, only
    # (1 - albedo) reflectance. Re-add it here only alongside a model change.


class CoolPavementParams(TypedDict):
    """High-albedo surface — same model and same keys as CoolRoofParams.

    Kept as a distinct alias so the discriminated union stays one class per
    intervention_type, and so a future divergence has somewhere to live.
    """

    deltaAlbedo: float  # 0–1  -> delta_albedo
    coverPct: float     # 0–1  -> area_coverage

    # `width_m` was dropped: turning a corridor width into a treated fraction
    # needs the polygon's area, which the model never sees. Send coverPct.


class StreetTreeParams(TypedDict):
    """Vegetation — read by `get_cooling_params`."""

    coverPct: float    # 0–1   -> vegetated_coverage
    lai: float         # ~0–6  -> lai (Beer-Lambert, saturating)
    irrigation: float  # 0–1   -> water_factor (gates the latent channel fully)

    # Optional: the model falls back to DEFAULT_CANOPY_FRACTION = 1.0. This
    # gates the shade channel, which carries 60% of the intensity weight, so
    # omitting it for a green roof or green wall overstates them substantially.
    canopyFraction: NotRequired[float]  # 0–1  -> canopy_fraction

    # `canopyRadius_m`, `canopyHeight_m` and `deciduous` were dropped: no
    # geometric canopy or seasonality term exists in the model.


class ShadeStructureParams(TypedDict):
    """Shade structure — read by `get_shade_params`."""

    # OPACITY, not transmissivity. The model reads this as the blocked fraction
    # of the direct beam, so sending 1 - opacity inverts every structure: a 0.95
    # solar canopy would arrive as 0.05.
    opacity: float            # 0–1  -> opacity
    footprintFraction: float  # 0–1  -> shaded_footprint (of the drawn polygon)

    # `height_m` was dropped: no mounting-height term in the model.


class MistingStationParams(TypedDict):
    """Evaporative / water — read by `get_evaporative_params`."""

    # EFFECTIVE evaporation: the share of water that reaches the air, not pumped
    # throughput. A 20 L/min fountain evaporates a few percent of that.
    #
    # Note the ceiling: i_source saturates at
    # EVAP_POWER_REF_W / (LATENT_HEAT_VAPORIZATION / 60) ≈ 1.22 L/min, so any
    # value at or above that is indistinguishable to the model.
    evapRateLpm: float       # >= 0  -> evap_rate_lpm
    coverageRadiusM: float   # > 0   -> coverage_radius_m (linear falloff to 0)
    activeFraction: float    # 0–1   -> active_fraction (duty cycle)

    # `nozzleCount`, `flowRate_L_per_min`, `dropletDiameter_um` and
    # `mountHeight_m` were dropped: the model takes an evaporation rate, not an
    # emitter spec. Convert on the client and send the result.


Params: TypeAlias = (
    CoolRoofParams
    | MistingStationParams
    | StreetTreeParams
    | ShadeStructureParams
    | CoolPavementParams
)


# ---------------------------------------------------------------------------
# Runtime validation tables
#
# TypedDict is erased at runtime, so nothing above stops a client from POSTing
# `{"albedo": 0.65}`. Because a missing key makes the simulation skip the object
# silently rather than fail, the cost of not checking is a plausible-looking
# result that quietly excludes an intervention. Validate on write instead.
# ---------------------------------------------------------------------------

REQUIRED_PARAM_KEYS: dict[InterventionType, frozenset[str]] = {
    "cool_roof": frozenset({"deltaAlbedo", "coverPct"}),
    "cool_pavement": frozenset({"deltaAlbedo", "coverPct"}),
    "street_tree": frozenset({"coverPct", "lai", "irrigation"}),
    "shade_structure": frozenset({"opacity", "footprintFraction"}),
    "misting_station": frozenset(
        {"evapRateLpm", "coverageRadiusM", "activeFraction"}
    ),
}

OPTIONAL_PARAM_KEYS: dict[InterventionType, frozenset[str]] = {
    "cool_roof": frozenset(),
    "cool_pavement": frozenset(),
    "street_tree": frozenset({"canopyFraction"}),
    "shade_structure": frozenset(),
    "misting_station": frozenset(),
}

# (minimum, maximum) per key. None means unbounded on that side.
PARAM_BOUNDS: dict[str, tuple[float, float | None]] = {
    "deltaAlbedo": (0.0, 1.0),
    "coverPct": (0.0, 1.0),
    "lai": (0.0, None),
    "irrigation": (0.0, 1.0),
    "canopyFraction": (0.0, 1.0),
    "opacity": (0.0, 1.0),
    "footprintFraction": (0.0, 1.0),
    "evapRateLpm": (0.0, None),
    "coverageRadiusM": (0.0, None),
    "activeFraction": (0.0, 1.0),
}

# Which geometries actually reach a reading for each type.
#
# Vegetation, albedo and shade go through `get_object_polygon`, which requires
# kind == "polygon" with a non-empty ring — a tree saved as a point cools
# nothing whatever its params say. Evaporative sources anchor via
# `geometry_anchor`, which accepts any kind, though a missing geometry falls
# back to (0, 0) and puts the source in the Atlantic.
ALLOWED_GEOMETRY_KINDS: dict[InterventionType, frozenset[GeometryKind]] = {
    "cool_roof": frozenset({"polygon"}),
    "cool_pavement": frozenset({"polygon"}),
    "street_tree": frozenset({"polygon"}),
    "shade_structure": frozenset({"polygon"}),
    "misting_station": frozenset({"point", "line", "polygon"}),
}

# The archetype each intervention_type belongs to. The simulation groups objects
# by category and matches its *_CATEGORY constants by exact string, so the code
# stored here has to map back to the display name the simulation expects.
ARCHETYPE_CODE_BY_INTERVENTION: dict[InterventionType, ArchetypeCode] = {
    "cool_roof": "high_albedo_surface",
    "cool_pavement": "high_albedo_surface",
    "street_tree": "vegetation",
    "shade_structure": "shade_structure",
    "misting_station": "evaporative_water",
}

SIMULATION_CATEGORY_BY_ARCHETYPE_CODE: dict[ArchetypeCode, str] = {
    "vegetation": "Vegetation",
    "high_albedo_surface": "High-albedo surface",
    "shade_structure": "Shade structure",
    "evaporative_water": "Evaporative / water",
}


def validate_parameters(
    intervention_type: InterventionType,
    parameters: dict[str, object],
) -> list[str]:
    """Check a parameters blob against the model's expectations.

    Returns a list of human-readable problems; empty means it will be read
    correctly by the simulation. Call this on write — a body that stores
    successfully with the wrong keys produces no error later, only an
    intervention that quietly does nothing.
    """
    problems: list[str] = []

    required = REQUIRED_PARAM_KEYS[intervention_type]
    optional = OPTIONAL_PARAM_KEYS[intervention_type]

    for key in sorted(required - parameters.keys()):
        problems.append(
            f"missing required parameter {key!r} — "
            f"{intervention_type} will be skipped by the simulation"
        )

    for key in sorted(parameters.keys() - required - optional):
        problems.append(f"unrecognized parameter {key!r} — it will be ignored")

    for key in sorted(parameters.keys() & (required | optional)):
        value = parameters[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problems.append(f"parameter {key!r} must be a number, got {type(value).__name__}")
            continue
        low, high = PARAM_BOUNDS[key]
        if value < low or (high is not None and value > high):
            bound = f"[{low}, {high}]" if high is not None else f">= {low}"
            problems.append(f"parameter {key!r} = {value} is outside {bound}")

    if intervention_type == "misting_station":
        radius = parameters.get("coverageRadiusM")
        if isinstance(radius, (int, float)) and not isinstance(radius, bool) and radius <= 0:
            # The model treats a non-positive radius as zero falloff, so the
            # source is stored but cools nothing.
            problems.append("coverageRadiusM must be greater than 0 to have any effect")

    return problems


def validate_geometry(
    intervention_type: InterventionType,
    geometry: Geometry | None,
) -> list[str]:
    """Check that this geometry can actually reach a reading."""
    problems: list[str] = []

    if not geometry:
        problems.append("geometry is required")
        return problems

    kind = geometry.get("kind")
    allowed = ALLOWED_GEOMETRY_KINDS[intervention_type]
    if kind not in allowed:
        problems.append(
            f"{intervention_type} accepts {sorted(allowed)} geometry, got {kind!r} — "
            "the simulation will not apply it"
        )
    elif kind == "polygon" and not geometry.get("ring"):
        problems.append("polygon geometry has an empty ring")

    return problems


# ---------------------------------------------------------------------------
# Archetype creation
# ---------------------------------------------------------------------------

class ArchetypeCreate(TypedDict):
    code: str
    name: str
    allowed_geometry_kinds: list[GeometryKind]
    default_parameters: dict[str, object]

    # Optional because the database accepts NULL
    description: NotRequired[str | None]

    # Optional because the database defaults to "1.0"
    model_version: NotRequired[str]


class UrbanInterventionCreateBase(TypedDict):
    market_code: str
    name: str
    color: str
    archetype_code: str
    geometry: Geometry

    # Optional database fields with defaults or nullable columns
    status: NotRequired[InterventionStatus]
    active_from: NotRequired[datetime | None]
    active_to: NotRequired[datetime | None]


class CoolRoofInterventionCreate(UrbanInterventionCreateBase):
    intervention_type: Literal["cool_roof"]
    parameters: CoolRoofParams


class MistingStationInterventionCreate(UrbanInterventionCreateBase):
    intervention_type: Literal["misting_station"]
    parameters: MistingStationParams


class StreetTreeInterventionCreate(UrbanInterventionCreateBase):
    intervention_type: Literal["street_tree"]
    parameters: StreetTreeParams


class ShadeStructureInterventionCreate(UrbanInterventionCreateBase):
    intervention_type: Literal["shade_structure"]
    parameters: ShadeStructureParams


class CoolPavementInterventionCreate(UrbanInterventionCreateBase):
    intervention_type: Literal["cool_pavement"]
    parameters: CoolPavementParams


UrbanInterventionCreate: TypeAlias = (
    CoolRoofInterventionCreate
    | MistingStationInterventionCreate
    | StreetTreeInterventionCreate
    | ShadeStructureInterventionCreate
    | CoolPavementInterventionCreate
)