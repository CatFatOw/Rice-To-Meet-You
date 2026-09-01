"""Shared fixtures for the backend unit tests.

Scope: the backend functions the frontend actually reaches, which is the
``core_poi``, ``urban_intervention`` and ``final_visitor`` stacks. The heatmap
router, service and repository are deliberately out of scope, so where a
visitor function reads the heatmap weather cache (``_heat_index_f``) the tests
stub that seam instead of exercising it.

Nothing here talks to Postgres. Two strategies stand in for it:

* **SQLite** for the code paths that are dialect-agnostic — the core POI
  repository (which has an explicit non-Postgres branch) and the one visitor
  read that goes to the database.
* **Recording fakes** for the urban intervention repository, whose SQL is
  Postgres-only (``ST_AsGeoJSON``, ``= ANY(:statuses)``, ``CAST(... AS jsonb)``).
  Those tests assert on the bindings sent and the records mapped back.
"""

from __future__ import annotations

import os

# database.py reads DATABASE_URL at import time and every app module imports it
# transitively. Pin it before the first app import so a developer's real
# connection string can never be picked up by a test run.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from datetime import date
from typing import Any, Mapping, Sequence

import pytest
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    Float,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.orm import sessionmaker

from models.final_visitor_tables import VisitorData
from repository.core_poi_geometry_respository import CorePoiGeometryRepository
from repository.final_visitor_repository import PoiAttributes, VisitorPoint, VisitorRepository

# A single date reused across the visitor tests.
TEST_DATE = date(2026, 8, 16)


# --------------------------------------------------------------------------- #
# Core POI geometry — SQLite stand-in for core_poi_geometry + the UHI join
# --------------------------------------------------------------------------- #


def _build_poi_metadata() -> MetaData:
    """The three tables ``CorePoiGeometryRepository._load_statement`` reflects.

    ``core_poi_geometry`` carries every column ``CorePOICreate`` can emit, so a
    route test can post a full validated body without tripping the
    unknown-column check. ``polygon_geom`` is plain TEXT: the repository
    detects a geometry column by name (``GEOMETRY_COLUMN_NAMES``) and its
    non-Postgres branch stores WKT as text, so the type is never exercised.
    """
    metadata = MetaData()
    Table(
        "core_poi_geometry",
        metadata,
        Column("id", Integer, primary_key=True),
        # Identity and location
        Column("placekey", Text),
        Column("parent_placekey", Text),
        Column("safegraph_place_id", Text),
        Column("location_name", Text, nullable=False),
        Column("street_address", Text),
        Column("city", Text),
        Column("region", Text),
        Column("postal_code", Text),
        Column("iso_country_code", Text),
        Column("market", Text),
        Column("market_code", Text),
        Column("latitude", Float),
        Column("longitude", Float),
        # Classification
        Column("top_category", Text),
        Column("top_category_2022", Text),
        Column("sub_category", Text),
        Column("sub_category_2022", Text),
        Column("naics_code", Integer),
        Column("naics_code_2022", Integer),
        Column("brands", JSON),
        Column("category_tags", JSON),
        Column("domains", JSON),
        Column("open_hours", JSON),
        Column("phone_number", Text),
        Column("website", Text),
        # Lifecycle
        Column("opened_on", Date),
        Column("tracking_closed_since", Date),
        # Geometry
        Column("geometry_type", Text),
        Column("polygon_class", Text),
        Column("polygon_wkt", Text),
        Column("polygon_geom", Text),
        Column("wkt_area_sq_meters", Float),
        # Flags and provenance
        Column("enclosed", Boolean),
        Column("includes_parking_lot", Boolean),
        Column("is_synthetic", Boolean),
        Column("provided", Boolean),
        Column("user_id", Integer),
        Column("color", Text),
        # Present so PROTECTED_COLUMNS has something to strip.
        Column("created_at", Text),
    )
    Table(
        "core_poi_uhi_mapping",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("core_poi_id", Integer),
        Column("urban_heat_index_id", Integer),
    )
    Table(
        "urban_heat_index_updated",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("uhi", Float),
    )
    return metadata


@pytest.fixture
def poi_metadata() -> MetaData:
    return _build_poi_metadata()


@pytest.fixture
def poi_engine(poi_metadata: MetaData):
    """Fresh in-memory database, with the repository's process-wide cache reset.

    ``CorePoiGeometryRepository`` caches reflection and rows on the class, so
    both sides of the test need a clean slate or ordering decides the result.
    """
    CorePoiGeometryRepository.invalidate_cache(drop_metadata=True)
    engine = create_engine("sqlite:///:memory:")
    poi_metadata.create_all(engine)
    try:
        yield engine
    finally:
        CorePoiGeometryRepository.invalidate_cache(drop_metadata=True)
        engine.dispose()


