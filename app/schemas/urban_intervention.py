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
# ---------------------------------------------------------------------------

class CoolRoofParams(TypedDict):
    albedo: float
    emissivity: float


class MistingStationParams(TypedDict):
    nozzleCount: int
    flowRate_L_per_min: float
    dropletDiameter_um: float
    mountHeight_m: float


class StreetTreeParams(TypedDict):
    canopyRadius_m: float
    canopyHeight_m: float
    lai: float
    deciduous: bool


class ShadeStructureParams(TypedDict):
    transmissivity: float
    height_m: float


class CoolPavementParams(TypedDict):
    albedo: float
    width_m: float


Params: TypeAlias = (
    CoolRoofParams
    | MistingStationParams
    | StreetTreeParams
    | ShadeStructureParams
    | CoolPavementParams
)


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