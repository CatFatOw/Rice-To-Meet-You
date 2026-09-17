"""``services/grid_interpolation_service.py`` — kriging for map surfaces.

Both ``/grid_interpolation/surface`` routes end in ``krige_surface``. The route
tests in ``test_grid_interpolation_surface.py`` exercise it only where a route
depends on it; this file covers the pieces underneath:

* ``surface_bounds``         — the extent when no city is given
* ``subsample_points``       — the cost bound on the fit
* ``points_inside_city``     — which readings feed a city's fit
* ``_krige_values``          — variogram selection, the flat-field short cut and
                               the overshoot clamp
* ``krige_surface``          — lattice geometry the raster renderer relies on

Where the assertion is about *which* model was chosen or *where* the lattice
sits, ``_fit_and_execute`` is replaced with a stub so the test states its own
fitted values instead of depending on pykrige's numerics. A handful of tests run
the real fit to pin behaviour that only the real fit can show.
"""

from __future__ import annotations

import numpy as np
import pytest

from data.city_boundaries import get_city_bounds
from schemas.interpolate_schemas import SurfaceResponse
from services import grid_interpolation_service as service
from services.grid_interpolation_service import (
    SURFACE_BOUNDS_PADDING,
    SURFACE_MAX_FIT_POINTS,
    SURFACE_MAX_RESOLUTION,
    SURFACE_MIN_RESOLUTION,
    SURFACE_MIN_SPAN,
    SURFACE_OVERSHOOT_MARGIN,
    SURFACE_VARIOGRAM_MODELS,
    _krige_values,
    krige_surface,
    points_inside_city,
    subsample_points,
    surface_bounds,
)

CITY = "Houston"


def reading(longitude, latitude, value):
    return {"longitude": longitude, "latitude": latitude, "value": value}


def inside_houston(values):
    """Readings spread diagonally across Houston's rectangle, one per value."""
    min_lon, min_lat, max_lon, max_lat = get_city_bounds(CITY)
    span = len(values) - 1 or 1
    return [
        reading(
            min_lon + (max_lon - min_lon) * index / span,
            min_lat + (max_lat - min_lat) * index / span,
            value,
        )
        for index, value in enumerate(values)
    ]


class FitRecorder:
    """Stands in for ``_fit_and_execute``.

    ``by_model`` maps a variogram model to either an exception to raise or a
    callable ``(target_lons, target_lats) -> values``. Every call is recorded,
    so a test can say which models were tried, in which order, on which
    lattice.
    """

    def __init__(self, by_model):
        self.by_model = by_model
        self.calls = []

    def __call__(self, x, y, z, target_lons, target_lats, model):
        self.calls.append(
            {"model": model, "x": x, "y": y, "z": z, "lons": target_lons, "lats": target_lats}
        )
        outcome = self.by_model[model]
        if isinstance(outcome, Exception):
            raise outcome
        values = np.asarray(outcome(target_lons, target_lats), dtype=float)
        return values, np.full(values.shape, 0.5)

    @property
    def models(self):
        return [call["model"] for call in self.calls]


def lattice(value_fn):
    """A fit outcome whose value at each cell is ``value_fn(lon, lat)``."""
    return lambda lons, lats: [[value_fn(lon, lat) for lon in lons] for lat in lats]


def constant(value):
    return lattice(lambda lon, lat: value)


@pytest.fixture
def stub_fit(monkeypatch):
    def install(by_model):
        recorder = FitRecorder(by_model)
        monkeypatch.setattr(service, "_fit_and_execute", recorder)
        return recorder

    return install


# --------------------------------------------------------------------------- #
# surface_bounds
# --------------------------------------------------------------------------- #


