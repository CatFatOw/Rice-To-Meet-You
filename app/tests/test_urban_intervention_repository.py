"""``UrbanInterventionRepository`` — the three toolbox endpoints' data access.

All three of its methods are reached from the frontend:

* ``get_many_by_city_and_date``    — Toolbox / Heatmap load a date's objects.
* ``get_all_by_city_between_date`` — the simulation panel loads a date range.
* ``create``                       — saving a placed object.

The SQL is Postgres-only (``ST_AsGeoJSON``, ``= ANY(:statuses)``,
``CAST(... AS jsonb)``), so these drive a recording session instead of a
database: the assertions are on the bindings sent, the clauses built, and the
records mapped back out of the rows. That keeps them unit tests — input in,
output asserted — rather than a Postgres integration suite.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from uuid import UUID

import pytest

from repository.urban_internvetion_repository import (
    InvalidGeometryError,
    InvalidParametersError,
    UrbanInterventionRecord,
    UrbanInterventionRepository,
)

POLYGON = {"kind": "polygon", "ring": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]}
TREE_PARAMS = {"coverPct": 0.4, "lai": 3.0, "irrigation": 0.8}

CREATE_BODY = {
    "market_code": "houston",
    "name": "Shade trees on Main",
    "color": "#22c55e",
    "archetype_code": "vegetation",
    "intervention_type": "street_tree",
    "geometry": POLYGON,
    "parameters": TREE_PARAMS,
}


# --------------------------------------------------------------------------- #
# Recording session
# --------------------------------------------------------------------------- #


class _Executed:
    def __init__(self, sql: str, bindings: dict):
        self.sql = " ".join(sql.split())  # collapse the triple-quoted layout
        self.bindings = bindings


class _FakeResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def one(self):
        if len(self._rows) != 1:
            raise AssertionError(f"expected exactly one row, got {len(self._rows)}")
        return self._rows[0]


class _FakeSession:
    """Captures the statement and bindings, replays canned rows."""

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.executed: list[_Executed] = []
        self.flushes = 0
        self.commits = 0

    def execute(self, statement, bindings=None):
        self.executed.append(_Executed(str(statement), dict(bindings or {})))
        return _FakeResult(self.rows)

    def flush(self):
        self.flushes += 1

    def commit(self):
        self.commits += 1

    @property
    def only(self) -> _Executed:
        assert len(self.executed) == 1, f"expected 1 statement, got {len(self.executed)}"
        return self.executed[0]


def db_row(**overrides):
    """One row shaped like the shared ``_COLUMNS`` projection."""
    row = {
        "id": UUID("00000000-0000-0000-0000-000000000001"),
        "market_code": "houston",
        "name": "Shade trees on Main",
        "color": "#22c55e",
        "archetype_code": "vegetation",
        "intervention_type": "street_tree",
        "geometry_kind": "polygon",
        "geometry_geojson": '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}',
        "parameters": json.dumps(TREE_PARAMS),
        "status": "active",
        "active_from": datetime(2026, 8, 1),
        "active_to": None,
    }
    row.update(overrides)
    return row


# --------------------------------------------------------------------------- #
# _to_record — rows into the dataclass the router serializes
# --------------------------------------------------------------------------- #


class TestToRecord:
    def test_every_column_lands_on_the_record(self):
        record = UrbanInterventionRepository._to_record(db_row())

        assert isinstance(record, UrbanInterventionRecord)
        assert record.id == UUID("00000000-0000-0000-0000-000000000001")
        assert record.market_code == "houston"
        assert record.name == "Shade trees on Main"
        assert record.color == "#22c55e"
        assert record.archetype_code == "vegetation"
        assert record.intervention_type == "street_tree"
        assert record.geometry_kind == "polygon"
        assert record.status == "active"
        assert record.active_from == datetime(2026, 8, 1)
        assert record.active_to is None

    def test_the_geojson_string_is_parsed_into_a_dict(self):
        # ST_AsGeoJSON returns text; the frontend needs an object.
        record = UrbanInterventionRepository._to_record(db_row())

        assert record.geometry == {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        }

    def test_a_geometry_already_decoded_is_left_alone(self):
        geometry = {"type": "Point", "coordinates": [-95.4, 29.7]}

        record = UrbanInterventionRepository._to_record(
            db_row(geometry_geojson=geometry)
        )

        assert record.geometry == geometry

    def test_the_parameters_string_is_parsed_into_a_dict(self):
        record = UrbanInterventionRepository._to_record(db_row())

        assert record.parameters == TREE_PARAMS
        assert record.parameters["lai"] == 3.0

    def test_parameters_already_decoded_are_left_alone(self):
        # psycopg2 hands jsonb back as a dict, not a string.
        record = UrbanInterventionRepository._to_record(
            db_row(parameters={"opacity": 0.9})
        )

        assert record.parameters == {"opacity": 0.9}

    def test_the_record_is_immutable(self):
        record = UrbanInterventionRepository._to_record(db_row())

        with pytest.raises(Exception):
            record.name = "changed"


# --------------------------------------------------------------------------- #
# get_many_by_city_and_date
# --------------------------------------------------------------------------- #


class TestGetManyByCityAndDate:
    def test_matching_rows_come_back_as_records(self):
        session = _FakeSession([db_row(name="A"), db_row(name="B")])

        records = UrbanInterventionRepository(session).get_many_by_city_and_date(
            city="houston", as_of=date(2026, 8, 16)
        )

        assert [record.name for record in records] == ["A", "B"]

    def test_no_matches_is_an_empty_list_not_an_error(self):
        session = _FakeSession([])

        records = UrbanInterventionRepository(session).get_many_by_city_and_date(
            city="houston", as_of=date(2026, 8, 16)
        )

        assert records == []

    def test_the_city_and_date_are_bound_as_parameters(self):
        session = _FakeSession([])

        UrbanInterventionRepository(session).get_many_by_city_and_date(
            city="houston", as_of=date(2026, 8, 16)
        )

        assert session.only.bindings == {
            "city": "houston",
            "as_of": date(2026, 8, 16),
        }

    def test_the_city_is_matched_against_market_code(self):
        session = _FakeSession([])

        UrbanInterventionRepository(session).get_many_by_city_and_date(
            city="houston", as_of=date(2026, 8, 16)
        )

        assert "WHERE market_code = :city" in session.only.sql

    def test_null_activity_bounds_are_treated_as_open_ended(self):
        session = _FakeSession([])

        UrbanInterventionRepository(session).get_many_by_city_and_date(
            city="houston", as_of=date(2026, 8, 16)
        )

        sql = session.only.sql
        assert "(active_from IS NULL OR active_from <= :as_of)" in sql
        assert "(active_to IS NULL OR active_to >= :as_of)" in sql

    def test_results_are_ordered_by_name_then_id(self):
        session = _FakeSession([])

        UrbanInterventionRepository(session).get_many_by_city_and_date(
            city="houston", as_of=date(2026, 8, 16)
        )

        assert "ORDER BY name, id" in session.only.sql

    def test_omitting_statuses_leaves_the_filter_out_entirely(self):
        session = _FakeSession([])

        UrbanInterventionRepository(session).get_many_by_city_and_date(
            city="houston", as_of=date(2026, 8, 16)
        )

        assert "status = ANY" not in session.only.sql
        assert "statuses" not in session.only.bindings

    def test_a_status_whitelist_is_bound_as_a_list(self):
        session = _FakeSession([])

        UrbanInterventionRepository(session).get_many_by_city_and_date(
            city="houston",
            as_of=date(2026, 8, 16),
            statuses=("active", "planned"),
        )

        assert "AND status = ANY(:statuses)" in session.only.sql
        assert session.only.bindings["statuses"] == ["active", "planned"]

    def test_an_empty_status_whitelist_short_circuits_without_querying(self):
        # Nothing can match "no allowed statuses", so the round trip is skipped.
        session = _FakeSession([db_row()])

        records = UrbanInterventionRepository(session).get_many_by_city_and_date(
            city="houston", as_of=date(2026, 8, 16), statuses=[]
        )

        assert records == []
        assert session.executed == []

    def test_a_datetime_is_accepted_as_well_as_a_date(self):
        session = _FakeSession([])
        as_of = datetime(2026, 8, 16, 14, 30)

        UrbanInterventionRepository(session).get_many_by_city_and_date(
            city="houston", as_of=as_of
        )

        assert session.only.bindings["as_of"] == as_of

    def test_the_camel_case_alias_is_the_same_method(self):
        assert (
            UrbanInterventionRepository.getManyByCityAndDate
            is UrbanInterventionRepository.get_many_by_city_and_date
        )


# --------------------------------------------------------------------------- #
# get_all_by_city_between_date
# --------------------------------------------------------------------------- #


class TestGetAllByCityBetweenDate:
    def test_matching_rows_come_back_as_records(self):
        session = _FakeSession([db_row(name="A")])

        records = UrbanInterventionRepository(session).get_all_by_city_between_date(
            city="houston", from_date=date(2026, 8, 1), to_date=date(2026, 8, 31)
        )

        assert [record.name for record in records] == ["A"]

    def test_the_range_is_bound_as_parameters(self):
        session = _FakeSession([])

        UrbanInterventionRepository(session).get_all_by_city_between_date(
            city="houston", from_date=date(2026, 8, 1), to_date=date(2026, 8, 31)
        )

        assert session.only.bindings == {
            "city": "houston",
            "from_date": date(2026, 8, 1),
            "to_date": date(2026, 8, 31),
        }

    def test_the_window_test_is_an_overlap_not_a_containment(self):
        # active_from <= to_date AND active_to >= from_date is the overlap
        # form: an object that started before the range and is still running
        # has to match.
        session = _FakeSession([])

        UrbanInterventionRepository(session).get_all_by_city_between_date(
            city="houston", from_date=date(2026, 8, 1), to_date=date(2026, 8, 31)
        )

        sql = session.only.sql
        assert "(active_from IS NULL OR active_from <= :to_date)" in sql
        assert "(active_to IS NULL OR active_to >= :from_date)" in sql

    def test_an_inverted_range_is_rejected(self):
        session = _FakeSession([])

        with pytest.raises(ValueError, match="must not be after to_date"):
            UrbanInterventionRepository(session).get_all_by_city_between_date(
                city="houston", from_date=date(2026, 8, 31), to_date=date(2026, 8, 1)
            )

    def test_an_inverted_range_is_rejected_before_any_query_runs(self):
        session = _FakeSession([])

        with pytest.raises(ValueError):
            UrbanInterventionRepository(session).get_all_by_city_between_date(
                city="houston", from_date=date(2026, 8, 31), to_date=date(2026, 8, 1)
            )

        assert session.executed == []

    def test_a_single_day_range_is_allowed(self):
        session = _FakeSession([])
        day = date(2026, 8, 16)

        UrbanInterventionRepository(session).get_all_by_city_between_date(
            city="houston", from_date=day, to_date=day
        )

        assert session.only.bindings["from_date"] == day
        assert session.only.bindings["to_date"] == day

    def test_an_empty_status_whitelist_short_circuits_without_querying(self):
        session = _FakeSession([db_row()])

        records = UrbanInterventionRepository(session).get_all_by_city_between_date(
            city="houston",
            from_date=date(2026, 8, 1),
            to_date=date(2026, 8, 31),
            statuses=[],
        )

        assert records == []
        assert session.executed == []

    def test_a_status_whitelist_is_bound_as_a_list(self):
        session = _FakeSession([])

        UrbanInterventionRepository(session).get_all_by_city_between_date(
            city="houston",
            from_date=date(2026, 8, 1),
            to_date=date(2026, 8, 31),
            statuses=["retired"],
        )

        assert "AND status = ANY(:statuses)" in session.only.sql
        assert session.only.bindings["statuses"] == ["retired"]

    def test_the_camel_case_alias_is_the_same_method(self):
        assert (
            UrbanInterventionRepository.getAllByCityBetweenDate
            is UrbanInterventionRepository.get_all_by_city_between_date
        )


# --------------------------------------------------------------------------- #
# create
# --------------------------------------------------------------------------- #


class TestCreate:
    def test_the_inserted_row_comes_back_as_a_record(self):
        session = _FakeSession([db_row()])

        record = UrbanInterventionRepository(session).create(dict(CREATE_BODY))

        assert record.name == "Shade trees on Main"
        assert record.market_code == "houston"
        assert record.parameters == TREE_PARAMS

    def test_the_scalar_columns_are_bound_from_the_body(self):
        session = _FakeSession([db_row()])

        UrbanInterventionRepository(session).create(dict(CREATE_BODY))

        bindings = session.only.bindings
        assert bindings["market_code"] == "houston"
        assert bindings["name"] == "Shade trees on Main"
        assert bindings["color"] == "#22c55e"
        assert bindings["archetype_code"] == "vegetation"
        assert bindings["intervention_type"] == "street_tree"

    def test_the_geometry_is_bound_as_wkt_with_its_kind(self):
        session = _FakeSession([db_row()])

        UrbanInterventionRepository(session).create(dict(CREATE_BODY))

        bindings = session.only.bindings
        assert bindings["geometry_kind"] == "polygon"
        assert bindings["geometry_wkt"] == "POLYGON((0.0 0.0, 1.0 0.0, 1.0 1.0, 0.0 0.0))"

    def test_the_geometry_is_built_with_the_srid(self):
        session = _FakeSession([db_row()])

        UrbanInterventionRepository(session).create(dict(CREATE_BODY))

        assert "ST_GeomFromText(:geometry_wkt, 4326)" in session.only.sql

    def test_the_geometry_kind_is_derived_not_taken_from_the_caller(self):
        session = _FakeSession([db_row()])
        body = {
            **CREATE_BODY,
            "intervention_type": "misting_station",
            "parameters": {
                "evapRateLpm": 1.0,
                "coverageRadiusM": 8.0,
                "activeFraction": 0.5,
            },
            "geometry": {"kind": "point", "longitude": -95.4, "latitude": 29.7},
        }

        UrbanInterventionRepository(session).create(body)

        assert session.only.bindings["geometry_kind"] == "point"
        assert session.only.bindings["geometry_wkt"] == "POINT(-95.4 29.7)"

    def test_the_parameters_are_bound_as_a_json_string(self):
        session = _FakeSession([db_row()])

        UrbanInterventionRepository(session).create(dict(CREATE_BODY))

        assert json.loads(session.only.bindings["parameters"]) == TREE_PARAMS
        assert "CAST(:parameters AS jsonb)" in session.only.sql

    def test_omitted_optional_columns_are_left_to_the_database(self):
        # Sending status/active_from/active_to as NULL would override the
        # column defaults, so they must not appear at all.
        session = _FakeSession([db_row()])

        UrbanInterventionRepository(session).create(dict(CREATE_BODY))

        bindings = session.only.bindings
        assert "status" not in bindings
        assert "active_from" not in bindings
        assert "active_to" not in bindings
        assert "status" not in session.only.sql.split("VALUES")[0]

    def test_supplied_optional_columns_are_included(self):
        session = _FakeSession([db_row()])
        body = {
            **CREATE_BODY,
            "status": "planned",
            "active_from": datetime(2026, 8, 1),
            "active_to": datetime(2026, 9, 1),
        }

        UrbanInterventionRepository(session).create(body)

        bindings = session.only.bindings
        assert bindings["status"] == "planned"
        assert bindings["active_from"] == datetime(2026, 8, 1)
        assert bindings["active_to"] == datetime(2026, 9, 1)

    def test_an_explicit_null_active_to_is_still_sent(self):
        # `in data` is the test, not truthiness, so an explicit None means
        # "open-ended" rather than "unset".
        session = _FakeSession([db_row()])

        UrbanInterventionRepository(session).create({**CREATE_BODY, "active_to": None})

        assert "active_to" in session.only.bindings
        assert session.only.bindings["active_to"] is None

    def test_the_insert_returns_the_full_projection(self):
        session = _FakeSession([db_row()])

        UrbanInterventionRepository(session).create(dict(CREATE_BODY))

        sql = session.only.sql
        assert "RETURNING" in sql
        assert "ST_AsGeoJSON(geometry) AS geometry_geojson" in sql

    def test_create_flushes_but_does_not_commit(self):
        # Transaction boundaries belong to the caller; the router commits.
        session = _FakeSession([db_row()])

        UrbanInterventionRepository(session).create(dict(CREATE_BODY))

        assert session.flushes == 1
        assert session.commits == 0


class TestCreateValidation:
    def test_bad_parameters_are_rejected_before_the_insert(self):
        session = _FakeSession([db_row()])

        with pytest.raises(InvalidParametersError, match="missing required parameter"):
            UrbanInterventionRepository(session).create(
                {**CREATE_BODY, "parameters": {"coverPct": 0.4}}
            )

        assert session.executed == []

    def test_an_unrecognized_parameter_is_rejected(self):
        session = _FakeSession([db_row()])

        with pytest.raises(InvalidParametersError, match="unrecognized parameter"):
            UrbanInterventionRepository(session).create(
                {**CREATE_BODY, "parameters": {**TREE_PARAMS, "albedo": 0.9}}
            )

    def test_an_out_of_range_parameter_is_rejected(self):
        session = _FakeSession([db_row()])

        with pytest.raises(InvalidParametersError, match="outside"):
            UrbanInterventionRepository(session).create(
                {**CREATE_BODY, "parameters": {**TREE_PARAMS, "coverPct": 5.0}}
            )

    def test_several_parameter_problems_are_joined_into_one_message(self):
        session = _FakeSession([db_row()])

        with pytest.raises(InvalidParametersError) as excinfo:
            UrbanInterventionRepository(session).create(
                {**CREATE_BODY, "parameters": {}}
            )

        assert str(excinfo.value).count(";") == 2

    def test_an_unusable_geometry_is_rejected_before_the_insert(self):
        session = _FakeSession([db_row()])

        with pytest.raises(InvalidGeometryError, match="at least 3 distinct"):
            UrbanInterventionRepository(session).create(
                {**CREATE_BODY, "geometry": {"kind": "polygon", "ring": []}}
            )

        assert session.executed == []

    def test_an_out_of_range_coordinate_is_rejected(self):
        session = _FakeSession([db_row()])

        with pytest.raises(InvalidGeometryError, match="Longitude out of range"):
            UrbanInterventionRepository(session).create(
                {
                    **CREATE_BODY,
                    "geometry": {
                        "kind": "polygon",
                        "ring": [(0.0, 0.0), (1.0, 0.0), (999.0, 1.0)],
                    },
                }
            )

    def test_parameters_are_checked_before_the_geometry(self):
        # Both are invalid; the parameter error is the one that surfaces.
        session = _FakeSession([db_row()])

        with pytest.raises(InvalidParametersError):
            UrbanInterventionRepository(session).create(
                {
                    **CREATE_BODY,
                    "parameters": {},
                    "geometry": {"kind": "polygon", "ring": []},
                }
            )

    def test_a_tree_saved_as_a_point_is_stored_despite_cooling_nothing(self):
        """No geometry-kind check runs on write.

        ``ALLOWED_GEOMETRY_KINDS`` says vegetation only reaches a reading as a
        polygon, and ``validate_geometry`` exists to enforce exactly that — but
        ``create`` never calls it. So this insert succeeds and the object is
        skipped later by the simulation, silently, which is the failure mode
        the parameter validation was added to prevent.
        """
        session = _FakeSession([db_row(geometry_kind="point")])

        record = UrbanInterventionRepository(session).create(
            {
                **CREATE_BODY,
                "geometry": {"kind": "point", "longitude": -95.4, "latitude": 29.7},
            }
        )

        assert session.only.bindings["geometry_kind"] == "point"
        assert record is not None

    def test_both_error_types_are_value_errors(self):
        assert issubclass(InvalidParametersError, ValueError)
        assert issubclass(InvalidGeometryError, ValueError)


def test_the_session_is_exposed_but_never_closed_by_the_repository():
    session = _FakeSession([])

    repository = UrbanInterventionRepository(session)

    assert repository.session is session
    assert not hasattr(session, "closed")
