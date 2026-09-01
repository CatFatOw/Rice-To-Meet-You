"""``routers/core_poi.py`` — the two handlers the frontend calls.

* ``GET  /core_poi/get-all-pois`` — Heatmap.tsx loads the POI layer from this.
* ``POST /core_poi/create-poi``   — the toolbox saves a drawn POI through it.

``get_pois_by_city`` lives in the same module but no frontend call reaches it,
so it is out of scope.

Both handlers open their own session with ``SessionLocal()`` rather than taking
``Depends(get_db)``, so the tests swap that module-level name for a session
bound to SQLite. Calling the handler function directly is what makes these unit
tests: the input is the argument, the assertion is on the returned value.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from routers import core_poi
from schemas.core_poi_geometry import CorePOICreate, GeometryType

POLYGON_WKT = "POLYGON((-96.80 32.78, -96.70 32.78, -96.70 32.88, -96.80 32.78))"

VALID_BODY = {
    "polygon_wkt": POLYGON_WKT,
    "city": "Dallas",
    "location_name": "Klyde Warren Park",
    "region": "TX",
    "includes_parking_lot": False,
    "latitude": 32.7893,
    "longitude": -96.8016,
    "market": "dallas",
    "color": "#22c55e",
}


@pytest.fixture
def wired_router(monkeypatch, poi_session):
    """Point the module's ``SessionLocal`` at the SQLite test session."""
    monkeypatch.setattr(core_poi, "SessionLocal", lambda: poi_session)
    return poi_session


# --------------------------------------------------------------------------- #
# GET /core_poi/get-all-pois
# --------------------------------------------------------------------------- #


def test_get_all_pois_returns_a_list_of_row_dicts(wired_router, insert_pois):
    insert_pois(
        pois=[
            {"id": 1, "location_name": "Rice University", "market_code": "houston"},
            {"id": 2, "location_name": "NRG Stadium", "market_code": "houston"},
        ]
    )

    result = core_poi.get_all_pois()

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(row, dict) for row in result)
    assert [row["location_name"] for row in result] == ["Rice University", "NRG Stadium"]


def test_get_all_pois_returns_an_empty_list_when_there_are_no_pois(wired_router):
    assert core_poi.get_all_pois() == []


def test_get_all_pois_includes_the_uhi_aggregate_the_frontend_reads(
    wired_router, insert_pois
):
    insert_pois(
        pois=[{"id": 1, "placekey": "222-223-224"}],
        readings=[{"id": 10, "uhi": 4.0}, {"id": 11, "uhi": 6.0}],
        mappings=[
            {"id": 1, "core_poi_id": 1, "urban_heat_index_id": 10},
            {"id": 2, "core_poi_id": 1, "urban_heat_index_id": 11},
        ],
    )

    row = core_poi.get_all_pois()[0]

    assert row["average_uhi"] == 5.0
    assert row["matched_uhi_count"] == 2


def test_get_all_pois_spans_every_market(wired_router, insert_pois):
    insert_pois(
        pois=[
            {"id": 1, "market_code": "houston"},
            {"id": 2, "market_code": "dallas"},
            {"id": 3, "market_code": None},
        ]
    )

    result = core_poi.get_all_pois()

    assert [row["market_code"] for row in result] == ["houston", "dallas", None]


# --------------------------------------------------------------------------- #
# POST /core_poi/create-poi
# --------------------------------------------------------------------------- #


def test_create_poi_returns_the_persisted_row(wired_router):
    result = core_poi.create_poi(CorePOICreate(**VALID_BODY))

    assert isinstance(result, dict)
    assert result["location_name"] == "Klyde Warren Park"
    assert result["city"] == "Dallas"
    assert result["region"] == "TX"
    assert result["latitude"] == 32.7893
    assert result["longitude"] == -96.8016
    assert result["color"] == "#22c55e"
    assert result["id"] is not None


def test_create_poi_writes_the_normalized_values_not_the_raw_body(wired_router):
    # The schema upper-cases region, normalizes the market and adds a scheme to
    # the website; the row must carry those, not what the client typed.
    body = {**VALID_BODY, "region": "tx", "market": "Kansas City", "website": "rice.edu"}

    result = core_poi.create_poi(CorePOICreate(**body))

    assert result["region"] == "TX"
    assert result["market"] == "kansas_city"
    assert result["market_code"] == "kansas_city"
    assert result["website"] == "https://rice.edu"


def test_create_poi_stores_the_polygon_geometry(wired_router):
    result = core_poi.create_poi(CorePOICreate(**VALID_BODY))

    assert result["polygon_wkt"] == POLYGON_WKT
    assert result["polygon_geom"] == POLYGON_WKT


def test_create_poi_applies_the_schema_defaults(wired_router):
    result = core_poi.create_poi(CorePOICreate(**VALID_BODY))

    assert result["iso_country_code"] == "US"
    assert result["polygon_class"] == "OWNED_POLYGON"
    assert result["geometry_type"] == "POLYGON"
    assert result["is_synthetic"] == 0 or result["is_synthetic"] is False
    assert result["provided"] == 0 or result["provided"] is False


