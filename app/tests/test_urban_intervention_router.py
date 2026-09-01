"""``routers/urban_intervention.py`` — all three handlers the toolbox calls.

* ``GET  /urban_intervention/get-urban-interventions-by-city-date``
* ``GET  /urban_intervention/get-urban-interventions-by-city-between-dates``
* ``POST /urban_intervention/create-urban-intervention``

Each handler opens its own ``SessionLocal()``, so the tests swap that name and
the repository class for stubs. What is under test is the handler's own work:
turning ``UrbanInterventionRecord`` dataclasses into JSON-ready dicts, resolving
the ``statuses`` query parameter, and mapping a ``ValueError`` to a 400.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import pytest
from fastapi import HTTPException

from repository.urban_internvetion_repository import (
    InvalidGeometryError,
    InvalidParametersError,
    UrbanInterventionRecord,
)
from routers import urban_intervention

CREATE_BODY = {
    "market_code": "houston",
    "name": "Shade trees on Main",
    "color": "#22c55e",
    "archetype_code": "vegetation",
    "intervention_type": "street_tree",
    "geometry": {"kind": "polygon", "ring": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]},
    "parameters": {"coverPct": 0.4, "lai": 3.0, "irrigation": 0.8},
}


def record(**overrides) -> UrbanInterventionRecord:
    fields = {
        "id": UUID("00000000-0000-0000-0000-000000000001"),
        "market_code": "houston",
        "name": "Shade trees on Main",
        "color": "#22c55e",
        "archetype_code": "vegetation",
        "intervention_type": "street_tree",
        "geometry_kind": "polygon",
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        "parameters": {"coverPct": 0.4, "lai": 3.0, "irrigation": 0.8},
        "status": "active",
        "active_from": datetime(2026, 8, 1),
        "active_to": None,
    }
    fields.update(overrides)
    return UrbanInterventionRecord(**fields)


class _StubSession:
    def __init__(self):
        self.commits = 0
        self.closed = 0

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed += 1


class _StubRepository:
    """Records the arguments each handler forwards; replays canned records."""

    records: list[UrbanInterventionRecord] = []
    error: Exception | None = None
    calls: list[dict] = []

    def __init__(self, db):
        self.db = db

    def _answer(self, **call):
        type(self).calls.append(call)
        if type(self).error is not None:
            raise type(self).error
        return list(type(self).records)

    def get_many_by_city_and_date(self, city, as_of, *, statuses=None):
        return self._answer(
            method="get_many_by_city_and_date", city=city, as_of=as_of, statuses=statuses
        )

    def get_all_by_city_between_date(
        self, city, from_date, to_date, *, statuses=None
    ):
        return self._answer(
            method="get_all_by_city_between_date",
            city=city,
            from_date=from_date,
            to_date=to_date,
            statuses=statuses,
        )

    def create(self, payload):
        type(self).calls.append({"method": "create", "payload": payload})
        if type(self).error is not None:
            raise type(self).error
        return type(self).records[0]


@pytest.fixture
def stub(monkeypatch):
    session = _StubSession()
    _StubRepository.records = [record()]
    _StubRepository.error = None
    _StubRepository.calls = []
    monkeypatch.setattr(urban_intervention, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        urban_intervention, "UrbanInterventionRepository", _StubRepository
    )
    return _StubRepository, session


# --------------------------------------------------------------------------- #
# GET .../get-urban-interventions-by-city-date
# --------------------------------------------------------------------------- #


def test_by_city_date_returns_plain_dicts(stub):
    repository, _ = stub

    result = urban_intervention.get_urban_interventions_by_city_date(
        city="houston", as_of=date(2026, 8, 16)
    )

    assert isinstance(result, list)
    assert isinstance(result[0], dict)


def test_by_city_date_exposes_every_record_field(stub):
    result = urban_intervention.get_urban_interventions_by_city_date(
        city="houston", as_of=date(2026, 8, 16)
    )

    item = result[0]
    assert item["id"] == UUID("00000000-0000-0000-0000-000000000001")
    assert item["market_code"] == "houston"
    assert item["name"] == "Shade trees on Main"
    assert item["color"] == "#22c55e"
    assert item["archetype_code"] == "vegetation"
    assert item["intervention_type"] == "street_tree"
    assert item["geometry_kind"] == "polygon"
    assert item["status"] == "active"
    assert item["active_from"] == datetime(2026, 8, 1)
    assert item["active_to"] is None


def test_by_city_date_keeps_geometry_and_parameters_as_objects(stub):
    # The frontend reads record.geometry.coordinates and record.params.* , so
    # these have to survive as nested structures rather than strings.
    item = urban_intervention.get_urban_interventions_by_city_date(
        city="houston", as_of=date(2026, 8, 16)
    )[0]

    assert item["geometry"]["type"] == "Polygon"
    assert item["geometry"]["coordinates"] == [[[0, 0], [1, 0], [1, 1], [0, 0]]]
    assert item["parameters"]["lai"] == 3.0


def test_by_city_date_forwards_the_query_parameters(stub):
    repository, _ = stub

    urban_intervention.get_urban_interventions_by_city_date(
        city="dallas", as_of=date(2026, 8, 16)
    )

    assert repository.calls == [
        {
            "method": "get_many_by_city_and_date",
            "city": "dallas",
            "as_of": date(2026, 8, 16),
            "statuses": None,
        }
    ]


def test_by_city_date_returns_an_empty_list_when_nothing_matches(stub):
    repository, _ = stub
    repository.records = []

    result = urban_intervention.get_urban_interventions_by_city_date(
        city="houston", as_of=date(2026, 8, 16)
    )

    assert result == []


def test_by_city_date_maps_every_record(stub):
    repository, _ = stub
    repository.records = [record(name="A"), record(name="B"), record(name="C")]

    result = urban_intervention.get_urban_interventions_by_city_date(
        city="houston", as_of=date(2026, 8, 16)
    )

    assert [item["name"] for item in result] == ["A", "B", "C"]


# --------------------------------------------------------------------------- #
# GET .../get-urban-interventions-by-city-between-dates
# --------------------------------------------------------------------------- #


def test_between_dates_forwards_the_range(stub):
    repository, _ = stub

    urban_intervention.get_urban_interventions_by_city_between_dates(
        city="houston", from_date=date(2026, 8, 1), to_date=date(2026, 8, 31)
    )

    call = repository.calls[0]
    assert call["method"] == "get_all_by_city_between_date"
    assert call["city"] == "houston"
    assert call["from_date"] == date(2026, 8, 1)
    assert call["to_date"] == date(2026, 8, 31)


def test_between_dates_returns_dicts(stub):
    result = urban_intervention.get_urban_interventions_by_city_between_dates(
        city="houston", from_date=date(2026, 8, 1), to_date=date(2026, 8, 31)
    )

    assert [item["name"] for item in result] == ["Shade trees on Main"]


def test_between_dates_returns_an_empty_list_when_nothing_matches(stub):
    repository, _ = stub
    repository.records = []

    result = urban_intervention.get_urban_interventions_by_city_between_dates(
        city="houston", from_date=date(2026, 8, 1), to_date=date(2026, 8, 31)
    )

    assert result == []


def test_an_omitted_status_filter_reaches_the_repository_as_none(stub):
    # The default is a fastapi Query object, not None, so the handler has to
    # normalize it before passing it down.
    repository, _ = stub

    urban_intervention.get_urban_interventions_by_city_between_dates(
        city="houston", from_date=date(2026, 8, 1), to_date=date(2026, 8, 31)
    )

    assert repository.calls[0]["statuses"] is None


def test_a_status_list_is_forwarded(stub):
    repository, _ = stub

    urban_intervention.get_urban_interventions_by_city_between_dates(
        city="houston",
        from_date=date(2026, 8, 1),
        to_date=date(2026, 8, 31),
        statuses=["active", "planned"],
    )

    assert repository.calls[0]["statuses"] == ["active", "planned"]


def test_an_empty_status_list_is_forwarded_as_an_empty_list(stub):
    # [] is a list, so it survives the isinstance check and the repository can
    # apply its "nothing can match" short circuit.
    repository, _ = stub

    urban_intervention.get_urban_interventions_by_city_between_dates(
        city="houston",
        from_date=date(2026, 8, 1),
        to_date=date(2026, 8, 31),
        statuses=[],
    )

    assert repository.calls[0]["statuses"] == []


def test_a_non_list_status_filter_is_silently_dropped(stub):
    """A tuple of statuses is discarded rather than applied.

    The handler normalizes with ``isinstance(statuses, list)``, which is aimed
    at the fastapi ``Query`` default but catches every non-list sequence with
    it. Over HTTP this cannot happen — FastAPI always builds a list — but a
    Python caller passing a tuple gets an unfiltered result and no warning.
    """
    repository, _ = stub

    urban_intervention.get_urban_interventions_by_city_between_dates(
        city="houston",
        from_date=date(2026, 8, 1),
        to_date=date(2026, 8, 31),
        statuses=("active",),
    )

    assert repository.calls[0]["statuses"] is None


def test_an_inverted_range_becomes_a_400(stub):
    repository, _ = stub
    repository.error = ValueError("from_date must not be after to_date.")

    with pytest.raises(HTTPException) as excinfo:
        urban_intervention.get_urban_interventions_by_city_between_dates(
            city="houston", from_date=date(2026, 8, 31), to_date=date(2026, 8, 1)
        )

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "from_date must not be after to_date."


def test_a_non_value_error_is_not_converted_to_a_400(stub):
    # Only ValueError is a client mistake; anything else must surface as a 500
    # rather than being reported as bad input.
    repository, _ = stub
    repository.error = RuntimeError("connection lost")

    with pytest.raises(RuntimeError):
        urban_intervention.get_urban_interventions_by_city_between_dates(
            city="houston", from_date=date(2026, 8, 1), to_date=date(2026, 8, 31)
        )


# --------------------------------------------------------------------------- #
# POST .../create-urban-intervention
# --------------------------------------------------------------------------- #


def test_create_returns_the_persisted_record_as_a_dict(stub):
    result = urban_intervention.create_urban_intervention(dict(CREATE_BODY))

    assert isinstance(result, dict)
    assert result["name"] == "Shade trees on Main"
    assert result["market_code"] == "houston"
    assert result["intervention_type"] == "street_tree"
    assert result["status"] == "active"


def test_create_returns_the_database_geometry_not_the_posted_one(stub):
    # The body carries a {kind, ring} input shape; the response carries the
    # GeoJSON the database round-tripped back.
    result = urban_intervention.create_urban_intervention(dict(CREATE_BODY))

    assert result["geometry"] == {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
    }
    assert "kind" not in result["geometry"]


def test_create_forwards_the_body_unchanged(stub):
    repository, _ = stub

    urban_intervention.create_urban_intervention(dict(CREATE_BODY))

    assert repository.calls[0]["method"] == "create"
    assert repository.calls[0]["payload"] == CREATE_BODY


def test_create_commits_exactly_once(stub):
    _, session = stub

    urban_intervention.create_urban_intervention(dict(CREATE_BODY))

    assert session.commits == 1


def test_a_rejected_body_does_not_commit(stub):
    repository, session = stub
    repository.error = InvalidParametersError("missing required parameter 'lai'")

    with pytest.raises(InvalidParametersError):
        urban_intervention.create_urban_intervention(dict(CREATE_BODY))

    assert session.commits == 0


def test_a_rejected_body_is_not_turned_into_a_400(stub):
    """``create`` has no ValueError handler, unlike the range endpoint.

    ``InvalidParametersError`` and ``InvalidGeometryError`` both subclass
    ValueError, so the same mistake that yields a clean 400 on the between-dates
    route escapes uncaught here and surfaces as a 500 — the client is told the
    server broke rather than that its parameters were wrong.
    """
    repository, _ = stub
    repository.error = InvalidGeometryError("A polygon ring needs at least 3 ...")

    with pytest.raises(InvalidGeometryError):
        urban_intervention.create_urban_intervention(dict(CREATE_BODY))


def test_read_handlers_do_not_commit(stub):
    _, session = stub

    urban_intervention.get_urban_interventions_by_city_date(
        city="houston", as_of=date(2026, 8, 16)
    )
    urban_intervention.get_urban_interventions_by_city_between_dates(
        city="houston", from_date=date(2026, 8, 1), to_date=date(2026, 8, 31)
    )

    assert session.commits == 0


def test_no_handler_closes_the_session_it_opened(stub):
    # Same leak as the core_poi handlers: SessionLocal() with no close().
    _, session = stub

    urban_intervention.create_urban_intervention(dict(CREATE_BODY))
    urban_intervention.get_urban_interventions_by_city_date(
        city="houston", as_of=date(2026, 8, 16)
    )

    assert session.closed == 0


# --------------------------------------------------------------------------- #
# Route wiring
# --------------------------------------------------------------------------- #


def test_routes_are_registered_at_the_paths_the_frontend_calls():
    paths = {route.path: route for route in urban_intervention.router.routes}

    assert "/urban_intervention/create-urban-intervention" in paths
    assert "/urban_intervention/get-urban-interventions-by-city-date" in paths
    assert "/urban_intervention/get-urban-interventions-by-city-between-dates" in paths
    assert paths["/urban_intervention/create-urban-intervention"].status_code == 201
    assert "POST" in paths["/urban_intervention/create-urban-intervention"].methods
