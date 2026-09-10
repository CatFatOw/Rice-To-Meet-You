"""The visitor reads served straight from the in-memory cache.

Four frontend endpoints land here:

* ``GET /final_visitor/get-visitor-by-city-date``            → getVisitorDataByCityDate
* ``GET /final_visitor/get-heat-risk-score-by-city-date``    → getHeatRiskScoreByCityDate
* ``GET /final_visitor/get-total-visits-by-city-date``       → getTotalVisitsByCityDate
* ``GET /final_visitor/get-average-heat-risk-score-by-city-date``
                                                            → getAverageHeatRiskScoreByCityDate

The first two answer in the ``HeatmapPointsByDate`` shape the map layers read:
``{"2026-08-16": [{value, location_coordinates, individual_metrics}, ...]}``.
The repository holds a session it never uses on these paths, so the fixture
hands it ``None`` — any stray query would raise rather than pass quietly.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import TEST_DATE, make_point, make_poi

ISO = TEST_DATE.isoformat()
OTHER_DATE = date(2026, 8, 17)


@pytest.fixture
def cache_houston(visitor_cache):
    """Three Houston rows, in the risk-descending order the preload leaves."""
    visitor_cache[("houston", TEST_DATE)] = [
        make_point(
            lon=-95.40,
            lat=29.70,
            brand="Chipotle",
            street_address="1 Main St",
            location_name="Chipotle Midtown",
            avg_daily_visits=100.0,
            heat_risk_score=95.0,
        ),
        make_point(
            lon=-95.50,
            lat=29.80,
            brand="Panera",
            street_address="2 Oak St",
            location_name="Panera Rice Village",
            avg_daily_visits=50.0,
            heat_risk_score=70.0,
        ),
        make_point(
            lon=-95.60,
            lat=29.90,
            brand="Local",
            street_address="3 Elm St",
            location_name="Corner Cafe",
            avg_daily_visits=25.0,
            heat_risk_score=None,
        ),
    ]
    return visitor_cache


# --------------------------------------------------------------------------- #
# getVisitorDataByCityDate
# --------------------------------------------------------------------------- #


class TestGetVisitorDataByCityDate:
    def test_the_result_is_keyed_on_the_iso_date(self, visitor_repo, cache_houston):
        result = visitor_repo.getVisitorDataByCityDate("houston", TEST_DATE)

        assert list(result) == [ISO]

    def test_every_cached_row_becomes_a_point(self, visitor_repo, cache_houston):
        result = visitor_repo.getVisitorDataByCityDate("houston", TEST_DATE)

        assert len(result[ISO]) == 3

    def test_the_value_is_the_visit_count(self, visitor_repo, cache_houston):
        points = visitor_repo.getVisitorDataByCityDate("houston", TEST_DATE)[ISO]

        assert [point["value"] for point in points] == [100.0, 50.0, 25.0]

    def test_coordinates_are_longitude_first(self, visitor_repo, cache_houston):
        # GeoJSON order, which is what the map layer expects.
        point = visitor_repo.getVisitorDataByCityDate("houston", TEST_DATE)[ISO][0]

        assert point["location_coordinates"] == [-95.40, 29.70]

    def test_the_metrics_carry_the_identity_and_the_risk_score(
        self, visitor_repo, cache_houston
    ):
        point = visitor_repo.getVisitorDataByCityDate("houston", TEST_DATE)[ISO][0]

        assert point["individual_metrics"] == {
            "brand": "Chipotle",
            "street_address": "1 Main St",
            "location_name": "Chipotle Midtown",
            "heat_risk_score": 95.0,
        }

    def test_a_point_has_exactly_the_three_documented_keys(
        self, visitor_repo, cache_houston
    ):
        point = visitor_repo.getVisitorDataByCityDate("houston", TEST_DATE)[ISO][0]

        assert set(point) == {"value", "location_coordinates", "individual_metrics"}

    def test_an_unscored_row_omits_the_risk_metric(self, visitor_repo, cache_houston):
        point = visitor_repo.getVisitorDataByCityDate("houston", TEST_DATE)[ISO][2]

        assert "heat_risk_score" not in point["individual_metrics"]
        assert point["individual_metrics"]["brand"] == "Local"

    def test_a_row_without_visits_is_dropped(self, visitor_repo, visitor_cache):
        # `value` is a required number, so there is nothing to plot.
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(avg_daily_visits=None),
            make_point(avg_daily_visits=10.0),
        ]

        points = visitor_repo.getVisitorDataByCityDate("houston", TEST_DATE)[ISO]

        assert len(points) == 1
        assert points[0]["value"] == 10.0

    def test_an_uncached_city_yields_an_empty_dict(self, visitor_repo, cache_houston):
        assert visitor_repo.getVisitorDataByCityDate("atlantis", TEST_DATE) == {}

    def test_an_uncached_date_yields_an_empty_dict(self, visitor_repo, cache_houston):
        assert visitor_repo.getVisitorDataByCityDate("houston", OTHER_DATE) == {}

    def test_a_bucket_where_nothing_is_plottable_yields_an_empty_dict(
        self, visitor_repo, visitor_cache
    ):
        # Not {"2026-08-16": []} -- the date key is dropped entirely.
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=None)]

        assert visitor_repo.getVisitorDataByCityDate("houston", TEST_DATE) == {}

    @pytest.mark.parametrize("city", ["Houston", "HOUSTON", "  Houston "])
    def test_the_city_argument_is_normalized(
        self, visitor_repo, cache_houston, city
    ):
        assert len(visitor_repo.getVisitorDataByCityDate(city, TEST_DATE)[ISO]) == 3

    def test_cache_order_is_preserved(self, visitor_repo, cache_houston):
        # The preload sorts by risk descending, so the projection must not
        # reshuffle: "top N by risk" is a slice at the call site.
        points = visitor_repo.getVisitorDataByCityDate("houston", TEST_DATE)[ISO]

        assert [p["individual_metrics"]["brand"] for p in points] == [
            "Chipotle",
            "Panera",
            "Local",
        ]

    def test_rows_are_included_whether_or_not_they_link_to_a_poi(
        self, visitor_repo, visitor_cache
    ):
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(poi=make_poi(id=7)),
            make_point(poi=None),
        ]

        assert len(visitor_repo.getVisitorDataByCityDate("houston", TEST_DATE)[ISO]) == 2


# --------------------------------------------------------------------------- #
# getHeatRiskScoreByCityDate
# --------------------------------------------------------------------------- #


class TestGetHeatRiskScoreByCityDate:
    def test_the_value_is_the_risk_score(self, visitor_repo, cache_houston):
        points = visitor_repo.getHeatRiskScoreByCityDate("houston", TEST_DATE)[ISO]

        assert [point["value"] for point in points] == [95.0, 70.0]

    def test_unscored_rows_are_dropped(self, visitor_repo, cache_houston):
        # The third row has no score, so it cannot drive this layer's value.
        points = visitor_repo.getHeatRiskScoreByCityDate("houston", TEST_DATE)[ISO]

        assert len(points) == 2

    def test_the_metrics_carry_visits_instead_of_the_risk_score(
        self, visitor_repo, cache_houston
    ):
        point = visitor_repo.getHeatRiskScoreByCityDate("houston", TEST_DATE)[ISO][0]

        assert point["individual_metrics"] == {
            "brand": "Chipotle",
            "street_address": "1 Main St",
            "location_name": "Chipotle Midtown",
            "avg_daily_visits": 100.0,
        }

    def test_coordinates_are_longitude_first(self, visitor_repo, cache_houston):
        point = visitor_repo.getHeatRiskScoreByCityDate("houston", TEST_DATE)[ISO][0]

        assert point["location_coordinates"] == [-95.40, 29.70]

    def test_a_row_without_visits_still_appears(self, visitor_repo, visitor_cache):
        # This view keys on the score, so a missing visit count only blanks
        # one metric rather than dropping the point.
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(avg_daily_visits=None, heat_risk_score=80.0)
        ]

        points = visitor_repo.getHeatRiskScoreByCityDate("houston", TEST_DATE)[ISO]

        assert len(points) == 1
        assert "avg_daily_visits" not in points[0]["individual_metrics"]

    def test_an_uncached_city_yields_an_empty_dict(self, visitor_repo, cache_houston):
        assert visitor_repo.getHeatRiskScoreByCityDate("atlantis", TEST_DATE) == {}

    def test_a_bucket_with_no_scores_yields_an_empty_dict(
        self, visitor_repo, visitor_cache
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(heat_risk_score=None)]

        assert visitor_repo.getHeatRiskScoreByCityDate("houston", TEST_DATE) == {}

    def test_a_zero_score_is_kept(self, visitor_repo, visitor_cache):
        # 0.0 is a real reading; only None means "unscored".
        visitor_cache[("houston", TEST_DATE)] = [make_point(heat_risk_score=0.0)]

        points = visitor_repo.getHeatRiskScoreByCityDate("houston", TEST_DATE)[ISO]

        assert points[0]["value"] == 0.0


# --------------------------------------------------------------------------- #
# getTotalVisitsByCityDate
# --------------------------------------------------------------------------- #


class TestGetTotalVisitsByCityDate:
    def test_a_city_total_is_keyed_on_the_iso_date(self, visitor_repo, cache_houston):
        assert visitor_repo.getTotalVisitsByCityDate("houston", TEST_DATE) == {
            ISO: 175.0
        }

    def test_rows_without_visits_are_ignored_not_counted_as_zero(
        self, visitor_repo, visitor_cache
    ):
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(avg_daily_visits=10.0),
            make_point(avg_daily_visits=None),
        ]

        assert visitor_repo.getTotalVisitsByCityDate("houston", TEST_DATE) == {ISO: 10.0}

    def test_an_uncached_city_yields_an_empty_dict(self, visitor_repo, cache_houston):
        assert visitor_repo.getTotalVisitsByCityDate("atlantis", TEST_DATE) == {}

    @pytest.mark.parametrize("city", [None, ""])
    def test_a_missing_city_totals_every_cached_city_for_that_date(
        self, visitor_repo, visitor_cache, city
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        visitor_cache[("dallas", TEST_DATE)] = [make_point(avg_daily_visits=200.0)]

        assert visitor_repo.getTotalVisitsByCityDate(city, TEST_DATE) == {ISO: 300.0}

    def test_a_whitespace_only_city_totals_nothing_at_all(
        self, visitor_repo, visitor_cache
    ):
        """"   " takes the single-city branch and matches no city.

        The docstring says a "null/blank" city pools every city, but the test
        is ``if city:`` and a whitespace-only string is truthy. So it falls
        through to a lookup for the city named "" (``_cached`` strips it), finds
        nothing, and returns ``{}`` — not the pooled total the wording implies.
        """
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        visitor_cache[("dallas", TEST_DATE)] = [make_point(avg_daily_visits=200.0)]

        assert visitor_repo.getTotalVisitsByCityDate("   ", TEST_DATE) == {}

    def test_the_all_cities_total_ignores_other_dates(
        self, visitor_repo, visitor_cache
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        visitor_cache[("houston", OTHER_DATE)] = [make_point(avg_daily_visits=900.0)]

        assert visitor_repo.getTotalVisitsByCityDate(None, TEST_DATE) == {ISO: 100.0}

    def test_a_named_city_ignores_the_other_cities(self, visitor_repo, visitor_cache):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        visitor_cache[("dallas", TEST_DATE)] = [make_point(avg_daily_visits=200.0)]

        assert visitor_repo.getTotalVisitsByCityDate("houston", TEST_DATE) == {ISO: 100.0}

    def test_a_genuine_zero_total_is_indistinguishable_from_no_data(
        self, visitor_repo, visitor_cache
    ):
        """A total of 0 collapses to ``{}``, same as an uncached city.

        The guard is ``if total else {}``, so a city whose rows all report zero
        visits reports "no data" rather than "zero visits". The frontend's
        ``getTotalVisitsByCityDate`` maps both to null, so the two really are
        indistinguishable downstream — worth knowing before anyone reads a
        missing tile as a backend outage.
        """
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=0.0)]

        assert visitor_repo.getTotalVisitsByCityDate("houston", TEST_DATE) == {}
        assert visitor_repo.getTotalVisitsByCityDate("atlantis", TEST_DATE) == {}

    def test_the_total_is_a_float(self, visitor_repo, visitor_cache):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=10)]

        assert isinstance(visitor_repo.getTotalVisitsByCityDate("houston", TEST_DATE)[ISO], float)


# --------------------------------------------------------------------------- #
# getAverageHeatRiskScoreByCityDate
# --------------------------------------------------------------------------- #


class TestGetAverageHeatRiskScoreByCityDate:
    def test_the_mean_of_the_scored_rows_is_returned(self, visitor_repo, visitor_cache):
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(heat_risk_score=60.0),
            make_point(heat_risk_score=80.0),
        ]

        assert visitor_repo.getAverageHeatRiskScoreByCityDate("houston", TEST_DATE) == 70.0

    def test_unscored_rows_are_left_out_of_both_sides_of_the_average(
        self, visitor_repo, cache_houston
    ):
        # (95 + 70) / 2, not (95 + 70 + 0) / 3.
        assert visitor_repo.getAverageHeatRiskScoreByCityDate("houston", TEST_DATE) == 82.5

    def test_an_uncached_city_has_no_average(self, visitor_repo, cache_houston):
        assert visitor_repo.getAverageHeatRiskScoreByCityDate("atlantis", TEST_DATE) is None

    def test_a_bucket_with_no_scores_has_no_average(self, visitor_repo, visitor_cache):
        # None rather than 0.0: an unscored city is not a cool one.
        visitor_cache[("houston", TEST_DATE)] = [make_point(heat_risk_score=None)]

        assert visitor_repo.getAverageHeatRiskScoreByCityDate("houston", TEST_DATE) is None

    def test_a_genuine_zero_average_is_reported_as_zero(
        self, visitor_repo, visitor_cache
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(heat_risk_score=0.0)]

        assert visitor_repo.getAverageHeatRiskScoreByCityDate("houston", TEST_DATE) == 0.0

    def test_the_average_is_a_float(self, visitor_repo, visitor_cache):
        visitor_cache[("houston", TEST_DATE)] = [make_point(heat_risk_score=50)]

        assert isinstance(
            visitor_repo.getAverageHeatRiskScoreByCityDate("houston", TEST_DATE), float
        )

    def test_a_single_scored_row_averages_to_itself(self, visitor_repo, visitor_cache):
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(heat_risk_score=42.5),
            make_point(heat_risk_score=None),
        ]

        assert visitor_repo.getAverageHeatRiskScoreByCityDate("houston", TEST_DATE) == 42.5

    @pytest.mark.parametrize("city", ["Houston", "  HOUSTON  "])
    def test_the_city_argument_is_normalized(self, visitor_repo, cache_houston, city):
        assert visitor_repo.getAverageHeatRiskScoreByCityDate(city, TEST_DATE) == 82.5
