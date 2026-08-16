
"""Repository for reading and writing points of interest in ``core_poi_geometry``.

Follows the same conventions as ``HeatmapRepository``:

* the session is injected and **never** closed or committed here — the caller
  (request scope / service layer) owns the transaction;
* tables are reflected lazily and the reflection is shared, so new columns need
  no code change and per-request instances stay cheap;
* methods are grouped into public API / DB helpers / pure helpers.

Caching
-------

``initializeTable`` loads every POI **annotated with its average urban heat
index** and stores the result in the instance variable ``self._rows``::

    WITH uhi_by_placekey AS (
        SELECT poi.placekey,
               AVG(uhi.uhi)   AS average_uhi,
               COUNT(uhi.id)  AS matched_uhi_count
        FROM core_poi_geometry AS poi
        LEFT JOIN core_poi_uhi_mapping AS mapping
            ON mapping.core_poi_id = poi.id
        LEFT JOIN urban_heat_index_updated AS uhi
            ON uhi.id = mapping.urban_heat_index_id
        WHERE poi.placekey IS NOT NULL
        GROUP BY poi.placekey
    )
    SELECT poi.*, aggregated.average_uhi, aggregated.matched_uhi_count
    FROM core_poi_geometry AS poi
    LEFT JOIN uhi_by_placekey AS aggregated
        ON aggregated.placekey = poi.placekey
    ORDER BY poi.id;

The aggregate is per ``placekey``, so POIs sharing a placekey share the same
``average_uhi`` and ``matched_uhi_count``. Rows with a NULL placekey, or with
no mapped readings, come back as ``average_uhi = None``,
``matched_uhi_count = 0``.

Because FastAPI builds one repository per request, a purely per-instance cache
would reload on every request. So the loaded rows are also published to a
process-wide snapshot that ``initialize_tables(engine)`` can warm at startup;
a new instance adopts that snapshot in ``__init__`` and only copies it if it
writes. ``self._rows`` is the instance's view either way.

Usage::

    # startup
    CorePoiGeometryRepository.initialize_tables(engine)

    # per request
    repo = CorePoiGeometryRepository(db)
    repo.getAllByMarketCode("dallas")     # served from self._rows
    repo.getByPlacekey("222@8fy-fjh-4d9")

Staleness: the aggregate is a snapshot. Writes to ``core_poi_uhi_mapping`` or
``urban_heat_index_updated`` do not invalidate it — call ``refresh(engine)``
after an ingest.
"""

from __future__ import annotations

