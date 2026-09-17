"""The server-side pieces behind the map's interpolated surfaces.

Every heatmap except ``avg_daily_visits`` and ``heat_risk_score`` is drawn as a
kriged surface instead of a point-density cloud. A surface has to be fitted on
the *same* readings the old heatmap drew, or it would describe a different
field from the layer it replaced -- and that is not one repository call. A
metric may be a weather column, a heat-index column, a synthetic zero, or a
per-point derivation, and the frontend reaches each through a different route.

Scope is the code that makes that work: the reading resolver and its unit
lookup, the tooltip-layer assembly, and the two surface routes built on top of
them. ``krige_surface`` itself is exercised only where a route depends on a
specific behaviour of it (a flat field, a secondary lattice).

Nothing here touches Postgres. ``FakeHeatmapRepository`` records the reads that
were made and answers from a canned map, so the assertions are about which
reader was called, with which arguments, and how the result was shaped.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from data.city_boundaries import get_city_bounds
from routers import grid_interpolation
from routers.grid_interpolation import (
    LOCAL_TEMPERATURE_SOURCES,
    _flatten_readings,
    attach_tooltip_layers,
    collect_extra_readings,
    get_city_surface,
    get_interpolated_surface,
    surface_metric_unit,
    surface_readings_for_metric,
    validate_surface_city,
    validate_surface_metric,
)
from schemas import interpolate_schemas
from services.grid_interpolation_service import (
    SURFACE_METRICS,
    SURFACE_MIN_RESOLUTION,
    krige_surface,
)

CITY = "Houston"
MARKET_CODE = "houston"
DATE = "2024-07-15"

# Every metric the map can display, in the order availableMetrics lists them in
# frontend/src/api/map.ts.
DISPLAYED_METRICS = (
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
)


# --------------------------------------------------------------------------- #
# Fixtures and fakes
# --------------------------------------------------------------------------- #


def spread_points(values, date=DATE):
    """A HeatmapPointsByDate block laid diagonally across Houston's rectangle.

    Readings have to be spread out and distinctly valued or there is no spatial
    structure for a variogram to fit, and kriging degenerates to a flat mean.
    """
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


def readings(values):
    """The same spread, already flattened into kriging input."""
    return _flatten_readings(spread_points(values))


class FakeHeatmapRepository:
    """Records every read the resolver makes; answers from canned blocks.

    Units are not among them: ``surface_metric_unit`` resolves those against
    the real class, so no test can pass by disagreeing with the rule the
    production formatter applies.
    """

    def __init__(self, by_metric=None, local_temperature=None):
        self.by_metric = by_metric or {}
        self.local_temperature = local_temperature or {}
        self.metric_calls = []
        self.local_calls = []

    def getDataPointsForCityDateMetric(self, weather_date, metric, market_code):
        self.metric_calls.append((weather_date, metric, market_code))
        if metric not in self.by_metric:
            # What the real repository does for a name that is not a column.
            raise ValueError(f"Metric {metric!r} is not an available column.")
        return self.by_metric[metric]

    def getLocalTemperatureByCityDate(
        self, weather_date, metric, market_code, temperature_unit
    ):
        self.local_calls.append((weather_date, metric, market_code, temperature_unit))
        return self.local_temperature


@pytest.fixture
def fake_repository(monkeypatch):
    """Install a FakeHeatmapRepository for the routes to construct.

    The routes build their own repository from the session, so the class is
    swapped rather than an instance injected. Returns a callable that installs
    a prepared fake and hands it back.
    """

    def install(**kwargs):
        fake = FakeHeatmapRepository(**kwargs)

        class Stand_in:
            """Stands in for the class, not just the instance.

            The routes name the class to construct it, so a class is what has
            to be swapped in; constructing it hands back the one prepared fake.
            Nothing class-level needs mirroring -- ``surface_metric_unit``
            resolves units against the real repository, not this stand-in.
            """

            def __new__(cls, _db):
                return fake

        monkeypatch.setattr(grid_interpolation, "HeatmapRepository", Stand_in)
        return fake

    return install


@pytest.fixture(autouse=True)
def clear_surface_cache():
    """The GET route memoizes responses; leaking one would mask the next test."""
    grid_interpolation._SURFACE_CACHE.clear()
    yield
    grid_interpolation._SURFACE_CACHE.clear()


# --------------------------------------------------------------------------- #
# Which metrics get a surface
# --------------------------------------------------------------------------- #


def test_only_the_per_poi_metrics_keep_the_density_heatmap():
    """Two metrics are excluded, both for the same reason.

    avg_daily_visits and heat_risk_score are per-POI records rather than
    samples of a field that exists between the POIs -- a footfall count, and a
    score carrying its POI's name, brand and address. Interpolating either
    would invent a value for empty ground.
    """
    assert SURFACE_METRICS == set(DISPLAYED_METRICS) - {
        "avg_daily_visits",
        "heat_risk_score",
    }


@pytest.mark.parametrize("metric", sorted(SURFACE_METRICS))
def test_a_surface_metric_passes_validation(metric):
    assert validate_surface_metric(metric) is None


@pytest.mark.parametrize("metric", ["avg_daily_visits", "heat_risk_score", "nonsense"])
def test_a_non_surface_metric_is_rejected_with_a_400(metric):
    with pytest.raises(HTTPException) as raised:
        validate_surface_metric(metric)

    assert raised.value.status_code == 400
    assert "metric_key must be one of" in raised.value.detail


@pytest.mark.parametrize("city", ["Houston", "houston", "nyc", "new_york_nj", None, ""])
def test_a_known_city_or_no_city_passes_validation(city):
    assert validate_surface_city(city) is None


def test_an_unknown_city_is_rejected_rather_than_widening_the_surface():
    """Falling back to the readings' bounding box would draw a surface well
    past the city, which is the behaviour the city extent exists to prevent."""
    with pytest.raises(HTTPException) as raised:
        validate_surface_city("Atlantis")

    assert raised.value.status_code == 400
    assert "Unknown city" in raised.value.detail


# --------------------------------------------------------------------------- #
# _flatten_readings
# --------------------------------------------------------------------------- #


class TestFlattenReadings:
    def test_a_point_becomes_longitude_latitude_value(self):
        block = {DATE: [{"value": 28.5, "location_coordinates": [-95.4, 29.7]}]}

        assert _flatten_readings(block) == [
            {"longitude": -95.4, "latitude": 29.7, "value": 28.5}
        ]

    def test_every_date_in_the_block_is_flattened_together(self):
        block = {
            "2024-07-15": [{"value": 1.0, "location_coordinates": [-95.0, 29.0]}],
            "2024-07-16": [{"value": 2.0, "location_coordinates": [-95.1, 29.1]}],
        }

        assert sorted(r["value"] for r in _flatten_readings(block)) == [1.0, 2.0]

    def test_a_point_with_no_value_is_dropped(self):
        """A NULL column is a point with nothing to interpolate, not a zero."""
        block = {
            DATE: [
                {"value": 28.0, "location_coordinates": [-95.4, 29.7]},
                {"value": None, "location_coordinates": [-95.5, 29.8]},
            ]
        }

        assert [r["value"] for r in _flatten_readings(block)] == [28.0]

    def test_a_zero_reading_is_kept(self):
        """change_in_temperature is all zeros until an intervention is placed."""
        block = {DATE: [{"value": 0, "location_coordinates": [-95.4, 29.7]}]}

        assert [r["value"] for r in _flatten_readings(block)] == [0]

    def test_an_empty_block_flattens_to_nothing(self):
        assert _flatten_readings({}) == []


# --------------------------------------------------------------------------- #
# surface_metric_unit
# --------------------------------------------------------------------------- #


class TestSurfaceMetricUnit:
    """The suffix an interpolated tooltip row carries.

    It has to match what the heatmap repository stamps on a *measured* value,
    or replacing a measured row with an interpolated one would change how the
    row reads.
    """

    @pytest.mark.parametrize(
        "metric, unit",
        [
            ("average_temperature_c", "°C"),
            ("maximum_temperature_c", "°C"),
            ("average_relative_humidity_pct", "%"),
            ("average_wind_speed_knots", " kn"),
            ("precipitation_3d_sum_mm", " mm"),
            ("average_dew_point_f", "°F"),
            ("heat_index_f", "°F"),
            ("heat_index_c", "°C"),
        ],
    )
    def test_a_metric_carries_the_repository_s_own_suffix(self, metric, unit):
        assert surface_metric_unit(metric) == unit

    @pytest.mark.parametrize(
        "metric, unit",
        [("local_temperature_c", "°C"), ("local_temperature_f", "°F")],
    )
    def test_local_temperature_beats_the_broader_hints(self, metric, unit):
        """``_index`` and ``temp`` would both otherwise swallow these two and
        stamp the wrong unit. The trailing _c/_f is read before any hint."""
        assert surface_metric_unit(metric) == unit

    @pytest.mark.parametrize("metric", sorted(SURFACE_METRICS))
    def test_no_surface_metric_is_stamped_a_unit_it_is_not_in(self, metric):
        """Every metric that gets a surface, against what its name says it is.

        A wrong unit here is worse than none: the number is never converted, so
        a renamed unit misreports the reading rather than just labelling it
        vaguely.
        """
        expected = {
            "average_temperature_c": "°C",
            "average_temperature_f": "°F",
            "heat_index_c": "°C",
            "heat_index_f": "°F",
            "average_relative_humidity_pct": "%",
            "change_in_temperature": "°C",
            "change_in_average_temperature_c": "°C",
            "change_in_average_temperature_f": "°F",
            "change_in_local_temperature_c": "°C",
            "change_in_local_temperature_f": "°F",
            "local_temperature_c": "°C",
            "local_temperature_f": "°F",
        }

        assert surface_metric_unit(metric) == expected[metric]

    def test_an_unhinted_metric_has_no_suffix(self):
        assert surface_metric_unit("some_unitless_metric") == ""

    def test_the_lookup_is_case_insensitive(self):
        assert surface_metric_unit("Average_Temperature_C") == "°C"


# --------------------------------------------------------------------------- #
# surface_readings_for_metric
# --------------------------------------------------------------------------- #


class TestSurfaceReadingsForMetric:
    def test_a_plain_metric_is_read_by_name_under_the_market_code(self):
        """The weather and heat-index caches are keyed on the market code, not
        on the display name the frontend sends."""
        repository = FakeHeatmapRepository(
            by_metric={"average_temperature_c": spread_points([28.0, 31.0, 29.5])}
        )

        result, unit = surface_readings_for_metric(
            "average_temperature_c", CITY, DATE, repository
        )

        assert repository.metric_calls == [
            (DATE, "average_temperature_c", MARKET_CODE)
        ]
        assert repository.local_calls == []
        assert [reading["value"] for reading in result] == [28.0, 31.0, 29.5]
        assert set(result[0]) == {"longitude", "latitude", "value"}
        assert unit == "°C"

    @pytest.mark.parametrize("city", ["Houston", "houston", "HOUSTON", " houston "])
    def test_any_spelling_of_a_city_reads_the_same_market(self, city):
        repository = FakeHeatmapRepository(
            by_metric={"average_temperature_c": spread_points([28.0])}
        )

        surface_readings_for_metric("average_temperature_c", city, DATE, repository)

        assert repository.metric_calls == [
            (DATE, "average_temperature_c", MARKET_CODE)
        ]

    @pytest.mark.parametrize(
        "metric, source_column, temperature_unit, unit",
        [
            ("local_temperature_c", "average_temperature_c", "c", "°C"),
            ("local_temperature_f", "average_temperature_f", "f", "°F"),
        ],
    )
    def test_local_temperature_uses_its_own_derivation(
        self, metric, source_column, temperature_unit, unit
    ):
        """Local temperature is not a column: it is one market temperature plus
        each point's urban-heat-island offset, so it has its own reader and a
        different source column per unit."""
        repository = FakeHeatmapRepository(
            local_temperature=spread_points([30.0, 33.0, 31.0])
        )

        result, resolved_unit = surface_readings_for_metric(
            metric, CITY, DATE, repository
        )

        assert repository.metric_calls == []  # never read as a plain column
        assert repository.local_calls == [
            (DATE, source_column, MARKET_CODE, temperature_unit)
        ]
        assert len(result) == 3
        assert resolved_unit == unit

    def test_the_local_temperature_source_table_matches_the_reader(self):
        assert LOCAL_TEMPERATURE_SOURCES == {
            "local_temperature_c": ("average_temperature_c", "c"),
            "local_temperature_f": ("average_temperature_f", "f"),
        }

    def test_a_synthetic_delta_metric_reads_through_the_plain_path(self):
        """change_in_* metrics are columns as far as the repository is
        concerned -- it reports them as zero -- so they need no special case."""
        repository = FakeHeatmapRepository(
            by_metric={"change_in_temperature": spread_points([0, 0, 0])}
        )

        result, unit = surface_readings_for_metric(
            "change_in_temperature", CITY, DATE, repository
        )

        assert repository.metric_calls == [(DATE, "change_in_temperature", MARKET_CODE)]
        assert [reading["value"] for reading in result] == [0, 0, 0]
        assert unit == "°C"

    def test_a_metric_with_no_rows_reads_as_no_readings(self):
        repository = FakeHeatmapRepository(by_metric={"average_temperature_c": {}})

        result, _ = surface_readings_for_metric(
            "average_temperature_c", CITY, DATE, repository
        )

        assert result == []

    def test_a_null_reading_never_reaches_the_fit(self):
        block = spread_points([28.0, 31.0])
        block[DATE].append({"value": None, "location_coordinates": [-95.0, 29.0]})
        repository = FakeHeatmapRepository(by_metric={"average_temperature_c": block})

        result, _ = surface_readings_for_metric(
            "average_temperature_c", CITY, DATE, repository
        )

        assert [reading["value"] for reading in result] == [28.0, 31.0]

    def test_a_metric_no_source_owns_raises(self):
        with pytest.raises(ValueError):
            surface_readings_for_metric(
                "not_a_metric", CITY, DATE, FakeHeatmapRepository()
            )


# --------------------------------------------------------------------------- #
# collect_extra_readings
# --------------------------------------------------------------------------- #


class TestCollectExtraReadings:
    """The readings behind the tooltip's secondary rows."""

    def test_each_requested_metric_comes_back_with_its_unit(self):
        repository = FakeHeatmapRepository(
            by_metric={
                "average_relative_humidity_pct": spread_points([55.0, 61.0]),
                "average_wind_speed_knots": spread_points([4.0, 9.0]),
            }
        )

        collected, units = collect_extra_readings(
            ["average_relative_humidity_pct", "average_wind_speed_knots"],
            "average_temperature_c",
            CITY,
            DATE,
            repository,
        )

        assert set(collected) == {
            "average_relative_humidity_pct",
            "average_wind_speed_knots",
        }
        assert units == {
            "average_relative_humidity_pct": "%",
            "average_wind_speed_knots": " kn",
        }
        assert [r["value"] for r in collected["average_wind_speed_knots"]] == [4.0, 9.0]

    def test_the_drawn_metric_is_not_read_a_second_time(self):
        """It is served from the primary lattice by attach_tooltip_layers, so
        reading and fitting it again would be identical work for nothing."""
        repository = FakeHeatmapRepository(
            by_metric={"average_temperature_c": spread_points([28.0, 31.0])}
        )

        collected, units = collect_extra_readings(
            ["average_temperature_c"],
            "average_temperature_c",
            CITY,
            DATE,
            repository,
        )

        assert repository.metric_calls == []
        assert collected == {}
        assert units == {}

    def test_an_unreadable_metric_is_dropped_not_raised(self):
        """A missing tooltip row is a far smaller loss than a missing map."""
        repository = FakeHeatmapRepository(
            by_metric={"average_relative_humidity_pct": spread_points([55.0, 61.0])}
        )

        collected, units = collect_extra_readings(
            ["not_a_metric", "average_relative_humidity_pct"],
            "average_temperature_c",
            CITY,
            DATE,
            repository,
        )

        assert set(collected) == {"average_relative_humidity_pct"}
        assert set(units) == {"average_relative_humidity_pct"}

    def test_a_metric_with_no_rows_is_dropped(self):
        repository = FakeHeatmapRepository(
            by_metric={"average_relative_humidity_pct": {}}
        )

        collected, units = collect_extra_readings(
            ["average_relative_humidity_pct"],
            "average_temperature_c",
            CITY,
            DATE,
            repository,
        )

        assert collected == {}
        assert units == {}

    def test_asking_for_nothing_reads_nothing(self):
        repository = FakeHeatmapRepository()

        assert collect_extra_readings(
            [], "average_temperature_c", CITY, DATE, repository
        ) == ({}, {})
        assert repository.metric_calls == []