def test_create_poi_round_trips_the_optional_fields(wired_router):
    body = {
        **VALID_BODY,
        "brands": "Chipotle, Panera",
        "top_category": "Restaurants",
        "naics_code": 722511,
        "opened_on": "2019-05-01",
        "postal_code": "75201",
        "street_address": "2012 Woodall Rodgers Fwy",
        "phone_number": "+1 (214) 716-4500",
    }

    result = core_poi.create_poi(CorePOICreate(**body))

    assert result["brands"] == ["Chipotle", "Panera"]
    assert result["top_category"] == "Restaurants"
    assert result["naics_code"] == 722511
    assert result["opened_on"] == date(2019, 5, 1)
    assert result["postal_code"] == "75201"
    assert result["street_address"] == "2012 Woodall Rodgers Fwy"
    assert result["phone_number"] == "+12147164500"


def test_a_created_poi_is_visible_to_the_next_get_all(wired_router):
    core_poi.create_poi(CorePOICreate(**VALID_BODY))

    names = [row["location_name"] for row in core_poi.get_all_pois()]

    assert names == ["Klyde Warren Park"]


def test_create_poi_commits_so_the_row_survives_the_session(wired_router, poi_engine):
    core_poi.create_poi(CorePOICreate(**VALID_BODY))

    with poi_engine.connect() as connection:
        stored = connection.execute(
            text("SELECT location_name FROM core_poi_geometry")
        ).scalars().all()
    assert stored == ["Klyde Warren Park"]


def test_create_poi_reports_the_new_poi_as_unmeasured(wired_router):
    # Nothing maps a fresh POI to a heat reading yet.
    result = core_poi.create_poi(CorePOICreate(**VALID_BODY))

    assert result["average_uhi"] is None
    assert result["matched_uhi_count"] == 0


# --------------------------------------------------------------------------- #
# Session handling
# --------------------------------------------------------------------------- #


class _RecordingSession:
    """Stands in for a session so the handler's lifecycle can be observed."""

    def __init__(self):
        self.committed = 0
        self.closed = 0

    def commit(self):
        self.committed += 1

    def close(self):
        self.closed += 1


class _StubRepository:
    last_payload = None

    def __init__(self, db):
        self.db = db

    def create(self, payload):
        type(self).last_payload = payload
        return {"id": 1, **payload}

    def getAll(self):
        return [{"id": 1}]


def test_create_poi_hands_the_repository_the_dumped_body(monkeypatch):
    session = _RecordingSession()
    monkeypatch.setattr(core_poi, "SessionLocal", lambda: session)
    monkeypatch.setattr(core_poi, "CorePoiGeometryRepository", _StubRepository)

    core_poi.create_poi(CorePOICreate(**VALID_BODY))

    payload = _StubRepository.last_payload
    assert payload["location_name"] == "Klyde Warren Park"
    assert payload["market"] == "dallas"
    assert payload["latitude"] == 32.7893
    # The handler serializes with model_dump(), not to_row(), so a defaulted
    # enum arrives as the GeometryType member. It equals "POLYGON" because the
    # enum subclasses str, but it is not a plain string -- see
    # test_model_dump_leaves_the_default_geometry_type_as_an_enum_member.
    assert payload["geometry_type"] == "POLYGON"
    assert isinstance(payload["geometry_type"], GeometryType)


def test_create_poi_commits_exactly_once(monkeypatch):
    session = _RecordingSession()
    monkeypatch.setattr(core_poi, "SessionLocal", lambda: session)
    monkeypatch.setattr(core_poi, "CorePoiGeometryRepository", _StubRepository)

    core_poi.create_poi(CorePOICreate(**VALID_BODY))

    assert session.committed == 1


def test_get_all_pois_does_not_commit(monkeypatch):
    session = _RecordingSession()
    monkeypatch.setattr(core_poi, "SessionLocal", lambda: session)
    monkeypatch.setattr(core_poi, "CorePoiGeometryRepository", _StubRepository)

    core_poi.get_all_pois()

    assert session.committed == 0


@pytest.mark.parametrize("handler", ["create_poi", "get_all_pois"])
def test_handlers_never_close_the_session_they_open(monkeypatch, handler):
    """Pins a leak rather than endorsing it.

    Both handlers call ``SessionLocal()`` directly instead of depending on
    ``get_db``, whose ``finally: db.close()`` is the only thing that returns a
    connection to the pool. Nothing here closes, so every request holds one
    until garbage collection gets to it. Should these move to
    ``Depends(get_db)``, this test is the one that should fail.
    """
    session = _RecordingSession()
    monkeypatch.setattr(core_poi, "SessionLocal", lambda: session)
    monkeypatch.setattr(core_poi, "CorePoiGeometryRepository", _StubRepository)

    if handler == "create_poi":
        core_poi.create_poi(CorePOICreate(**VALID_BODY))
    else:
        core_poi.get_all_pois()

    assert session.closed == 0


# --------------------------------------------------------------------------- #
# Route wiring
# --------------------------------------------------------------------------- #


def test_routes_are_registered_at_the_paths_the_frontend_calls():
    paths = {route.path: route for route in core_poi.router.routes}

    assert "/core_poi/get-all-pois" in paths
    assert "/core_poi/create-poi" in paths
    assert paths["/core_poi/create-poi"].status_code == 201
    assert paths["/core_poi/get-all-pois"].status_code == 200
    assert "GET" in paths["/core_poi/get-all-pois"].methods
    assert "POST" in paths["/core_poi/create-poi"].methods
