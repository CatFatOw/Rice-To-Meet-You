"""``queryVisitorRowsWithGeometryByCityDate`` — the one visitor read that queries.

Behind ``GET /final_visitor/query-visitor-rows-with-geometry-by-city-date``,
which the statistics panel calls for both the POI table and the top-destination
list. Unlike its cached sibling it goes to the database every time, so these run
against a SQLite mirror of ``final_visitor_table``: the filter, the ordering and
the limit are all plain SQL that SQLite evaluates the same way.
"""

from __future__ import annotations

from datetime import date

import pytest

from repository.final_visitor_repository import VisitorRepository

from conftest import TEST_DATE

OTHER_DATE = date(2026, 8, 17)


@pytest.fixture
def repo(visitor_db_session):
    return VisitorRepository(visitor_db_session)


@pytest.fixture
def rows(insert_visitor_rows):
    """Four Houston rows: three linked to a POI, one not."""
    insert_visitor_rows(
        {
            "id": 1,
            "location_name": "Chipotle Midtown",
            "heat_risk_score": 50.0,
            "avg_daily_visits": 100.0,
            "core_poi_geometry_id": 7,
        },
        {
            "id": 2,
            "location_name": "Panera Rice Village",
            "heat_risk_score": None,
            "avg_daily_visits": 50.0,
            "core_poi_geometry_id": 8,
        },
        {
            "id": 3,
            "location_name": "Unlinked Cafe",
            "heat_risk_score": 99.0,
            "avg_daily_visits": 25.0,
            "core_poi_geometry_id": None,
        },
        {
            "id": 4,
            "location_name": "Corner Store",
            "heat_risk_score": 70.0,
            "avg_daily_visits": 10.0,
            "core_poi_geometry_id": 9,
        },
    )


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #


def test_only_poi_linked_rows_are_returned(repo, rows):
    # The unlinked row has the highest score, so it would lead the result if
    # the IS NOT NULL filter were missing.
    result = repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE)

    assert sorted(row.id for row in result) == [1, 2, 4]


def test_a_city_with_no_rows_returns_an_empty_list(repo, rows):
    assert repo.queryVisitorRowsWithGeometryByCityDate("atlantis", TEST_DATE) == []


def test_a_date_with_no_rows_returns_an_empty_list(repo, rows):
    assert repo.queryVisitorRowsWithGeometryByCityDate("houston", OTHER_DATE) == []


def test_rows_from_other_dates_are_excluded(repo, insert_visitor_rows):
    insert_visitor_rows(
        {"id": 1, "local_date": TEST_DATE, "core_poi_geometry_id": 7},
        {"id": 2, "local_date": OTHER_DATE, "core_poi_geometry_id": 8},
    )

    result = repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE)

    assert [row.id for row in result] == [1]


def test_rows_from_other_cities_are_excluded(repo, insert_visitor_rows):
    insert_visitor_rows(
        {"id": 1, "city": "houston", "core_poi_geometry_id": 7},
        {"id": 2, "city": "dallas", "core_poi_geometry_id": 8},
    )

    result = repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE)

    assert [row.id for row in result] == [1]


@pytest.mark.parametrize("supplied", ["Houston", "HOUSTON", "  houston  ", "hOuStOn"])
def test_the_city_argument_is_matched_case_and_space_insensitively(
    repo, insert_visitor_rows, supplied
):
    insert_visitor_rows({"id": 1, "city": "houston", "core_poi_geometry_id": 7})

    assert len(repo.queryVisitorRowsWithGeometryByCityDate(supplied, TEST_DATE)) == 1


@pytest.mark.parametrize("stored", [" Houston ", "HOUSTON", "houston"])
def test_the_stored_city_is_normalized_too(repo, insert_visitor_rows, stored):
    # lower(trim(city)) is applied to the column, not just the argument, so
    # untrimmed data still matches.
    insert_visitor_rows({"id": 1, "city": stored, "core_poi_geometry_id": 7})

    assert len(repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE)) == 1


# --------------------------------------------------------------------------- #
# Ordering
# --------------------------------------------------------------------------- #


def test_sorting_puts_the_highest_risk_first(repo, rows):
    result = repo.queryVisitorRowsWithGeometryByCityDate(
        "houston", TEST_DATE, sorted=True
    )

    assert [row.heat_risk_score for row in result] == [70.0, 50.0, None]


def test_unscored_rows_sort_last_not_first(repo, rows):
    # NULLS LAST matters here: paired with a limit, unscored rows would
    # otherwise crowd out the real scores the panel is asking for.
    result = repo.queryVisitorRowsWithGeometryByCityDate(
        "houston", TEST_DATE, sorted=True
    )

    assert result[-1].heat_risk_score is None