class TestSurfaceBounds:
    def test_the_bounding_box_is_padded_by_a_fraction_of_its_span(self):
        points = [reading(-96.0, 29.0, 1.0), reading(-95.0, 30.0, 2.0)]

        pad = 1.0 * SURFACE_BOUNDS_PADDING
        assert surface_bounds(points) == pytest.approx(
            [-96.0 - pad, 29.0 - pad, -95.0 + pad, 30.0 + pad]
        )

    def test_each_axis_is_padded_by_its_own_span(self):
        points = [reading(-96.0, 29.0, 1.0), reading(-94.0, 29.5, 2.0)]

        min_lon, min_lat, max_lon, max_lat = surface_bounds(points)

        assert max_lon - min_lon == pytest.approx(2.0 * (1 + 2 * SURFACE_BOUNDS_PADDING))
        assert max_lat - min_lat == pytest.approx(0.5 * (1 + 2 * SURFACE_BOUNDS_PADDING))

    def test_a_single_reading_gets_a_minimum_span_centred_on_it(self):
        """A zero-width box would give a lattice with zero-width cells."""
        min_lon, min_lat, max_lon, max_lat = surface_bounds([reading(-95.0, 29.0, 1.0)])

        padded_span = SURFACE_MIN_SPAN * (1 + 2 * SURFACE_BOUNDS_PADDING)
        assert max_lon - min_lon == pytest.approx(padded_span)
        assert max_lat - min_lat == pytest.approx(padded_span)
        assert (min_lon + max_lon) / 2 == pytest.approx(-95.0)
        assert (min_lat + max_lat) / 2 == pytest.approx(29.0)

    def test_readings_sharing_a_latitude_widen_that_axis_symmetrically(self):
        points = [reading(-96.0, 29.0, 1.0), reading(-95.0, 29.0, 2.0)]

        _, min_lat, _, max_lat = surface_bounds(points)

        assert (min_lat + max_lat) / 2 == pytest.approx(29.0)
        assert max_lat - min_lat == pytest.approx(
            SURFACE_MIN_SPAN * (1 + 2 * SURFACE_BOUNDS_PADDING)
        )

    def test_string_coordinates_are_accepted(self):
        points = [reading("-96.0", "29.0", 1.0), reading("-95.0", "30.0", 2.0)]

        assert surface_bounds(points)[0] == pytest.approx(-96.0 - SURFACE_BOUNDS_PADDING)


# --------------------------------------------------------------------------- #
# subsample_points
# --------------------------------------------------------------------------- #


class TestSubsamplePoints:
    def test_readings_under_the_limit_are_returned_untouched(self):
        points = [reading(0.0, 0.0, float(i)) for i in range(10)]

        assert subsample_points(points, max_points=10) is points

    def test_readings_over_the_limit_are_thinned_to_exactly_the_limit(self):
        points = [reading(0.0, 0.0, float(i)) for i in range(50)]

        assert len(subsample_points(points, max_points=20)) == 20

    def test_the_default_limit_is_the_fit_ceiling(self):
        points = [reading(0.0, 0.0, float(i)) for i in range(SURFACE_MAX_FIT_POINTS + 1)]

        assert len(subsample_points(points)) == SURFACE_MAX_FIT_POINTS

    def test_survivors_keep_their_input_order_and_values(self):
        """Readings are dropped whole, not averaged, so every survivor is an
        original reading and the peaks survive intact."""
        points = [reading(0.0, 0.0, float(i)) for i in range(50)]

        kept = subsample_points(points, max_points=20)

        values = [point["value"] for point in kept]
        assert values == sorted(values)
        assert all(point in points for point in kept)
        assert len({point["value"] for point in kept}) == 20

    def test_the_same_readings_thin_the_same_way_every_time(self):
        """Seeded, so repeated requests for the same data return the same
        surface."""
        points = [reading(0.0, 0.0, float(i)) for i in range(50)]

        assert subsample_points(points, max_points=20) == subsample_points(
            points, max_points=20
        )

    def test_a_different_seed_thins_differently(self):
        points = [reading(0.0, 0.0, float(i)) for i in range(50)]

        assert subsample_points(points, max_points=20, seed=0) != subsample_points(
            points, max_points=20, seed=1
        )


# --------------------------------------------------------------------------- #
# points_inside_city
# --------------------------------------------------------------------------- #


