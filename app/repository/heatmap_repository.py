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
from services.heatmap import create_weather_cache_key, create_urban_heat_cache_key

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

    WEATHER_TABLE = "market_daily_weather"
    HEAT_INDEX_TABLE = "urban_heat_index_updated"
    SYNTHETIC_METRICS = {"change_in_temperature"}

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

    # Suffix appended to a numeric metric based on its column name. First match wins.
    UNIT_HINTS: Sequence[Tuple[str, str]] = (
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
    def refresh_weather(cls, bind: Any) -> None:
        """Reload the weather cache.

        Weather is mutable: new rows land daily and backfills revise old ones.
        Call this on a timer, otherwise the cache will serve stale data with no
        way to notice. The heat-index cache is reference data and does not need
        the same treatment.
        """
        cls.initialize_metadata(bind)
        with cls._data_cache_lock:
            cls._load_weather(bind)

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

        cls._weather_cache = cache
        cls._weather_index = index
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

        lon_name = cls._resolve_column(table, cls.LONGITUDE_CANDIDATES)
        lat_name = cls._resolve_column(table, cls.LATITUDE_CANDIDATES)

        metric_names = tuple(
            c.name
            for c in table.columns
            if c.name not in cls.EXCLUDED_METRIC_COLUMNS
            and c.name not in (lon_name, lat_name)
        )
        numeric = {c.name: cls._is_numeric(c) for c in table.columns}

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

        cls._heat_cache = cache
        cls._heat_metric_names = metric_names
        # A partial (per-market) load must not mark the whole table as resident.
        cls._heat_loaded = markets is None

        logger.info(
            "Preloaded %s heat-index points across %s blocks in %.2fs (~%.1f MB)",
            f"{total_rows:,}",
            len(cache),
            perf_counter() - started,
            sum(block.nbytes() for block in cache.values()) / 1_048_576,
        )

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
        """Cached weather row, falling back to a single-row query."""
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

    # -- public API ---------------------------------------------------------

    def getDataPointsForCityAndDate(
        self,
        weather_date: DateLike,
        market_code: Optional[Union[str, Iterable[str]]] = None,
    ) -> HeatmapPointsByDate:
        """Return heatmap points for the given date, keyed by date string.

        Served from the in-process cache. Weather metrics are formatted once
        per market and reused across that market's points; heat-index metrics
        are formatted per point, with a per-column memo since values repeat
        heavily across a city.

        Args:
            weather_date: the day to pull, as a `date`/`datetime` or ISO string.
            market_code: a single market code or an iterable of them. Defaults
                to all supported markets.

        Returns:
            HeatmapPointsByDate, e.g.
            {"2026-08-10": [{"location_coordinates": [...], "individual_metrics": {...}}]}
        """
        total_start = perf_counter()
        stage_start = total_start

        def print_timing(stage: str) -> None:
            nonlocal stage_start

            now = perf_counter()

            print(
                f"[TIMING] {stage}: "
                f"{now - stage_start:.4f}s "
                f"(total: {now - total_start:.4f}s)"
            )

            stage_start = now

        # 1. Parse and validate inputs
        target_date = self._coerce_date(weather_date)
        markets = self._resolve_markets(market_code)

        print_timing("Parse date and markets")

        if not markets:
            print_timing("Return empty result")
            return {}

        # 2. Metadata is still needed to know which columns exist
        self._get_table(self.WEATHER_TABLE)
        self._get_table(self.HEAT_INDEX_TABLE)

        print_timing("Load cached table metadata")

        cls = type(self)
        weather_index = cls._weather_index
        heat_names = cls._heat_metric_names
        format_value = self._format_value

        date_key = target_date.isoformat()
        results: HeatmapPointsByDate = {}

        # 3. Build points, one market at a time.
        #
        # Cache lookups are timed separately: they are near-instant on a hit,
        # but a miss falls back to a database load, so a large number here
        # means the preload has not finished or did not cover this market.
        weather_seconds = 0.0
        block_seconds = 0.0
        markets_served = 0
        markets_skipped = 0
        points_built = 0

        for market in markets:
            lookup_start = perf_counter()
            weather_values = self._weather_values(market, target_date)
            weather_seconds += perf_counter() - lookup_start

            if weather_values is None:
                markets_skipped += 1
                continue  # no weather for this market: the old join dropped it

            lookup_start = perf_counter()
            block = self._heat_block(market, target_date)
            block_seconds += perf_counter() - lookup_start

            if block is None or block.count == 0:
                markets_skipped += 1
                continue

            markets_served += 1

            # Formatted once per market, reused for every point.
            weather_metrics = {
                name: format_value(name, weather_values[position])
                for name, position in weather_index.items()
                if weather_values[position] is not None
            }

            longitudes = block.longitude
            latitudes = block.latitude
            columns = [block.metrics[name] for name in heat_names]
            # raw value -> formatted string, per column. Heat-index values
            # repeat across a city, so the hit rate is high.
            memos: List[Dict[Any, str]] = [{} for _ in heat_names]

            points = results.setdefault(date_key, [])

            for i in range(block.count):
                # Heat-index keys overwrite weather keys on collision, matching
                # the old iteration order (weather first, heat-index second).
                metrics = dict(weather_metrics)

                for name, column, memo in zip(heat_names, columns, memos):
                    raw = column[i]
                    if raw is None or raw != raw:  # None or the NaN sentinel
                        continue
                    rendered = memo.get(raw)
                    if rendered is None:
                        rendered = format_value(name, raw)
                        memo[raw] = rendered
                    metrics[name] = rendered

                points.append(
                    {
                        "location_coordinates": [longitudes[i], latitudes[i]],
                        "individual_metrics": metrics,
                    }
                )

            points_built += block.count

        print_timing(
            f"Build {points_built:,} points "
            f"({markets_served} markets served, "
            f"{markets_skipped} skipped)"
        )

        print(
            f"[TIMING] cache lookups: "
            f"weather {weather_seconds:.4f}s, "
            f"heat blocks {block_seconds:.4f}s"
        )

        # 4. Build final response
        if not results:
            print_timing("Build empty response")
            return {}

        print(
            f"[TIMING] COMPLETE: "
            f"{perf_counter() - total_start:.4f}s"
        )

        return results
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
        weather_index = cls._weather_index
        to_weight = self._to_weight
        format_value = self._format_value

        # This metric is always reported as zero, regardless of source data.
        force_zero = metric_name == "change_in_temperature"

        points: List[HeatmapMetricValue] = []

        for market in markets:
            # --- per-market weather, resolved once -------------------------
            market_weight: Optional[float] = None
            weather_metrics: Dict[str, str] = {}

            if needs_weather:
                weather_values = self._weather_values(market, target_date)
                if weather_values is None:
                    continue  # no weather for this market/date

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

    # -- schema helpers -----------------------------------------------------

    def _build_metrics(
        self, row: Any, allowed: Optional[set] = None
    ) -> Dict[str, str]:
        """Everything that isn't a join key or a coordinate, stringified with units.

        `allowed`, when given, restricts the output to that set of column names.
        Retained for callers that still work with prefixed row mappings; the
        cache-backed query paths do not use it.
        """
        metrics: Dict[str, str] = {}
        for prefixed_key, value in row.items():
            column = prefixed_key.split("__", 1)[1]
            if column in self.EXCLUDED_METRIC_COLUMNS or value is None:
                continue
            if allowed is not None and column not in allowed:
                continue
            metrics[column] = self._format_value(column, value)
        return metrics

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
        # Weather wins a name collision, matching _build_metrics' iteration order.
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
        return [
            m
            for m in (str(c).strip().lower() for c in requested)
            if m in self.SUPPORTED_MARKET_CODES
        ]

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
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_date(value: DateLike) -> dt.date:
        if isinstance(value, dt.datetime):
            return value.date()
        if isinstance(value, dt.date):
            return value
        return dt.date.fromisoformat(str(value).strip()[:10])

    @staticmethod
    def _to_date_key(value: Any, fallback: dt.date) -> str:
        if isinstance(value, dt.datetime):
            return value.date().isoformat()
        if isinstance(value, dt.date):
            return value.isoformat()
        if value:
            return str(value)[:10]
        return fallback.isoformat()

