"""``routers/heatmap.py`` — the three handlers the frontend calls.

Mapped to their callers in ``src/api``:

* get-heatmap-points-by-city-date-metric → map.ts        getHeatmapPointsByCityDateMetric
* get-local-temperature-by-city-date     → map.ts        getLocalTemperature{C,F}ByCityDate
* get-simulated-point-by-date            → simulation.ts getSimulatedPointsByDate

The handlers are plain ``def`` and open their own session with ``SessionLocal``
rather than taking one from ``Depends(get_db)``, so both ``SessionLocal`` and
``HeatmapRepository`` are swapped on the module. The assertions are about what
each handler forwards, and how it maps the repository's answer onto a status:
the frontend treats a 404 from the two GET routes as an empty map.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from routers import heatmap
from schemas.simulation_schemas import SimulationRequest

DATE = "2026-07-15"
POINTS = {DATE: [{"value": 30.0, "location_coordinates": [-95.4, 29.7]}]}


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class StubRepository:
    """Answers each read from ``answers`` and records every call.

    An answer that is an exception is raised instead of returned.
    """

    answers: dict = {}
    calls: list = []
    sessions: list = []  # sessions the handler passed in
    opened: list = []  # sessions SessionLocal handed out

    def __init__(self, session):
        type(self).sessions.append(session)

    def _answer(self, name, **kwargs):
        type(self).calls.append((name, kwargs))
        answer = type(self).answers.get(name)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def getDataPointsForCityDateMetric(self, **kwargs):
        return self._answer("getDataPointsForCityDateMetric", **kwargs)

    def getLocalTemperatureByCityDate(self, **kwargs):
        return self._answer("getLocalTemperatureByCityDate", **kwargs)

    def get_simulated_points_by_date(self, **kwargs):
        return self._answer("get_simulated_points_by_date", **kwargs)


@pytest.fixture
def repository(monkeypatch):
    sessions = []

    def session_factory():
        session = FakeSession()
        sessions.append(session)
        return session

    StubRepository.answers = {}
    StubRepository.calls = []
    StubRepository.sessions = []
    monkeypatch.setattr(heatmap, "SessionLocal", session_factory)
    monkeypatch.setattr(heatmap, "HeatmapRepository", StubRepository)
    StubRepository.opened = sessions
    return StubRepository


# --------------------------------------------------------------------------- #
# GET /heatmap/get-heatmap-points-by-city-date-metric
# --------------------------------------------------------------------------- #


class TestHeatmapPointsByCityDateMetric:
    def test_the_repository_answer_is_returned_as_is(self, repository):
        repository.answers["getDataPointsForCityDateMetric"] = POINTS

        result = heatmap.get_heatmap_points_by_city_date_metric(
            city="houston", date=DATE, metric="average_temperature_c"
        )

        assert result is POINTS

    def test_the_query_is_forwarded_to_the_repository(self, repository):
        """map.ts sends the market code as ``city`` and repeats
        ``additional_metrics`` once per name."""
        repository.answers["getDataPointsForCityDateMetric"] = POINTS

        heatmap.get_heatmap_points_by_city_date_metric(
            city="kansas_city",
            date=DATE,
            metric="heat_index_f",
            additional_metrics=["average_temperature_f", "heat_index_f"],
        )

        assert repository.calls == [
            (
                "getDataPointsForCityDateMetric",
                {
                    "market_code": "kansas_city",
                    "weather_date": DATE,
                    "metric": "heat_index_f",
                    "additional_metrics": ["average_temperature_f", "heat_index_f"],
                },
            )
        ]
        assert repository.sessions == repository.opened

    @pytest.mark.parametrize("empty", [{}, None])
    def test_no_points_is_a_404(self, repository, empty):
        repository.answers["getDataPointsForCityDateMetric"] = empty

        with pytest.raises(HTTPException) as raised:
            heatmap.get_heatmap_points_by_city_date_metric(
                city="houston", date=DATE, metric="average_temperature_c"
            )

        assert raised.value.status_code == 404
        assert raised.value.detail == "NO HEATMAP POINTS FOUND"

    def test_a_bad_metric_or_date_is_a_400_carrying_the_reason(self, repository):
        repository.answers["getDataPointsForCityDateMetric"] = ValueError(
            "Unknown metric 'nope'. Available metrics: [...]"
        )

        with pytest.raises(HTTPException) as raised:
            heatmap.get_heatmap_points_by_city_date_metric(
                city="houston", date=DATE, metric="nope"
            )

        assert raised.value.status_code == 400
        assert raised.value.detail == "Unknown metric 'nope'. Available metrics: [...]"

    def test_an_unexpected_error_is_not_disguised_as_a_400(self, repository):
        repository.answers["getDataPointsForCityDateMetric"] = RuntimeError("db down")

        with pytest.raises(RuntimeError):
            heatmap.get_heatmap_points_by_city_date_metric(
                city="houston", date=DATE, metric="average_temperature_c"
            )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "BUG: the handler opens SessionLocal() itself and never closes it. "
            "get_db, which every other frontend-facing router uses, closes the "
            "session in a finally block."
        ),
    )
    def test_the_request_session_is_closed(self, repository):
        repository.answers["getDataPointsForCityDateMetric"] = POINTS

        heatmap.get_heatmap_points_by_city_date_metric(
            city="houston", date=DATE, metric="average_temperature_c"
        )

        assert [session.closed for session in repository.opened] == [True]


# --------------------------------------------------------------------------- #
# GET /heatmap/get-local-temperature-by-city-date
# --------------------------------------------------------------------------- #


class TestLocalTemperatureByCityDate:
    def test_the_repository_answer_is_returned_as_is(self, repository):
        repository.answers["getLocalTemperatureByCityDate"] = POINTS

        result = heatmap.get_local_temperature_by_city_date(
            city="houston", date=DATE, metric="average_temperature_c", temperature_unit="c"
        )

        assert result is POINTS

    def test_the_query_is_forwarded_to_the_repository(self, repository):
        repository.answers["getLocalTemperatureByCityDate"] = POINTS

        heatmap.get_local_temperature_by_city_date(
            city="new_york_nj",
            date=DATE,
            metric="average_temperature_c",
            additional_metrics=["uhi"],
            temperature_unit="c",
        )

        assert repository.calls == [
            (
                "getLocalTemperatureByCityDate",
                {
                    "weather_date": DATE,
                    "metric": "average_temperature_c",
                    "market_code": "new_york_nj",
                    "additional_metrics": ["uhi"],
                    "temperature_unit": "c",
                },
            )
        ]

    def test_the_defaults_are_no_source_column_and_fahrenheit(self, repository):
        """``additional_metrics`` is passed explicitly: its default is a
        ``Query`` marker that only FastAPI's request parsing resolves."""
        repository.answers["getLocalTemperatureByCityDate"] = POINTS

        heatmap.get_local_temperature_by_city_date(
            city="houston", date=DATE, additional_metrics=None
        )

        _, kwargs = repository.calls[0]
        assert kwargs["metric"] is None
        assert kwargs["temperature_unit"] == "f"

    @pytest.mark.parametrize("empty", [{}, None])
    def test_no_points_is_a_404(self, repository, empty):
        repository.answers["getLocalTemperatureByCityDate"] = empty

        with pytest.raises(HTTPException) as raised:
            heatmap.get_local_temperature_by_city_date(city="houston", date=DATE)

        assert raised.value.status_code == 404
        assert raised.value.detail == "NO LOCAL TEMPERATURE POINTS FOUND"

    def test_a_bad_unit_or_column_is_a_400_carrying_the_reason(self, repository):
        repository.answers["getLocalTemperatureByCityDate"] = ValueError(
            "temperature_unit must be 'f' or 'c', got 'k'"
        )

        with pytest.raises(HTTPException) as raised:
            heatmap.get_local_temperature_by_city_date(
                city="houston", date=DATE, temperature_unit="k"
            )

        assert raised.value.status_code == 400
        assert raised.value.detail == "temperature_unit must be 'f' or 'c', got 'k'"

    @pytest.mark.xfail(
        strict=True,
        reason="BUG: SessionLocal() is opened per request and never closed.",
    )
    def test_the_request_session_is_closed(self, repository):
        repository.answers["getLocalTemperatureByCityDate"] = POINTS

        heatmap.get_local_temperature_by_city_date(city="houston", date=DATE)

        assert [session.closed for session in repository.opened] == [True]


