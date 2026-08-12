"""Repository for the ``urban_interventions`` table.

Write methods flush but never commit — transaction boundaries belong to the
caller / unit of work.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final, Mapping, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from schemas.urban_intervention import (
    Coordinate,
    Geometry,
    GeometryKind,
    InterventionStatus,
    InterventionType,
    UrbanInterventionCreate,
)

SRID: Final[int] = 4326

# Columns that may be omitted by the caller; the database supplies a default
# (``status``) or accepts NULL (``active_from`` / ``active_to``).
_OPTIONAL_COLUMNS: Final[tuple[str, ...]] = ("status", "active_from", "active_to")

_REQUIRED_PARAM_KEYS: Final[Mapping[InterventionType, frozenset[str]]] = {
    "cool_roof": frozenset({"albedo", "emissivity"}),
    "misting_station": frozenset(
        {
            "nozzleCount",
            "flowRate_L_per_min",
            "dropletDiameter_um",
            "mountHeight_m",
        }
    ),
    "street_tree": frozenset(
        {"canopyRadius_m", "canopyHeight_m", "lai", "deciduous"}
    ),
    "shade_structure": frozenset({"transmissivity", "height_m"}),
    "cool_pavement": frozenset({"albedo", "width_m"}),
}

# The projection every read and write shares, so ``_to_record`` can map either.
_COLUMNS: Final[str] = """
    id,
    market_code,
    name,
    archetype_code,
    intervention_type,
    geometry_kind,
    ST_AsGeoJSON(geometry) AS geometry_geojson,
    parameters,
    status,
    active_from,
    active_to