class TestPointsInsideCity:
    def test_only_readings_inside_the_rectangle_are_kept(self):
        inside = reading(-95.37, 29.76, 1.0)
        outside = reading(-80.19, 25.76, 2.0)  # Miami

        assert points_inside_city([inside, outside], CITY) == [inside]

    def test_the_rectangle_edges_are_inclusive(self):
        min_lon, min_lat, max_lon, max_lat = get_city_bounds(CITY)
        corners = [
            reading(min_lon, min_lat, 1.0),
            reading(max_lon, max_lat, 2.0),
        ]

        assert points_inside_city(corners, CITY) == corners

    def test_a_buffer_widens_the_rectangle_on_every_side(self):
        min_lon, min_lat, max_lon, max_lat = get_city_bounds(CITY)
        just_west = reading(min_lon - 0.05, (min_lat + max_lat) / 2, 1.0)
        just_north = reading((min_lon + max_lon) / 2, max_lat + 0.05, 2.0)

        assert points_inside_city([just_west, just_north], CITY) == []
        assert points_inside_city([just_west, just_north], CITY, buffer_deg=0.1) == [
            just_west,
            just_north,
        ]

    def test_any_spelling_of_the_city_uses_the_same_rectangle(self):
        inside = reading(-95.37, 29.76, 1.0)

        assert points_inside_city([inside], "houston") == [inside]

    @pytest.mark.parametrize("city", [None, "", "Atlantis"])
    def test_an_unknown_or_missing_city_keeps_every_reading(self, city):
        points = [reading(-95.37, 29.76, 1.0), reading(-80.19, 25.76, 2.0)]

        result = points_inside_city(points, city)

        assert result == points
        assert result is not points  # a new list, safe for the caller to thin

    def test_no_readings_gives_no_readings(self):
        assert points_inside_city([], CITY) == []


# --------------------------------------------------------------------------- #
# _krige_values
# --------------------------------------------------------------------------- #


LONS = np.array([0.5, 1.5, 2.5])
LATS = np.array([0.5, 1.5])


def krige(z, variogram_model=None):
    """``_krige_values`` on a 2x3 lattice; coordinates only matter to the stub."""
    z = np.asarray(z, dtype=float)
    x = np.arange(len(z), dtype=float)
    return _krige_values(
        x, x, z, LONS, LATS, rows=len(LATS), cols=len(LONS), variogram_model=variogram_model
    )