import threading
from typing import (
    Any,
    ClassVar,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from sqlalchemy import Column, MetaData, Table, event, func, insert, inspect, select
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.orm import Session

__all__ = ["CorePoiGeometryRepository"]


class CorePoiGeometryRepository:
    """Repository for POI geometry rows, cached with their average UHI."""

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #

    TABLE_NAME = "core_poi_geometry"

    #: Postgres schema. ``None`` uses the connection's ``search_path``.
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

    #: Business key the heat index is aggregated by.
    PLACEKEY_COLUMN = "placekey"

    #: Join path from a POI to its urban heat index readings.
    UHI_MAPPING_TABLE = "core_poi_uhi_mapping"
    UHI_MAPPING_POI_COLUMN = "core_poi_id"
    UHI_MAPPING_UHI_COLUMN = "urban_heat_index_id"
    UHI_TABLE = "urban_heat_index_updated"
    UHI_VALUE_COLUMN = "uhi"

    #: Derived keys the load query adds on top of ``core_poi_geometry``.
    AVERAGE_UHI_KEY = "average_uhi"
    MATCHED_UHI_COUNT_KEY = "matched_uhi_count"

    #: First of these that exists orders the cache; falls back to the primary
    #: key. Mirrors ``ORDER BY poi.id`` in the load query.
    ORDER_BY_PREFERENCE = ("id",)

    # ------------------------------------------------------------------ #
    # Shared state (process-wide, guarded by ``_cache_lock``)
    # ------------------------------------------------------------------ #

    _cache_lock: ClassVar[threading.RLock] = threading.RLock()
    _metadata: ClassVar[Optional[MetaData]] = None
    _table_cache: ClassVar[Optional[Table]] = None
    _related_tables: ClassVar[Dict[Tuple[Optional[str], str], Table]] = {}
    _cached_schema: ClassVar[Optional[str]] = None
    _shared_rows: ClassVar[Optional[List[Dict[str, Any]]]] = None
    _shared_by_market: ClassVar[Dict[Any, List[Dict[str, Any]]]] = {}

    # ================================================================== #
    #                                                                    #
    #   TIER 0 — CLASS-LEVEL CACHE CONTROL (startup / maintenance)       #
    #                                                                    #
    # ================================================================== #

    @classmethod
    def initialize_metadata(cls, engine, schema: Optional[str] = None) -> Table:
        """Reflect ``core_poi_geometry`` once, without reading any rows.

        Cheap and safe at startup: it makes every later request skip
        reflection. Reflecting under a different schema resets the row cache.

        Raises:
            NoSuchTableError: With a diagnosis of *why* it was not found.
        """
        schema = schema if schema is not None else cls.SCHEMA
        with cls._cache_lock:
            if cls._table_cache is not None and cls._cached_schema == schema:
                return cls._table_cache

            metadata = MetaData()
            table = cls._reflect(engine, cls.TABLE_NAME, schema, metadata)

            cls._metadata = metadata
            cls._table_cache = table
            cls._related_tables = {}
            cls._cached_schema = schema
            cls._shared_rows = None
            cls._shared_by_market = {}
            return table

    @classmethod
    def initialize_tables(cls, engine, schema: Optional[str] = None) -> int:
        """Run the load query and publish the result as the shared snapshot.

        Blocking; run it off the event loop (``asyncio.to_thread``). Every
        repository built afterwards adopts these rows for free.

        Returns:
            Number of rows cached.
        """
        stmt = cls._load_statement(engine, schema)
        with engine.connect() as connection:
            rows = [
                cls._normalize_row(row)
                for row in connection.execute(stmt).mappings().all()
            ]

        with cls._cache_lock:
            cls._shared_rows, cls._shared_by_market = cls._build_index(rows)
        return len(rows)

    @classmethod
    def refresh(cls, engine, schema: Optional[str] = None) -> int:
        """Re-run the load query, replacing the shared snapshot.

        Call this after an ingest into ``core_poi_uhi_mapping`` or
        ``urban_heat_index_updated``: those tables are joined at load time and
        the repository cannot notice they changed.
        """
        with cls._cache_lock:
            cls._shared_rows = None
            cls._shared_by_market = {}
        return cls.initialize_tables(engine, schema)

    @classmethod
    def invalidate_cache(cls, *, drop_metadata: bool = False) -> None:
        """Drop the shared snapshot. Instances built later reload on demand."""
        with cls._cache_lock:
            cls._shared_rows = None
            cls._shared_by_market = {}
            if drop_metadata:
                cls._metadata = None
                cls._table_cache = None
                cls._related_tables = {}
                cls._cached_schema = None

    @classmethod
    def cache_stats(cls) -> Dict[str, Any]:
        """Snapshot of cache state, for logging and health checks."""
        with cls._cache_lock:
            rows = cls._shared_rows
            matched = (
                sum(1 for r in rows if r.get(cls.MATCHED_UHI_COUNT_KEY))
                if rows is not None
                else 0
            )
            return {
                "table": cls.TABLE_NAME,
                "schema": cls._cached_schema or "search_path",
                "reflected": cls._table_cache is not None,
                "loaded": rows is not None,
                "rows": len(rows) if rows is not None else 0,
                "markets": len(cls._shared_by_market),
                "rows_with_uhi": matched,
            }

    @classmethod
    def is_initialized(cls) -> bool:
        """True once the shared snapshot has been loaded."""
        return cls._shared_rows is not None

    # ================================================================== #
    #                                                                    #
    #   TIER 1 — MAIN METHODS (public API)                               #
    #                                                                    #
    # ================================================================== #

    def __init__(self, db: Session, schema: Optional[str] = None) -> None:
        """Initialize the repository with an active database session.

        Adopts the shared snapshot when one exists, so construction costs
        nothing and does no database work.

        Args:
            db: Active SQLAlchemy session. Not closed or committed by this class.
            schema: Schema holding the tables. Defaults to ``SCHEMA``.
        """
        self.db = db
        self.schema = schema if schema is not None else self.SCHEMA

        cls = type(self)
        with cls._cache_lock:
            adopt = cls._shared_rows is not None and cls._cached_schema == self.schema
            #: POIs with their average UHI, ordered by id. The instance cache.
            self._rows: Optional[List[Dict[str, Any]]] = (
                cls._shared_rows if adopt else None
            )
            self._rows_by_market: Dict[Any, List[Dict[str, Any]]] = (
                cls._shared_by_market if adopt else {}
            )

        #: False while ``_rows`` still points at the shared snapshot. Writes
        #: copy first, so one request's inserts stay out of everyone else's view.
        self._owns_rows = False

        #: Rows inserted but not committed, awaiting publication to the snapshot.
        self._pending: List[Dict[str, Any]] = []
        self._hooks_registered = False

    def initializeTable(self, *, force: bool = False) -> List[Dict[str, Any]]:
        """Load every POI with its average UHI into ``self._rows``.

        Runs the placekey aggregate shown in the module docstring and stores
        the result on the instance. Normally a no-op, because startup already
        warmed the shared snapshot; this is the lazy fallback for when the
        preload failed or was skipped.

        Args:
            force: Reload even when rows are already present.

        Returns:
            The cached rows (the instance's own list — treat as read-only).
        """
        if self._rows is not None and not force:
            return self._rows

        stmt = self._load_statement(self.db.get_bind(), self.schema)
        rows = [
            self._normalize_row(row) for row in self.db.execute(stmt).mappings().all()
        ]

        self._rows, self._rows_by_market = self._build_index(rows)
        self._owns_rows = True
        self._publish_snapshot()
        return self._rows

    def getAll(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return every cached POI with its average UHI, ordered by id."""
        self.initializeTable()
        return self._window(self._rows or [], limit=limit, offset=offset)

    def getAllByMarketCode(
        self,
        market_code: str,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return every POI whose ``market_code`` matches, from the cache.

        No database round trip once the cache is warm. Each row carries
        ``average_uhi`` and ``matched_uhi_count`` alongside its own columns.

        Args:
            market_code: Exact value to match. Matching is case-sensitive, as
                the column is stored.
            limit: Optional cap on rows returned.
            offset: Optional number of rows to skip.

        Returns:
            Copies of the cached rows as plain dicts, ordered by id, empty when
            the market has no POIs. Geometry is EWKT.

        Raises:
            ValueError: The table has no ``market_code`` column.
        """
        self._column(self.MARKET_CODE_COLUMN)  # validates the column exists
        self.initializeTable()

        rows = self._rows_by_market.get(market_code, [])
        return self._window(rows, limit=limit, offset=offset)

    def getByPlacekey(self, placekey: str) -> List[Dict[str, Any]]:
        """Return the cached POIs sharing a placekey (same UHI aggregate)."""
        self.initializeTable()
        key = self.PLACEKEY_COLUMN
        return [dict(r) for r in (self._rows or []) if r.get(key) == placekey]

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

        The row enters this instance's cache immediately and the shared
        snapshot on commit, with ``average_uhi = None`` and
        ``matched_uhi_count = 0``: a new POI has no mapping rows yet. If one is
        added later, the cache needs a ``refresh`` to pick it up.

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
        row = self._normalize_row(self.db.execute(stmt).mappings().one())

        self.db.flush()  # surface constraint violations now, still no commit
        self._add_rows([row])
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

        values = [self._build_values(dict(p), strict=strict) for p in pois]
        stmt = insert(self._table).values(values).returning(*self._returning_columns())
        inserted = [
            self._normalize_row(r) for r in self.db.execute(stmt).mappings().all()
        ]

        self.db.flush()
        self._add_rows(inserted)
        return [dict(r) for r in inserted]

    #: Backward-compatible aliases.
    createPOI = create
    createManyPOIs = createMany
    getAllPOIsByMarketCode = getAllByMarketCode

    #: Snake-case aliases.
    create_poi = create
    create_many_pois = createMany
    get_all_by_market_code = getAllByMarketCode
    get_all = getAll
    get_by_placekey = getByPlacekey
    initialize_table = initializeTable

    # ================================================================== #
    #                                                                    #
    #   TIER 2 — DATABASE HELPERS (internal, touch the session)          #
    #                                                                    #
    # ================================================================== #

    @property
    def _table(self) -> Table:
        """Reflected ``core_poi_geometry`` table (shared, lazy)."""
        cls = type(self)
        with cls._cache_lock:
            if cls._table_cache is not None and cls._cached_schema == self.schema:
                return cls._table_cache
        return cls.initialize_metadata(self.db.get_bind(), self.schema)

    @classmethod
    def _load_statement(cls, bind, schema: Optional[str] = None):
        """Build the placekey-aggregate load query.

        Equivalent to the ``WITH uhi_by_placekey AS (...) SELECT poi.*, ...``
        statement in the module docstring.
        """
        schema = schema if schema is not None else cls.SCHEMA
        poi = cls.initialize_metadata(bind, schema)
        mapping = cls._related_table(bind, cls.UHI_MAPPING_TABLE, schema)
        uhi = cls._related_table(bind, cls.UHI_TABLE, schema)

        placekey = cls._require_column(poi, cls.PLACEKEY_COLUMN)
        poi_id = cls._identity_column(poi)
        uhi_id = cls._identity_column(uhi)
        mapping_poi = cls._require_column(mapping, cls.UHI_MAPPING_POI_COLUMN)
        mapping_uhi = cls._require_column(mapping, cls.UHI_MAPPING_UHI_COLUMN)
        uhi_value = cls._require_column(uhi, cls.UHI_VALUE_COLUMN)

        aggregated = (
            select(
                placekey.label(cls.PLACEKEY_COLUMN),
                func.avg(uhi_value).label(cls.AVERAGE_UHI_KEY),
                func.count(uhi_id).label(cls.MATCHED_UHI_COUNT_KEY),
            )
            .select_from(
                poi.outerjoin(mapping, mapping_poi == poi_id).outerjoin(
                    uhi, uhi_id == mapping_uhi
                )
            )
            .where(placekey.is_not(None))
            .group_by(placekey)
            .cte("uhi_by_placekey")
        )

        return (
            select(
                *cls._returning_columns_for(poi, cls._bind_is_postgres(bind)),
                aggregated.c[cls.AVERAGE_UHI_KEY],
                aggregated.c[cls.MATCHED_UHI_COUNT_KEY],
            )
            .select_from(
                poi.outerjoin(aggregated, aggregated.c[cls.PLACEKEY_COLUMN] == placekey)
            )
            .order_by(*cls._order_by_for(poi))
        )

    @classmethod
    def _related_table(cls, bind, name: str, schema: Optional[str]) -> Table:
        """Reflect a joined table once, sharing the POI table's MetaData."""
        key = (schema, name)
        with cls._cache_lock:
            cached = cls._related_tables.get(key)
            if cached is not None:
                return cached
            metadata = cls._metadata
            if metadata is None:
                metadata = cls._metadata = MetaData()
            existing = metadata.tables.get(f"{schema}.{name}" if schema else name)

        table = (
            existing
            if existing is not None
            else cls._reflect(bind, name, schema, metadata)
        )
        with cls._cache_lock:
            cls._related_tables[key] = table
        return table

    @classmethod
    def _reflect(
        cls, bind, name: str, schema: Optional[str], metadata: MetaData
    ) -> Table:
        """Reflect one table, turning a bare NoSuchTableError into a useful one."""
        try:
            return Table(name, metadata, schema=schema, autoload_with=bind)
        except NoSuchTableError:
            raise NoSuchTableError(
                cls._diagnose_missing_table(bind, name, schema)
            ) from None

    @classmethod
    def _diagnose_missing_table(cls, bind, name: str, schema: Optional[str]) -> str:
        """Explain *why* reflection failed: wrong DB, wrong schema, no table."""
        lines = [
            f"Could not reflect '{name}' (schema={schema or 'search_path'}).",
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

    @staticmethod
    def _bind_is_postgres(bind) -> bool:
        return bind.dialect.name == "postgresql"

    @property
    def _is_postgres(self) -> bool:
        return self._bind_is_postgres(self.db.get_bind())

    def _column(self, name: str) -> Column:
        """Look up a POI column, failing with the valid names."""
        return self._require_column(self._table, name)

    def _returning_columns(self) -> List[Any]:
        """All POI columns, with geometry rendered as EWKT rather than raw WKB."""
        return self._returning_columns_for(self._table, self._is_postgres)

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

        # Derived keys are read-only: they come from the join, not the table.
        for key in (self.AVERAGE_UHI_KEY, self.MATCHED_UHI_COUNT_KEY):
            if key in payload and key not in column_names:
                payload.pop(key)

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
    #   TIER 2b — CACHE HELPERS                                          #
    #                                                                    #
    # ================================================================== #

    @classmethod
    def _build_index(
        cls, rows: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[Any, List[Dict[str, Any]]]]:
        """Pair a row list with a ``market_code`` index over the same dicts."""
        by_market: Dict[Any, List[Dict[str, Any]]] = {}
        for row in rows:
            by_market.setdefault(row.get(cls.MARKET_CODE_COLUMN), []).append(row)
        return rows, by_market

    def _publish_snapshot(self) -> None:
        """Offer this instance's rows to later instances as the shared snapshot."""
        cls = type(self)
        with cls._cache_lock:
            if cls._cached_schema == self.schema:
                cls._shared_rows = self._rows
                cls._shared_by_market = self._rows_by_market

    def _own_rows(self) -> None:
        """Copy-on-write: stop sharing the snapshot before mutating it."""
        if self._owns_rows:
            return
        self._rows, self._rows_by_market = self._build_index(list(self._rows or []))
        self._owns_rows = True

    def _add_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """Add inserted rows to this instance now, to the snapshot on commit."""
        if not rows:
            return

        if self._rows is not None:
            self._own_rows()
            sort_key = self._sort_key_for(self._table)
            touched: set = set()
            for row in rows:
                stored = dict(row)
                self._rows.append(stored)
                key = stored.get(self.MARKET_CODE_COLUMN)
                self._rows_by_market.setdefault(key, []).append(stored)
                touched.add(key)
            self._rows.sort(key=sort_key)
            for key in touched:
                self._rows_by_market[key].sort(key=sort_key)

        self._pending.extend(dict(r) for r in rows)
        self._register_session_hooks()

    def _register_session_hooks(self) -> None:
        """Publish pending rows on commit; drop them on rollback (once per repo)."""
        if self._hooks_registered:
            return
        self._hooks_registered = True
        repo = self
        cls = type(self)

        @event.listens_for(self.db, "after_commit")
        def _publish(session) -> None:  # pragma: no cover - driven by the session
            rows, repo._pending = repo._pending, []
            if not rows:
                return
            with cls._cache_lock:
                shared = cls._shared_rows
                if shared is None or cls._cached_schema != repo.schema:
                    return  # cold snapshot: the next load reads these from the DB
                if shared is repo._rows:
                    return  # same list object; already added
                sort_key = cls._sort_key_for(cls._table_cache)
                for row in rows:
                    stored = dict(row)
                    shared.append(stored)
                    cls._shared_by_market.setdefault(
                        stored.get(cls.MARKET_CODE_COLUMN), []
                    ).append(stored)
                shared.sort(key=sort_key)
                for bucket in cls._shared_by_market.values():
                    bucket.sort(key=sort_key)

        @event.listens_for(self.db, "after_soft_rollback")
        def _discard(session, previous_transaction) -> None:  # pragma: no cover
            repo._pending = []
            if repo._owns_rows:
                # This instance's view held the rolled-back rows; drop it and
                # re-adopt the snapshot on the next read.
                repo._rows = None
                repo._rows_by_market = {}
                repo._owns_rows = False

    @classmethod
    def _normalize_row(cls, row: Mapping[str, Any]) -> Dict[str, Any]:
        """Plain dict with the aggregate keys always present and typed.

        ``AVG`` comes back as ``Decimal`` on Postgres, and a POI with no match
        (or a NULL placekey) has no CTE row at all.
        """
        data = dict(row)
        data[cls.AVERAGE_UHI_KEY] = cls._as_float(data.get(cls.AVERAGE_UHI_KEY))
        data[cls.MATCHED_UHI_COUNT_KEY] = int(data.get(cls.MATCHED_UHI_COUNT_KEY) or 0)
        return data

    @classmethod
    def _order_by_names_for(cls, table: Table) -> List[str]:
        """Names of the columns that define the stable read ordering."""
        for name in cls.ORDER_BY_PREFERENCE:
            if table.c.get(name) is not None:
                return [name]
        return [c.name for c in table.primary_key.columns]

    @classmethod
    def _order_by_for(cls, table: Table) -> List[Any]:
        """A stable ordering for reads: ``id``, else the primary key."""
        return [table.c[name] for name in cls._order_by_names_for(table)]

    @classmethod
    def _sort_key_for(cls, table: Table):
        """Python equivalent of the SQL ``ORDER BY`` used when loading."""
        names = cls._order_by_names_for(table)

        def key(row: Mapping[str, Any]) -> Tuple[Any, ...]:
            return tuple(cls._orderable(row.get(name)) for name in names)

        return key

    @classmethod
    def _returning_columns_for(cls, table: Table, is_postgres: bool) -> List[Any]:
        """All columns, with geometry rendered as EWKT rather than raw WKB."""
        columns: List[Any] = []
        for column in table.c:
            if cls._is_geometry_column(column) and is_postgres:
                columns.append(func.ST_AsEWKT(column).label(column.name))
            else:
                columns.append(column)
        return columns

    @staticmethod
    def _window(
        rows: Sequence[Mapping[str, Any]],
        *,
        limit: Optional[int],
        offset: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Apply limit/offset and hand back copies, so callers cannot mutate the cache."""
        start = offset or 0
        end = start + limit if limit is not None else None
        return [dict(row) for row in rows[start:end]]

    # ================================================================== #
    #                                                                    #
    #   TIER 3 — PURE HELPERS (no DB access, no side effects)            #
    #                                                                    #
    # ================================================================== #

    @classmethod
    def _require_column(cls, table: Table, name: str) -> Column:
        """Look up a column, failing with the valid names rather than a KeyError."""
        column = table.c.get(name)
        if column is None:
            raise ValueError(
                f"{table.name} has no '{name}' column. "
                f"Valid columns: {sorted(c.name for c in table.c)}"
            )
        return column

    @classmethod
    def _identity_column(cls, table: Table) -> Column:
        """The ``id`` column, or the single primary key standing in for it."""
        column = table.c.get("id")
        if column is not None:
            return column
        primary_key = list(table.primary_key.columns)
        if len(primary_key) == 1:
            return primary_key[0]
        raise ValueError(
            f"{table.name} has no 'id' column and no single-column primary key; "
            "set the join columns explicitly on CorePoiGeometryRepository."
        )

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

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        """``Decimal``/``None`` -> ``float``/``None``, for JSON-friendly output."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):  # pragma: no cover - unexpected driver type
            return None

    @staticmethod
    def _orderable(value: Any) -> Tuple[int, Any]:
        """Sort wrapper that tolerates NULLs, matching Postgres' NULLS LAST."""
        if value is None:
            return (1, "")
        return (0, value)

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