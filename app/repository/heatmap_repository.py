"""Repository for building heatmap data points from weather + urban heat index data.

Mirrors the TypeScript contract:

    export interface HeatmapPointsByDate {
      [date: string]: HeatmapMetricValue[];
    }

    export interface HeatmapMetricValue {
      location_coordinates: [number, number]; // [lon, lat]
      individual_metrics?: Record<string, string>;
    }

Both tables are cached in full, in process, rather than only their metadata.

  * `initialize_metadata(bind)` reflects the schema. Cheap, idempotent, and
    still called lazily by `_get_table`.
  * `initialize_tables(bind)` reflects the schema AND loads every row of both
    tables into memory. Call it from the FastAPI lifespan hook. Once it has
    finished, serving a request touches no database at all.

Storage is columnar. Coordinates and numeric metrics live in `array('d')`
buffers (8 bytes per value) rather than lists of Python floats (~32 bytes per
value including the pointer). For ~1M heat-index points that is roughly 25 MB
instead of roughly 400 MB.

NULL handling: `array('d')` cannot hold None, so numeric columns use NaN as the
null sentinel and readers test `value != value`. Non-numeric columns fall back
to a plain list and keep None as-is.

Schema vs. cache: reflected `Table` objects tell you which columns EXIST;
`_weather_index` / `_heat_metric_names` tell you which columns are RESIDENT in
the cache. The two diverge before the preload finishes, so column *validation*
always resolves against the reflected tables and only value *lookups* use the
cache indexes -- re-read immediately after the cache accessor, since a loader
rebinds those class attributes to fresh objects.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import logging
from array import array
from decimal import Decimal
from threading import Lock
from time import perf_counter
from typing import Any, ClassVar, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

from sqlalchemy import Float, Integer, MetaData, Numeric, Table, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from repository.urban_internvetion_repository import UrbanInterventionRecord, UrbanInterventionRepository

logger = logging.getLogger(__name__)

# --- Type aliases matching the TS interfaces -------------------------------

HeatmapMetricValue = Dict[str, Any]   # {"location_coordinates": [lon, lat],
                                      #  "individual_metrics": {str: str}}
HeatmapPointsByDate = Dict[str, List[HeatmapMetricValue]]

DateLike = Union[str, dt.date, dt.datetime]

HeatCacheKey = Tuple[str, Optional[dt.date]]
WeatherCacheKey = Tuple[str, dt.date]

NAN = float("nan")


class HeatBlock:
    """Columnar heat-index rows for one cache key."""

    __slots__ = ("longitude", "latitude", "metrics", "count")

    def __init__(self, metric_names: Sequence[str], numeric: Dict[str, bool]) -> None:
        self.longitude: array = array("d")
        self.latitude: array = array("d")
        # column name -> array('d') for numeric columns, list for everything else
        self.metrics: Dict[str, Any] = {
            name: (array("d") if numeric[name] else []) for name in metric_names
        }
        self.count: int = 0

    def append(
        self, longitude: float, latitude: float, values: Sequence[Any], names: Sequence[str]
    ) -> None:
        self.longitude.append(longitude)
        self.latitude.append(latitude)
        for index, name in enumerate(names):
            value = values[index]
            column = self.metrics[name]
            if isinstance(column, array):
                column.append(NAN if value is None else float(value))
            else:
                column.append(value)
        self.count += 1

    def nbytes(self) -> int:
        total = self.longitude.buffer_info()[1] * self.longitude.itemsize
        total += self.latitude.buffer_info()[1] * self.latitude.itemsize
        for column in self.metrics.values():
            if isinstance(column, array):
                total += column.buffer_info()[1] * column.itemsize
            else:
                total += 8 * len(column)  # pointers only; referents not counted
        return total


class HeatmapRepository:
    """Reads market weather + urban heat index rows and shapes them for the map."""

    SUPPORTED_MARKET_CODES: Tuple[str, ...] = (
        "dallas",
        "kansas_city",
        "houston",
        "miami",
        "los_angeles",
        "san_francisco",
        "new_york_nj",
        "philadelphia",
        "boston",
        "atlanta",
        "seattle",
    )
    MARKET_CODE_ALIASES: ClassVar[Dict[str, str]] = {
        "new_york": "new_york_nj",
        "new_jersey": "new_york_nj",
        "san_francisco_bay_area": "san_francisco",
    }

    WEATHER_TABLE = "market_daily_weather"
    HEAT_INDEX_TABLE = "urban_heat_index_updated"
    SYNTHETIC_METRICS = {
        "change_in_temperature",
        "change_in_average_temperature_c",
        "change_in_local_temperature_c",
        "change_in_average_temperature_f",
        "change_in_local_temperature_f",
    }

    # -- urban heat island model -------------------------------------------

    MIN_UHI = 1.0
    MAX_UHI = 11.0
    MEAN_UHI = 5.266180261630485

    # Assumed temperature difference between UHI 1 and UHI 11.
    ASSUMED_SPREAD_F = 7.0
    # A *difference* in Fahrenheit converts to Celsius with the ratio alone --
    # no 32-degree offset.
    ASSUMED_SPREAD_C = ASSUMED_SPREAD_F * 5.0 / 9.0

    # -- schema cache -------------------------------------------------------
    # Reflected schema objects are shared by every repository instance in this
    # Python process. Sessions remain request-scoped and are never shared.
    _metadata: ClassVar[MetaData] = MetaData()
    _weather_table: ClassVar[Optional[Table]] = None
    _heat_index_table: ClassVar[Optional[Table]] = None
    _table_cache_lock: ClassVar[Lock] = Lock()

    # True when the heat-index table carries its own `weather_date` column, in
    # which case its cache is keyed per (market, date) rather than per market.
    _heat_partitioned: ClassVar[bool] = False

    # -- row cache ----------------------------------------------------------
    _heat_cache: ClassVar[Dict[HeatCacheKey, HeatBlock]] = {}
    _heat_metric_names: ClassVar[Tuple[str, ...]] = ()

    _weather_cache: ClassVar[Dict[WeatherCacheKey, Tuple[Any, ...]]] = {}
    _weather_index: ClassVar[Dict[str, int]] = {}

    _heat_loaded: ClassVar[bool] = False
    _weather_loaded: ClassVar[bool] = False
    _data_cache_lock: ClassVar[Lock] = Lock()

    # Rows fetched per round trip while streaming a table into memory.
    PRELOAD_CHUNK: ClassVar[int] = 50_000

    # Guard against an unbounded preload. A `weather_date` column on the
    # heat-index table turns the cache from "one block per market" into "one
    # block per market per date".
    HEAT_PRELOAD_MAX_ROWS: ClassVar[int] = 5_000_000

    # Structural columns (join keys, coordinates, bookkeeping) never emitted
    # inside `individual_metrics`.
    EXCLUDED_METRIC_COLUMNS = {
        "id",
        "market_code",
        "weather_date",
        "longitude",
        "latitude",
        "lon",
        "lat",
        "lng",
        "long",
        "created_at",
        "updated_at",
        "inserted_at",
    }

    # Candidate coordinate column names, in priority order.
    LONGITUDE_CANDIDATES = ("longitude", "lon", "lng", "long")
    LATITUDE_CANDIDATES = ("latitude", "lat")

    # Urban heat index column on the heat-index table, in priority order.
    UHI_CANDIDATES: Tuple[str, ...] = (
        "urban_heat_index",
        "uhi",
        "urban_heat_index_value",
        "heat_index",
    )

    # Fallback average-temperature columns on the weather table, per unit.
    # Used only when the caller does not name one explicitly.
    AVG_TEMP_CANDIDATES: ClassVar[Dict[str, Tuple[str, ...]]] = {
        "f": (
            "average_temperature_f",
            "avg_temperature_f",
            "avg_temp_f",
            "temperature_f",
            "temp_f",
        ),
        "c": (
            "average_temperature_c",
            "avg_temperature_c",
            "avg_temp_c",
            "temperature_c",
            "temp_c",
        ),
    }

    # Suffix appended to a numeric metric based on its column name. First match wins.
    # The two local_temperature_* entries must stay above "heat_index"/"_index"/
    # "temp", all of which would otherwise swallow them and stamp the wrong unit.
    UNIT_HINTS: Sequence[Tuple[str, str]] = (
        ("local_temperature_f", "\u00b0F"),
        ("local_temperature_c", "\u00b0C"),
        ("humidity", "%"),
        ("cloud_cover", "%"),
        ("precip", " in"),
        ("rainfall", " in"),
        ("snow", " in"),
        ("wind_speed", " mph"),
        ("wind_gust", " mph"),
        ("pressure", " hPa"),
        ("visibility", " mi"),
        ("uv_index", ""),
        ("heat_index", " / 100"),
        ("_score", " / 100"),
        ("_index", " / 100"),
        ("temp", "\u00b0C"),
        ("feels_like", "\u00b0C"),
        ("dew_point", "\u00b0C"),
    )

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- schema reflection --------------------------------------------------

    @classmethod
    def initialize_metadata(cls, bind: Any) -> None:
        """Reflect and cache both table definitions once per server process.

        This is the cheap half of startup. `_get_table` calls it lazily, so a
        request that arrives before `initialize_tables` finishes still works.
        """
        if cls._weather_table is not None and cls._heat_index_table is not None:
            return

        # Prevent simultaneous first requests from reflecting the same tables
        # more than once.
        with cls._table_cache_lock:
            if cls._weather_table is None:
                cls._weather_table = Table(
                    cls.WEATHER_TABLE,
                    cls._metadata,
                    autoload_with=bind,
                    resolve_fks=False,
                )

            if cls._heat_index_table is None:
                cls._heat_index_table = Table(
                    cls.HEAT_INDEX_TABLE,
                    cls._metadata,
                    autoload_with=bind,
                    resolve_fks=False,
                )

            cls._heat_partitioned = (
                "weather_date" in cls._heat_index_table.columns
            )

    # -- full preload -------------------------------------------------------

    @classmethod
    def initialize_tables(
        cls,
        bind: Any,
        *,
        preload: bool = True,
        markets: Optional[Sequence[str]] = None,
        force: bool = False,
    ) -> None:
        """Reflect metadata and load both tables into memory.

        Args:
            bind: an Engine (preferred) or Connection. Sessions also work.
            preload: set False for the old metadata-only behaviour.
            markets: restrict the heat-index preload to these market codes.
            force: reload even when the cache is already populated.
        """
        cls.initialize_metadata(bind)

        if not preload:
            return

        with cls._data_cache_lock:
            if force:
                cls._heat_cache = {}
                cls._weather_cache = {}
                cls._heat_loaded = False
                cls._weather_loaded = False

            if not cls._weather_loaded:
                cls._load_weather(bind)

            if not cls._heat_loaded:
                cls._load_heat_index(bind, markets)

    @classmethod
    def cache_stats(cls) -> Dict[str, Any]:
        heat_bytes = sum(block.nbytes() for block in cls._heat_cache.values())
        return {
            "heat_blocks": len(cls._heat_cache),
            "heat_points": sum(block.count for block in cls._heat_cache.values()),
            "heat_mb": round(heat_bytes / 1_048_576, 1),
            "heat_loaded": cls._heat_loaded,
            "weather_rows": len(cls._weather_cache),
            "weather_loaded": cls._weather_loaded,
            "heat_partitioned_by_date": cls._heat_partitioned,
        }

    # -- loaders ------------------------------------------------------------

    @staticmethod
    @contextlib.contextmanager
    def _connect(bind: Any) -> Iterator[Any]:
        """Yield a Connection, opening one only when `bind` is an Engine."""
        if isinstance(bind, Engine):
            with bind.connect() as connection:
                yield connection
        else:
            yield bind

    @staticmethod
    def _is_numeric(column: Any) -> bool:
        # Boolean is deliberately excluded: it is not an Integer subclass, so it
        # stays in a list and keeps formatting as Yes/No rather than 1/0.
        return isinstance(column.type, (Numeric, Float, Integer))

    @classmethod
    def _heat_column_plan(cls, table: Table) -> Tuple[str, str, Tuple[str, ...], Dict[str, bool]]:
        """(lon_name, lat_name, metric_names, numeric-by-column) for the heat table.

        Shared by the bulk preload and the single-market fallback so both build
        blocks with identical column sets.
        """
        lon_name = cls._resolve_column(table, cls.LONGITUDE_CANDIDATES)
        lat_name = cls._resolve_column(table, cls.LATITUDE_CANDIDATES)

        metric_names = tuple(
            c.name
            for c in table.columns
            if c.name not in cls.EXCLUDED_METRIC_COLUMNS
            and c.name not in (lon_name, lat_name)
        )
        numeric = {c.name: cls._is_numeric(c) for c in table.columns}
        return lon_name, lat_name, metric_names, numeric

    @classmethod
    def _load_weather(cls, bind: Any) -> None:
        table = cls._weather_table
        started = perf_counter()

        # Everything except structural bookkeeping; market_code and
        # weather_date become the cache key rather than stored values.
        columns = [
            c.name for c in table.columns if c.name not in cls.EXCLUDED_METRIC_COLUMNS
        ]
        index = {name: position for position, name in enumerate(columns)}

        stmt = select(
            table.c.market_code,
            table.c.weather_date,
            *[table.c[name] for name in columns],
        ).where(table.c.market_code.in_(cls.SUPPORTED_MARKET_CODES))

        cache: Dict[WeatherCacheKey, Tuple[Any, ...]] = {}

        with cls._connect(bind) as connection:
            result = connection.execution_options(
                stream_results=True, yield_per=cls.PRELOAD_CHUNK
            ).execute(stmt)

            for row in result:
                date_value = row[1]
                if isinstance(date_value, dt.datetime):
                    date_value = date_value.date()

                key = (row[0], date_value)
                if key in cache:
                    # (market_code, weather_date) should be unique; keep the
                    # first row, matching the previous query-time behaviour.
                    continue
                cache[key] = tuple(row[2:])

        # Publish the index before the rows: a reader that sees a populated
        # cache must never find a stale index alongside it.
        cls._weather_index = index
        cls._weather_cache = cache
        cls._weather_loaded = True

        logger.info(
            "Preloaded %s weather rows in %.2fs",
            f"{len(cache):,}",
            perf_counter() - started,
        )

    @classmethod
    def _load_heat_index(
        cls, bind: Any, markets: Optional[Sequence[str]] = None
    ) -> None:
        table = cls._heat_index_table
        started = perf_counter()

        lon_name, lat_name, metric_names, numeric = cls._heat_column_plan(table)

        target_markets = list(markets or cls.SUPPORTED_MARKET_CODES)
        cache: Dict[HeatCacheKey, HeatBlock] = dict(cls._heat_cache)
        total_rows = 0

        with cls._connect(bind) as connection:
            # One query per market: each uses the market_code index, and no
            # single result set stays open across the entire load.
            for market in target_markets:
                select_columns = [table.c[lon_name], table.c[lat_name]]
                if cls._heat_partitioned:
                    select_columns.append(table.c.weather_date)
                select_columns += [table.c[name] for name in metric_names]

                stmt = (
                    select(*select_columns)
                    .where(table.c.market_code == market)
                    .where(table.c[lon_name].isnot(None))
                    .where(table.c[lat_name].isnot(None))
                )

                result = connection.execution_options(
                    stream_results=True, yield_per=cls.PRELOAD_CHUNK
                ).execute(stmt)

                offset = 3 if cls._heat_partitioned else 2
                market_rows = 0

                for row in result:
                    if cls._heat_partitioned:
                        date_value = row[2]
                        if isinstance(date_value, dt.datetime):
                            date_value = date_value.date()
                        key: HeatCacheKey = (market, date_value)
                    else:
                        key = (market, None)

                    block = cache.get(key)
                    if block is None:
                        block = HeatBlock(metric_names, numeric)
                        cache[key] = block

                    block.append(
                        float(row[0]),
                        float(row[1]),
                        row[offset:],
                        metric_names,
                    )

                    market_rows += 1
                    total_rows += 1

                    if total_rows > cls.HEAT_PRELOAD_MAX_ROWS:
                        raise RuntimeError(
                            "Heat-index preload exceeded %s rows; narrow the "
                            "`markets` argument or raise HEAT_PRELOAD_MAX_ROWS."
                            % f"{cls.HEAT_PRELOAD_MAX_ROWS:,}"
                        )

                logger.info("Preloaded %s points for %s", f"{market_rows:,}", market)

        cls._heat_metric_names = metric_names
        cls._heat_cache = cache
        # A partial (per-market) load must not mark the whole table as resident.
        cls._heat_loaded = markets is None

        logger.info(
            "Preloaded %s heat-index points across %s blocks in %.2fs (~%.1f MB)",
            f"{total_rows:,}",
            len(cache),
            perf_counter() - started,
            sum(block.nbytes() for block in cache.values()) / 1_048_576,
        )

    @classmethod
    def _build_block(
        cls, bind: Any, market: str, target_date: dt.date
    ) -> Optional[HeatBlock]:
        """Load one market's heat-index rows WITHOUT touching the shared cache.

        Used when the preload holds the data lock: this request gets its data
        from the database and throws the block away rather than queueing behind
        a multi-minute load.
        """
        table = cls._heat_index_table
        if table is None:
            return None

        lon_name, lat_name, metric_names, numeric = cls._heat_column_plan(table)

        select_columns = [table.c[lon_name], table.c[lat_name]]
        select_columns += [table.c[name] for name in metric_names]

        stmt = (
            select(*select_columns)
            .where(table.c.market_code == market)
            .where(table.c[lon_name].isnot(None))
            .where(table.c[lat_name].isnot(None))
        )
        if cls._heat_partitioned:
            stmt = stmt.where(table.c.weather_date == target_date)

        block = HeatBlock(metric_names, numeric)

        with cls._connect(bind) as connection:
            result = connection.execution_options(
                stream_results=True, yield_per=cls.PRELOAD_CHUNK
            ).execute(stmt)

            for row in result:
                block.append(float(row[0]), float(row[1]), row[2:], metric_names)

        # Column names are derived deterministically from the reflected schema,
        # so publishing them early is safe and lets readers that key off
        # _heat_metric_names work before the preload finishes.
        if not cls._heat_metric_names:
            cls._heat_metric_names = metric_names

        logger.debug(
            "Built an uncached block of %s points for %s", f"{block.count:,}", market
        )
        return block if block.count else None

    # -- cache accessors ----------------------------------------------------

    def _heat_block(self, market: str, target_date: dt.date) -> Optional[HeatBlock]:
        cls = type(self)
        key: HeatCacheKey = (
            (market, target_date) if cls._heat_partitioned else (market, None)
        )

        block = cls._heat_cache.get(key)
        if block is not None or cls._heat_loaded:
            return block

        # The preload holds this lock for its whole run. Don't queue behind it:
        # load this one market directly and skip the cache write instead.
        if not cls._data_cache_lock.acquire(blocking=False):
            return cls._build_block(self.session.get_bind(), market, target_date)

        try:
            block = cls._heat_cache.get(key)
            if block is None:
                cls._load_heat_index(self.session.get_bind(), [market])
                block = cls._heat_cache.get(key)
            return block
        finally:
            cls._data_cache_lock.release()

    def _weather_values(
        self, market: str, target_date: dt.date
    ) -> Optional[Tuple[Any, ...]]:
        """Cached weather row, falling back to a single-row query.

        Callers must re-read `_weather_index` after this returns: a fallback
        load rebinds it to a new dict, and positions in the returned tuple are
        only meaningful against the current index.
        """
        cls = type(self)
        values = cls._weather_cache.get((market, target_date))
        if values is not None or cls._weather_loaded:
            return values

        with cls._data_cache_lock:
            values = cls._weather_cache.get((market, target_date))
            if values is None:
                cls._load_weather(self.session.get_bind())
                values = cls._weather_cache.get((market, target_date))
        return values

    # -- urban heat island maths --------------------------------------------

    @classmethod
    def _clamp_urban_heat_index(cls, urban_heat_index: float) -> float:
        return max(cls.MIN_UHI, min(cls.MAX_UHI, urban_heat_index))

    @classmethod
    def _calculate_local_temperature_f(
        cls,
        average_temperature_f: float,
        urban_heat_index: float,
    ) -> float:
        uhi = cls._clamp_urban_heat_index(urban_heat_index)

        adjustment_f = (
            (uhi - cls.MEAN_UHI)
            * cls.ASSUMED_SPREAD_F
            / (cls.MAX_UHI - cls.MIN_UHI)
        )

        return average_temperature_f + adjustment_f

    @classmethod
    def _calculate_local_temperature_c(
        cls,
        average_temperature_c: float,
        urban_heat_index: float,
    ) -> float:
        uhi = cls._clamp_urban_heat_index(urban_heat_index)

        adjustment_c = (
            (uhi - cls.MEAN_UHI)
            * cls.ASSUMED_SPREAD_C
            / (cls.MAX_UHI - cls.MIN_UHI)
        )

        return average_temperature_c + adjustment_c

    # -- public API ---------------------------------------------------------

    def getDataPointsForCityDateMetric(
        self,
        weather_date: DateLike,
        metric: str,
        market_code: Optional[Union[str, Iterable[str]]] = None,
        additional_metrics: Optional[Iterable[str]] = None,
    ) -> HeatmapPointsByDate:
        """Return weighted heatmap points for one primary metric.

        Same contract as the SQL-backed version, served from memory.
        """
        total_start = perf_counter()

        target_date = self._coerce_date(weather_date)
        markets = self._resolve_markets(market_code)
        metric_name = str(metric).strip()
        if not markets:
            return {}

        weather = self._get_table(self.WEATHER_TABLE)
        heat_index = self._get_table(self.HEAT_INDEX_TABLE)

        metric_column, metric_source = self._resolve_metric_column(
            metric_name, weather, heat_index
        )
        metric_on_weather = metric_source == "w__"
        metric_is_synthetic = metric_source == "synthetic__"

        requested_names: List[str] = []
        if additional_metrics:
            requested_names = list(
                dict.fromkeys(
                    name
                    for raw_name in additional_metrics
                    if (name := str(raw_name).strip())
                )
            )

        # Which cache each requested metric comes from, in requested order.
        plan: List[Tuple[str, str]] = []
        for name in requested_names:
            column, _ = self._resolve_metric_column(name, weather, heat_index)
            source = (
                "s"
                if name in self.SYNTHETIC_METRICS
                else "w" if column.table is weather else "h"
            )
            plan.append((source, name))

        heat_names = [name for source, name in plan if source == "h"]
        needs_weather = metric_on_weather or any(
            source == "w" for source, _ in plan
        )

        cls = type(self)
        to_weight = self._to_weight
        format_value = self._format_value

        # This metric is always reported as zero, regardless of source data.
        force_zero = metric_name in self.SYNTHETIC_METRICS

        points: List[HeatmapMetricValue] = []

        for market in markets:
            # --- per-market weather, resolved once -------------------------
            market_weight: Optional[float] = None
            weather_metrics: Dict[str, str] = {}

            if needs_weather:
                weather_values = self._weather_values(market, target_date)
                if weather_values is None:
                    continue  # no weather for this market/date

                # Re-read after the accessor: a fallback load rebinds the index.
                weather_index = cls._weather_index

                if metric_on_weather:
                    market_weight = to_weight(
                        weather_values[weather_index[metric_name]]
                    )
                    if market_weight is None:
                        continue  # every point here would be skipped anyway

                for source, name in plan:
                    if source != "w":
                        continue
                    raw = weather_values[weather_index[name]]
                    if raw is not None:
                        weather_metrics[name] = format_value(name, raw)

            block = self._heat_block(market, target_date)
            if block is None or block.count == 0:
                continue

            longitudes = block.longitude
            latitudes = block.latitude
            heat_columns = [block.metrics[name] for name in heat_names]
            memos: List[Dict[Any, str]] = [{} for _ in heat_names]
            metric_values = (
                None
                if metric_on_weather or metric_is_synthetic
                else block.metrics[metric_name]
            )

            # When no requested metric comes from the heat-index table, every
            # point in this market carries an identical individual_metrics
            # dict. Build it once and share the object; safe as long as nothing
            # downstream mutates the response in place.
            shared_metrics = (
                weather_metrics if weather_metrics and not heat_names else None
            )

            for i in range(block.count):
                if metric_on_weather:
                    value = market_weight
                elif metric_is_synthetic:
                    value = 0
                else:
                    value = metric_values[i]
                    if value != value:  # NaN sentinel: the column was NULL
                        continue

                if force_zero:
                    value = 0

                point: HeatmapMetricValue = {
                    "value": value,
                    "location_coordinates": [longitudes[i], latitudes[i]],
                }

                if shared_metrics is not None:
                    point["individual_metrics"] = shared_metrics
                elif requested_names:
                    rendered_by_name = dict(weather_metrics)

                    for name, column, memo in zip(heat_names, heat_columns, memos):
                        raw = column[i]
                        if raw is None or raw != raw:
                            continue
                        rendered = memo.get(raw)
                        if rendered is None:
                            rendered = format_value(name, raw)
                            memo[raw] = rendered
                        rendered_by_name[name] = rendered

                    if rendered_by_name:
                        # Preserve the caller's requested ordering.
                        point["individual_metrics"] = {
                            name: rendered_by_name[name]
                            for _, name in plan
                            if name in rendered_by_name
                        }

                points.append(point)

        logger.debug(
            "Served %s points in %.4fs",
            f"{len(points):,}",
            perf_counter() - total_start,
        )

        if not points:
            return {}
        return {target_date.isoformat(): points}

    def getLocalTemperatureByCityDate(
        self,
        weather_date: DateLike,
        metric: Optional[str] = None,
        market_code: Optional[Union[str, Iterable[str]]] = None,
        additional_metrics: Optional[Iterable[str]] = None,
        temperature_unit: str = "f",
    ) -> HeatmapPointsByDate:
        """Per-point local temperature: one weather row + every heat-index point.

        For each market the weather table supplies a single average temperature
        for the date; each urban-heat-index point for that market is then offset
        from it by its UHI, via _calculate_local_temperature_f/_c.

        Args:
            weather_date: the day to pull.
            metric: name of the weather column holding the average temperature.
                Defaults to the first AVG_TEMP_CANDIDATES entry that exists.
                Must match `temperature_unit` -- passing a Celsius column with
                unit "f" silently produces nonsense.
            market_code: a single market code or an iterable. Defaults to all.
            additional_metrics: extra columns to render into individual_metrics.
            temperature_unit: "f" or "c". Selects both the default source column
                and the calculation.

        Returns:
            HeatmapPointsByDate, `value` being the local temperature.
        """
        total_start = perf_counter()

        target_date = self._coerce_date(weather_date)
        markets = self._resolve_markets(market_code)
        if not markets:
            return {}

        unit = str(temperature_unit or "f").strip().lower()
        if unit not in ("f", "c"):
            raise ValueError(
                "temperature_unit must be 'f' or 'c', got %r" % temperature_unit
            )

        weather = self._get_table(self.WEATHER_TABLE)
        heat_index = self._get_table(self.HEAT_INDEX_TABLE)

        cls = type(self)

        # --- resolve the two driving columns -------------------------------
        # Validated against the reflected schema, not the cache indexes: those
        # are empty until the preload runs and would reject valid names.
        temp_name = str(metric).strip() if metric else ""
        if temp_name:
            if (
                temp_name not in weather.columns
                or temp_name in self.EXCLUDED_METRIC_COLUMNS
            ):
                raise ValueError(
                    "Average-temperature metric '%s' is not an available column "
                    "on %s. Available: %s"
                    % (
                        temp_name,
                        self.WEATHER_TABLE,
                        sorted(
                            c.name
                            for c in weather.columns
                            if c.name not in self.EXCLUDED_METRIC_COLUMNS
                        ),
                    )
                )
        else:
            temp_name = next(
                (n for n in self.AVG_TEMP_CANDIDATES[unit] if n in weather.columns),
                "",
            )
            if not temp_name:
                raise ValueError(
                    "No average-temperature column for unit '%s' on %s. Pass one "
                    "explicitly as `metric`. Tried: %s"
                    % (unit, self.WEATHER_TABLE, list(self.AVG_TEMP_CANDIDATES[unit]))
                )

        uhi_name = next(
            (n for n in self.UHI_CANDIDATES if n in heat_index.columns), ""
        )
        if not uhi_name:
            raise ValueError(
                "No urban-heat-index column on %s. Tried: %s"
                % (self.HEAT_INDEX_TABLE, list(self.UHI_CANDIDATES))
            )

        calculate = (
            cls._calculate_local_temperature_f
            if unit == "f"
            else cls._calculate_local_temperature_c
        )
        output_name = "local_temperature_%s" % unit

        # --- additional_metrics plan, mirroring getDataPointsForCityDateMetric
        requested_names: List[str] = []
        if additional_metrics:
            requested_names = list(
                dict.fromkeys(
                    name
                    for raw_name in additional_metrics
                    if (name := str(raw_name).strip())
                )
            )

        plan: List[Tuple[str, str]] = []
        for name in requested_names:
            column, _ = self._resolve_metric_column(name, weather, heat_index)
            source = (
                "s" if name in self.SYNTHETIC_METRICS
                else "w" if column.table is weather
                else "h"
            )
            plan.append((source, name))

        heat_names = [name for source, name in plan if source == "h"]
        format_value = self._format_value
        to_weight = self._to_weight

        points: List[HeatmapMetricValue] = []

        for market in markets:
            # The one exact weather row for this market/date.
            weather_values = self._weather_values(market, target_date)
            if weather_values is None:
                continue

            # Re-read after the accessor: a fallback load rebinds the index,
            # and tuple positions are only valid against the current one.
            weather_index = cls._weather_index
            if temp_name not in weather_index:
                continue  # column exists but isn't resident in the cache

            average_temperature = to_weight(weather_values[weather_index[temp_name]])
            if average_temperature is None:
                continue  # no baseline, so every point here is unresolvable

            weather_metrics: Dict[str, str] = {}
            for source, name in plan:
                if source != "w" or name not in weather_index:
                    continue
                raw = weather_values[weather_index[name]]
                if raw is not None:
                    weather_metrics[name] = format_value(name, raw)

            # Every heat-index row for this market (all dates, when the table
            # isn't partitioned by weather_date).
            block = self._heat_block(market, target_date)
            if block is None or block.count == 0:
                continue

            uhi_column = block.metrics.get(uhi_name)
            if uhi_column is None:
                continue  # UHI not resident in this block

            longitudes = block.longitude
            latitudes = block.latitude
            resident_heat = [name for name in heat_names if name in block.metrics]
            heat_columns = [block.metrics[name] for name in resident_heat]
            memos: List[Dict[Any, str]] = [{} for _ in resident_heat]
            # UHI values repeat heavily across a city, so memo the arithmetic.
            temp_memo: Dict[float, float] = {}

            for i in range(block.count):
                uhi = uhi_column[i]
                if uhi is None or uhi != uhi:  # None or the NaN sentinel
                    continue

                value = temp_memo.get(uhi)
                if value is None:
                    value = calculate(average_temperature, uhi)
                    temp_memo[uhi] = value

                point: HeatmapMetricValue = {
                    "value": value,
                    "location_coordinates": [longitudes[i], latitudes[i]],
                }

                metrics = dict(weather_metrics)
                for name, column, memo in zip(resident_heat, heat_columns, memos):
                    raw = column[i]
                    if raw is None or raw != raw:
                        continue
                    rendered = memo.get(raw)
                    if rendered is None:
                        rendered = format_value(name, raw)
                        memo[raw] = rendered
                    metrics[name] = rendered

                # Requested order first, then the computed temperature.
                point["individual_metrics"] = {
                    **{name: metrics[name] for _, name in plan if name in metrics},
                    output_name: format_value(output_name, value),
                }

                points.append(point)

        logger.debug(
            "Served %s local-temperature points in %.4fs",
            f"{len(points):,}",
            perf_counter() - total_start,
        )

        if not points:
            return {}
        return {target_date.isoformat(): points}

    def get_simulated_points_by_date(
        self,
        from_date: DateLike,
        to_date: DateLike,
        city: str,
        metric: str,
        additional_metrics: Optional[Iterable[str]] = None,
        mode: str = "standard",
    ) -> HeatmapPointsByDate:
        """Retrieve a city's inputs for a date range and return simulated readings."""
        from services.simulation_services import run_diminishing_return_simulation

        total_start = perf_counter()
        stage_start = total_start

        def print_timing(stage: str) -> None:
            nonlocal stage_start
            now = perf_counter()
            print(
                f"[SIM] {stage}: "
                f"{now - stage_start:.4f}s "
                f"(total: {now - total_start:.4f}s)"
            )
            stage_start = now

        # --- 1. inputs -----------------------------------------------------
        start_date = self._coerce_date(from_date)
        end_date = self._coerce_date(to_date)
        if start_date > end_date:
            raise ValueError("from_date must not be after to_date.")

        market_codes = self._resolve_markets(city)
        if not market_codes:
            raise ValueError("Unknown city %r." % city)
        market_code = market_codes[0]

        day_count = (end_date - start_date).days + 1
        print(
            f"[SIM] range {start_date.isoformat()} -> {end_date.isoformat()} "
            f"({day_count} days), market={market_code}, metric={metric}, mode={mode}"
        )
        print_timing("Parse inputs")

        # --- 2. fetch baseline points, one date at a time -------------------
        # Timed per date as well as in aggregate: the first date usually pays
        # for a cache miss / preload fallback, so a large first entry and small
        # rest means the cache is working. Uniformly large means it is not.
        heatmap_points_by_date: HeatmapPointsByDate = {}
        per_date_seconds: List[Tuple[str, float, int]] = []
        local_temperature_unit = {
            "local_temperature_c": "c",
            "change_in_local_temperature_c": "c",
            "local_temperature_f": "f",
            "change_in_local_temperature_f": "f",
        }.get(metric)

        current_date = start_date
        while current_date <= end_date:
            date_key = current_date.isoformat()

            date_start = perf_counter()
            if local_temperature_unit:
                points = self.getLocalTemperatureByCityDate(
                    weather_date=current_date,
                    market_code=market_code,
                    additional_metrics=additional_metrics,
                    temperature_unit=local_temperature_unit,
                )
            else:
                points = self.getDataPointsForCityDateMetric(
                    weather_date=current_date,
                    metric=metric,
                    market_code=market_code,
                    additional_metrics=additional_metrics,
                )
            date_points = points.get(date_key, [])
            elapsed = perf_counter() - date_start

            heatmap_points_by_date[date_key] = date_points
            per_date_seconds.append((date_key, elapsed, len(date_points)))

            current_date += dt.timedelta(days=1)

        total_points = sum(count for _, _, count in per_date_seconds)
        fetch_seconds = sum(seconds for _, seconds, _ in per_date_seconds)

        print_timing(
            f"Fetch baseline points ({total_points:,} across {len(per_date_seconds)} dates)"
        )

        if per_date_seconds:
            slowest = max(per_date_seconds, key=lambda entry: entry[1])
            fastest = min(per_date_seconds, key=lambda entry: entry[1])
            print(
                f"[SIM]   per-date: "
                f"mean {fetch_seconds / len(per_date_seconds):.4f}s, "
                f"slowest {slowest[0]} {slowest[1]:.4f}s, "
                f"fastest {fastest[0]} {fastest[1]:.4f}s"
            )
            # Uncomment for a full per-date breakdown.
            # for date_key, seconds, count in per_date_seconds:
            #     print(f"[SIM]     {date_key}: {seconds:.4f}s ({count:,} points)")

        # --- 3. interventions ----------------------------------------------
        interventions = UrbanInterventionRepository(self.session).get_all_by_city_between_date(
            city=market_code,
            from_date=start_date,
            to_date=end_date,
        )
        interventions = list(interventions)  # materialize before timing the query
        print_timing(f"Query interventions ({len(interventions)} rows)")

        placed_objects = self._group_interventions_for_simulation(interventions)
        object_count = sum(len(objects) for objects in placed_objects.values())
        print_timing(f"Group interventions ({object_count} placed objects)")

        # --- 4. simulation ---------------------------------------------------
        simulated = run_diminishing_return_simulation(
            metric=metric,
            points_by_date=heatmap_points_by_date,
            categorized_objects=placed_objects,
            mode=mode,
        )
        simulation_seconds = perf_counter() - stage_start
        print_timing("Run simulation")

        feedback = simulated.feedback
        print(
            f"[SIM]   affected {feedback.affected_points:,} points "
            f"({feedback.overlap_points:,} overlapping, "
            f"max {feedback.max_objects_at_point} objects at a point)"
        )
        if total_points:
            print(
                f"[SIM]   simulation cost: "
                f"{simulation_seconds / total_points * 1e6:.1f} us/point "
                f"across {total_points:,} points"
            )

        total_seconds = perf_counter() - total_start
        print(
            f"[SIM] COMPLETE: {total_seconds:.4f}s "
            f"(fetch {fetch_seconds / total_seconds * 100:.0f}%, "
            f"simulate {simulation_seconds / total_seconds * 100:.0f}%)"
        )

        return simulated.points_by_date

    @staticmethod
    def _group_interventions_for_simulation(
        interventions: Iterable[UrbanInterventionRecord],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Convert persisted intervention records into the simulation input shape."""
        category_by_type = {
            "street_tree": "Vegetation",
            "cool_roof": "High-albedo surface",
            "cool_pavement": "High-albedo surface",
            "shade_structure": "Shade structure",
            "misting_station": "Evaporative / water",
        }
        grouped: Dict[str, List[Dict[str, Any]]] = {
            "Vegetation": [],
            "High-albedo surface": [],
            "Shade structure": [],
            "Evaporative / water": [],
        }

        for intervention in interventions:
            category = category_by_type[intervention.intervention_type]
            geometry = intervention.geometry
            geometry_type = geometry["type"]
            coordinates = geometry["coordinates"]
            if geometry_type == "Point":
                longitude, latitude = coordinates
                simulation_geometry = {
                    "kind": "point",
                    "longitude": longitude,
                    "latitude": latitude,
                }
            elif geometry_type == "LineString":
                simulation_geometry = {"kind": "line", "coordinates": coordinates}
            else:
                simulation_geometry = {"kind": "polygon", "ring": coordinates[0]}

            grouped[category].append(
                {
                    "id": str(intervention.id),
                    "name": intervention.name,
                    "type": intervention.intervention_type,
                    "category": category,
                    "color": intervention.color,
                    "market_code": intervention.market_code,
                    "geometry": simulation_geometry,
                    "params": intervention.parameters,
                    "activeFrom": intervention.active_from.isoformat()
                    if intervention.active_from
                    else None,
                    "activeTo": intervention.active_to.isoformat()
                    if intervention.active_to
                    else None,
                }
            )

        return grouped

    # -- schema helpers -----------------------------------------------------

    @staticmethod
    def _to_weight(value: Any) -> Optional[float]:
        """Coerce a metric to a number for heatmap weighting. Bools -> 1.0/0.0."""
        if value is None:
            return None
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None  # e.g. a text band like "favorable"
        if number != number:  # NaN sentinel from a cached numeric column
            return None
        return number

    def _resolve_metric_column(
        self, metric: str, weather: Table, heat_index: Table
    ) -> Tuple[Any, str]:
        """Find `metric` on either table. Returns (column, label_prefix)."""
        name = str(metric).strip()
        if name in self.EXCLUDED_METRIC_COLUMNS:
            raise ValueError(
                "'%s' is a structural column and is not available as a metric."
                % name
            )
        # Weather wins a name collision.
        for table, prefix in ((weather, "w__"), (heat_index, "h__")):
            if name in table.columns:
                return table.columns[name], prefix
        if name in self.SYNTHETIC_METRICS:
            return None, "synthetic__"
        available = sorted(
            c.name
            for t in (weather, heat_index)
            for c in t.columns
            if c.name not in self.EXCLUDED_METRIC_COLUMNS
        )
        raise ValueError(
            "Unknown metric '%s'. Available metrics: %s" % (name, available)
        )

    def _get_table(self, name: str) -> Table:
        if name not in (self.WEATHER_TABLE, self.HEAT_INDEX_TABLE):
            raise ValueError("Unknown table: %s" % name)

        repository_type = type(self)
        # Metadata only. A lazy call from a request must never trigger a full
        # row preload while holding the lock.
        repository_type.initialize_metadata(self.session.get_bind())

        if name == self.WEATHER_TABLE:
            table = repository_type._weather_table
        else:
            table = repository_type._heat_index_table

        if table is None:  # defensive; initialize_metadata should populate it
            raise RuntimeError("Table metadata cache was not initialized.")

        return table

    @staticmethod
    def _resolve_column(table: Table, candidates: Sequence[str]) -> str:
        for candidate in candidates:
            if candidate in table.columns:
                return candidate
        raise ValueError(
            "None of %s found on table '%s'. Available columns: %s"
            % (list(candidates), table.name, [c.name for c in table.columns])
        )

    def _resolve_markets(
        self, market_code: Optional[Union[str, Iterable[str]]]
    ) -> List[str]:
        if market_code is None:
            return list(self.SUPPORTED_MARKET_CODES)
        requested = [market_code] if isinstance(market_code, str) else list(market_code)
        normalized: List[str] = []
        for value in requested:
            code = "_".join(str(value).strip().lower().split())
            code = self.MARKET_CODE_ALIASES.get(code, code)
            if code in self.SUPPORTED_MARKET_CODES:
                normalized.append(code)
        return normalized

    def _format_value(self, column: str, value: Any) -> str:
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (dt.date, dt.datetime)):
            return value.isoformat()
        if isinstance(value, (int, float, Decimal)):
            number = float(value)
            rendered = "%.0f" % number if number.is_integer() else "%.1f" % number
            return rendered + self._unit_for(column)
        return str(value)

    def _unit_for(self, column: str) -> str:
        lowered = column.lower()
        for fragment, unit in self.UNIT_HINTS:
            if fragment in lowered:
                return unit
        return ""

    @staticmethod
    def _coerce_date(value: DateLike) -> dt.date:
        if isinstance(value, dt.datetime):
            return value.date()
        if isinstance(value, dt.date):
            return value
        return dt.date.fromisoformat(str(value).strip()[:10])
