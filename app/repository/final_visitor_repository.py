"""File handling core logic that interacts w/ the database"""
import math
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import NamedTuple, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from models.final_visitor_tables import VisitorData
from .heatmap_repository import HeatmapRepository

UNSAFE_HEAT_INDEX_F = 90.0

# Leaf field names that keep their own type in individual_metrics (numbers,
# booleans, dates) and are omitted when null. Everything else stringifies,
# with null becoming "".
TYPED_METRICS = frozenset({
    # visitor
    "avg_daily_visits",
    "heat_risk_score",
    # poi
    "id",
    "latitude",
    "longitude",
    "naics_code",
    "naics_code_2022",
    "wkt_area_sq_meters",
    "enclosed",
    "includes_parking_lot",
    "is_synthetic",
    "provided",
    "user_id",
    "opened_on",
    "closed_on",
    "tracking_closed_since",
    "created_at",
})


def _num(value) -> Optional[float]:
    """Coerce to a JSON-safe float (DB numerics often come back as Decimal)."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _txt(value) -> str:
    """Textual metrics -- null becomes an empty string, not "None"."""
    return "" if value is None else str(value)


def _json_safe(value):
    """Typed metrics -- dates/Decimals into something serializable."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date_type)):
        return value.isoformat()
    return value


def _risk_desc(point):
    """Sort key: heat_risk_score descending, nulls last, ties broken stably.

    None can't be negated, so it rides in the first slot instead -- True
    sorts after False, putting unscored rows at the end. Address/name break
    ties so the cache order is reproducible across restarts (the workers
    read rows in whatever order the DB hands them back).
    """
    score = point.heat_risk_score
    return (
        score is None,
        -score if score is not None else 0.0,
        point.street_address,
        point.location_name,
    )


class PoiAttributes(NamedTuple):
    """Scalar core_poi_geometry columns for one row.

    Deliberately excludes brands, category_tags, domains, open_hours (json),
    polygon_wkt, and polygon_geom -- see VisitorRepository.HEAVY_POI_COLUMNS.
    """
    id: int
    placekey: str
    parent_placekey: str
    safegraph_place_id: str
    store_id: str
    location_name: str
    street_address: str
    city: str
    region: str
    postal_code: str
    iso_country_code: str
    market: str
    market_code: str
    latitude: Optional[float]
    longitude: Optional[float]
    top_category: str
    top_category_2022: str
    sub_category: str
    sub_category_2022: str
    naics_code: Optional[int]
    naics_code_2022: Optional[int]
    phone_number: str
    website: str
    opened_on: Optional[date_type]
    closed_on: Optional[date_type]
    tracking_closed_since: Optional[date_type]
    enclosed: Optional[bool]
    includes_parking_lot: Optional[bool]
    is_synthetic: Optional[bool]
    geometry_type: str
    polygon_class: str
    wkt_area_sq_meters: Optional[float]
    color: str
    provided: Optional[bool]
    user_id: Optional[int]
    created_at: Optional[datetime]


class VisitorPoint(NamedTuple):
    """One plottable row. Tuple-backed, so no per-row __dict__.

    `poi` is None when the row never resolved to a core POI geometry, which
    keeps unlinked rows at one pointer rather than ~35 nulls.
    """
    lon: float
    lat: float
    brand: str
    street_address: str
    location_name: str
    avg_daily_visits: Optional[float]
    heat_risk_score: Optional[float]
    poi: Optional[PoiAttributes]