# --------------------------------------------------------------------------- #
# POST /heatmap/get-simulated-point-by-date
# --------------------------------------------------------------------------- #


def simulation_request(**overrides):
    fields = dict(
        from_date="2026-07-15",
        to_date="2026-07-17",
        city="Houston",
        metric="average_temperature_c",
    )
    fields.update(overrides)
    return SimulationRequest(**fields)


class TestSimulatedPointByDate:
    def test_the_simulated_points_are_returned_as_is(self, repository):
        repository.answers["get_simulated_points_by_date"] = POINTS

        assert heatmap.get_simulated_point_by_date(simulation_request()) is POINTS

    def test_every_payload_field_is_forwarded(self, repository):
        repository.answers["get_simulated_points_by_date"] = POINTS

        heatmap.get_simulated_point_by_date(
            simulation_request(
                additional_metrics=["average_relative_humidity_pct"], mode="contextual"
            )
        )

        assert repository.calls == [
            (
                "get_simulated_points_by_date",
                {
                    "from_date": "2026-07-15",
                    "to_date": "2026-07-17",
                    "city": "Houston",
                    "metric": "average_temperature_c",
                    "additional_metrics": ["average_relative_humidity_pct"],
                    "mode": "contextual",
                },
            )
        ]

    def test_an_empty_simulation_is_returned_rather_than_a_404(self, repository):
        """simulation.ts treats any non-2xx as a failure, so an empty range
        must come back as an empty body."""
        repository.answers["get_simulated_points_by_date"] = {}

        assert heatmap.get_simulated_point_by_date(simulation_request()) == {}

    @pytest.mark.parametrize(
        "error", [ValueError("from_date must not be after to_date."), KeyError("bad_type")]
    )
    def test_any_failure_is_a_400_carrying_the_reason(self, repository, error):
        repository.answers["get_simulated_points_by_date"] = error

        with pytest.raises(HTTPException) as raised:
            heatmap.get_simulated_point_by_date(simulation_request())

        assert raised.value.status_code == 400
        assert raised.value.detail == str(error)

    def test_the_request_defaults_match_the_frontend_s_plain_call(self):
        payload = simulation_request()

        assert payload.additional_metrics is None
        assert payload.mode == "standard"

    def test_an_unknown_mode_is_rejected_by_the_schema(self):
        with pytest.raises(ValidationError):
            simulation_request(mode="aggressive")

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "BUG: SessionLocal() is opened per request and never closed; this "
            "route also queries interventions through it, so it holds a pooled "
            "connection until garbage collection."
        ),
    )
    def test_the_request_session_is_closed(self, repository):
        repository.answers["get_simulated_points_by_date"] = POINTS

        heatmap.get_simulated_point_by_date(simulation_request())

        assert [session.closed for session in repository.opened] == [True]
