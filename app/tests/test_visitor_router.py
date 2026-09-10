"""``routers/final_visitor.py`` — the eight handlers the frontend calls.

Mapped to their callers in ``src/api``:

* get-visitor-by-city-date              → map.ts    getVisitorDataByCityDate
* get-heat-risk-score-by-city-date      → map.ts    getHeatRiskDataByCityDate
* query-visitor-rows-with-geometry-...  → statistics.ts fetchVisitorPOIs / top destinations
* get-visitor-percentage-by-heat-risk   → statistics.ts getRiskDistributionByCityDate
* get-average-heat-risk-score-by-...    → statistics.ts getAverageHeatRiskScoreByCityDate
* get-visitor-in-unsafe-condition       → statistics.ts getVisitorInUnsafeCondition
* get-total-visits-by-city-date         → statistics.ts getTotalVisitsByCityDate
* get-poi-count-in-unsafe-condition     → statistics.ts getPoiCountInUnsafeCondition

``/all``, ``/upload``, ``/update/{id}`` and ``/delete/{id}`` are in the same
module but unreached from the frontend, so they are out of scope.

The handlers are ``async def``, so each test drives one through ``asyncio.run``.
The repository is swapped for a stub via the module's ``visitor_data_class``
name, which is the seam the module already exposes.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from fastapi import HTTPException

from routers import final_visitor

from conftest import TEST_DATE

DB = object()  # stand-in for the injected session; the stub never uses it


def run(coroutine):
    return asyncio.run(coroutine)


class _StubRepository:
    """Returns a canned answer per method and records how it was called."""

    answers: dict = {}
    calls: list = []

    def __init__(self, db):
        type(self).calls.append(("__init__", db))

    def _answer(self, name, **kwargs):
        type(self).calls.append((name, kwargs))
        return type(self).answers.get(name)

    def getVisitorDataByCityDate(self, city, date):
        return self._answer("getVisitorDataByCityDate", city=city, date=date)

    def getHeatRiskScoreByCityDate(self, city, date):
        return self._answer("getHeatRiskScoreByCityDate", city=city, date=date)

    def queryVisitorRowsWithGeometryByCityDate(self, city, date, sorted=False, limit=None):
        return self._answer(
            "queryVisitorRowsWithGeometryByCityDate",
            city=city,
            date=date,
            sorted=sorted,
            limit=limit,
        )

    def getTotalVisitsByCityDate(self, city, date):
        return self._answer("getTotalVisitsByCityDate", city=city, date=date)

    def getVisitorPercentageByHeatRisk(self, city, date):
        return self._answer("getVisitorPercentageByHeatRisk", city=city, date=date)

    def getAverageHeatRiskScoreByCityDate(self, city, date):
        return self._answer("getAverageHeatRiskScoreByCityDate", city=city, date=date)

    def getVisitorInUnsafeCondition(self, city, date):
        return self._answer("getVisitorInUnsafeCondition", city=city, date=date)

    def getPoiCountInUnsafeCondition(self, city, date):
        return self._answer("getPoiCountInUnsafeCondition", city=city, date=date)


class _FakeRow:
    """Mimics a SQLAlchemy Row well enough for ``dict(row._mapping)``."""

    def __init__(self, **values):
        self._mapping = values


@pytest.fixture
def stub(monkeypatch):
    _StubRepository.answers = {}
    _StubRepository.calls = []
    monkeypatch.setattr(final_visitor, "visitor_data_class", _StubRepository)
    return _StubRepository


def only_call(stub, name):
    matching = [call for call in stub.calls if call[0] == name]
    assert len(matching) == 1, f"expected one {name} call, got {len(matching)}"
    return matching[0][1]


# --------------------------------------------------------------------------- #
# get-visitor-by-city-date
# --------------------------------------------------------------------------- #


class TestGetVisitorByCityDate:
    def test_the_repository_payload_is_returned_unchanged(self, stub):
        payload = {"2026-08-16": [{"value": 100.0}]}
        stub.answers["getVisitorDataByCityDate"] = payload

        result = run(
            final_visitor.get_visitor_data_by_city_date("houston", TEST_DATE, db=DB)
        )

        assert result == payload

    def test_the_arguments_are_forwarded(self, stub):
        stub.answers["getVisitorDataByCityDate"] = {"x": 1}

        run(final_visitor.get_visitor_data_by_city_date("dallas", TEST_DATE, db=DB))

        assert only_call(stub, "getVisitorDataByCityDate") == {
            "city": "dallas",
            "date": TEST_DATE,
        }

    def test_an_empty_result_becomes_a_404(self, stub):
        stub.answers["getVisitorDataByCityDate"] = {}

        with pytest.raises(HTTPException) as excinfo:
            run(final_visitor.get_visitor_data_by_city_date("houston", TEST_DATE, db=DB))

        assert excinfo.value.status_code == 404


# --------------------------------------------------------------------------- #
# get-heat-risk-score-by-city-date
# --------------------------------------------------------------------------- #


class TestGetHeatRiskScoreByCityDate:
    def test_the_repository_payload_is_returned_unchanged(self, stub):
        payload = {"2026-08-16": [{"value": 95.0}]}
        stub.answers["getHeatRiskScoreByCityDate"] = payload

        result = run(
            final_visitor.get_heat_risk_score_by_city_date("houston", TEST_DATE, db=DB)
        )

        assert result == payload

    def test_an_empty_result_becomes_a_404(self, stub):
        stub.answers["getHeatRiskScoreByCityDate"] = {}

        with pytest.raises(HTTPException) as excinfo:
            run(
                final_visitor.get_heat_risk_score_by_city_date(
                    "houston", TEST_DATE, db=DB
                )
            )

        assert excinfo.value.status_code == 404


# --------------------------------------------------------------------------- #
# query-visitor-rows-with-geometry-by-city-date
# --------------------------------------------------------------------------- #


class TestQueryVisitorRows:
    def test_rows_are_serialized_into_dicts(self, stub):
        stub.answers["queryVisitorRowsWithGeometryByCityDate"] = [
            _FakeRow(id=1, location_name="Chipotle", heat_risk_score=95.0),
            _FakeRow(id=2, location_name="Panera", heat_risk_score=70.0),
        ]

        result = run(
            final_visitor.query_visitor_rows_with_geometry_by_city_date(
                "houston", TEST_DATE, db=DB
            )
        )

        assert result == [
            {"id": 1, "location_name": "Chipotle", "heat_risk_score": 95.0},
            {"id": 2, "location_name": "Panera", "heat_risk_score": 70.0},
        ]

    def test_the_response_is_a_bare_list(self, stub):
        # statistics.ts accepts an array or a {data|results|rows} wrapper; the
        # handler sends the array.
        stub.answers["queryVisitorRowsWithGeometryByCityDate"] = [_FakeRow(id=1)]

        result = run(
            final_visitor.query_visitor_rows_with_geometry_by_city_date(
                "houston", TEST_DATE, db=DB
            )
        )

        assert isinstance(result, list)

    def test_sorting_is_off_and_limit_unset_by_default(self, stub):
        stub.answers["queryVisitorRowsWithGeometryByCityDate"] = [_FakeRow(id=1)]

        run(
            final_visitor.query_visitor_rows_with_geometry_by_city_date(
                "houston", TEST_DATE, db=DB
            )
        )

        call = only_call(stub, "queryVisitorRowsWithGeometryByCityDate")
        assert call["sorted"] is False
        assert call["limit"] is None

    def test_sorted_and_limit_are_forwarded(self, stub):
        stub.answers["queryVisitorRowsWithGeometryByCityDate"] = [_FakeRow(id=1)]

        run(
            final_visitor.query_visitor_rows_with_geometry_by_city_date(
                "houston", TEST_DATE, sorted=True, limit=5, db=DB
            )
        )

        call = only_call(stub, "queryVisitorRowsWithGeometryByCityDate")
        assert call["sorted"] is True
        assert call["limit"] == 5

    def test_no_rows_becomes_a_404(self, stub):
        stub.answers["queryVisitorRowsWithGeometryByCityDate"] = []

        with pytest.raises(HTTPException) as excinfo:
            run(
                final_visitor.query_visitor_rows_with_geometry_by_city_date(
                    "houston", TEST_DATE, db=DB
                )
            )

        assert excinfo.value.status_code == 404


# --------------------------------------------------------------------------- #
# get-total-visits-by-city-date
# --------------------------------------------------------------------------- #


class TestGetTotalVisits:
    def test_the_keyed_total_is_returned(self, stub):
        stub.answers["getTotalVisitsByCityDate"] = {"2026-08-16": 48213.0}

        result = run(
            final_visitor.get_total_visits_by_city_date(TEST_DATE, city="houston", db=DB)
        )

        assert result == {"2026-08-16": 48213.0}

    def test_the_city_is_optional(self, stub):
        stub.answers["getTotalVisitsByCityDate"] = {"2026-08-16": 79220.0}

        run(final_visitor.get_total_visits_by_city_date(TEST_DATE, db=DB))

        assert only_call(stub, "getTotalVisitsByCityDate") == {
            "city": None,
            "date": TEST_DATE,
        }

    def test_an_empty_total_becomes_a_404(self, stub):
        """The frontend expects ``{}`` here, and gets a 404 instead.

        ``statistics.ts`` documents this endpoint as returning ``{}`` when the
        total is zero or nothing is cached, and maps that to null. The handler
        turns the same case into a 404, which ``getTotalVisitsByCityDate``
        treats as a hard failure and throws on. So a city with no cached rows
        surfaces as an error in the UI rather than as an empty tile.
        """
        stub.answers["getTotalVisitsByCityDate"] = {}

        with pytest.raises(HTTPException) as excinfo:
            run(
                final_visitor.get_total_visits_by_city_date(
                    TEST_DATE, city="houston", db=DB
                )
            )

        assert excinfo.value.status_code == 404


# --------------------------------------------------------------------------- #
# get-visitor-percentage-by-heat-risk
# --------------------------------------------------------------------------- #


class TestGetVisitorPercentageByHeatRisk:
    def test_the_band_percentages_are_returned(self, stub):
        payload = {
            "Low": 0.0,
            "Caution": 0.0,
            "Extreme Caution": 38.6,
            "Danger": 61.4,
            "Extreme Danger": 0.0,
        }
        stub.answers["getVisitorPercentageByHeatRisk"] = payload

        result = run(
            final_visitor.get_visitor_percentage_by_heat_risk(
                TEST_DATE, city="houston", db=DB
            )
        )

        assert result == payload

    def test_the_city_is_optional(self, stub):
        stub.answers["getVisitorPercentageByHeatRisk"] = {"Low": 100.0}

        run(final_visitor.get_visitor_percentage_by_heat_risk(TEST_DATE, db=DB))

        assert only_call(stub, "getVisitorPercentageByHeatRisk")["city"] is None

    def test_an_unclassifiable_date_becomes_a_404(self, stub):
        """Same mismatch as the total-visits endpoint.

        ``getRiskDistributionByCityDate`` in statistics.ts is written to read
        ``{}`` as "no data" and return an empty bucket list. It never gets the
        chance: the handler 404s first and the fetch wrapper throws.
        """
        stub.answers["getVisitorPercentageByHeatRisk"] = {}

        with pytest.raises(HTTPException) as excinfo:
            run(
                final_visitor.get_visitor_percentage_by_heat_risk(
                    TEST_DATE, city="houston", db=DB
                )
            )

        assert excinfo.value.status_code == 404

    def test_an_all_zero_distribution_is_returned_rather_than_404ed(self, stub):
        # The guard is `if not result`, and a populated dict is truthy however
        # small its values, so only the empty dict trips it.
        payload = dict.fromkeys(
            ["Low", "Caution", "Extreme Caution", "Danger", "Extreme Danger"], 0.0
        )
        stub.answers["getVisitorPercentageByHeatRisk"] = payload

        result = run(
            final_visitor.get_visitor_percentage_by_heat_risk(
                TEST_DATE, city="houston", db=DB
            )
        )

        assert result == payload


# --------------------------------------------------------------------------- #
# get-average-heat-risk-score-by-city-date
# --------------------------------------------------------------------------- #


class TestGetAverageHeatRiskScore:
    def test_the_average_is_returned(self, stub):
        stub.answers["getAverageHeatRiskScoreByCityDate"] = 72.4

        result = run(
            final_visitor.get_average_heat_risk_score_by_city_date(
                "houston", TEST_DATE, db=DB
            )
        )

        assert result == 72.4

    def test_a_genuine_zero_average_is_returned_rather_than_404ed(self, stub):
        """This handler checks ``is None``, not truthiness.

        That is the right test and the only endpoint in the module that gets it
        right: a city averaging 0.0 is real data, and the truthiness check its
        neighbours use would report it as missing.
        """
        stub.answers["getAverageHeatRiskScoreByCityDate"] = 0.0

        result = run(
            final_visitor.get_average_heat_risk_score_by_city_date(
                "houston", TEST_DATE, db=DB
            )
        )

        assert result == 0.0

    def test_no_scored_rows_becomes_a_404(self, stub):
        stub.answers["getAverageHeatRiskScoreByCityDate"] = None

        with pytest.raises(HTTPException) as excinfo:
            run(
                final_visitor.get_average_heat_risk_score_by_city_date(
                    "houston", TEST_DATE, db=DB
                )
            )

        assert excinfo.value.status_code == 404

    def test_the_arguments_are_forwarded(self, stub):
        stub.answers["getAverageHeatRiskScoreByCityDate"] = 50.0

        run(
            final_visitor.get_average_heat_risk_score_by_city_date(
                "dallas", TEST_DATE, db=DB
            )
        )

        assert only_call(stub, "getAverageHeatRiskScoreByCityDate") == {
            "city": "dallas",
            "date": TEST_DATE,
        }


# --------------------------------------------------------------------------- #
# The two ungated counters
# --------------------------------------------------------------------------- #


class TestUnsafeConditionEndpoints:
    def test_unsafe_visits_are_returned(self, stub):
        stub.answers["getVisitorInUnsafeCondition"] = 48213.0

        result = run(
            final_visitor.get_visitor_in_unsafe_condition("houston", TEST_DATE, db=DB)
        )

        assert result == 48213.0

    def test_a_zero_visit_count_is_returned_not_404ed(self, stub):
        # No `if not result` guard here, so a cool day answers 0 as data.
        stub.answers["getVisitorInUnsafeCondition"] = 0

        result = run(
            final_visitor.get_visitor_in_unsafe_condition("houston", TEST_DATE, db=DB)
        )

        assert result == 0

    def test_the_unsafe_poi_count_is_returned(self, stub):
        stub.answers["getPoiCountInUnsafeCondition"] = 42

        result = run(
            final_visitor.get_poi_count_in_unsafe_condition("houston", TEST_DATE, db=DB)
        )

        assert result == 42

    def test_a_zero_poi_count_is_returned_not_404ed(self, stub):
        stub.answers["getPoiCountInUnsafeCondition"] = 0

        result = run(
            final_visitor.get_poi_count_in_unsafe_condition("houston", TEST_DATE, db=DB)
        )

        assert result == 0

    @pytest.mark.parametrize(
        ("handler", "method"),
        [
            ("get_visitor_in_unsafe_condition", "getVisitorInUnsafeCondition"),
            ("get_poi_count_in_unsafe_condition", "getPoiCountInUnsafeCondition"),
        ],
    )
    def test_the_arguments_are_forwarded(self, stub, handler, method):
        stub.answers[method] = 1

        run(getattr(final_visitor, handler)("dallas", TEST_DATE, db=DB))

        assert only_call(stub, method) == {"city": "dallas", "date": TEST_DATE}


# --------------------------------------------------------------------------- #
# Cross-cutting
# --------------------------------------------------------------------------- #


def test_the_repository_is_built_from_the_injected_session(stub):
    stub.answers["getVisitorInUnsafeCondition"] = 0

    run(final_visitor.get_visitor_in_unsafe_condition("houston", TEST_DATE, db=DB))

    assert ("__init__", DB) in stub.calls


def test_a_404_detail_is_a_string(stub):
    stub.answers["getVisitorDataByCityDate"] = {}

    with pytest.raises(HTTPException) as excinfo:
        run(final_visitor.get_visitor_data_by_city_date("houston", TEST_DATE, db=DB))

    assert isinstance(excinfo.value.detail, str)
    assert excinfo.value.detail


def test_routes_are_registered_at_the_paths_the_frontend_calls():
    paths = {route.path for route in final_visitor.router.routes}

    assert {
        "/final_visitor/get-visitor-by-city-date",
        "/final_visitor/get-heat-risk-score-by-city-date",
        "/final_visitor/query-visitor-rows-with-geometry-by-city-date",
        "/final_visitor/get-total-visits-by-city-date",
        "/final_visitor/get-visitor-percentage-by-heat-risk",
        "/final_visitor/get-average-heat-risk-score-by-city-date",
        "/final_visitor/get-visitor-in-unsafe-condition",
        "/final_visitor/get-poi-count-in-unsafe-condition",
    } <= paths


def test_the_frontend_facing_routes_are_all_get():
    frontend_paths = {
        "/final_visitor/get-visitor-by-city-date",
        "/final_visitor/get-heat-risk-score-by-city-date",
        "/final_visitor/query-visitor-rows-with-geometry-by-city-date",
        "/final_visitor/get-total-visits-by-city-date",
        "/final_visitor/get-visitor-percentage-by-heat-risk",
        "/final_visitor/get-average-heat-risk-score-by-city-date",
        "/final_visitor/get-visitor-in-unsafe-condition",
        "/final_visitor/get-poi-count-in-unsafe-condition",
    }

    for route in final_visitor.router.routes:
        if route.path in frontend_paths:
            assert route.methods == {"GET"}