# --------------------------------------------------------------------------- #
# attach_tooltip_layers
# --------------------------------------------------------------------------- #


def one_surface(primary, extra_points_by_metric=None):
    """A real kriged surface over Houston, for the assembly tests to finish."""
    return krige_surface(
        readings(primary),
        rows=SURFACE_MIN_RESOLUTION,
        cols=SURFACE_MIN_RESOLUTION,
        city=CITY,
        extra_points_by_metric=extra_points_by_metric,
    )


class TestAttachTooltipLayers:
    def test_each_layer_is_stamped_with_its_unit(self):
        surface = one_surface(
            [28.0, 29.0, 30.0, 31.0],
            {"average_relative_humidity_pct": readings([50.0, 55.0, 60.0, 65.0])},
        )

        attach_tooltip_layers(
            surface,
            "average_temperature_c",
            ["average_relative_humidity_pct"],
            {"average_relative_humidity_pct": "%"},
        )

        assert surface["metrics"]["average_relative_humidity_pct"]["unit"] == "%"

    def test_the_drawn_metric_s_row_is_the_surface_itself(self):
        """Its values are the lattice already computed, not a second fit."""
        surface = one_surface([28.0, 29.0, 30.0, 31.0])

        attach_tooltip_layers(
            surface,
            "average_temperature_c",
            ["average_temperature_c"],
            {},
            primary_unit="°C",
        )

        row = surface["metrics"]["average_temperature_c"]
        assert row["values"] == surface["values"]
        assert row["min"] == surface["min"]
        assert row["max"] == surface["max"]
        assert row["source_count"] == surface["source_count"]
        assert row["variogram_model"] == surface["variogram_model"]
        assert row["unit"] == "°C"

    def test_rows_come_back_in_the_order_they_were_requested(self):
        """The tooltip renders the rows in the order the layers arrive, and the
        caller listed them in the order it wants them read."""
        surface = one_surface(
            [28.0, 29.0, 30.0, 31.0],
            {
                "average_relative_humidity_pct": readings([50.0, 55.0, 60.0, 65.0]),
                "average_wind_speed_knots": readings([3.0, 6.0, 9.0, 12.0]),
            },
        )
        requested = [
            "average_wind_speed_knots",
            "average_temperature_c",
            "average_relative_humidity_pct",
        ]

        attach_tooltip_layers(
            surface,
            "average_temperature_c",
            requested,
            {"average_relative_humidity_pct": "%", "average_wind_speed_knots": " kn"},
            primary_unit="°C",
        )

        assert list(surface["metrics"]) == requested

    def test_a_requested_metric_that_produced_no_lattice_is_omitted(self):
        """Nothing was interpolated for it, so there is no row to show."""
        surface = one_surface([28.0, 29.0, 30.0, 31.0])

        attach_tooltip_layers(
            surface,
            "average_temperature_c",
            ["maximum_temperature_c"],
            {},
        )

        assert surface["metrics"] == {}

    def test_asking_for_no_rows_leaves_no_rows(self):
        surface = one_surface(
            [28.0, 29.0, 30.0, 31.0],
            {"average_relative_humidity_pct": readings([50.0, 55.0, 60.0, 65.0])},
        )

        attach_tooltip_layers(surface, "average_temperature_c", [], {})

        assert surface["metrics"] == {}

    def test_the_surface_is_returned_for_chaining(self):
        surface = one_surface([28.0, 29.0, 30.0, 31.0])

        assert attach_tooltip_layers(surface, "average_temperature_c", [], {}) is surface


