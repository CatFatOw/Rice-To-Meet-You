"""Geometry → WKT conversion for POST /urban_intervention/create-urban-intervention.

The toolbox posts what the user drew on the map as ``{kind, ...}``; these
functions turn it into the WKT handed to ``ST_GeomFromText``. Everything here
is pure, so the tests are plain input/output.
"""

from __future__ import annotations

import math

import pytest

from repository.urban_internvetion_repository import (
    InvalidGeometryError,
    _close_ring,
    _num,
    _pair,
    geometry_to_wkt,
)


# --------------------------------------------------------------------------- #
# geometry_to_wkt — the happy paths
# --------------------------------------------------------------------------- #


def test_a_point_becomes_point_wkt():
    kind, wkt = geometry_to_wkt(
        {"kind": "point", "longitude": -95.4018, "latitude": 29.7174}
    )

    assert kind == "point"
    assert wkt == "POINT(-95.4018 29.7174)"


def test_a_line_becomes_linestring_wkt():
    kind, wkt = geometry_to_wkt(
        {"kind": "line", "coordinates": [(-95.4, 29.7), (-95.3, 29.8)]}
    )

    assert kind == "line"
    assert wkt == "LINESTRING(-95.4 29.7, -95.3 29.8)"


def test_a_line_may_have_more_than_two_vertices():
    _, wkt = geometry_to_wkt(
        {"kind": "line", "coordinates": [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]}
    )

    assert wkt == "LINESTRING(0.0 0.0, 1.0 1.0, 2.0 2.0)"


def test_a_polygon_becomes_polygon_wkt_with_a_doubled_ring():
    kind, wkt = geometry_to_wkt(
        {"kind": "polygon", "ring": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]}
    )

    assert kind == "polygon"
    assert wkt == "POLYGON((0.0 0.0, 1.0 0.0, 1.0 1.0, 0.0 0.0))"


def test_an_already_closed_ring_is_not_closed_twice():
    ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]

    _, wkt = geometry_to_wkt({"kind": "polygon", "ring": ring})

    assert wkt.count("0.0 0.0") == 2


def test_a_ring_supplied_as_lists_is_accepted():
    # JSON bodies arrive with lists, not tuples.
    _, wkt = geometry_to_wkt(
        {"kind": "polygon", "ring": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]}
    )

    assert wkt == "POLYGON((0.0 0.0, 1.0 0.0, 1.0 1.0, 0.0 0.0))"


def test_integer_coordinates_are_rendered_as_floats():
    _, wkt = geometry_to_wkt({"kind": "point", "longitude": 0, "latitude": 0})

    assert wkt == "POINT(0.0 0.0)"


@pytest.mark.parametrize(
    ("longitude", "latitude"),
    [(-180.0, -90.0), (180.0, 90.0), (0.0, 0.0)],
)
def test_coordinate_bounds_are_inclusive(longitude, latitude):
    kind, wkt = geometry_to_wkt(
        {"kind": "point", "longitude": longitude, "latitude": latitude}
    )

    assert kind == "point"
    assert wkt == f"POINT({longitude} {latitude})"


# --------------------------------------------------------------------------- #
# geometry_to_wkt — the rejections
# --------------------------------------------------------------------------- #


def test_an_unsupported_kind_is_rejected():
    with pytest.raises(InvalidGeometryError, match="Unsupported geometry kind"):
        geometry_to_wkt({"kind": "circle", "radius": 10})


def test_a_line_needs_at_least_two_coordinates():
    with pytest.raises(InvalidGeometryError, match="at least 2 coordinates"):
        geometry_to_wkt({"kind": "line", "coordinates": [(0.0, 0.0)]})


def test_an_empty_line_is_rejected():
    with pytest.raises(InvalidGeometryError, match="at least 2 coordinates"):
        geometry_to_wkt({"kind": "line", "coordinates": []})


def test_a_ring_of_two_distinct_points_is_rejected():
    # Closing adds one vertex, giving 3 -- still short of the 4 a ring needs.
    with pytest.raises(InvalidGeometryError, match="at least 3 distinct coordinates"):
        geometry_to_wkt({"kind": "polygon", "ring": [(0.0, 0.0), (1.0, 0.0)]})


