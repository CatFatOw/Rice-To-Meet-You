"""Row/point plumbing inside ``VisitorRepository``.

Every ``final_visitor`` endpoint the frontend calls is built out of these: rows
become ``VisitorPoint``s at startup, and the read methods project those back out
through ``_render`` / ``_metrics``. Testing them directly pins the coercion
rules — which nulls become ``""``, which are dropped, which stay typed — that
the endpoint tests then take for granted.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from repository.final_visitor_repository import (
    TYPED_METRICS,
    PoiAttributes,
    VisitorRepository,
    _json_safe,
    _num,
    _risk_desc,
    _txt,
)

from conftest import TEST_DATE, make_point, make_poi


def db_row(**overrides) -> SimpleNamespace:
    """A row shaped like the one ``_load_range`` reads out of the query."""
    values = {
        "id": 1,
        "city": "houston",
        "local_date": TEST_DATE,
        "longitude": -95.4,
        "latitude": 29.7,
        "brand": "Brand",
        "street_address": "1 Main St",
        "location_name": "Location",
        "avg_daily_visits": 10.0,
        "heat_risk_score": 50.0,
    }
    values.update(
        {f"core_poi_geometry_{field}": None for field in PoiAttributes._fields}
    )
    values.update(overrides)
    return SimpleNamespace(**values)


# --------------------------------------------------------------------------- #
# Scalar coercion
# --------------------------------------------------------------------------- #


class TestNum:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(Decimal("10.5"), 10.5), (10, 10.0), ("2.5", 2.5), (0, 0.0)],
    )
    def test_values_become_floats(self, value, expected):
        result = _num(value)

        assert result == expected
        assert isinstance(result, float)

    def test_none_stays_none(self):
        assert _num(None) is None


class TestTxt:
    @pytest.mark.parametrize(
        ("value", "expected"), [("Brand", "Brand"), (12, "12"), (1.5, "1.5")]
    )
    def test_values_become_strings(self, value, expected):
        assert _txt(value) == expected

    def test_none_becomes_an_empty_string_not_the_word_none(self):
        # A textual metric rendered as "None" would show up in the UI.
        assert _txt(None) == ""


class TestJsonSafe:
    def test_a_decimal_becomes_a_float(self):
        assert _json_safe(Decimal("3.5")) == 3.5

    def test_a_date_becomes_an_iso_string(self):
        assert _json_safe(date(2026, 8, 16)) == "2026-08-16"

    def test_a_datetime_becomes_an_iso_string(self):
        assert _json_safe(datetime(2026, 8, 16, 12, 30)) == "2026-08-16T12:30:00"

    @pytest.mark.parametrize("value", [10, 1.5, "text", True, None])
    def test_everything_else_is_passed_through(self, value):
        assert _json_safe(value) is value


# --------------------------------------------------------------------------- #
# _to_poi
# --------------------------------------------------------------------------- #


class TestToPoi:
    def test_an_unlinked_row_has_no_poi(self):
        # One None pointer rather than ~35 null fields.
        assert VisitorRepository._to_poi(db_row(core_poi_geometry_id=None)) is None

    def test_a_linked_row_becomes_poi_attributes(self):
        poi = VisitorRepository._to_poi(
            db_row(
                core_poi_geometry_id=7,
                core_poi_geometry_placekey="222-223-224",
                core_poi_geometry_top_category="Restaurants",
            )
        )

        assert isinstance(poi, PoiAttributes)
        assert poi.id == 7
        assert poi.placekey == "222-223-224"
        assert poi.top_category == "Restaurants"

    def test_text_fields_normalize_null_to_an_empty_string(self):
        poi = VisitorRepository._to_poi(
            db_row(core_poi_geometry_id=7, core_poi_geometry_placekey=None)
        )

        assert poi.placekey == ""
        assert poi.top_category == ""
        assert poi.market_code == ""

    def test_typed_fields_keep_their_null(self):
        # A null latitude must stay null rather than become "".
        poi = VisitorRepository._to_poi(
            db_row(core_poi_geometry_id=7, core_poi_geometry_latitude=None)
        )

        assert poi.latitude is None
        assert poi.naics_code is None

    def test_typed_fields_keep_their_type(self):
        poi = VisitorRepository._to_poi(
            db_row(
                core_poi_geometry_id=7,
                core_poi_geometry_latitude=29.7,
                core_poi_geometry_naics_code=722511,
                core_poi_geometry_enclosed=True,
                core_poi_geometry_opened_on=date(2019, 5, 1),
            )
        )

        assert poi.latitude == 29.7
        assert poi.naics_code == 722511
        assert poi.enclosed is True
        assert poi.opened_on == date(2019, 5, 1)


# --------------------------------------------------------------------------- #
# _to_point
# --------------------------------------------------------------------------- #


class TestToPoint:
    def test_a_plottable_row_becomes_a_point(self):
        point = VisitorRepository._to_point(db_row())

        assert point.lon == -95.4
        assert point.lat == 29.7
        assert point.brand == "Brand"
        assert point.street_address == "1 Main St"
        assert point.location_name == "Location"
        assert point.avg_daily_visits == 10.0
        assert point.heat_risk_score == 50.0

    @pytest.mark.parametrize(
        ("longitude", "latitude"), [(None, 29.7), (-95.4, None), (None, None)]
    )
    def test_a_row_without_coordinates_is_dropped(self, longitude, latitude):
        # These are the rows the preload counts as "skipped".
        assert (
            VisitorRepository._to_point(db_row(longitude=longitude, latitude=latitude))
            is None
        )

    def test_decimal_coordinates_are_coerced_to_floats(self):
        point = VisitorRepository._to_point(
            db_row(longitude=Decimal("-95.4"), latitude=Decimal("29.7"))
        )

        assert point.lon == -95.4
        assert isinstance(point.lon, float)
        assert isinstance(point.lat, float)

    def test_null_metrics_stay_null(self):
        point = VisitorRepository._to_point(
            db_row(avg_daily_visits=None, heat_risk_score=None)
        )

        assert point.avg_daily_visits is None
        assert point.heat_risk_score is None

    def test_null_text_columns_become_empty_strings(self):
        point = VisitorRepository._to_point(db_row(brand=None, street_address=None))

        assert point.brand == ""
        assert point.street_address == ""

    def test_a_row_with_no_poi_link_carries_a_null_poi(self):
        point = VisitorRepository._to_point(db_row(core_poi_geometry_id=None))

        assert point.poi is None

    def test_a_linked_row_carries_its_poi(self):
        point = VisitorRepository._to_point(db_row(core_poi_geometry_id=7))

        assert point.poi is not None
        assert point.poi.id == 7


# --------------------------------------------------------------------------- #
# _risk_desc — the cache's load-time ordering
# --------------------------------------------------------------------------- #


class TestRiskDesc:
    def test_higher_scores_sort_first(self):
        points = [
            make_point(heat_risk_score=10.0),
            make_point(heat_risk_score=90.0),
            make_point(heat_risk_score=50.0),
        ]

        ordered = sorted(points, key=_risk_desc)

        assert [p.heat_risk_score for p in ordered] == [90.0, 50.0, 10.0]

    def test_unscored_rows_sort_last(self):
        # None cannot be negated, so it rides in the first slot of the key;
        # True sorts after False, putting unscored rows at the end.
        points = [
            make_point(heat_risk_score=None),
            make_point(heat_risk_score=10.0),
        ]

        ordered = sorted(points, key=_risk_desc)

        assert [p.heat_risk_score for p in ordered] == [10.0, None]

    def test_ties_break_on_address_then_name(self):
        points = [
            make_point(heat_risk_score=50.0, street_address="B St", location_name="Z"),
            make_point(heat_risk_score=50.0, street_address="A St", location_name="Y"),
            make_point(heat_risk_score=50.0, street_address="A St", location_name="X"),
        ]

        ordered = sorted(points, key=_risk_desc)

        assert [(p.street_address, p.location_name) for p in ordered] == [
            ("A St", "X"),
            ("A St", "Y"),
            ("B St", "Z"),
        ]

    def test_a_zero_score_outranks_an_unscored_row(self):
        points = [make_point(heat_risk_score=None), make_point(heat_risk_score=0.0)]

        ordered = sorted(points, key=_risk_desc)

        assert ordered[0].heat_risk_score == 0.0


# --------------------------------------------------------------------------- #
# _resolve / _metrics
# --------------------------------------------------------------------------- #


class TestResolve:
    def test_a_plain_field_is_read_off_the_point(self):
        point = make_point(brand="Chipotle")

        assert VisitorRepository._resolve(point, "brand") == "Chipotle"

    def test_a_dotted_field_reaches_into_the_poi(self):
        point = make_point(poi=make_poi(top_category="Restaurants"))

        assert VisitorRepository._resolve(point, "poi.top_category") == "Restaurants"

    def test_a_dotted_field_on_an_unlinked_point_is_none(self):
        # No AttributeError: unlinked rows resolve to None rather than raising.
        point = make_point(poi=None)

        assert VisitorRepository._resolve(point, "poi.top_category") is None


class TestMetrics:
    def test_text_metrics_are_stringified(self):
        metrics = VisitorRepository._metrics(
            make_point(brand="Chipotle"), ("brand", "location_name")
        )

        assert metrics == {"brand": "Chipotle", "location_name": "Location"}

    def test_a_null_text_metric_becomes_an_empty_string(self):
        metrics = VisitorRepository._metrics(make_point(brand=None), ("brand",))

        assert metrics == {"brand": ""}

    def test_a_typed_metric_keeps_its_type(self):
        metrics = VisitorRepository._metrics(
            make_point(heat_risk_score=72.4), ("heat_risk_score",)
        )

        assert metrics == {"heat_risk_score": 72.4}
        assert isinstance(metrics["heat_risk_score"], float)

    def test_a_null_typed_metric_is_omitted_rather_than_emitted_as_null(self):
        metrics = VisitorRepository._metrics(
            make_point(heat_risk_score=None), ("heat_risk_score", "brand")
        )

        assert "heat_risk_score" not in metrics
        assert metrics == {"brand": "Brand"}

    def test_a_dotted_metric_is_keyed_on_its_last_segment(self):
        metrics = VisitorRepository._metrics(
            make_point(poi=make_poi(top_category="Restaurants")), ("poi.top_category",)
        )

        assert metrics == {"top_category": "Restaurants"}

    def test_a_dotted_typed_metric_is_json_safed(self):
        metrics = VisitorRepository._metrics(
            make_point(poi=make_poi(id=7, opened_on=date(2019, 5, 1))),
            ("poi.id", "poi.opened_on"),
        )

        assert metrics == {"id": 7, "opened_on": "2019-05-01"}

    def test_an_empty_field_list_yields_an_empty_dict(self):
        assert VisitorRepository._metrics(make_point(), ()) == {}

    def test_the_typed_set_covers_the_numeric_metrics_the_frontend_reads(self):
        assert "avg_daily_visits" in TYPED_METRICS
        assert "heat_risk_score" in TYPED_METRICS
        assert "brand" not in TYPED_METRICS
        assert "location_name" not in TYPED_METRICS


# --------------------------------------------------------------------------- #
# Small predicates and aggregates
# --------------------------------------------------------------------------- #


class TestHasPoiGeometry:
    def test_a_linked_point_passes(self):
        assert VisitorRepository._has_poi_geometry(make_point(poi=make_poi())) is True

    def test_an_unlinked_point_fails(self):
        assert VisitorRepository._has_poi_geometry(make_point(poi=None)) is False


class TestSumVisits:
    def test_visits_are_totalled(self, visitor_repo):
        points = [make_point(avg_daily_visits=10.0), make_point(avg_daily_visits=20.5)]

        assert visitor_repo._sum_visits(points) == 30.5

    def test_rows_without_the_metric_are_ignored(self, visitor_repo):
        points = [make_point(avg_daily_visits=10.0), make_point(avg_daily_visits=None)]

        assert visitor_repo._sum_visits(points) == 10.0

    def test_an_empty_bucket_totals_zero(self, visitor_repo):
        result = visitor_repo._sum_visits([])

        assert result == 0.0
        assert isinstance(result, float)


class TestCached:
    def test_a_cached_bucket_is_returned(self, visitor_repo, visitor_cache):
        points = [make_point()]
        visitor_cache[("houston", TEST_DATE)] = points

        assert visitor_repo._cached("houston", TEST_DATE) == points

    @pytest.mark.parametrize("city", ["Houston", "HOUSTON", "  houston  ", "hOuStOn"])
    def test_the_city_lookup_ignores_case_and_surrounding_space(
        self, visitor_repo, visitor_cache, city
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point()]

        assert len(visitor_repo._cached(city, TEST_DATE)) == 1

    def test_an_unknown_city_yields_an_empty_list(self, visitor_repo, visitor_cache):
        visitor_cache[("houston", TEST_DATE)] = [make_point()]

        assert visitor_repo._cached("atlantis", TEST_DATE) == []

    def test_an_unknown_date_yields_an_empty_list(self, visitor_repo, visitor_cache):
        visitor_cache[("houston", TEST_DATE)] = [make_point()]

        assert visitor_repo._cached("houston", date(2000, 1, 1)) == []


# --------------------------------------------------------------------------- #
# _risk_category — the band a heat index falls in
# --------------------------------------------------------------------------- #


class TestRiskCategory:
    @pytest.mark.parametrize(
        ("heat_index", "expected"),
        [
            (0.0, "Low"),
            (79.9, "Low"),
            (80.0, "Caution"),
            (89.9, "Caution"),
            (90.0, "Extreme Caution"),
            (102.9, "Extreme Caution"),
            (103.0, "Danger"),
            (124.9, "Danger"),
            (125.0, "Extreme Danger"),
            (200.0, "Extreme Danger"),
        ],
    )
    def test_banding(self, heat_index, expected):
        assert VisitorRepository._risk_category(heat_index) == expected

    def test_bounds_are_exclusive_on_the_upper_end(self):
        # 90.0 is the start of Extreme Caution, not the end of Caution.
        assert VisitorRepository._risk_category(90.0) == "Extreme Caution"
        assert VisitorRepository._risk_category(89.999) == "Caution"

    def test_a_negative_index_still_lands_in_the_lowest_band(self):
        assert VisitorRepository._risk_category(-40.0) == "Low"

    def test_no_reading_has_no_band(self):
        # None means "no weather row", which must not be scored as Low.
        assert VisitorRepository._risk_category(None) is None

    def test_the_band_labels_match_what_the_frontend_legend_expects(self):
        labels = [label for _, label in VisitorRepository.HEAT_RISK_BANDS]

        assert labels == [
            "Low",
            "Caution",
            "Extreme Caution",
            "Danger",
            "Extreme Danger",
        ]

    def test_the_bands_are_in_ascending_order(self):
        bounds = [upper for upper, _ in VisitorRepository.HEAT_RISK_BANDS]

        assert bounds == sorted(bounds)