# --------------------------------------------------------------------------- #
# krige_surface, where a route depends on a specific behaviour
# --------------------------------------------------------------------------- #


class TestKrigeSurfaceBehaviourTheRoutesRelyOn:
    def test_a_surface_spans_exactly_the_city_rectangle(self):
        """The lattice, the readings that feed it and the drawn image are all
        the same rectangle, so every cell carries a real value."""
        surface = one_surface([28.0, 29.0, 30.0, 31.0])

        assert surface["bounds"] == get_city_bounds(CITY)
        assert surface["city"] == CITY
        assert len(surface["values"]) == surface["rows"]
        assert all(len(row) == surface["cols"] for row in surface["values"])

    def test_a_flat_field_krige_to_a_flat_surface(self):
        """change_in_temperature is all zeros until an intervention is placed.
        That is a legitimate input and must not raise on an unfittable
        variogram."""
        surface = one_surface([0.0, 0.0, 0.0, 0.0])

        assert surface["variogram_model"] == "constant"
        assert surface["min"] == surface["max"] == 0.0
        assert all(value == 0.0 for row in surface["values"] for value in row)

    def test_a_secondary_metric_lands_on_the_same_lattice(self):
        """The tooltip reads it with the same sampler as the drawn surface, so
        the two have to share rows, cols and bounds exactly."""
        surface = one_surface(
            [28.0, 29.0, 30.0, 31.0],
            {"average_relative_humidity_pct": readings([50.0, 55.0, 60.0, 65.0])},
        )

        layer = surface["metrics"]["average_relative_humidity_pct"]
        assert len(layer["values"]) == surface["rows"]
        assert all(len(row) == surface["cols"] for row in layer["values"])
        assert layer["source_count"] == 4

    def test_a_secondary_metric_with_too_few_readings_is_skipped(self):
        """Ordinary kriging needs two distinct observations; one row cannot fit
        a variogram, and losing that row must not fail the whole surface."""
        surface = one_surface(
            [28.0, 29.0, 30.0, 31.0],
            {"average_relative_humidity_pct": readings([55.0])},
        )

        assert "average_relative_humidity_pct" not in surface["metrics"]
        assert surface["values"]  # the drawn surface survived

    def test_readings_outside_the_city_do_not_feed_the_fit(self):
        """A city's surface is fitted on that city's readings alone, so a
        neighbouring city's heat pattern cannot influence it."""
        inside = readings([28.0, 29.0, 30.0, 31.0])
        outside = [{"longitude": -80.0, "latitude": 25.0, "value": 99.0}]

        surface = krige_surface(
            inside + outside,
            rows=SURFACE_MIN_RESOLUTION,
            cols=SURFACE_MIN_RESOLUTION,
            city=CITY,
        )

        assert surface["source_count"] == len(inside)
        assert surface["max"] < 99.0

    def test_no_readings_at_all_raises(self):
        with pytest.raises(ValueError):
            krige_surface([], rows=8, cols=8, city=CITY)