def test_ties_break_on_id_so_a_limited_result_is_reproducible(
    repo, insert_visitor_rows
):
    insert_visitor_rows(
        {"id": 5, "heat_risk_score": 80.0, "core_poi_geometry_id": 1},
        {"id": 3, "heat_risk_score": 80.0, "core_poi_geometry_id": 2},
        {"id": 4, "heat_risk_score": 80.0, "core_poi_geometry_id": 3},
    )

    result = repo.queryVisitorRowsWithGeometryByCityDate(
        "houston", TEST_DATE, sorted=True
    )

    assert [row.id for row in result] == [3, 4, 5]


def test_sorting_is_off_by_default(repo, rows):
    # No ORDER BY is emitted, so the ordering is whatever the database returns
    # -- callers wanting risk order have to ask for it.
    result = repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE)

    assert sorted(row.id for row in result) == [1, 2, 4]


# --------------------------------------------------------------------------- #
# Limit
# --------------------------------------------------------------------------- #


def test_a_limit_caps_the_row_count(repo, rows):
    result = repo.queryVisitorRowsWithGeometryByCityDate(
        "houston", TEST_DATE, sorted=True, limit=2
    )

    assert len(result) == 2


def test_the_limit_is_applied_after_the_sort(repo, rows):
    # ORDER BY precedes LIMIT, so this is the top 2 by risk, not the first 2
    # rows the table happens to hold.
    result = repo.queryVisitorRowsWithGeometryByCityDate(
        "houston", TEST_DATE, sorted=True, limit=2
    )

    assert [row.heat_risk_score for row in result] == [70.0, 50.0]


def test_a_limit_larger_than_the_result_returns_everything(repo, rows):
    result = repo.queryVisitorRowsWithGeometryByCityDate(
        "houston", TEST_DATE, limit=100
    )

    assert len(result) == 3


def test_a_zero_limit_returns_nothing(repo, rows):
    assert repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE, limit=0) == []


def test_no_limit_returns_everything(repo, rows):
    result = repo.queryVisitorRowsWithGeometryByCityDate(
        "houston", TEST_DATE, limit=None
    )

    assert len(result) == 3


@pytest.mark.parametrize("limit", [-1, -100])
def test_a_negative_limit_is_rejected(repo, rows, limit):
    with pytest.raises(ValueError, match="limit must be non-negative or None"):
        repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE, limit=limit)


def test_a_negative_limit_is_rejected_before_the_query_runs(repo, rows):
    with pytest.raises(ValueError):
        repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE, limit=-1)


def test_a_limit_works_without_sorting(repo, rows):
    result = repo.queryVisitorRowsWithGeometryByCityDate(
        "houston", TEST_DATE, limit=1
    )

    assert len(result) == 1


# --------------------------------------------------------------------------- #
# Projection
# --------------------------------------------------------------------------- #


def test_a_row_exposes_the_visitor_columns(repo, rows):
    row = repo.queryVisitorRowsWithGeometryByCityDate(
        "houston", TEST_DATE, sorted=True
    )[0]
    mapping = dict(row._mapping)

    assert mapping["id"] == 4
    assert mapping["city"] == "houston"
    assert mapping["local_date"] == TEST_DATE
    assert mapping["location_name"] == "Corner Store"
    assert mapping["heat_risk_score"] == 70.0
    assert mapping["avg_daily_visits"] == 10.0
    assert mapping["latitude"] == 29.7
    assert mapping["longitude"] == -95.4


def test_a_row_exposes_the_scalar_poi_columns(repo, insert_visitor_rows):
    insert_visitor_rows(
        {
            "id": 1,
            "core_poi_geometry_id": 7,
            "core_poi_geometry_placekey": "222-223-224",
            "core_poi_geometry_top_category": "Restaurants",
            "core_poi_geometry_postal_code": "77005",
        }
    )

    mapping = dict(
        repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE)[0]._mapping
    )

    assert mapping["core_poi_geometry_id"] == 7
    assert mapping["core_poi_geometry_placekey"] == "222-223-224"
    assert mapping["core_poi_geometry_top_category"] == "Restaurants"
    assert mapping["core_poi_geometry_postal_code"] == "77005"


def test_the_heavy_columns_are_left_out_of_the_projection(repo, rows):
    # Polygons and the json blobs are fetched separately by id; selecting them
    # per row is what the column list exists to avoid.
    mapping = dict(
        repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE)[0]._mapping
    )

    for column in VisitorRepository.HEAVY_POI_COLUMNS:
        assert column not in mapping


def test_the_projection_matches_the_declared_column_list(repo, rows):
    mapping = dict(
        repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE)[0]._mapping
    )

    assert list(mapping) == list(VisitorRepository._point_columns())


def test_the_router_can_serialize_a_row_as_a_dict(repo, rows):
    # The handler returns [dict(row._mapping) for row in rows]; this is that
    # step, so a projection change that breaks it fails here first.
    result = repo.queryVisitorRowsWithGeometryByCityDate("houston", TEST_DATE)

    payload = [dict(row._mapping) for row in result]

    assert all(isinstance(item, dict) for item in payload)
    assert {"location_name", "heat_risk_score", "street_address"} <= payload[0].keys()
