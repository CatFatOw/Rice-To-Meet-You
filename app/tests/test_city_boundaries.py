"""``data/city_boundaries.py`` — the city rectangles every surface is drawn in.

Both surface routes resolve the city the frontend sends through this module:
``resolve_city_name`` validates it, ``get_market_code`` picks the heatmap market
the readings are read from, and ``get_city_bounds`` is the lattice extent. The
module promises two contracts worth pinning:

* its centres match ``frontend/src/data/hostCities.ts`` exactly, so the city the
  map selects and the city the surface covers are the same place;
* its aliases cover the market codes the heatmap repository stores readings
  under.
"""

from __future__ import annotations

import pytest

from data.city_boundaries import (
    CITY_BOUNDARIES,
    HALF_SPAN_DEGREES,
    get_city_boundary,
    get_city_bounds,
    get_market_code,
    resolve_city_name,
    supported_cities,
)
from repository.heatmap_repository import HeatmapRepository

# ``cities`` in frontend/src/data/hostCities.ts, as (name, latitude, longitude).
FRONTEND_HOST_CITIES = (
    ("Atlanta", 33.7490, -84.3880),
    ("Boston", 42.3601, -71.0589),
    ("Dallas", 32.7767, -96.7970),
    ("Houston", 29.7604, -95.3698),
    ("Kansas City", 39.0997, -94.5786),
    ("Los Angeles", 34.0522, -118.2437),
    ("Miami", 25.7617, -80.1918),
    ("New York", 40.7128, -74.0060),
    ("New Jersey", 40.0583, -74.4057),
    ("Philadelphia", 39.9526, -75.1652),
    ("Seattle", 47.6062, -122.3321),
    ("San Francisco Bay Area", 37.7749, -122.4194),
)


# --------------------------------------------------------------------------- #
# resolve_city_name
# --------------------------------------------------------------------------- #


class TestResolveCityName:
    @pytest.mark.parametrize("name", [city for city, _, _ in FRONTEND_HOST_CITIES])
    def test_every_frontend_city_name_resolves_to_itself(self, name):
        assert resolve_city_name(name) == name

    @pytest.mark.parametrize(
        "spelling, expected",
        [
            ("houston", "Houston"),
            ("HOUSTON", "Houston"),
            ("  Houston  ", "Houston"),
            ("kansas_city", "Kansas City"),
            ("KANSAS CITY", "Kansas City"),
            ("nyc", "New York"),
            ("new york city", "New York"),
            ("new york/new jersey", "New York"),
            ("newark", "New Jersey"),
            ("san francisco", "San Francisco Bay Area"),
        ],
    )
    def test_an_alias_resolves_regardless_of_case_or_padding(self, spelling, expected):
        assert resolve_city_name(spelling) == expected

    @pytest.mark.parametrize("market_code", HeatmapRepository.SUPPORTED_MARKET_CODES)
    def test_every_heatmap_market_code_resolves_back_to_its_market(self, market_code):
        """The GET surface route sends whatever the frontend holds, which may be
        a market code; it must land on a rectangle whose readings live under
        that same code."""
        resolved = resolve_city_name(market_code)

        assert resolved is not None
        assert get_market_code(resolved) == market_code

    @pytest.mark.parametrize("city", [None, "", "Atlantis", "Houston, TX"])
    def test_an_unknown_or_empty_city_resolves_to_none(self, city):
        assert resolve_city_name(city) is None


# --------------------------------------------------------------------------- #
# get_city_boundary / get_city_bounds
# --------------------------------------------------------------------------- #


class TestCityRectangles:
    @pytest.mark.parametrize("name, latitude, longitude", FRONTEND_HOST_CITIES)
    def test_the_centre_matches_the_frontend_host_city(self, name, latitude, longitude):
        assert get_city_boundary(name)["center"] == [longitude, latitude]

    @pytest.mark.parametrize("name, latitude, longitude", FRONTEND_HOST_CITIES)
    def test_bounds_are_the_centre_plus_or_minus_the_half_span(
        self, name, latitude, longitude
    ):
        assert get_city_bounds(name) == pytest.approx(
            [
                longitude - HALF_SPAN_DEGREES,
                latitude - HALF_SPAN_DEGREES,
                longitude + HALF_SPAN_DEGREES,
                latitude + HALF_SPAN_DEGREES,
            ]
        )

    def test_houston_s_rectangle_in_minlon_minlat_maxlon_maxlat_order(self):
        assert get_city_bounds("houston") == pytest.approx(
            [-95.9898, 29.1404, -94.7498, 30.3804]
        )

    def test_a_boundary_carries_state_and_market_code(self):
        boundary = get_city_boundary("Kansas City")

        assert boundary["state"] == "Missouri"
        assert boundary["market_code"] == "kansas_city"

    def test_the_returned_bounds_are_a_copy(self):
        """Callers such as krige_surface receive this list; mutating it must not
        move the city for every later request."""
        bounds = get_city_bounds("Houston")
        bounds[0] = 0.0

        assert get_city_bounds("Houston")[0] == pytest.approx(-95.9898)

    @pytest.mark.parametrize("city", [None, "", "Atlantis"])
    def test_an_unknown_city_has_no_rectangle(self, city):
        assert get_city_boundary(city) is None
        assert get_city_bounds(city) is None


# --------------------------------------------------------------------------- #
# get_market_code / supported_cities
# --------------------------------------------------------------------------- #


class TestMarketCodeAndCityList:
    @pytest.mark.parametrize(
        "city, market_code",
        [
            ("Houston", "houston"),
            ("Los Angeles", "los_angeles"),
            ("San Francisco Bay Area", "san_francisco"),
            ("Kansas City", "kansas_city"),
        ],
    )
    def test_a_city_maps_to_the_market_its_readings_are_stored_under(
        self, city, market_code
    ):
        assert get_market_code(city) == market_code

    def test_new_york_and_new_jersey_share_one_market(self):
        """The source data has a single combined market; the rectangles, not
        the market code, keep the two surfaces apart."""
        assert get_market_code("New York") == "new_york_nj"
        assert get_market_code("New Jersey") == "new_york_nj"
        assert get_city_bounds("New York") != get_city_bounds("New Jersey")

    def test_an_unknown_city_has_no_market_code(self):
        assert get_market_code("Atlantis") is None

    def test_supported_cities_lists_every_rectangle_alphabetically(self):
        assert supported_cities() == sorted(city for city, _, _ in FRONTEND_HOST_CITIES)
        assert set(supported_cities()) == set(CITY_BOUNDARIES)
