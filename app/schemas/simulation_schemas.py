"""Payload shapes shared by the heatmap and the intervention toolbox.

Port of the parts of `types/heatmap.ts` and `hooks/usePlacedObjects.ts` that the
simulation actually depends on.

These are TypedDicts rather than dataclasses because they cross the wire as
JSON. The *keys* therefore keep the exact spelling the TypeScript side uses —
`activeFrom`, `coverPct`, `deltaAlbedo` and so on stay camelCase, since renaming
them would break deserialization. Python-side identifiers (functions, locals)
use snake_case as usual. If your API layer already snake_cases incoming
payloads, change the key literals here and in `simulation.py` to match.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict, Union
from pydantic import BaseModel, Field

# [longitude, latitude] — GeoJSON order, note it's lng first.
Coordinates = tuple[float, float]

# A closed ring of coordinates.
Polygon = list[Coordinates]


class HeatmapMetricValue(TypedDict, total=False):
    """A single measured / interpolated reading at one coordinate.

    `value` and `location_coordinates` are always present; `individual_metrics`
    is an open bag of human-readable sub-metrics where every value is a string
    carrying its own unit (e.g. "97°C", "62%").
    """

    value: float
    location_coordinates: Coordinates
    individual_metrics: dict[str, str]


# Date -> readings for that day, e.g. {"2020-01-01": [...]}.
HeatmapPointsByDate = dict[str, list[HeatmapMetricValue]]


class Geometry(TypedDict, total=False):
    """Drawn footprint of a placed object.

    A `point` carries longitude/latitude, a `line` carries `coordinates`, and a
    `polygon` carries `ring`.
    """

    kind: Literal["point", "line", "polygon"]
    longitude: float
    latitude: float
    coordinates: list[Coordinates]
    ring: Polygon


# Design params carried by a placed object (deltaAlbedo, coverPct, lai, ...).
# Kept as a plain numeric mapping so the simulation stays archetype-agnostic.
PlacedObjectParams = dict[str, float]


class BasePlacedObject(TypedDict, total=False):
    """One planner-placed intervention.

    `activeFrom` / `activeTo` are ISO date strings (e.g. "2025-07-01") and are
    optional — an absent bound means open-ended on that side.
    """

    id: str
    type: str
    category: str
    name: str
    color: str
    market_code: str
    geometry: Geometry
    params: PlacedObjectParams
    activeFrom: str
    activeTo: str


# The archetype buckets a placed object can belong to.
PlacedObjectCategory = Literal[
    "Vegetation",
    "High-albedo surface",
    "Shade structure",
    "Evaporative / water",
]

# Canonical iteration order and a stable list of every category.
PLACED_OBJECT_CATEGORIES: list[PlacedObjectCategory] = [
    "Vegetation",
    "High-albedo surface",
    "Shade structure",
    "Evaporative / water",
]

# Placed objects grouped by archetype category.
BasePlacedObjectCategorized = dict[str, list[BasePlacedObject]]


class SimulationRequest(BaseModel):
    """Payload for running a simulated points calculation."""

    metric: str
    points_by_date: Dict[str, List[Dict[str, Any]]]
    placed_objects: Dict[str, List[Dict[str, Any]]]
    mode: Literal["standard", "contextual"] = "standard"


def flatten_categorized(
    categorized: BasePlacedObjectCategorized,
) -> list[BasePlacedObject]:
    """Flatten the categorized collection into one list, in canonical order."""
    return [
        obj
        for category in PLACED_OBJECT_CATEGORIES
        for obj in categorized.get(category, [])
    ]