# --------------------------------------------------------------------------- #
# GET /grid_interpolation/surface
# --------------------------------------------------------------------------- #


def get_surface(db=None, **kwargs):
    """Call the GET route, which is async, and return its response dict."""
    parameters = {
        "city": CITY,
        "date": DATE,
        "metric_key": "average_temperature_c",
        "rows": SURFACE_MIN_RESOLUTION,
        "cols": SURFACE_MIN_RESOLUTION,
        "additional_metrics": None,
        "db": db,
        **kwargs,
    }
    return asyncio.run(get_city_surface(**parameters))


class TestGetCitySurfaceRoute:
    def test_it_returns_the_lattice_for_the_named_city_metric_and_date(
        self, fake_repository
    ):
        fake_repository(
            by_metric={"average_temperature_c": spread_points([28.0, 29.0, 30.0, 31.0])}
        )

        response = get_surface()

        assert response["metric_key"] == "average_temperature_c"
        assert response["city"] == CITY
        assert response["bounds"] == get_city_bounds(CITY)
        assert response["source_count"] == 4
        assert 28.0 <= response["min"] <= response["max"] <= 31.0
        assert len(response["values"]) == response["rows"]

    def test_the_drawn_metric_is_read_by_name_for_the_city_s_market(
        self, fake_repository
    ):
        repository = fake_repository(
            by_metric={"average_temperature_c": spread_points([28.0, 29.0, 30.0, 31.0])}
        )

        get_surface()

        assert repository.metric_calls == [
            (DATE, "average_temperature_c", MARKET_CODE)
        ]

    def test_additional_metrics_arrive_as_tooltip_rows_in_order(self, fake_repository):
        fake_repository(
            by_metric={
                "average_temperature_c": spread_points([28.0, 29.0, 30.0, 31.0]),
                "average_relative_humidity_pct": spread_points([50.0, 55.0, 60.0, 65.0]),
            }
        )

        response = get_surface(
            additional_metrics=[
                "average_relative_humidity_pct",
                "average_temperature_c",
            ]
        )

        assert list(response["metrics"]) == [
            "average_relative_humidity_pct",
            "average_temperature_c",
        ]
        assert response["metrics"]["average_relative_humidity_pct"]["unit"] == "%"
        # The drawn metric's row is the surface itself.
        assert response["metrics"]["average_temperature_c"]["values"] == response["values"]
        assert response["metrics"]["average_temperature_c"]["unit"] == "°C"

    def test_a_duplicated_additional_metric_yields_one_row(self, fake_repository):
        fake_repository(
            by_metric={
                "average_temperature_c": spread_points([28.0, 29.0, 30.0, 31.0]),
                "average_relative_humidity_pct": spread_points([50.0, 55.0, 60.0, 65.0]),
            }
        )

        response = get_surface(
            additional_metrics=[
                "average_relative_humidity_pct",
                "average_relative_humidity_pct",
            ]
        )

        assert list(response["metrics"]) == ["average_relative_humidity_pct"]

    def test_a_blank_additional_metric_is_ignored(self, fake_repository):
        fake_repository(
            by_metric={"average_temperature_c": spread_points([28.0, 29.0, 30.0, 31.0])}
        )

        response = get_surface(additional_metrics=["  ", ""])

        assert response["metrics"] == {}

    def test_no_readings_for_the_day_is_a_404(self, fake_repository):
        fake_repository(by_metric={"average_temperature_c": {}})

        with pytest.raises(HTTPException) as raised:
            get_surface()

        assert raised.value.status_code == 404
        assert CITY in raised.value.detail

    def test_a_metric_with_no_surface_is_a_400(self, fake_repository):
        fake_repository()

        with pytest.raises(HTTPException) as raised:
            get_surface(metric_key="avg_daily_visits")

        assert raised.value.status_code == 400

    def test_an_unknown_city_is_a_400(self, fake_repository):
        fake_repository()

        with pytest.raises(HTTPException) as raised:
            get_surface(city="Atlantis")

        assert raised.value.status_code == 400

    def test_an_oversized_lattice_is_a_400(self, fake_repository):
        """Kriging cost grows with the number of predicted cells, so the
        request is refused rather than served slowly."""
        fake_repository(
            by_metric={"average_temperature_c": spread_points([28.0, 29.0, 30.0, 31.0])}
        )

        with pytest.raises(HTTPException) as raised:
            get_surface(rows=1000, cols=1000)

        assert raised.value.status_code == 400
        assert "rows * cols" in raised.value.detail

    def test_an_identical_request_is_served_from_the_cache(self, fake_repository):
        """Readings come from an immutable startup cache, so the same query
        always yields the same surface and need only be kriged once."""
        repository = fake_repository(
            by_metric={"average_temperature_c": spread_points([28.0, 29.0, 30.0, 31.0])}
        )

        first = get_surface()
        second = get_surface()

        assert second is first
        assert len(repository.metric_calls) == 1

    def test_a_different_date_is_not_served_from_the_cache(self, fake_repository):
        repository = fake_repository(
            by_metric={
                "average_temperature_c": {
                    DATE: spread_points([28.0, 29.0, 30.0, 31.0])[DATE],
                    "2024-07-16": spread_points([20.0, 21.0, 22.0, 23.0], "2024-07-16")[
                        "2024-07-16"
                    ],
                }
            }
        )

        get_surface()
        get_surface(date="2024-07-16")

        assert len(repository.metric_calls) == 2

    def test_a_city_alias_and_its_display_name_share_one_cache_entry(
        self, fake_repository
    ):
        """The key is the resolved city, so "houston" and "Houston" are one
        request rather than two identical fits."""
        repository = fake_repository(
            by_metric={"average_temperature_c": spread_points([28.0, 29.0, 30.0, 31.0])}
        )

        get_surface(city="Houston")
        get_surface(city="houston")

        assert len(repository.metric_calls) == 1

    def test_local_temperature_is_served_through_its_own_reader(self, fake_repository):
        repository = fake_repository(
            local_temperature=spread_points([30.0, 32.0, 34.0, 36.0])
        )

        response = get_surface(metric_key="local_temperature_c")

        assert repository.local_calls == [
            (DATE, "average_temperature_c", MARKET_CODE, "c")
        ]
        assert response["metric_key"] == "local_temperature_c"
        assert response["source_count"] == 4