@pytest.fixture
def poi_session(poi_engine):
    session = sessionmaker(bind=poi_engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def insert_pois(poi_engine, poi_metadata):
    """Insert POI / mapping / UHI rows, defaulting the NOT NULL columns."""
    table = poi_metadata.tables["core_poi_geometry"]
    mapping = poi_metadata.tables["core_poi_uhi_mapping"]
    uhi = poi_metadata.tables["urban_heat_index_updated"]

    def _insert(
        pois: Sequence[Mapping[str, Any]] = (),
        readings: Sequence[Mapping[str, Any]] = (),
        mappings: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        with poi_engine.begin() as connection:
            if pois:
                connection.execute(
                    table.insert(),
                    [{"location_name": "POI", **dict(row)} for row in pois],
                )
            if readings:
                connection.execute(uhi.insert(), [dict(row) for row in readings])
            if mappings:
                connection.execute(mapping.insert(), [dict(row) for row in mappings])

    return _insert


@pytest.fixture
def poi_repo(poi_session):
    return CorePoiGeometryRepository(poi_session)


# --------------------------------------------------------------------------- #
# Final visitor — in-memory cache control and point factories
# --------------------------------------------------------------------------- #


@pytest.fixture
def visitor_cache():
    """Own ``VisitorRepository._cache`` for one test, then hand it back.

    The cache is a class attribute filled once at application startup, so a
    test that writes it without restoring leaks into every later test.
    """
    original = VisitorRepository._cache
    VisitorRepository._cache = {}
    try:
        yield VisitorRepository._cache
    finally:
        VisitorRepository._cache = original


@pytest.fixture
def visitor_repo(visitor_cache):
    """Repository over the test cache.

    The session is None on purpose: every cached read must answer without
    touching the database, and a None session turns any stray query into a
    loud AttributeError rather than a silent connection attempt.
    """
    return VisitorRepository(None)


def make_poi(**overrides: Any) -> PoiAttributes:
    """A ``PoiAttributes`` with every field defaulted to None."""
    fields: dict[str, Any] = {name: None for name in PoiAttributes._fields}
    fields.update(overrides)
    return PoiAttributes(**fields)


def make_point(
    lon: float = -95.4,
    lat: float = 29.7,
    brand: str = "Brand",
    street_address: str = "1 Main St",
    location_name: str = "Location",
    avg_daily_visits: float | None = 10.0,
    heat_risk_score: float | None = 50.0,
    poi: PoiAttributes | None = None,
) -> VisitorPoint:
    """A cached ``VisitorPoint`` with plottable defaults."""
    return VisitorPoint(
        lon=lon,
        lat=lat,
        brand=brand,
        street_address=street_address,
        location_name=location_name,
        avg_daily_visits=avg_daily_visits,
        heat_risk_score=heat_risk_score,
        poi=poi,
    )


@pytest.fixture
def point_factory():
    return make_point


@pytest.fixture
def poi_factory():
    return make_poi


@pytest.fixture
def stub_heat_index(monkeypatch):
    """Replace ``VisitorRepository._heat_index_f`` with a lookup table.

    That method reads ``HeatmapRepository``'s weather cache, which is out of
    scope for these tests. Stubbing it keeps the visitor functions under test
    while pinning the one input they take from the heatmap side.
    """

    def _stub(by_city: Mapping[str, float | None]) -> None:
        def _heat_index_f(self, city, date_value):  # noqa: ANN001 - patched method
            return by_city.get(city.strip().lower())

        monkeypatch.setattr(VisitorRepository, "_heat_index_f", _heat_index_f)

    return _stub


# --------------------------------------------------------------------------- #
# Final visitor — SQLite mirror of final_visitor_table
# --------------------------------------------------------------------------- #


@pytest.fixture
def visitor_table() -> Table:
    """``final_visitor_table`` rebuilt with SQLite-creatable types.

    The real model carries a PostGIS ``Geometry`` column, whose DDL calls
    ``RecoverGeometryColumn`` and fails on plain SQLite. That column is in
    ``HEAVY_POI_COLUMNS`` and never selected by the read under test, so the
    mirror swaps it for TEXT. Server defaults are dropped and everything but
    the primary key is nullable, so a row can set only the columns a case
    cares about; the query is what's being tested, not the constraints.
    """
    metadata = MetaData()
    columns = [
        Column(
            column.name,
            Text() if column.name == "core_poi_geometry_polygon_geom" else column.type,
            primary_key=column.primary_key,
            nullable=True,
        )
        for column in VisitorData.__table__.columns
    ]
    return Table("final_visitor_table", metadata, *columns)


@pytest.fixture
def visitor_db_session(visitor_table):
    engine = create_engine("sqlite:///:memory:")
    visitor_table.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def insert_visitor_rows(visitor_db_session, visitor_table):
    """Insert rows into the mirror table, defaulting the plottable columns."""
    defaults = {
        "city": "houston",
        "local_date": TEST_DATE,
        "avg_daily_visits": 10.0,
        "location_name": "Location",
        "brand": "Brand",
        "street_address": "1 Main St",
        "latitude": 29.7,
        "longitude": -95.4,
    }

    def _insert(*rows: Mapping[str, Any]) -> None:
        visitor_db_session.execute(
            visitor_table.insert(), [{**defaults, **dict(row)} for row in rows]
        )
        visitor_db_session.commit()

    return _insert
