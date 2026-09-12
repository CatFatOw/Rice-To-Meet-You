"""Metric routing and tooltip layers for the interpolated map surfaces.

Every heatmap except ``avg_daily_visits`` is drawn as a kriged surface, and a
surface has to be fitted on the *same* readings the old heatmap drew. That is
not one repository call: a metric may be a weather column, a heat-index column,
a synthetic zero, a per-point derivation, or a visitor-cache field, and the
frontend reaches each through a different route. These tests pin that routing,
plus the tooltip rows built on top of it.

Nothing here touches Postgres. The two repositories are recording fakes, so the
assertions are about which reader was called, with which arguments, and how the
result was shaped.
"""

from __future__ import annotations

import pytest

from data.city_boundaries import get_city_bounds
from routers.grid_interpolation import (
    LOCAL_TEMPERATURE_SOURCES,
    VISITOR_METRIC_READERS,
    attach_tooltip_layers,
    collect_extra_readings,
    surface_metric_unit,
    surface_readings_for_metric,
)
from services.grid_interpolation_service import SURFACE_METRICS, krige_surface

CITY = "Houston"
DATE = "2024-07-15"


def points_by_date(values, date=DATE):
    """A HeatmapPointsByDate block spread across the Houston rectangle."""
    min_lon, min_lat, max_lon, max_lat = get_city_bounds(CITY)
    span = len(values) - 1 or 1
    return {
        date: [
            {
                "value": value,
                "location_coordinates": [
                    min_lon + (max_lon - min_lon) * index / span,
                    min_lat + (max_lat - min_lat) * index / span,
                ],
            }
            for index, value in enumerate(values)
        ]
    }


class FakeHeatmapRepository:
    """Records the reads the resolver makes, and answers from a canned map."""

    def __init__(self, by_metric=None, local_temperature=None):
        self.by_metric = by_metric or {}
        self.local_temperature = local_temperature or {}
        self.metric_calls = []
        self.local_calls = []

    def getDataPointsForCityDateMetric(self, weather_date, metric, market_code):
        self.metric_calls.append((weather_date, metric, market_code))
        if metric not in self.by_metric:
            raise ValueError(f"Metric {metric!r} is not an available column.")
        return self.by_metric[metric]

    def getLocalTemperatureByCityDate(
        self, weather_date, metric, market_code, temperature_unit
    ):
        self.local_calls.append(
            (weather_date, metric, market_code, temperature_unit)
        )
        return self.local_temperature


class FakeVisitorRepository:
    def __init__(self, risk=None, visits=None):
        self.risk = risk or {}
        self.visits = visits or {}
        self.calls = []

    def getHeatRiskScoreByCityDate(self, city, date):
        self.calls.append(("risk", city, date))
        return self.risk

    def getVisitorDataByCityDate(self, city, date):
        self.calls.append(("visits", city, date))
        return self.visits


# ---------------------------------------------------------------------------
# The metric set the map can draw
# ---------------------------------------------------------------------------


def test_every_displayed_metric_but_visits_has_a_surface():
    """avg_daily_visits is the one metric that keeps the density heatmap.

    Visits are a per-POI count, not a sample of a field that exists between
    the POIs, so kriging one would invent footfall for empty ground.
    """
    # frontend/src/api/map.ts availableMetrics, in order.
    displayed = [
        "average_temperature_c",
        "average_temperature_f",
        "heat_index_f",
        "heat_index_c",
        "average_relative_humidity_pct",
        "change_in_temperature",
        "change_in_average_temperature_c",
        "change_in_average_temperature_f",
        "change_in_local_temperature_c",
        "change_in_local_temperature_f",
        "avg_daily_visits",
        "heat_risk_score",
        "local_temperature_c",
        "local_temperature_f",
    ]

    assert SURFACE_METRICS == set(displayed) - {"avg_daily_visits"}


# ---------------------------------------------------------------------------
# Reading sources
# ---------------------------------------------------------------------------


