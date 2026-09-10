"""The three visitor reads gated on the day's heat index.

* ``GET /final_visitor/get-visitor-percentage-by-heat-risk`` → the donut chart
* ``GET /final_visitor/get-visitor-in-unsafe-condition``     → the exposure tile
* ``GET /final_visitor/get-poi-count-in-unsafe-condition``   → the POI tile

All three read ``_heat_index_f``, which goes to ``HeatmapRepository``'s weather
cache. The heatmap side is out of scope, so these stub that one method and vary
its answer: what is under test is how the visitor code classifies and gates on
the number, not where the number comes from.
"""

from __future__ import annotations

from datetime import date

import pytest

from repository.final_visitor_repository import UNSAFE_HEAT_INDEX_F, VisitorRepository

from conftest import TEST_DATE, make_point, make_poi

BANDS = ["Low", "Caution", "Extreme Caution", "Danger", "Extreme Danger"]


# --------------------------------------------------------------------------- #
# getVisitorPercentageByHeatRisk
# --------------------------------------------------------------------------- #


class TestVisitorPercentageByHeatRisk:
    def test_one_city_puts_all_of_its_visits_in_a_single_band(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(avg_daily_visits=100.0),
            make_point(avg_daily_visits=50.0),
        ]
        stub_heat_index({"houston": 95.0})

        result = visitor_repo.getVisitorPercentageByHeatRisk("houston", TEST_DATE)

        assert result["Extreme Caution"] == 100.0
        assert result["Danger"] == 0.0

    def test_every_band_is_present_even_at_zero(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        # The chart legend stays put across dates only if the keys never move.
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        stub_heat_index({"houston": 95.0})

        result = visitor_repo.getVisitorPercentageByHeatRisk("houston", TEST_DATE)

        assert list(result) == BANDS

    def test_the_percentages_sum_to_one_hundred(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        visitor_cache[("dallas", TEST_DATE)] = [make_point(avg_daily_visits=200.0)]
        visitor_cache[("miami", TEST_DATE)] = [make_point(avg_daily_visits=300.0)]
        stub_heat_index({"houston": 95.0, "dallas": 70.0, "miami": 130.0})

        result = visitor_repo.getVisitorPercentageByHeatRisk(None, TEST_DATE)

        assert sum(result.values()) == pytest.approx(100.0)

    def test_pooling_weights_bands_by_visits_not_by_city_count(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        # 100 of 300 visits sit in a hot city, 200 in a cool one.
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        visitor_cache[("dallas", TEST_DATE)] = [make_point(avg_daily_visits=200.0)]
        stub_heat_index({"houston": 95.0, "dallas": 70.0})

        result = visitor_repo.getVisitorPercentageByHeatRisk(None, TEST_DATE)

        assert result["Low"] == pytest.approx(200 / 300 * 100)
        assert result["Extreme Caution"] == pytest.approx(100 / 300 * 100)

    def test_two_cities_in_the_same_band_are_added_together(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        visitor_cache[("dallas", TEST_DATE)] = [make_point(avg_daily_visits=300.0)]
        stub_heat_index({"houston": 95.0, "dallas": 100.0})

        result = visitor_repo.getVisitorPercentageByHeatRisk(None, TEST_DATE)

        assert result["Extreme Caution"] == 100.0

    def test_a_city_with_no_weather_row_is_dropped_from_both_sides(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        # Counting it in the denominator only would deflate every band.
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        visitor_cache[("dallas", TEST_DATE)] = [make_point(avg_daily_visits=900.0)]
        stub_heat_index({"houston": 95.0})  # dallas has no reading

        result = visitor_repo.getVisitorPercentageByHeatRisk(None, TEST_DATE)

        assert result["Extreme Caution"] == 100.0
        assert sum(result.values()) == pytest.approx(100.0)

    def test_nothing_classifiable_yields_an_empty_dict(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        # {} is "no data", distinct from every band genuinely sitting at zero.
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        stub_heat_index({})

        assert visitor_repo.getVisitorPercentageByHeatRisk("houston", TEST_DATE) == {}

    def test_an_uncached_city_yields_an_empty_dict(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        stub_heat_index({"atlantis": 95.0})

        assert visitor_repo.getVisitorPercentageByHeatRisk("atlantis", TEST_DATE) == {}

    def test_a_city_whose_rows_have_no_visits_yields_an_empty_dict(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=None)]
        stub_heat_index({"houston": 95.0})

        assert visitor_repo.getVisitorPercentageByHeatRisk("houston", TEST_DATE) == {}

    def test_other_dates_are_not_pooled_in(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        visitor_cache[("dallas", date(2026, 8, 17))] = [
            make_point(avg_daily_visits=900.0)
        ]
        stub_heat_index({"houston": 95.0, "dallas": 70.0})

        result = visitor_repo.getVisitorPercentageByHeatRisk(None, TEST_DATE)

        assert result["Extreme Caution"] == 100.0
        assert result["Low"] == 0.0

    @pytest.mark.parametrize(
        ("heat_index", "band"),
        [
            (70.0, "Low"),
            (85.0, "Caution"),
            (95.0, "Extreme Caution"),
            (110.0, "Danger"),
            (130.0, "Extreme Danger"),
        ],
    )
    def test_the_city_lands_in_the_band_its_index_selects(
        self, visitor_repo, visitor_cache, stub_heat_index, heat_index, band
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        stub_heat_index({"houston": heat_index})

        result = visitor_repo.getVisitorPercentageByHeatRisk("houston", TEST_DATE)

        assert result[band] == 100.0

    def test_the_result_is_percentages_not_counts(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=48213.0)]
        stub_heat_index({"houston": 95.0})

        result = visitor_repo.getVisitorPercentageByHeatRisk("houston", TEST_DATE)

        assert result["Extreme Caution"] == 100.0


# --------------------------------------------------------------------------- #
# getVisitorInUnsafeCondition
# --------------------------------------------------------------------------- #


class TestVisitorInUnsafeCondition:
    def test_a_hot_day_totals_every_cached_visit(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(avg_daily_visits=100.0),
            make_point(avg_daily_visits=50.0),
        ]
        stub_heat_index({"houston": 95.0})

        assert visitor_repo.getVisitorInUnsafeCondition("houston", TEST_DATE) == 150.0

    def test_the_threshold_is_inclusive(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        # The gate is `< UNSAFE_HEAT_INDEX_F`, so exactly 90 counts as unsafe.
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        stub_heat_index({"houston": UNSAFE_HEAT_INDEX_F})

        assert visitor_repo.getVisitorInUnsafeCondition("houston", TEST_DATE) == 100.0

    def test_just_below_the_threshold_counts_nothing(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        stub_heat_index({"houston": 89.99})

        assert visitor_repo.getVisitorInUnsafeCondition("houston", TEST_DATE) == 0

    def test_a_cool_day_counts_nothing(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        stub_heat_index({"houston": 60.0})

        assert visitor_repo.getVisitorInUnsafeCondition("houston", TEST_DATE) == 0

    def test_a_missing_weather_row_counts_nothing(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        # A 0 here means "not counted as unsafe", not "no visitors".
        visitor_cache[("houston", TEST_DATE)] = [make_point(avg_daily_visits=100.0)]
        stub_heat_index({})

        assert visitor_repo.getVisitorInUnsafeCondition("houston", TEST_DATE) == 0

    def test_a_hot_day_with_no_cached_rows_counts_nothing(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        stub_heat_index({"houston": 95.0})

        assert visitor_repo.getVisitorInUnsafeCondition("houston", TEST_DATE) == 0

    def test_rows_without_visits_are_skipped(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(avg_daily_visits=100.0),
            make_point(avg_daily_visits=None),
        ]
        stub_heat_index({"houston": 95.0})

        assert visitor_repo.getVisitorInUnsafeCondition("houston", TEST_DATE) == 100.0

    def test_the_gate_is_per_city_not_per_row(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        # The heat index is a market/date reading, so it decides the whole
        # bucket; individual heat_risk_scores play no part.
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(avg_daily_visits=100.0, heat_risk_score=0.0),
            make_point(avg_daily_visits=50.0, heat_risk_score=None),
        ]
        stub_heat_index({"houston": 95.0})

        assert visitor_repo.getVisitorInUnsafeCondition("houston", TEST_DATE) == 150.0

    def test_unlinked_rows_are_still_counted(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        # Unlike the POI count, this one does not require a POI link.
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(avg_daily_visits=100.0, poi=None)
        ]
        stub_heat_index({"houston": 95.0})

        assert visitor_repo.getVisitorInUnsafeCondition("houston", TEST_DATE) == 100.0


# --------------------------------------------------------------------------- #
# getPoiCountInUnsafeCondition
# --------------------------------------------------------------------------- #


class TestPoiCountInUnsafeCondition:
    def test_a_hot_day_counts_the_poi_linked_rows(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(poi=make_poi(id=1)),
            make_point(poi=make_poi(id=2)),
            make_point(poi=None),
        ]
        stub_heat_index({"houston": 95.0})

        assert visitor_repo.getPoiCountInUnsafeCondition("houston", TEST_DATE) == 2

    def test_the_count_is_an_integer(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(poi=make_poi(id=1))]
        stub_heat_index({"houston": 95.0})

        result = visitor_repo.getPoiCountInUnsafeCondition("houston", TEST_DATE)

        assert isinstance(result, int)
        assert result == 1

    def test_rows_are_counted_not_distinct_pois(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        # Two visitor rows pointing at the same POI count twice.
        visitor_cache[("houston", TEST_DATE)] = [
            make_point(poi=make_poi(id=7)),
            make_point(poi=make_poi(id=7)),
        ]
        stub_heat_index({"houston": 95.0})

        assert visitor_repo.getPoiCountInUnsafeCondition("houston", TEST_DATE) == 2

    def test_the_threshold_is_inclusive(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(poi=make_poi(id=1))]
        stub_heat_index({"houston": UNSAFE_HEAT_INDEX_F})

        assert visitor_repo.getPoiCountInUnsafeCondition("houston", TEST_DATE) == 1

    def test_a_cool_day_counts_nothing(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(poi=make_poi(id=1))]
        stub_heat_index({"houston": 60.0})

        assert visitor_repo.getPoiCountInUnsafeCondition("houston", TEST_DATE) == 0

    def test_a_missing_weather_row_counts_nothing(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(poi=make_poi(id=1))]
        stub_heat_index({})

        assert visitor_repo.getPoiCountInUnsafeCondition("houston", TEST_DATE) == 0

    def test_a_hot_day_with_no_linked_rows_counts_nothing(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        visitor_cache[("houston", TEST_DATE)] = [make_point(poi=None)]
        stub_heat_index({"houston": 95.0})

        assert visitor_repo.getPoiCountInUnsafeCondition("houston", TEST_DATE) == 0

    def test_an_uncached_city_counts_nothing(
        self, visitor_repo, visitor_cache, stub_heat_index
    ):
        stub_heat_index({"atlantis": 95.0})

        assert visitor_repo.getPoiCountInUnsafeCondition("atlantis", TEST_DATE) == 0


# --------------------------------------------------------------------------- #
# The threshold constant
# --------------------------------------------------------------------------- #


def test_the_unsafe_threshold_is_ninety_fahrenheit():
    assert UNSAFE_HEAT_INDEX_F == 90.0


def test_the_class_attribute_mirrors_the_module_constant():
    """Two copies of the threshold exist; the methods read the module one.

    ``VisitorRepository.UNSAFE_HEAT_INDEX_F`` is never referenced by the gating
    code — both ``getVisitorInUnsafeCondition`` and
    ``getPoiCountInUnsafeCondition`` close over the module-level constant. They
    agree today, so this test is the tripwire for the day someone edits the
    class attribute and expects the endpoints to follow.
    """
    assert VisitorRepository.UNSAFE_HEAT_INDEX_F == UNSAFE_HEAT_INDEX_F