# --------------------------------------------------------------------------- #
# POST /grid_interpolation/surface
# --------------------------------------------------------------------------- #


def post_surface(db=None, **fields):
    """Call the POST route with a SurfaceRequest built from `fields`."""
    payload = interpolate_schemas.SurfaceRequest(
        metric_key="change_in_temperature",
        city=CITY,
        rows=SURFACE_MIN_RESOLUTION,
        cols=SURFACE_MIN_RESOLUTION,
        **fields,
    )
    return asyncio.run(get_interpolated_surface(payload, db))


def simulated_points(values):
    """Client-supplied readings, in the shape SurfaceRequest takes."""
    return [
        {
            "longitude": reading["longitude"],
            "latitude": reading["latitude"],
            "value": reading["value"],
        }
        for reading in readings(values)
    ]


class TestInterpolatedSurfaceRoute:
    """The simulation path: readings that exist only in the browser."""

    def test_it_kriges_the_posted_readings(self, fake_repository):
        fake_repository()

        response = post_surface(points=simulated_points([-2.0, -1.0, 1.0, 2.0]))

        assert response["metric_key"] == "change_in_temperature"
        assert response["city"] == CITY
        assert response["source_count"] == 4
        assert -2.5 <= response["min"] <= response["max"] <= 2.5

    def test_empty_points_are_a_400(self, fake_repository):
        fake_repository()

        with pytest.raises(HTTPException) as raised:
            post_surface(points=[])

        assert raised.value.status_code == 400
        assert "points cannot be empty" in raised.value.detail

    def test_malformed_bounds_are_a_400(self, fake_repository):
        fake_repository()

        with pytest.raises(HTTPException) as raised:
            post_surface(
                points=simulated_points([-2.0, -1.0, 1.0, 2.0]), bounds=[0.0, 1.0]
            )

        assert raised.value.status_code == 400
        assert "bounds must be" in raised.value.detail

    def test_an_oversized_lattice_is_a_400(self, fake_repository):
        fake_repository()

        with pytest.raises(HTTPException) as raised:
            payload = interpolate_schemas.SurfaceRequest(
                metric_key="change_in_temperature",
                city=CITY,
                rows=1000,
                cols=1000,
                points=simulated_points([-2.0, -1.0, 1.0, 2.0]),
            )
            asyncio.run(get_interpolated_surface(payload, None))

        assert raised.value.status_code == 400

    def test_secondary_rows_are_read_server_side_for_the_city_and_date(
        self, fake_repository
    ):
        """A simulation only alters the drawn metric, so the other rows come
        from storage rather than travelling up with the points."""
        repository = fake_repository(
            by_metric={
                "average_relative_humidity_pct": spread_points([50.0, 55.0, 60.0, 65.0])
            }
        )

        response = post_surface(
            points=simulated_points([-2.0, -1.0, 1.0, 2.0]),
            date=DATE,
            additional_metrics=["average_relative_humidity_pct"],
        )

        assert repository.metric_calls == [
            (DATE, "average_relative_humidity_pct", MARKET_CODE)
        ]
        assert list(response["metrics"]) == ["average_relative_humidity_pct"]
        assert response["metrics"]["average_relative_humidity_pct"]["unit"] == "%"

    def test_the_drawn_metric_s_row_reports_the_simulated_lattice(
        self, fake_repository
    ):
        """Hovering during a run has to show the simulated value, not the
        stored one."""
        repository = fake_repository()

        response = post_surface(
            points=simulated_points([-2.0, -1.0, 1.0, 2.0]),
            date=DATE,
            additional_metrics=["change_in_temperature"],
        )

        # Never read from storage: it is the posted lattice.
        assert repository.metric_calls == []
        row = response["metrics"]["change_in_temperature"]
        assert row["values"] == response["values"]
        assert row["unit"] == "°C"

    def test_additional_metrics_without_a_date_are_skipped(self, fake_repository):
        """There is nothing to read them for, and the surface still stands."""
        repository = fake_repository(
            by_metric={
                "average_relative_humidity_pct": spread_points([50.0, 55.0, 60.0, 65.0])
            }
        )

        response = post_surface(
            points=simulated_points([-2.0, -1.0, 1.0, 2.0]),
            additional_metrics=["average_relative_humidity_pct"],
        )

        assert repository.metric_calls == []
        assert response["metrics"] == {}
        assert response["values"]

    def test_a_metric_with_no_surface_is_a_400(self, fake_repository):
        fake_repository()

        with pytest.raises(HTTPException) as raised:
            payload = interpolate_schemas.SurfaceRequest(
                metric_key="avg_daily_visits",
                city=CITY,
                points=simulated_points([1.0, 2.0]),
            )
            asyncio.run(get_interpolated_surface(payload, None))

        assert raised.value.status_code == 400

    def test_the_request_defaults_need_only_points(self):
        """date and additional_metrics are optional: the plain simulation call
        sends neither."""
        payload = interpolate_schemas.SurfaceRequest(points=simulated_points([1.0, 2.0]))

        assert payload.date is None
        assert payload.additional_metrics is None
        assert payload.city is None
        assert payload.boundary_buffer_deg == 0.0