def test_plain_metric_reads_the_weather_cache_by_name():
    heatmap = FakeHeatmapRepository(
        by_metric={"average_temperature_c": points_by_date([28.0, 31.0, 29.5])}
    )
    readings, unit = surface_readings_for_metric(
        "average_temperature_c", CITY, DATE, heatmap, FakeVisitorRepository()
    )

    # Read by name, under the city's market code -- not the display name.
    assert heatmap.metric_calls == [(DATE, "average_temperature_c", "houston")]
    assert [reading["value"] for reading in readings] == [28.0, 31.0, 29.5]
    assert unit == "°C"
    assert set(readings[0]) == {"longitude", "latitude", "value"}


@pytest.mark.parametrize(
    "metric, source_column, temperature_unit, unit",
    [
        ("local_temperature_c", "average_temperature_c", "c", "°C"),
        ("local_temperature_f", "average_temperature_f", "f", "°F"),
    ],
)
def test_local_temperature_reads_its_own_derivation(
    metric, source_column, temperature_unit, unit
):
    """Local temperature is not a column: it is one market temperature plus
    each point's urban-heat-island offset, so it has its own reader and its own
    source column per unit."""
    heatmap = FakeHeatmapRepository(
        local_temperature=points_by_date([30.0, 33.0, 31.0])
    )
    readings, resolved_unit = surface_readings_for_metric(
        metric, CITY, DATE, heatmap, FakeVisitorRepository()
    )

    assert heatmap.metric_calls == []  # never read as a plain column
    assert heatmap.local_calls == [(DATE, source_column, "houston", temperature_unit)]
    assert len(readings) == 3
    assert resolved_unit == unit
    assert LOCAL_TEMPERATURE_SOURCES[metric] == (source_column, temperature_unit)


def test_heat_risk_reads_the_visitor_cache_under_the_frontend_city_name():
    """The visitor cache is keyed on the city string the frontend sends, not on
    the market code the weather cache uses."""
    from datetime import date

    visitor = FakeVisitorRepository(risk=points_by_date([61.0, 88.0]))
    heatmap = FakeHeatmapRepository()

    readings, unit = surface_readings_for_metric(
        "heat_risk_score", CITY, DATE, heatmap, visitor
    )

    assert visitor.calls == [("risk", CITY, date(2024, 7, 15))]
    assert heatmap.metric_calls == []
    assert [reading["value"] for reading in readings] == [61.0, 88.0]
    # Visitor routes report these as bare numbers, so no unit suffix.
    assert unit == ""


def test_visits_are_readable_as_a_tooltip_row():
    """avg_daily_visits gets no surface of its own, but it is still a tooltip
    row under heat_risk_score, so the resolver has to be able to read it."""
    visitor = FakeVisitorRepository(visits=points_by_date([1200.0, 8400.0]))

    readings, unit = surface_readings_for_metric(
        "avg_daily_visits", CITY, DATE, FakeHeatmapRepository(), visitor
    )

    assert visitor.calls[0][0] == "visits"
    assert [reading["value"] for reading in readings] == [1200.0, 8400.0]
    assert unit == ""
    assert "avg_daily_visits" in VISITOR_METRIC_READERS


def test_readings_drop_points_with_no_value():
    block = points_by_date([28.0, 31.0])
    block[DATE].append({"value": None, "location_coordinates": [-95.0, 29.0]})
    heatmap = FakeHeatmapRepository(by_metric={"average_temperature_c": block})

    readings, _ = surface_readings_for_metric(
        "average_temperature_c", CITY, DATE, heatmap, FakeVisitorRepository()
    )

    assert [reading["value"] for reading in readings] == [28.0, 31.0]