class TestKrigeValues:
    def test_a_flat_field_is_a_constant_lattice_without_a_fit(self, stub_fit):
        recorder = stub_fit({})

        values, variance, model = krige([4.0, 4.0, 4.0])

        assert model == "constant"
        assert values.tolist() == [[4.0, 4.0, 4.0], [4.0, 4.0, 4.0]]
        assert variance.tolist() == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        assert recorder.calls == []

    def test_a_single_reading_is_a_constant_lattice(self, stub_fit):
        stub_fit({})

        values, _, model = krige([7.5])

        assert model == "constant"
        assert values.shape == (2, 3)
        assert np.all(values == 7.5)

    def test_the_first_model_with_real_structure_is_accepted(self, stub_fit):
        recorder = stub_fit(
            {model: lattice(lambda lon, lat: lon * 10) for model in SURFACE_VARIOGRAM_MODELS}
        )

        values, _, model = krige([0.0, 10.0, 20.0])

        assert model == SURFACE_VARIOGRAM_MODELS[0] == "spherical"
        assert recorder.models == ["spherical"]
        assert values.tolist() == [[5.0, 15.0, 25.0], [5.0, 15.0, 25.0]]

    def test_a_flat_degenerate_fit_is_rejected_for_the_next_model(self, stub_fit):
        """A variogram that fits badly returns the global mean everywhere
        rather than raising, so a flat result means try again."""
        recorder = stub_fit(
            {
                "spherical": constant(10.0),
                "exponential": lattice(lambda lon, lat: lon * 10),
                "power": lattice(lambda lon, lat: lat),
            }
        )

        values, _, model = krige([0.0, 10.0, 20.0])

        assert model == "exponential"
        assert recorder.models == ["spherical", "exponential"]
        assert values[0].tolist() == [5.0, 15.0, 25.0]

    def test_a_model_that_raises_is_skipped(self, stub_fit):
        recorder = stub_fit(
            {
                "spherical": np.linalg.LinAlgError("singular matrix"),
                "exponential": lattice(lambda lon, lat: lon * 10),
                "power": lattice(lambda lon, lat: lat),
            }
        )

        _, _, model = krige([0.0, 10.0, 20.0])

        assert model == "exponential"
        assert recorder.models == ["spherical", "exponential"]

    def test_when_every_model_is_degenerate_the_last_fit_is_kept(self, stub_fit):
        recorder = stub_fit({model: constant(10.0) for model in SURFACE_VARIOGRAM_MODELS})

        values, _, model = krige([0.0, 10.0, 20.0])

        assert model == SURFACE_VARIOGRAM_MODELS[-1]
        assert recorder.models == list(SURFACE_VARIOGRAM_MODELS)
        assert np.all(values == 10.0)

    def test_when_every_model_raises_it_is_a_value_error(self, stub_fit):
        stub_fit({model: RuntimeError("boom") for model in SURFACE_VARIOGRAM_MODELS})

        with pytest.raises(ValueError, match="Kriging failed for every variogram model"):
            krige([0.0, 10.0, 20.0])

    def test_a_named_model_is_the_only_one_tried(self, stub_fit):
        recorder = stub_fit({"power": constant(10.0)})

        _, _, model = krige([0.0, 10.0, 20.0], variogram_model="power")

        assert model == "power"
        assert recorder.models == ["power"]

    def test_an_overshooting_fit_is_clamped_to_the_widened_observed_range(self, stub_fit):
        """Observed 0..20, so the clamp is 20 * 25% = 5 beyond either end."""
        stub_fit(
            {
                "spherical": lambda lons, lats: [[-1000.0, 10.0, 1000.0], [-3.0, 12.0, 24.0]],
            }
        )

        values, _, _ = krige([0.0, 10.0, 20.0])

        margin = 20.0 * SURFACE_OVERSHOOT_MARGIN
        assert values.tolist() == [[-margin, 10.0, 20.0 + margin], [-3.0, 12.0, 24.0]]


# --------------------------------------------------------------------------- #
# krige_surface — lattice geometry
# --------------------------------------------------------------------------- #


def north_gradient(lon, lat):
    return lat


class TestKrigeSurfaceLattice:
    def test_cells_are_sampled_at_their_centroids(self, stub_fit):
        """Values describe cell centres, not corners: an 8-degree extent split
        into 8 cells is sampled at 0.5, 1.5, ... 7.5."""
        recorder = stub_fit({"spherical": lattice(north_gradient)})

        krige_surface(
            [reading(0.0, 0.0, 0.0), reading(8.0, 8.0, 8.0)],
            rows=8,
            cols=8,
            bounds=[0.0, 0.0, 8.0, 8.0],
        )

        expected = [0.5 + i for i in range(8)]
        assert recorder.calls[0]["lons"].tolist() == expected
        assert recorder.calls[0]["lats"].tolist() == expected

    def test_row_zero_is_the_southern_edge(self, stub_fit):
        """The raster renderer draws values[0] at the bottom of the image."""
        stub_fit({"spherical": lattice(north_gradient)})

        surface = krige_surface(
            [reading(0.0, 0.0, 0.0), reading(8.0, 8.0, 8.0)],
            rows=8,
            cols=8,
            bounds=[0.0, 0.0, 8.0, 8.0],
        )

        assert surface["values"][0] == [0.5] * 8
        assert surface["values"][-1] == [7.5] * 8

    def test_column_zero_is_the_western_edge(self, stub_fit):
        stub_fit({"spherical": lattice(lambda lon, lat: lon)})

        surface = krige_surface(
            [reading(0.0, 0.0, 0.0), reading(8.0, 8.0, 8.0)],
            rows=8,
            cols=8,
            bounds=[0.0, 0.0, 8.0, 8.0],
        )

        assert [row[0] for row in surface["values"]] == [0.5] * 8
        assert [row[-1] for row in surface["values"]] == [7.5] * 8

    def test_the_real_fit_puts_the_warm_south_in_row_zero(self):
        """Same orientation, through pykrige rather than a stub: readings
        cooling from south to north must leave the warmest row first."""
        min_lon, min_lat, max_lon, max_lat = get_city_bounds(CITY)
        points = [
            reading(
                min_lon + (max_lon - min_lon) * col / 4,
                min_lat + (max_lat - min_lat) * row / 4,
                40.0 - 2.0 * row,
            )
            for row in range(5)
            for col in range(5)
        ]

        surface = krige_surface(points, rows=8, cols=8, city=CITY)

        row_means = [sum(row) / len(row) for row in surface["values"]]
        assert row_means == sorted(row_means, reverse=True)
        assert row_means[0] > row_means[-1] + 4.0

    @pytest.mark.parametrize(
        "requested, clamped",
        [
            (1, SURFACE_MIN_RESOLUTION),
            (SURFACE_MIN_RESOLUTION, SURFACE_MIN_RESOLUTION),
            (20, 20),
            (SURFACE_MAX_RESOLUTION + 50, SURFACE_MAX_RESOLUTION),
        ],
    )
    def test_resolution_is_clamped_to_the_supported_range(self, stub_fit, requested, clamped):
        stub_fit({"spherical": lattice(north_gradient)})

        surface = krige_surface(
            [reading(0.0, 0.0, 0.0), reading(8.0, 8.0, 8.0)],
            rows=requested,
            cols=requested,
            bounds=[0.0, 0.0, 8.0, 8.0],
        )

        assert surface["rows"] == surface["cols"] == clamped
        assert len(surface["values"]) == clamped
        assert all(len(row) == clamped for row in surface["values"])


