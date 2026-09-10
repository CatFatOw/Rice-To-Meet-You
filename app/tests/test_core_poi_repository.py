"""``CorePoiGeometryRepository`` — reads and writes behind the core_poi routes.

The frontend reaches two methods here: ``getAll`` (GET /core_poi/get-all-pois)
and ``create`` (POST /core_poi/create-poi). ``getAllByMarketCode`` and
``getByPlacekey`` back routes the frontend never calls, so they are left alone.

These run against SQLite. The repository has an explicit non-Postgres branch
that stores geometry as WKT text instead of calling ST_* functions, so the
paths under test are the ones that actually run — no PostGIS stub required.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, Text, text

from repository.core_poi_geometry_respository import CorePoiGeometryRepository


# --------------------------------------------------------------------------- #
# getAll — the cached read with its average-UHI aggregate
# --------------------------------------------------------------------------- #


def test_get_all_returns_every_row_ordered_by_id(poi_repo, insert_pois):
    insert_pois(
        pois=[
            {"id": 3, "location_name": "Third"},
            {"id": 1, "location_name": "First"},
            {"id": 2, "location_name": "Second"},
        ]
    )

    rows = poi_repo.getAll()

    assert [row["id"] for row in rows] == [1, 2, 3]
    assert [row["location_name"] for row in rows] == ["First", "Second", "Third"]


def test_get_all_returns_an_empty_list_when_the_table_is_empty(poi_repo):
    assert poi_repo.getAll() == []


def test_every_row_carries_its_own_columns(poi_repo, insert_pois):
    insert_pois(
        pois=[
            {
                "id": 1,
                "location_name": "Rice University",
                "market_code": "houston",
                "city": "Houston",
                "region": "TX",
                "latitude": 29.7174,
                "longitude": -95.4018,
                "color": "#22c55e",
            }
        ]
    )

    row = poi_repo.getAll()[0]

    assert row["location_name"] == "Rice University"
    assert row["market_code"] == "houston"
    assert row["city"] == "Houston"
    assert row["region"] == "TX"
    assert row["latitude"] == 29.7174
    assert row["longitude"] == -95.4018
    assert row["color"] == "#22c55e"


def test_average_uhi_is_the_mean_of_the_mapped_readings(poi_repo, insert_pois):
    insert_pois(
        pois=[{"id": 1, "placekey": "222-223-224"}],
        readings=[{"id": 10, "uhi": 2.0}, {"id": 11, "uhi": 4.0}],
        mappings=[
            {"id": 1, "core_poi_id": 1, "urban_heat_index_id": 10},
            {"id": 2, "core_poi_id": 1, "urban_heat_index_id": 11},
        ],
    )

    row = poi_repo.getAll()[0]

    assert row["average_uhi"] == 3.0
    assert row["matched_uhi_count"] == 2


def test_pois_sharing_a_placekey_share_the_aggregate(poi_repo, insert_pois):
    # The CTE groups by placekey, not by POI id, so both rows report the same
    # average even though only one of them is mapped to a reading.
    insert_pois(
        pois=[
            {"id": 1, "placekey": "222-223-224", "location_name": "Terminal A"},
            {"id": 2, "placekey": "222-223-224", "location_name": "Terminal B"},
        ],
        readings=[{"id": 10, "uhi": 5.0}],
        mappings=[{"id": 1, "core_poi_id": 1, "urban_heat_index_id": 10}],
    )

    first, second = poi_repo.getAll()

    assert first["average_uhi"] == second["average_uhi"] == 5.0
    assert first["matched_uhi_count"] == second["matched_uhi_count"] == 1


def test_a_poi_with_no_readings_reports_none_and_zero(poi_repo, insert_pois):
    insert_pois(pois=[{"id": 1, "placekey": "222-223-224"}])

    row = poi_repo.getAll()[0]

    assert row["average_uhi"] is None
    assert row["matched_uhi_count"] == 0


def test_a_poi_with_a_null_placekey_reports_none_and_zero(poi_repo, insert_pois):
    # The CTE filters `placekey IS NOT NULL`, so these rows never join.
    insert_pois(pois=[{"id": 1, "placekey": None}])

    row = poi_repo.getAll()[0]

    assert row["average_uhi"] is None
    assert row["matched_uhi_count"] == 0


def test_the_aggregate_keys_are_always_present(poi_repo, insert_pois):
    insert_pois(pois=[{"id": 1}])

    row = poi_repo.getAll()[0]

    assert "average_uhi" in row
    assert "matched_uhi_count" in row


# --------------------------------------------------------------------------- #
# getAll — limit / offset windowing
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("limit", "offset", "expected"),
    [
        (None, None, [1, 2, 3, 4]),
        (2, None, [1, 2]),
        (None, 2, [3, 4]),
        (2, 1, [2, 3]),
        (10, None, [1, 2, 3, 4]),
        (None, 10, []),
        (0, None, []),
        (2, 3, [4]),
    ],
)
def test_limit_and_offset_window_the_result(
    poi_repo, insert_pois, limit, offset, expected
):
    insert_pois(pois=[{"id": index} for index in (1, 2, 3, 4)])

    rows = poi_repo.getAll(limit=limit, offset=offset)

    assert [row["id"] for row in rows] == expected


def test_returned_rows_are_copies_that_cannot_corrupt_the_cache(poi_repo, insert_pois):
    insert_pois(pois=[{"id": 1, "location_name": "Original"}])

    poi_repo.getAll()[0]["location_name"] = "Mutated"

    assert poi_repo.getAll()[0]["location_name"] == "Original"


# --------------------------------------------------------------------------- #
# create — the insert behind POST /core_poi/create-poi
# --------------------------------------------------------------------------- #


def test_create_returns_the_inserted_row(poi_repo):
    created = poi_repo.create(
        {"location_name": "Klyde Warren Park", "market_code": "dallas", "city": "Dallas"}
    )

    assert created["location_name"] == "Klyde Warren Park"
    assert created["market_code"] == "dallas"
    assert created["city"] == "Dallas"
    assert created["id"] is not None


def test_create_stamps_the_aggregate_keys_on_the_new_row(poi_repo):
    # A brand-new POI has no mapping rows, so it reads as unmeasured rather
    # than as an average of nothing.
    created = poi_repo.create({"location_name": "New Park"})

    assert created["average_uhi"] is None
    assert created["matched_uhi_count"] == 0


def test_create_accepts_keyword_arguments(poi_repo):
    created = poi_repo.create(location_name="Discovery Green", city="Houston")

    assert created["location_name"] == "Discovery Green"
    assert created["city"] == "Houston"


def test_keyword_arguments_win_over_the_mapping(poi_repo):
    created = poi_repo.create({"location_name": "From mapping"}, location_name="From kwargs")

    assert created["location_name"] == "From kwargs"


def test_create_with_no_values_is_rejected(poi_repo):
    with pytest.raises(ValueError, match="at least one column value"):
        poi_repo.create({})


def test_the_new_row_is_visible_to_the_next_read(poi_repo, insert_pois):
    insert_pois(pois=[{"id": 1, "location_name": "Existing"}])
    poi_repo.getAll()  # warm the cache before the write

    poi_repo.create({"location_name": "Added"})

    assert [row["location_name"] for row in poi_repo.getAll()] == ["Existing", "Added"]


def test_the_new_row_is_inserted_in_id_order(poi_repo, insert_pois):
    insert_pois(pois=[{"id": 5, "location_name": "Fifth"}])
    poi_repo.getAll()

    poi_repo.create({"id": 2, "location_name": "Second"})

    assert [row["id"] for row in poi_repo.getAll()] == [2, 5]


def test_create_persists_to_the_database_not_just_the_cache(poi_repo, poi_session):
    poi_repo.create({"location_name": "Persisted"})
    poi_session.commit()

    names = poi_session.execute(
        text("SELECT location_name FROM core_poi_geometry")
    ).scalars().all()
    assert names == ["Persisted"]


# --------------------------------------------------------------------------- #
# create — geometry handling
# --------------------------------------------------------------------------- #


def test_polygon_wkt_is_written_to_the_geometry_column_as_text(poi_repo):
    wkt = "POLYGON((-96.80 32.78, -96.70 32.78, -96.70 32.88, -96.80 32.78))"

    created = poi_repo.create({"location_name": "Park", "polygon_wkt": wkt})

    # Non-Postgres branch: stored verbatim rather than wrapped in ST_Multi.
    assert created["polygon_geom"] == wkt
    assert created["polygon_wkt"] == wkt


def test_coordinates_alone_do_not_populate_a_polygon_geometry_column(poi_repo):
    # _build_values only derives a point when the geometry column is not a
    # polygon column, and this table's is `polygon_geom`.
    created = poi_repo.create(
        {"location_name": "Park", "longitude": -96.80, "latitude": 32.78}
    )

    assert created["polygon_geom"] is None
    assert created["longitude"] == -96.80
    assert created["latitude"] == 32.78


def test_an_explicit_geometry_value_is_left_alone(poi_repo):
    created = poi_repo.create(
        {
            "location_name": "Park",
            "polygon_geom": "POLYGON((0 0, 1 0, 1 1, 0 0))",
            "polygon_wkt": "POLYGON((9 9, 8 9, 8 8, 9 9))",
        }
    )

    assert created["polygon_geom"] == "POLYGON((0 0, 1 0, 1 1, 0 0))"


@pytest.mark.parametrize("alias", ["lon", "lng", "long", "x"])
def test_longitude_aliases_land_in_the_longitude_column(poi_repo, alias):
    created = poi_repo.create({"location_name": "Park", alias: -96.80, "latitude": 32.78})

    assert created["longitude"] == -96.80


@pytest.mark.parametrize("alias", ["lat", "y"])
def test_latitude_aliases_land_in_the_latitude_column(poi_repo, alias):
    created = poi_repo.create({"location_name": "Park", "longitude": -96.80, alias: 32.78})

    assert created["latitude"] == 32.78


# --------------------------------------------------------------------------- #
# create — validation
# --------------------------------------------------------------------------- #


def test_unknown_columns_are_rejected_in_strict_mode(poi_repo):
    with pytest.raises(ValueError) as excinfo:
        poi_repo.create({"location_name": "Park", "not_a_column": 1})

    assert "Unknown column(s)" in str(excinfo.value)
    assert "not_a_column" in str(excinfo.value)


def test_unknown_columns_are_dropped_when_strict_is_off(poi_repo):
    created = poi_repo.create({"location_name": "Park", "not_a_column": 1}, strict=False)

    assert created["location_name"] == "Park"
    assert "not_a_column" not in created


def test_missing_required_columns_are_reported(poi_repo):
    # location_name is NOT NULL with no default.
    with pytest.raises(ValueError) as excinfo:
        poi_repo.create({"city": "Dallas"})

    assert "Missing required column(s)" in str(excinfo.value)
    assert "location_name" in str(excinfo.value)


def test_protected_columns_are_stripped_rather_than_rejected(poi_repo):
    # created_at is a real column, so this is not an "unknown column" error;
    # it is silently dropped so the database keeps ownership of the value.
    created = poi_repo.create({"location_name": "Park", "created_at": "1999-01-01"})

    assert created["created_at"] is None


def test_market_code_is_backfilled_from_market(poi_repo):
    created = poi_repo.create({"location_name": "Park", "market": "houston"})

    assert created["market"] == "houston"
    assert created["market_code"] == "houston"


def test_market_is_backfilled_from_market_code(poi_repo):
    created = poi_repo.create({"location_name": "Park", "market_code": "dallas"})

    assert created["market"] == "dallas"
    assert created["market_code"] == "dallas"


def test_market_and_market_code_are_not_reconciled_when_both_are_given(poi_repo):
    created = poi_repo.create(
        {"location_name": "Park", "market": "houston", "market_code": "dallas"}
    )

    assert created["market"] == "houston"
    assert created["market_code"] == "dallas"


def test_derived_aggregate_keys_in_the_payload_are_dropped(poi_repo):
    # average_uhi comes from the join, not the table, so a caller supplying it
    # must not trip the unknown-column check.
    created = poi_repo.create(
        {"location_name": "Park", "average_uhi": 9.9, "matched_uhi_count": 7}
    )

    assert created["average_uhi"] is None
    assert created["matched_uhi_count"] == 0


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


class TestValidateCoordinates:
    def test_numeric_strings_are_coerced_to_floats(self):
        assert CorePoiGeometryRepository._validate_coordinates("-96.8", "32.78") == (
            -96.8,
            32.78,
        )

    @pytest.mark.parametrize(
        ("longitude", "latitude"), [(-180.0, -90.0), (180.0, 90.0), (0, 0)]
    )
    def test_bounds_are_inclusive(self, longitude, latitude):
        assert CorePoiGeometryRepository._validate_coordinates(longitude, latitude) == (
            float(longitude),
            float(latitude),
        )

    def test_longitude_out_of_range_is_rejected(self):
        with pytest.raises(ValueError, match=r"Longitude 180.5 is outside"):
            CorePoiGeometryRepository._validate_coordinates(180.5, 0)

    def test_latitude_out_of_range_hints_at_a_swap(self):
        with pytest.raises(ValueError, match="swapped"):
            CorePoiGeometryRepository._validate_coordinates(0, 95.0)

    @pytest.mark.parametrize("value", ["north", None, object()])
    def test_non_numeric_values_are_rejected(self, value):
        with pytest.raises(ValueError, match="must be numeric"):
            CorePoiGeometryRepository._validate_coordinates(value, 0)


class TestWindow:
    ROWS = [{"id": 1}, {"id": 2}, {"id": 3}]

    @pytest.mark.parametrize(
        ("limit", "offset", "expected"),
        [
            (None, None, [1, 2, 3]),
            (None, 0, [1, 2, 3]),
            (2, 0, [1, 2]),
            (1, 2, [3]),
            (5, 1, [2, 3]),
            (0, 0, []),
            (None, 5, []),
        ],
    )
    def test_windowing(self, limit, offset, expected):
        window = CorePoiGeometryRepository._window(
            self.ROWS, limit=limit, offset=offset
        )

        assert [row["id"] for row in window] == expected

    def test_rows_are_copied_not_aliased(self):
        source = [{"id": 1}]

        window = CorePoiGeometryRepository._window(source, limit=None, offset=None)
        window[0]["id"] = 99

        assert source[0]["id"] == 1


class TestNormalizeRow:
    def test_a_decimal_average_becomes_a_float(self):
        row = CorePoiGeometryRepository._normalize_row(
            {"id": 1, "average_uhi": Decimal("3.5"), "matched_uhi_count": 2}
        )

        assert row["average_uhi"] == 3.5
        assert isinstance(row["average_uhi"], float)

    def test_a_missing_aggregate_is_filled_in(self):
        row = CorePoiGeometryRepository._normalize_row({"id": 1})

        assert row["average_uhi"] is None
        assert row["matched_uhi_count"] == 0

    def test_a_null_count_becomes_zero(self):
        row = CorePoiGeometryRepository._normalize_row({"matched_uhi_count": None})

        assert row["matched_uhi_count"] == 0

    def test_other_columns_are_carried_through_untouched(self):
        row = CorePoiGeometryRepository._normalize_row({"id": 7, "city": "Houston"})

        assert row["id"] == 7
        assert row["city"] == "Houston"


class TestAsFloat:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(Decimal("2.5"), 2.5), (3, 3.0), ("4.5", 4.5), (None, None)],
    )
    def test_coercion(self, value, expected):
        assert CorePoiGeometryRepository._as_float(value) == expected

    def test_an_uncoercible_value_becomes_none(self):
        assert CorePoiGeometryRepository._as_float("not a number") is None


class TestOrderable:
    def test_null_sorts_after_a_value(self):
        assert CorePoiGeometryRepository._orderable(None) > (
            CorePoiGeometryRepository._orderable("")
        )

    def test_values_keep_their_natural_order(self):
        keys = [CorePoiGeometryRepository._orderable(v) for v in (3, 1, 2)]

        assert sorted(keys) == [(0, 1), (0, 2), (0, 3)]


class TestMergePayload:
    def test_keywords_override_the_mapping(self):
        merged = CorePoiGeometryRepository._merge_payload({"a": 1, "b": 2}, {"b": 3})

        assert merged == {"a": 1, "b": 3}

    def test_a_none_mapping_is_treated_as_empty(self):
        assert CorePoiGeometryRepository._merge_payload(None, {"a": 1}) == {"a": 1}

    def test_the_source_mapping_is_not_mutated(self):
        source = {"a": 1}

        CorePoiGeometryRepository._merge_payload(source, {"b": 2})

        assert source == {"a": 1}

    def test_an_empty_result_is_rejected(self):
        with pytest.raises(ValueError, match="at least one column value"):
            CorePoiGeometryRepository._merge_payload(None, {})


class TestRequireColumn:
    def _table(self):
        return Table(
            "sample", MetaData(), Column("id", Integer), Column("name", Text)
        )

    def test_an_existing_column_is_returned(self):
        column = CorePoiGeometryRepository._require_column(self._table(), "name")

        assert column.name == "name"

    def test_a_missing_column_reports_the_valid_names(self):
        with pytest.raises(ValueError) as excinfo:
            CorePoiGeometryRepository._require_column(self._table(), "nope")

        message = str(excinfo.value)
        assert "has no 'nope' column" in message
        assert "'id'" in message and "'name'" in message