"""


class InvalidGeometryError(ValueError):
    """Raised when a geometry payload cannot be expressed as valid WKT."""


class InvalidParametersError(ValueError):
    """Raised when ``parameters`` do not match the given ``intervention_type``."""


@dataclass(frozen=True, slots=True)
class UrbanInterventionRecord:
    """A row as it exists in the database."""

    id: UUID
    market_code: str
    name: str
    archetype_code: str
    intervention_type: InterventionType
    geometry_kind: GeometryKind
    geometry: dict[str, Any]
    parameters: dict[str, Any]
    status: InterventionStatus
    active_from: datetime | None
    active_to: datetime | None


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _num(value: float) -> str:
    """Render a coordinate component as WKT-safe text."""
    number = float(value)
    if not math.isfinite(number):
        raise InvalidGeometryError("Coordinates must be finite numbers.")
    return repr(number)


def _pair(coordinate: Coordinate) -> str:
    longitude, latitude = coordinate
    if not -180.0 <= float(longitude) <= 180.0:
        raise InvalidGeometryError(f"Longitude out of range: {longitude!r}")
    if not -90.0 <= float(latitude) <= 90.0:
        raise InvalidGeometryError(f"Latitude out of range: {latitude!r}")
    return f"{_num(longitude)} {_num(latitude)}"


def _close_ring(ring: Sequence[Coordinate]) -> list[Coordinate]:
    """Repeat the first vertex at the end if the caller left the ring open."""
    points = list(ring)
    if points and points[0] != points[-1]:
        points.append(points[0])
    return points


def geometry_to_wkt(geometry: Geometry) -> tuple[GeometryKind, str]:
    """Convert the discriminated geometry union into ``(kind, wkt)``."""
    kind = geometry["kind"]

    if kind == "point":
        return "point", f"POINT({_pair((geometry['longitude'], geometry['latitude']))})"

    if kind == "line":
        coordinates = geometry["coordinates"]
        if len(coordinates) < 2:
            raise InvalidGeometryError("A line needs at least 2 coordinates.")
        body = ", ".join(_pair(point) for point in coordinates)
        return "line", f"LINESTRING({body})"

    if kind == "polygon":
        ring = _close_ring(geometry["ring"])
        if len(ring) < 4:
            raise InvalidGeometryError(
                "A polygon ring needs at least 3 distinct coordinates."
            )
        body = ", ".join(_pair(point) for point in ring)
        return "polygon", f"POLYGON(({body}))"

    raise InvalidGeometryError(f"Unsupported geometry kind: {kind!r}")


def _validate_parameters(
    intervention_type: InterventionType,
    parameters: Mapping[str, Any],
) -> None:
    expected = _REQUIRED_PARAM_KEYS.get(intervention_type)
    if expected is None:
        raise InvalidParametersError(
            f"Unknown intervention type: {intervention_type!r}"
        )
    missing = expected - parameters.keys()
    if missing:
        raise InvalidParametersError(
            f"{intervention_type!r} is missing parameters: {sorted(missing)}"
        )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class UrbanInterventionRepository:
    """Data access for ``urban_interventions``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    # -- reads --------------------------------------------------------------

    def get_many_by_city_and_date(
        self,
        city: str,
        as_of: datetime | date,
        *,
        statuses: Sequence[InterventionStatus] | None = None,
    ) -> list[UrbanInterventionRecord]:
        """Return every intervention in ``city`` whose window covers ``as_of``.

        A NULL ``active_from`` or ``active_to`` is treated as an open-ended
        bound, so a row with no end date still matches a future date. Drop the
        ``IS NULL`` branches if you want NULL to mean "never active" instead.

        Args:
            city: value matched against ``market_code``.
            as_of: the instant the activity window is evaluated against.
            statuses: optional status whitelist; omit to include all statuses.

        Returns:
            Records ordered by name, empty if nothing matches.
        """
        bindings: dict[str, Any] = {"city": city, "as_of": as_of}

        status_filter = ""
        if statuses is not None:
            if not statuses:
                return []
            status_filter = "AND status = ANY(:statuses)"
            bindings["statuses"] = list(statuses)

        statement = text(
            f"""
            SELECT {_COLUMNS}
            FROM urban_interventions
            WHERE market_code = :city
              AND (active_from IS NULL OR active_from <= :as_of)
              AND (active_to   IS NULL OR active_to   >= :as_of)
              {status_filter}
            ORDER BY name, id
            """
        )

        rows = self._session.execute(statement, bindings).mappings().all()
        return [self._to_record(row) for row in rows]

    # Convenience alias for callers using the camelCase name.
    getManyByCityAndDate = get_many_by_city_and_date  # noqa: N815

    # -- writes -------------------------------------------------------------

    def create(self, data: UrbanInterventionCreate) -> UrbanInterventionRecord:
        """Insert one intervention and return the persisted row.

        Raises:
            InvalidGeometryError: the geometry cannot be rendered as WKT.
            InvalidParametersError: ``parameters`` don't match the type.
        """
        intervention_type: InterventionType = data["intervention_type"]
        parameters = data["parameters"]
        _validate_parameters(intervention_type, parameters)

        geometry_kind, wkt = geometry_to_wkt(data["geometry"])

        columns: list[str] = [
            "market_code",
            "name",
            "archetype_code",
            "intervention_type",
            "geometry_kind",
            "geometry",
            "parameters",
        ]
        placeholders: list[str] = [
            ":market_code",
            ":name",
            ":archetype_code",
            ":intervention_type",
            ":geometry_kind",
            f"ST_GeomFromText(:geometry_wkt, {SRID})",
            "CAST(:parameters AS jsonb)",
        ]
        bindings: dict[str, Any] = {
            "market_code": data["market_code"],
            "name": data["name"],
            "archetype_code": data["archetype_code"],
            "intervention_type": intervention_type,
            "geometry_kind": geometry_kind,
            "geometry_wkt": wkt,
            "parameters": json.dumps(parameters),
        }

        # Only send optional columns the caller actually set, so the database
        # keeps ownership of its defaults.
        for column in _OPTIONAL_COLUMNS:
            if column in data:
                columns.append(column)
                placeholders.append(f":{column}")
                bindings[column] = data[column]  # type: ignore[literal-required]

        statement = text(
            f"""
            INSERT INTO urban_interventions ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
            RETURNING {_COLUMNS}
            """
        )

        row = self._session.execute(statement, bindings).mappings().one()
        self._session.flush()
        return self._to_record(row)

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _to_record(row: Mapping[str, Any]) -> UrbanInterventionRecord:
        geometry = row["geometry_geojson"]
        if isinstance(geometry, str):
            geometry = json.loads(geometry)

        parameters = row["parameters"]
        if isinstance(parameters, str):
            parameters = json.loads(parameters)

        return UrbanInterventionRecord(
            id=row["id"],
            market_code=row["market_code"],
            name=row["name"],
            archetype_code=row["archetype_code"],
            intervention_type=row["intervention_type"],
            geometry_kind=row["geometry_kind"],
            geometry=geometry,
            parameters=parameters,
            status=row["status"],
            active_from=row["active_from"],
            active_to=row["active_to"],
        )