# --------------------------------------------------------------------------- #
# krige_surface — extent, filtering and output
# --------------------------------------------------------------------------- #


class TestKrigeSurfaceExtentAndOutput:
    def test_explicit_bounds_win_over_the_city_rectangle(self, stub_fit):
        stub_fit({"spherical": lattice(north_gradient)})
        min_lon, min_lat, _, _ = get_city_bounds(CITY)
        override = [min_lon, min_lat, min_lon + 0.4, min_lat + 0.4]

        surface = krige_surface(
            inside_houston([28.0, 29.0, 30.0, 31.0]),
            rows=8,
            cols=8,
            bounds=override,
            city=CITY,
        )

        assert surface["bounds"] == pytest.approx(override)

    def test_with_no_city_the_extent_is_the_padded_bounding_box(self, stub_fit):
        stub_fit({"spherical": lattice(north_gradient)})
        points = [reading(-96.0, 29.0, 1.0), reading(-95.0, 30.0, 2.0)]

        surface = krige_surface(points, rows=8, cols=8)

        assert surface["bounds"] == pytest.approx(surface_bounds(points))
        assert surface["city"] is None

    def test_the_city_is_reported_by_its_resolved_name(self, stub_fit):
        stub_fit({"spherical": lattice(north_gradient)})

        surface = krige_surface(
            inside_houston([28.0, 29.0, 30.0, 31.0]), rows=8, cols=8, city="houston"
        )

        assert surface["city"] == "Houston"
        assert surface["bounds"] == pytest.approx(get_city_bounds(CITY))

    def test_fewer_than_two_readings_inside_the_city_raises(self):
        """A city with one reading gets no surface rather than a fabricated one,
        even when plenty of readings exist elsewhere."""
        points = inside_houston([28.0]) + [
            reading(-80.19, 25.76, 30.0),
            reading(-80.20, 25.77, 31.0),
        ]

        with pytest.raises(ValueError, match="Only 1 reading.*Houston"):
            krige_surface(points, rows=8, cols=8, city=CITY)

    def test_a_boundary_buffer_lets_nearby_readings_feed_the_fit(self, stub_fit):
        recorder = stub_fit({"spherical": lattice(north_gradient)})
        min_lon, min_lat, _, _ = get_city_bounds(CITY)
        points = inside_houston([28.0, 29.0]) + [reading(min_lon - 0.05, min_lat, 35.0)]

        strict = krige_surface(points, rows=8, cols=8, city=CITY)
        buffered = krige_surface(points, rows=8, cols=8, city=CITY, buffer_deg=0.1)

        assert strict["source_count"] == 2
        assert buffered["source_count"] == 3
        assert recorder.calls[-1]["z"].tolist() == [28.0, 29.0, 35.0]

    def test_the_fit_is_thinned_to_the_fit_ceiling(self, stub_fit):
        recorder = stub_fit({"spherical": lattice(north_gradient)})
        points = [
            reading(-95.5 + i * 1e-4, 29.5 + i * 1e-4, float(i))
            for i in range(SURFACE_MAX_FIT_POINTS + 200)
        ]

        surface = krige_surface(points, rows=8, cols=8, city=CITY)

        assert surface["source_count"] == SURFACE_MAX_FIT_POINTS
        assert len(recorder.calls[0]["z"]) == SURFACE_MAX_FIT_POINTS

    def test_min_max_and_variance_summarise_the_lattice(self, stub_fit):
        stub_fit({"spherical": lattice(north_gradient)})

        surface = krige_surface(
            [reading(0.0, 0.0, 0.0), reading(8.0, 8.0, 8.0)],
            rows=8,
            cols=8,
            bounds=[0.0, 0.0, 8.0, 8.0],
        )

        assert surface["min"] == 0.5
        assert surface["max"] == 7.5
        assert surface["variance_mean"] == 0.5  # the stub's variance everywhere
        assert surface["variogram_model"] == "spherical"
        assert surface["source_count"] == 2
        assert surface["metrics"] == {}

    def test_a_secondary_metric_whose_fit_fails_is_dropped_not_raised(self, stub_fit):
        """The drawn metric here is flat, so it never reaches the fit; the
        secondary one does, and every model raises. Losing a tooltip row must
        not cost the map its surface."""
        stub_fit({model: RuntimeError("boom") for model in SURFACE_VARIOGRAM_MODELS})

        surface = krige_surface(
            inside_houston([0.0, 0.0, 0.0]),
            rows=8,
            cols=8,
            city=CITY,
            extra_points_by_metric={
                "average_relative_humidity_pct": inside_houston([50.0, 60.0, 70.0])
            },
        )

        assert surface["variogram_model"] == "constant"
        assert surface["metrics"] == {}

    def test_secondary_readings_outside_the_city_are_filtered_too(self, stub_fit):
        stub_fit({"spherical": lattice(north_gradient)})

        surface = krige_surface(
            inside_houston([28.0, 29.0, 30.0]),
            rows=8,
            cols=8,
            city=CITY,
            extra_points_by_metric={
                "average_relative_humidity_pct": inside_houston([50.0, 60.0])
                + [reading(-80.19, 25.76, 99.0)]
            },
        )

        assert surface["metrics"]["average_relative_humidity_pct"]["source_count"] == 2

    def test_the_real_output_validates_against_the_response_schema(self):
        """The frontend reads MetricSurface, which mirrors SurfaceResponse; a
        numpy scalar or a missing key would fail here before it failed there."""
        surface = krige_surface(
            inside_houston([28.0, 30.5, 29.0, 33.0, 31.0]),
            rows=8,
            cols=8,
            city=CITY,
            extra_points_by_metric={
                "average_relative_humidity_pct": inside_houston([50.0, 58.0, 55.0, 64.0, 61.0])
            },
        )

        response = SurfaceResponse.model_validate(
            {"metric_key": "average_temperature_c", **surface}
        )

        assert response.rows == response.cols == 8
        assert response.interpolation_method == "ordinary_kriging"
        assert response.variogram_model in SURFACE_VARIOGRAM_MODELS
        assert set(response.metrics) == {"average_relative_humidity_pct"}
        assert all(type(value) is float for row in surface["values"] for value in row)

    def test_the_real_fit_stays_within_the_clamped_observed_range(self):
        values = [28.0, 30.5, 29.0, 33.0, 31.0]

        surface = krige_surface(inside_houston(values), rows=8, cols=8, city=CITY)

        margin = (max(values) - min(values)) * SURFACE_OVERSHOOT_MARGIN
        assert min(values) - margin <= surface["min"]
        assert surface["max"] <= max(values) + margin
        assert surface["max"] > surface["min"]