def test_unknown_metric_raises():
    with pytest.raises(ValueError):
        surface_readings_for_metric(
            "not_a_metric", CITY, DATE, FakeHeatmapRepository(), FakeVisitorRepository()
        )


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "metric, unit",
    [
        ("average_temperature_c", "°C"),
        ("local_temperature_f", "°F"),
        ("average_relative_humidity_pct", "%"),
        ("average_wind_speed_knots", " mph"),
        ("precipitation_3d_sum_mm", " in"),
        ("heat_index_f", " / 100"),
        # Visitor metrics are reported as bare numbers by their own routes.
        ("heat_risk_score", ""),
        ("avg_daily_visits", ""),
    ],
)
def test_metric_unit_matches_the_measured_row_it_replaces(metric, unit):
    assert surface_metric_unit(metric) == unit


# ---------------------------------------------------------------------------
# Tooltip rows
# ---------------------------------------------------------------------------


def test_extra_readings_skip_the_drawn_metric_and_survive_failures():
    """The drawn metric is served from the primary lattice, so it is not read
    again here; an unreadable secondary metric costs one tooltip row and must
    not cost the map its surface."""
    heatmap = FakeHeatmapRepository(
        by_metric={
            "average_relative_humidity_pct": points_by_date([55.0, 61.0]),
            "average_temperature_c": points_by_date([28.0, 31.0]),
        }
    )

    readings, units = collect_extra_readings(
        ["average_temperature_c", "not_a_metric", "average_relative_humidity_pct"],
        "average_temperature_c",
        CITY,
        DATE,
        heatmap,
        FakeVisitorRepository(),
    )

    assert set(readings) == {"average_relative_humidity_pct"}
    assert units == {"average_relative_humidity_pct": "%"}


def test_tooltip_layers_reuse_the_surface_and_keep_the_requested_order():
    """The drawn metric's row is the surface itself, and rows come back in the
    order the caller listed them -- which is the order the tooltip renders."""
    min_lon, min_lat, max_lon, max_lat = get_city_bounds(CITY)
    readings = [
        {"longitude": min_lon + (max_lon - min_lon) * i / 9,
         "latitude": min_lat + (max_lat - min_lat) * i / 9,
         "value": 28 + i * 0.4}
        for i in range(10)
    ]
    humidity = [{**reading, "value": 50 + i} for i, reading in enumerate(readings)]

    surface = krige_surface(
        readings,
        rows=8,
        cols=8,
        city=CITY,
        extra_points_by_metric={"average_relative_humidity_pct": humidity},
    )
    extra_names = ["average_relative_humidity_pct", "average_temperature_c"]

    attach_tooltip_layers(
        surface,
        "average_temperature_c",
        extra_names,
        {"average_relative_humidity_pct": "%"},
        primary_unit="°C",
    )

    assert list(surface["metrics"]) == extra_names
    primary = surface["metrics"]["average_temperature_c"]
    assert primary["values"] == surface["values"]
    assert primary["unit"] == "°C"
    assert surface["metrics"]["average_relative_humidity_pct"]["unit"] == "%"


def test_tooltip_layers_omit_a_metric_the_caller_did_not_ask_for():
    readings = [
        {"longitude": -95.4 + i * 0.05, "latitude": 29.7 + i * 0.05, "value": 28 + i}
        for i in range(6)
    ]

    surface = krige_surface(readings, rows=8, cols=8, city=CITY)
    attach_tooltip_layers(surface, "average_temperature_c", [], {})

    assert surface["metrics"] == {}


def test_a_flat_field_krige_to_a_flat_surface():
    """change_in_temperature is all zeros until an intervention is placed. That
    is a legitimate input, and it has to come back as a genuinely flat surface
    rather than raising on an unfittable variogram."""
    readings = [
        {"longitude": -95.4 + i * 0.05, "latitude": 29.7 + i * 0.05, "value": 0.0}
        for i in range(10)
    ]

    surface = krige_surface(readings, rows=8, cols=8, city=CITY)

    assert surface["variogram_model"] == "constant"
    assert surface["min"] == surface["max"] == 0.0
    assert all(value == 0.0 for row in surface["values"] for value in row)