class VisitorRepository:
    _cache = {}

    # keep <= the connection pool size (pool_size + max_overflow)
    N_WORKERS = int(os.getenv("VISITOR_LOAD_WORKERS", "8"))
    YIELD_PER = 50_000
    CHUNKS_PER_WORKER = 4  # oversubscribe so uneven id gaps even out

    # Pre-sort every cache bucket by heat_risk_score descending at load time.
    # Once on, cached reads are already in risk order, so "top N by risk" is
    # a slice instead of a sort.
    SORT_BY_RISK = True

    # Columns off final_visitor_table itself.
    BASE_COLUMNS = (
        "id",
        "city",
        "local_date",
        "longitude",
        "latitude",
        "brand",
        "street_address",
        "location_name",
        "avg_daily_visits",
        "heat_risk_score",
    )

    # PoiAttributes fields map 1:1 onto core_poi_geometry_<field> columns.
    POI_FIELDS = PoiAttributes._fields

    # Never cached. Large, rarely needed, and fetched by id on demand via
    # getPoiGeometryDetailsByIds(). polygon_geom in particular is PostGIS and
    # would need geoalchemy2 to deserialize on every row.
    HEAVY_POI_COLUMNS = (
        "core_poi_geometry_brands",
        "core_poi_geometry_category_tags",
        "core_poi_geometry_domains",
        "core_poi_geometry_open_hours",
        "core_poi_geometry_polygon_wkt",
        "core_poi_geometry_polygon_geom",
    )

    # (field driving `value`, fields exposed under individual_metrics)
    # Dotted paths reach into `poi`; the metric key is the last segment.
    VISITS_VIEW = ("avg_daily_visits", ("brand", "street_address", "location_name", "heat_risk_score"))
    RISK_VIEW = ("heat_risk_score", ("brand", "street_address", "location_name", "avg_daily_visits"))
    GEOMETRY_VIEW = (
        "avg_daily_visits",
        (
            "brand",
            "street_address",
            "location_name",
            "heat_risk_score",
            "poi.id",
            "poi.placekey",
            "poi.top_category",
            "poi.sub_category",
            "poi.naics_code",
            "poi.postal_code",
            "poi.region",
            "poi.wkt_area_sq_meters",
        ),
    )
    UNSAFE_HEAT_INDEX_F = 90.0

    # (exclusive upper bound, label), ascending. The last band is open-ended.
    HEAT_RISK_BANDS = (
        (80.0, "Low"),
        (90.0, "Caution"),
        (103.0, "Extreme Caution"),
        (125.0, "Danger"),
        (math.inf, "Extreme Danger"),
    )

    def __init__(self, db: Session):
        self.db = db

    @classmethod
    def _poi_columns(cls):
        """core_poi_geometry_* column names, in PoiAttributes order."""
        return tuple(f"core_poi_geometry_{field}" for field in cls.POI_FIELDS)

    @classmethod
    def _point_columns(cls):
        """Every column the cache reads, base + scalar poi."""
        return cls.BASE_COLUMNS + cls._poi_columns()

    @classmethod
    def _columns(cls):
        """Column objects for _point_columns(), in declared order."""
        return [VisitorData.__table__.c[name] for name in cls._point_columns()]

    @classmethod
    def _id_ranges(cls, db: Session):
        """Split the pk space into contiguous [lo, hi] windows."""
        lo, hi = db.query(func.min(VisitorData.id), func.max(VisitorData.id)).one()
        if lo is None:
            return []

        n_chunks = cls.N_WORKERS * cls.CHUNKS_PER_WORKER
        step = max(1, math.ceil((hi - lo + 1) / n_chunks))
        return [(start, min(start + step - 1, hi)) for start in range(lo, hi + 1, step)]

    @classmethod
    def _to_poi(cls, row) -> Optional[PoiAttributes]:
        """Row -> PoiAttributes, or None when the row has no POI link."""
        if row.core_poi_geometry_id is None:
            return None

        values = []
        for field, column in zip(cls.POI_FIELDS, cls._poi_columns()):
            value = getattr(row, column)
            # text fields normalize to "" so callers never see None vs "None"
            values.append(value if field in TYPED_METRICS else _txt(value))
        return PoiAttributes._make(values)

    @classmethod
    def _to_point(cls, row) -> Optional[VisitorPoint]:
        """Row -> VisitorPoint. Returns None if the row can't be plotted."""
        lon, lat = _num(row.longitude), _num(row.latitude)
        if lon is None or lat is None:
            return None

        return VisitorPoint(
            lon=lon,
            lat=lat,
            brand=_txt(row.brand),
            street_address=_txt(row.street_address),
            location_name=_txt(row.location_name),
            avg_daily_visits=_num(row.avg_daily_visits),
            heat_risk_score=_num(row.heat_risk_score),
            poi=cls._to_poi(row),
        )

    @classmethod
    def _load_range(cls, session_factory, lo, hi):
        """Runs in a worker thread with its own session/connection."""
        local = defaultdict(list)
        skipped = 0

        with session_factory() as session:
            rows = (
                session.query(*cls._columns())
                .filter(VisitorData.id >= lo, VisitorData.id <= hi)
                .yield_per(cls.YIELD_PER)
            )

            for row in rows:
                point = cls._to_point(row)
                if point is None:
                    skipped += 1
                    continue

                key = (row.city.strip().lower(), row.local_date)
                local[key].append(point)

        return local, skipped

    @classmethod
    def initialize_table(cls, db: Session):
        """Fetch every point value in parallel and cache it in memory."""
        ranges = cls._id_ranges(db)
        # _id_ranges starts a transaction on the caller's session. Release
        # that connection before the potentially long worker preload.
        db.rollback()
        if not ranges:
            cls._cache = {}
            return

        session_factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
        cache = defaultdict(list)
        total = 0
        skipped = 0
        linked = 0

        with ThreadPoolExecutor(max_workers=cls.N_WORKERS) as pool:
            futures = [
                pool.submit(cls._load_range, session_factory, lo, hi)
                for lo, hi in ranges
            ]
            for future in futures:
                partial, part_skipped = future.result()  # re-raises worker errors
                skipped += part_skipped
                for key, points in partial.items():
                    cache[key].extend(points)
                    total += len(points)
                    linked += sum(1 for p in points if p.poi is not None)
                # once per completed chunk, not once per city/date key
                print(f"Pre-loaded {total:,} visitor rows...")

        if skipped:
            print(f"Skipped {skipped:,} rows with missing coordinates")
        print(f"{linked:,} of {total:,} rows linked to a core POI geometry")

        if cls.SORT_BY_RISK:
            # After the merge, not inside the workers: each worker only sees
            # its own id range, so per-chunk sorting would leave one sorted
            # run per chunk rather than one sorted list per city/date.
            for points in cache.values():
                points.sort(key=_risk_desc)  # in place -- no second copy

        cls._cache = dict(cache)

    @staticmethod
    def _resolve(point, field):
        """Read `field` off a point. Supports one level of `poi.` nesting."""
        if "." not in field:
            return getattr(point, field)

        parent, leaf = field.split(".", 1)
        container = getattr(point, parent)
        return None if container is None else getattr(container, leaf)

    @classmethod
    def _metrics(cls, point, fields):
        """Build individual_metrics, keeping typed fields typed."""
        metrics = {}
        for field in fields:
            key = field.rsplit(".", 1)[-1]
            value = cls._resolve(point, field)
            if key in TYPED_METRICS:
                if value is not None:  # omit rather than emit null
                    metrics[key] = _json_safe(value)
            else:
                metrics[key] = _txt(value)
        return metrics

    @staticmethod
    def _has_poi_geometry(point: VisitorPoint) -> bool:
        """True when the row is linked to a core POI geometry."""
        return point.poi is not None

    def _cached(self, city, date):
        """Cached points for a city/date, or an empty list."""
        return self._cache.get((city.strip().lower(), date)) or []

    def _render(self, city, date, view, predicate=None):
        """Project cached rows into HeatmapPointsByDate for the given view.

        `predicate` optionally filters points before projection.
        """
        value_field, metric_fields = view
        cached = self._cached(city, date)
        if not cached:
            return {}

        points = []
        for row in cached:
            if predicate is not None and not predicate(row):
                continue

            value = self._resolve(row, value_field)
            if value is None:
                continue  # `value` is a required number -- can't plot it
            points.append({
                "value": value,
                # [lon, lat] -- longitude first, per the interface
                "location_coordinates": [row.lon, row.lat],
                "individual_metrics": self._metrics(row, metric_fields),
            })

        return {date.isoformat(): points} if points else {}

    def getVisitorDataByCityDate(self, city, date):
        """HeatmapPointsByDate keyed on avg_daily_visits, e.g.
        ("kansas city", date(2026, 8, 16)) -> {"2026-08-16": [...]}
        """
        return self._render(city, date, self.VISITS_VIEW)

    def getHeatRiskScoreByCityDate(self, city, date):
        """HeatmapPointsByDate keyed on heat_risk_score, same city/date shape."""
        return self._render(city, date, self.RISK_VIEW)

    def getVisitorRowsWithGeometryByCityDate(self, city, date, limit=None):
        """Cached VisitorPoints for a city/date that resolved to a POI.

        With SORT_BY_RISK on, these come back highest heat_risk_score first,
        so `limit` is a plain slice -- no sort at read time.

            ("kansas city", date(2026, 8, 16)) -> [VisitorPoint(...), ...]
        """
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or None, got %r" % limit)

        rows = [p for p in self._cached(city, date) if self._has_poi_geometry(p)]
        return rows if limit is None else rows[:limit]

    def getVisitorDataWithGeometryByCityDate(self, city, date):
        """Same shape as getVisitorDataByCityDate, restricted to rows with a
        non-null core_poi_geometry_id, with POI attributes in the metrics.
        """
        return self._render(
            city, date, self.GEOMETRY_VIEW, predicate=self._has_poi_geometry
        )

    def getPoiAttributesByCityDate(self, city, date):
        """Every cached scalar POI column for a city/date, as plain dicts.

            ("kansas city", date(2026, 8, 16)) -> [{"id": 12, "placekey": ...}]
        """
        return [
            {key: _json_safe(value) for key, value in p.poi._asdict().items()}
            for p in self._cached(city, date)
            if p.poi is not None
        ]

    def getPoiGeometryDetailsByIds(self, poi_ids):
        """The columns HEAVY_POI_COLUMNS keeps out of the cache, by POI id.

        One row per distinct core_poi_geometry_id. Pair with
        getVisitorRowsWithGeometryByCityDate when you need polygons or the
        json columns for a specific subset of points.
        """
        poi_ids = list({poi_id for poi_id in poi_ids if poi_id is not None})
        if not poi_ids:
            return {}

        columns = [VisitorData.__table__.c["core_poi_geometry_id"]] + [
            VisitorData.__table__.c[name] for name in self.HEAVY_POI_COLUMNS
        ]

        rows = (
            self.db.query(*columns)
            .filter(VisitorData.core_poi_geometry_id.in_(poi_ids))
            .distinct(VisitorData.core_poi_geometry_id)
            .all()
        )

        return {
            row.core_poi_geometry_id: {
                name.removeprefix("core_poi_geometry_"): getattr(row, name)
                for name in self.HEAVY_POI_COLUMNS
            }
            for row in rows
        }

    def queryVisitorRowsWithGeometryByCityDate(
        self, city, date, sorted=False, limit=None
    ):
        """Same filter as the cached getter, but straight from the DB.

        Use when the cache may be cold. Returns the cached column set only --
        call getPoiGeometryDetailsByIds for polygons and json columns.

        sorted: order by heat_risk_score descending. Rows with a null score
            sort last rather than first, so they never crowd out real scores
            when combined with `limit`.
        limit: cap the number of rows returned. None returns everything.
            Applied after the sort, since ORDER BY precedes LIMIT in SQL.
        """
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or None, got %r" % limit)

        query = self.db.query(*self._columns()).filter(
            func.lower(func.trim(VisitorData.city)) == city.strip().lower(),
            VisitorData.local_date == date,
            VisitorData.core_poi_geometry_id.isnot(None),
        )

        if sorted:
            # id breaks ties so a limited result set is reproducible
            query = query.order_by(
                VisitorData.heat_risk_score.desc().nullslast(),
                VisitorData.id.asc(),
            )

        if limit is not None:
            query = query.limit(limit)

        return query.all()

    def _sum_visits(self, points) -> float:
        """Total avg_daily_visits across points, ignoring rows missing the metric."""
        return float(sum(p.avg_daily_visits for p in points if p.avg_daily_visits is not None))

    def getTotalVisitsByCityDate(self, city, date):
        """Total avg_daily_visits for a date.

        With a city, totals just that city. With a null/blank `city`, totals
        every city cached for that date into one number.

            ("kansas city", date(2026, 8, 16)) -> {"2026-08-16": 48213.0}
            (None,          date(2026, 8, 16)) -> {"2026-08-16": 79220.0}
        """
        if city:
            buckets = [self._cached(city, date)]
        else:
            buckets = [
                points for key, points in self._cache.items() if key[1] == date
            ]

        total = sum(self._sum_visits(points) for points in buckets)

        return {date.isoformat(): total} if total else {}

    def _heat_index_f(self, city, date) -> Optional[float]:
        """heat_index_f for a city/date, from HeatmapRepository's weather cache.

        Returns None when there is no weather row, or the column is null.
        """
        market = city.strip().lower().replace(" ", "_").replace("-", "_")

        values = HeatmapRepository(self.db)._weather_values(market, date)
        if values is None:
            return None  # no weather row cached or in the DB for this market/date

        position = HeatmapRepository._weather_index.get("heat_index_f")
        if position is None:
            raise ValueError(
                "'heat_index_f' is not a column on %s"
                % HeatmapRepository.WEATHER_TABLE
            )

        raw = values[position]
        try:
            return None if raw is None else float(raw)
        except (TypeError, ValueError):
            return None  # non-numeric value in the column

    def getVisitorInUnsafeCondition(self, city, date) -> float:
        """Total avg_daily_visits for a city/date, but only when it was hot.

        Returns 0 when heat_index_f for that city/date is missing or below
        UNSAFE_HEAT_INDEX_F; otherwise sums avg_daily_visits over every cached
        visitor row for that city/date.
        """
        heat_index = self._heat_index_f(city, date)
        if heat_index is None or heat_index < UNSAFE_HEAT_INDEX_F:
            return 0

        cached = self._cached(city, date)
        if not cached:
            return 0

        return self._sum_visits(cached)

    def getPoiCountInUnsafeCondition(self, city, date) -> int:
        """Count of POI-linked visitor rows for a city/date, when it was hot.

        Returns 0 when heat_index_f for that city/date is missing or below
        UNSAFE_HEAT_INDEX_F; otherwise counts cached rows that resolved to a
        core POI geometry. The heat index is per market/date, so it gates the
        whole bucket rather than filtering row by row.
        """
        heat_index = self._heat_index_f(city, date)
        if heat_index is None or heat_index < UNSAFE_HEAT_INDEX_F:
            return 0

        return sum(1 for p in self._cached(city, date) if self._has_poi_geometry(p))

    @classmethod
    def _risk_category(cls, heat_index) -> Optional[str]:
        """Band label for a heat index, or None when there's no reading.

        Bounds are exclusive on the upper end, so 90.0 is "Extreme Caution"
        rather than "Caution".
        """
        if heat_index is None:
            return None
        for upper, label in cls.HEAT_RISK_BANDS:
            if heat_index < upper:
                return label
        return cls.HEAT_RISK_BANDS[-1][1]  # unreachable while the last bound is inf

    def getVisitorPercentageByHeatRisk(self, city, date):
        """Share of avg_daily_visits falling in each heat risk band.

        With a city, that city's heat index decides one band, so the result
        is 100 in a single key. With a null/blank `city`, every city cached
        for that date is classified on its own heat index and the visits are
        pooled, which is where the split actually means something.

        Cities with no weather row are dropped from both the numerator and
        the denominator -- they'd otherwise silently deflate every band.
        Returns {} when nothing for that date could be classified.

            (None, date(2026, 8, 16)) -> {"Low": 0.0, ..., "Danger": 61.4}
        """
        if city:
            buckets = [(city, self._cached(city, date))]
        else:
            buckets = [
                (key[0], points)
                for key, points in self._cache.items()
                if key[1] == date
            ]

        totals = {label: 0.0 for _, label in self.HEAT_RISK_BANDS}
        total = 0.0

        for market, points in buckets:
            if not points:
                continue
            category = self._risk_category(self._heat_index_f(market, date))
            if category is None:
                continue
            visits = self._sum_visits(points)
            totals[category] += visits
            total += visits

        if not total:
            return {}

        return {label: visits / total * 100.0 for label, visits in totals.items()}

    def getAverageHeatRiskScoreByCityDate(self, city, date) -> Optional[float]:
        """Mean heat_risk_score across cached rows for a city/date.

        Rows with a null score are left out of both the numerator and the
        denominator, so this is the average over scored rows rather than an
        average that treats unscored rows as zero. Returns None when the
        city/date isn't cached or nothing in it has a score -- None means
        "no data", which 0.0 would misrepresent as a genuinely cool average.

            ("kansas city", date(2026, 8, 16)) -> 72.4
        """
        scores = [
            p.heat_risk_score
            for p in self._cached(city, date)
            if p.heat_risk_score is not None
        ]
        if not scores:
            return None

        return float(sum(scores)) / len(scores)