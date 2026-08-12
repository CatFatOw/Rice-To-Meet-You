"""Repository for reading and writing points of interest in ``core_poi_geometry``.

Follows the same conventions as ``HeatmapRepository``:

* the session is injected and **never** closed or committed here — the caller
  (request scope / service layer) owns the transaction;
* the table is reflected lazily, so new columns need no code change;
* methods are grouped into public API / DB helpers / pure helpers.

Usage::

    repo = CorePoiGeometryRepository(db)
    poi = repo.create({
        "market_code": "dallas",
        "poi_name": "Klyde Warren Park",
        "poi_type": "park",
        "longitude": -96.8016,
        "latitude": 32.7893,
    })
    db.commit()          # <- caller commits

    rows = repo.getAllByMarketCode("dallas")
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy import Column, MetaData, Table, func, insert, inspect, select, text
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.orm import Session

__all__ = ["CorePoiGeometryRepository"]


class CorePoiGeometryRepository:
    """Repository for POI geometry rows."""

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #

    TABLE_NAME = "core_poi_geometry"

    #: Postgres schema. ``None`` uses the session's ``search_path``.
    SCHEMA: Optional[str] = None

    #: SRID used when building a point from longitude/latitude.
    DEFAULT_SRID = 4326

    #: Accepted spellings for the coordinate inputs.
    LONGITUDE_ALIASES = ("longitude", "lon", "lng", "long", "x")
    LATITUDE_ALIASES = ("latitude", "lat", "y")

    #: Column names that hold a PostGIS geometry, if the type check misses.
    GEOMETRY_COLUMN_NAMES = ("geom", "geometry", "the_geom", "shape", "location")

    #: Never settable by a caller — the database owns these.
    PROTECTED_COLUMNS = frozenset({"created_at", "updated_at", "inserted_at"})

    #: Column that scopes a POI to a market.
    MARKET_CODE_COLUMN = "market_code"

    #: First of these that exists is used to order read results; falls back to
    #: the primary key so paging stays deterministic.
    ORDER_BY_PREFERENCE = ("poi_name", "name")

    # ================================================================== #
    #                                                                    #
    #   TIER 1 — MAIN METHODS (public API)                               #
    #                                                                    #
    # ================================================================== #

    def __init__(self, db: Session, schema: Optional[str] = None) -> None:
        """Initialize the repository with an active database session.

        Args:
            db: Active SQLAlchemy session. Not closed or committed by this class.
            schema: Schema holding ``core_poi_geometry``. Defaults to ``SCHEMA``.
        """
        self.db = db
        self.schema = schema if schema is not None else self.SCHEMA
        self._metadata = MetaData()
        self._table_cache: Optional[Table] = None

    def getAllByMarketCode(
        self,
        market_code: str,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return every POI whose ``market_code`` matches.

        Args:
            market_code: Exact value to match. Matching is case-sensitive, as
                the column is stored.
            limit: Optional cap on rows returned.
            offset: Optional number of rows to skip; requires ``limit`` to be
                meaningful under a stable ordering.

        Returns:
            Rows as plain dicts, ordered by name (or primary key), empty when
            the market has no POIs. Geometry comes back as EWKT.

        Raises:
            ValueError: The table has no ``market_code`` column.
        """
        column = self._column(self.MARKET_CODE_COLUMN)

        stmt = (
            select(*self._returning_columns())
            .where(column == market_code)
            .order_by(*self._default_order_by())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)

        return [dict(row) for row in self.db.execute(stmt).mappings().all()]

    def create(
        self,
        poi: Optional[Mapping[str, Any]] = None,
        *,
        strict: bool = True,
        **fields: Any,
    ) -> Dict[str, Any]:
        """Insert one POI row and return it.

        Accepts either a mapping or keyword arguments::

            repo.create({"poi_name": "Klyde Warren Park", ...})
            repo.create(poi_name="Klyde Warren Park", ...)

        If the table has a PostGIS geometry column and the payload carries
        ``longitude``/``latitude`` instead of a geometry, the point is built
        with ``ST_SetSRID(ST_MakePoint(lon, lat), 4326)``.

        Args:
            poi: Column values as a mapping.
            strict: Raise on keys that are not columns. When ``False``, unknown
                keys are dropped silently.
            **fields: Column values as keywords, merged over ``poi``.

        Returns:
            The inserted row as a plain dict. Geometry comes back as EWKT.

        Raises:
            ValueError: Unknown columns (strict), missing required columns, or
                an unusable coordinate pair.
        """
        payload = self._merge_payload(poi, fields)
        values = self._build_values(payload, strict=strict)

        stmt = insert(self._table).values(**values).returning(*self._returning_columns())
        row = self.db.execute(stmt).mappings().one()

        self.db.flush()  # surface constraint violations now, still no commit
        return dict(row)

    def createMany(
        self,
        pois: Sequence[Mapping[str, Any]],
        *,
        strict: bool = True,
    ) -> List[Dict[str, Any]]:
        """Insert several POIs in one round trip. Same rules as ``create``."""
        if not pois:
            return []

        rows = [self._build_values(dict(p), strict=strict) for p in pois]
        stmt = insert(self._table).values(rows).returning(*self._returning_columns())
        result = [dict(r) for r in self.db.execute(stmt).mappings().all()]

        self.db.flush()
        return result

    #: Backward-compatible aliases.
    createPOI = create
    createManyPOIs = createMany
    getAllPOIsByMarketCode = getAllByMarketCode

    #: Snake-case aliases.
    create_poi = create
    create_many_pois = createMany
    get_all_by_market_code = getAllByMarketCode

    # ================================================================== #
    #                                                                    #
    #   TIER 2 — DATABASE HELPERS (internal, touch the session)          #
    #                                                                    #
    # ================================================================== #

    @property
    def _table(self) -> Table:
        """Reflected ``core_poi_geometry`` table (lazy, cached)."""
        if self._table_cache is None:
            self._table_cache = self._reflect(self.TABLE_NAME)
        return self._table_cache

    def _reflect(self, name: str) -> Table:
        """Reflect the table, turning a bare NoSuchTableError into a useful one."""
        try:
            return Table(
                name,
                self._metadata,
                schema=self.schema,
                autoload_with=self.db.get_bind(),
            )
        except NoSuchTableError:
            raise NoSuchTableError(self._diagnose_missing_table(name)) from None

    def _diagnose_missing_table(self, name: str) -> str:
        """Explain *why* reflection failed: wrong DB, wrong schema, no table."""
        bind = self.db.get_bind()
        lines = [
            f"Could not reflect '{name}' (schema={self.schema or 'search_path'}).",
            f"  Engine URL: {bind.url.render_as_string(hide_password=True)}",
        ]
        try:
            inspector = inspect(bind)
            locations = [
                s
                for s in inspector.get_schema_names()
                if name in inspector.get_table_names(schema=s)
                or name in inspector.get_view_names(schema=s)
            ]
            if locations:
                lines.append(
                    f"  Found it in schema(s): {locations}. Pass "
                    f"schema='{locations[0]}' to CorePoiGeometryRepository."
                )
            else:
                lines.append(
                    "  Not visible to this connection - check DATABASE_URL, the "
                    "Neon branch/database, and role permissions."
                )
        except Exception:  # pragma: no cover - diagnostics must not mask the error
            pass
        return "\n".join(lines)

    @property
    def _is_postgres(self) -> bool:
        return self.db.get_bind().dialect.name == "postgresql"

    def _column(self, name: str) -> Column:
        """Look up a column, failing with the valid names rather than a KeyError."""
        column = self._table.c.get(name)
        if column is None:
            raise ValueError(
                f"{self.TABLE_NAME} has no '{name}' column. "
                f"Valid columns: {sorted(c.name for c in self._table.c)}"
            )
        return column

    def _default_order_by(self) -> List[Any]:
        """A stable ordering for reads: preferred name column, else the PK."""
        for name in self.ORDER_BY_PREFERENCE:
            column = self._table.c.get(name)
            if column is not None:
                return [column]
        return list(self._table.primary_key.columns)

    def _returning_columns(self) -> List[Any]:
        """All columns, with geometry rendered as EWKT rather than raw WKB."""
        columns: List[Any] = []
        for column in self._table.c:
            if self._is_geometry_column(column) and self._is_postgres:
                columns.append(func.ST_AsEWKT(column).label(column.name))
            else:
                columns.append(column)
        return columns

    def _build_values(self, payload: Dict[str, Any], *, strict: bool) -> Dict[str, Any]:
        """Validate a payload and turn it into an INSERT values dict."""
        table = self._table
        column_names = {c.name for c in table.c}

        payload = self._apply_coordinate_aliases(payload, column_names)
        geometry_column = self._geometry_column()

        # Coordinates -> geometry, when the table wants a geometry and the
        # caller did not supply one directly.
        lon, lat = payload.pop("__lon__", None), payload.pop("__lat__", None)
        if geometry_column is not None and geometry_column.name not in payload:
            if lon is not None and lat is not None:
                payload[geometry_column.name] = self._make_point(lon, lat)
            elif not geometry_column.nullable:
                raise ValueError(
                    f"'{geometry_column.name}' is required: supply it directly or "
                    "provide longitude and latitude."
                )

        unknown = sorted(set(payload) - column_names)
        if unknown:
            if strict:
                raise ValueError(
                    f"Unknown column(s) for {self.TABLE_NAME}: {unknown}. "
                    f"Valid columns: {sorted(column_names)}"
                )
            for key in unknown:
                payload.pop(key)

        for key in self.PROTECTED_COLUMNS & set(payload):
            payload.pop(key)

        missing = self._missing_required_columns(payload)
        if missing:
            raise ValueError(
                f"Missing required column(s) for {self.TABLE_NAME}: {sorted(missing)}"
            )

        return payload

    def _geometry_column(self) -> Optional[Column]:
        """The table's geometry column, if it has one."""
        for column in self._table.c:
            if self._is_geometry_column(column):
                return column
        return None

    def _missing_required_columns(self, payload: Mapping[str, Any]) -> List[str]:
        """NOT NULL columns with no default that the payload does not cover."""
        missing = []
        for column in self._table.c:
            if column.name in payload or column.nullable:
                continue
            if column.default is not None or column.server_default is not None:
                continue
            if column.primary_key and column.autoincrement:
                continue
            missing.append(column.name)
        return missing

    def _make_point(self, longitude: Any, latitude: Any) -> Any:
        """Build a SRID-tagged point expression from a coordinate pair."""
        lon, lat = self._validate_coordinates(longitude, latitude)
        if not self._is_postgres:
            return f"POINT({lon} {lat})"  # SQLite/tests: store as WKT text
        return func.ST_SetSRID(func.ST_MakePoint(lon, lat), self.DEFAULT_SRID)

    # ================================================================== #
    #                                                                    #
    #   TIER 3 — PURE HELPERS (no DB access, no side effects)            #
    #                                                                    #
    # ================================================================== #

    @staticmethod
    def _merge_payload(
        poi: Optional[Mapping[str, Any]], fields: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """Combine the mapping and keyword forms; keywords win."""
        merged: Dict[str, Any] = dict(poi or {})
        merged.update(fields)
        if not merged:
            raise ValueError("create requires at least one column value.")
        return merged

    def _apply_coordinate_aliases(
        self, payload: Dict[str, Any], column_names: Iterable[str]
    ) -> Dict[str, Any]:
        """Normalize lon/lat spellings, stashing them under private keys.

        If the table has real ``longitude``/``latitude`` columns, the values are
        also written straight through to them.
        """
        column_names = set(column_names)
        result = dict(payload)

        for aliases, slot in (
            (self.LONGITUDE_ALIASES, "__lon__"),
            (self.LATITUDE_ALIASES, "__lat__"),
        ):
            for alias in aliases:
                if alias in result and result[alias] is not None:
                    value = result[alias]
                    result[slot] = value
                    # Keep the canonical column if the table actually has one.
                    canonical = aliases[0]
                    if canonical in column_names:
                        result[canonical] = value
                    if alias not in column_names:
                        result.pop(alias, None)
                    break

        return result

    @staticmethod
    def _validate_coordinates(longitude: Any, latitude: Any) -> Tuple[float, float]:
        """Range-check a coordinate pair. Catches swapped lon/lat early."""
        try:
            lon, lat = float(longitude), float(latitude)
        except (TypeError, ValueError):
            raise ValueError(
                f"Coordinates must be numeric, got ({longitude!r}, {latitude!r})."
            ) from None
        if not -180.0 <= lon <= 180.0:
            raise ValueError(f"Longitude {lon} is outside [-180, 180].")
        if not -90.0 <= lat <= 90.0:
            raise ValueError(
                f"Latitude {lat} is outside [-90, 90] - are lon/lat swapped?"
            )
        return lon, lat

    @classmethod
    def _is_geometry_column(cls, column: Column) -> bool:
        """True for PostGIS geometry/geography columns."""
        if column.name.lower() in cls.GEOMETRY_COLUMN_NAMES:
            return True
        try:
            type_name = str(column.type).lower()
        except Exception:  # pragma: no cover - some dialect types refuse str()
            type_name = type(column.type).__name__.lower()
        return "geometry" in type_name or "geography" in type_name