def test_a_ring_that_doubles_back_on_itself_is_rejected():
    # [(0,0), (1,0), (0,0)] already reads as closed, so nothing is appended and
    # it stays 3 vertices: two distinct points, not three.
    with pytest.raises(InvalidGeometryError, match="at least 3 distinct coordinates"):
        geometry_to_wkt(
            {"kind": "polygon", "ring": [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0)]}
        )


def test_an_empty_ring_is_rejected():
    with pytest.raises(InvalidGeometryError, match="at least 3 distinct coordinates"):
        geometry_to_wkt({"kind": "polygon", "ring": []})


@pytest.mark.parametrize("longitude", [180.1, -180.1, 1000.0])
def test_longitude_outside_the_globe_is_rejected(longitude):
    with pytest.raises(InvalidGeometryError, match="Longitude out of range"):
        geometry_to_wkt({"kind": "point", "longitude": longitude, "latitude": 0.0})


@pytest.mark.parametrize("latitude", [90.1, -90.1, 1000.0])
def test_latitude_outside_the_globe_is_rejected(latitude):
    with pytest.raises(InvalidGeometryError, match="Latitude out of range"):
        geometry_to_wkt({"kind": "point", "longitude": 0.0, "latitude": latitude})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_coordinates_are_rejected_by_the_range_check(value):
    """NaN and the infinities never reach ``_num``'s finiteness guard.

    ``_pair`` range-checks first, and every comparison against NaN is False
    while the infinities fall outside the bounds, so all three surface as an
    out-of-range error. ``_num``'s "must be finite" message is therefore
    unreachable through ``geometry_to_wkt`` -- see test_num_rejects_non_finite
    for the only way to trigger it.
    """
    with pytest.raises(InvalidGeometryError, match="out of range"):
        geometry_to_wkt({"kind": "point", "longitude": value, "latitude": 0.0})


def test_a_bad_vertex_anywhere_in_a_line_is_rejected():
    with pytest.raises(InvalidGeometryError, match="Latitude out of range"):
        geometry_to_wkt(
            {"kind": "line", "coordinates": [(0.0, 0.0), (1.0, 95.0)]}
        )


def test_invalid_geometry_error_is_a_value_error():
    # The router's ValueError handler and any caller catching ValueError must
    # still see these.
    assert issubclass(InvalidGeometryError, ValueError)


# --------------------------------------------------------------------------- #
# The building blocks
# --------------------------------------------------------------------------- #


class TestNum:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(0, "0.0"), (1, "1.0"), (-95.4018, "-95.4018"), (1.5, "1.5")],
    )
    def test_rendering(self, value, expected):
        assert _num(value) == expected

    @pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
    def test_num_rejects_non_finite(self, value):
        with pytest.raises(InvalidGeometryError, match="must be finite numbers"):
            _num(value)

    def test_numeric_strings_are_accepted(self):
        assert _num("1.5") == "1.5"


class TestPair:
    def test_a_pair_renders_longitude_first(self):
        assert _pair((-95.4, 29.7)) == "-95.4 29.7"

    def test_the_error_names_which_component_is_wrong(self):
        with pytest.raises(InvalidGeometryError, match="Longitude out of range: 200.0"):
            _pair((200.0, 0.0))


class TestCloseRing:
    def test_an_open_ring_gains_its_first_vertex(self):
        assert _close_ring([(0, 0), (1, 0), (1, 1)]) == [(0, 0), (1, 0), (1, 1), (0, 0)]

    def test_a_closed_ring_is_left_alone(self):
        ring = [(0, 0), (1, 0), (1, 1), (0, 0)]

        assert _close_ring(ring) == ring

    def test_an_empty_ring_stays_empty(self):
        assert _close_ring([]) == []

    def test_the_input_is_not_mutated(self):
        ring = [(0, 0), (1, 0), (1, 1)]

        _close_ring(ring)

        assert len(ring) == 3
