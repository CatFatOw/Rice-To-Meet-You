"""``CorePOICreate`` — the body validated for POST /core_poi/create-poi.

The frontend posts this from the toolbox ("draw a POI, save it"), so every
normalization here decides what actually lands in ``core_poi_geometry``.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from schemas.core_poi_geometry import (
    CorePOICreate,
    GeometryType,
    MarketCode,
    PolygonClass,
)

POLYGON_WKT = "POLYGON((-96.80 32.78, -96.70 32.78, -96.70 32.88, -96.80 32.78))"
MULTIPOLYGON_WKT = (
    "MULTIPOLYGON(((-96.80 32.78, -96.70 32.78, -96.70 32.88, -96.80 32.78)))"
)

REQUIRED = {
    "polygon_wkt": POLYGON_WKT,
    "city": "Dallas",
    "location_name": "Klyde Warren Park",
    "region": "TX",
    "includes_parking_lot": False,
    "latitude": 32.7893,
    "longitude": -96.8016,
    "market": "dallas",
    "color": "#22c55e",
}


def build(**overrides):
    return CorePOICreate(**{**REQUIRED, **overrides})


# --------------------------------------------------------------------------- #
# Required fields and defaults
# --------------------------------------------------------------------------- #


def test_minimal_payload_populates_every_required_field():
    poi = build()

    assert poi.city == "Dallas"
    assert poi.location_name == "Klyde Warren Park"
    assert poi.region == "TX"
    assert poi.includes_parking_lot is False
    assert poi.latitude == 32.7893
    assert poi.longitude == -96.8016
    assert poi.color == "#22c55e"


def test_defaults_are_applied_when_omitted():
    poi = build()

    assert poi.iso_country_code == "US"
    assert poi.is_synthetic is False
    assert poi.provided is False
    assert poi.geometry_type == GeometryType.POLYGON
    assert poi.polygon_class == PolygonClass.OWNED_POLYGON
    assert poi.placekey is None
    assert poi.parent_placekey is None
    assert poi.opened_on is None


@pytest.mark.parametrize(
    "missing",
    ["polygon_wkt", "city", "location_name", "region", "latitude", "longitude", "color"],
)
def test_omitting_a_required_field_is_rejected(missing):
    payload = {key: value for key, value in REQUIRED.items() if key != missing}

    with pytest.raises(ValidationError) as excinfo:
        CorePOICreate(**payload)

    assert missing in str(excinfo.value)


def test_unknown_fields_are_rejected_rather_than_ignored():
    # extra="forbid": a frontend typo must fail loudly, not silently drop.
    with pytest.raises(ValidationError) as excinfo:
        build(poi_name="Klyde Warren Park")

    assert "poi_name" in str(excinfo.value)


def test_string_fields_are_stripped():
    poi = build(location_name="  Klyde Warren Park  ", city="  Dallas  ")

    assert poi.location_name == "Klyde Warren Park"
    assert poi.city == "Dallas"


# --------------------------------------------------------------------------- #
# Coordinates
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("latitude", 90.1),
        ("latitude", -90.1),
        ("longitude", 180.1),
        ("longitude", -180.1),
    ],
)
def test_coordinates_outside_the_globe_are_rejected(field, value):
    with pytest.raises(ValidationError):
        build(**{field: value})


@pytest.mark.parametrize(
    ("latitude", "longitude"), [(90.0, 180.0), (-90.0, -180.0), (0.0, 0.0)]
)
def test_coordinate_bounds_are_inclusive(latitude, longitude):
    poi = build(latitude=latitude, longitude=longitude)

    assert poi.latitude == latitude
    assert poi.longitude == longitude


# --------------------------------------------------------------------------- #
# WKT validation
# --------------------------------------------------------------------------- #


def test_multipolygon_wkt_is_accepted():
    assert build(polygon_wkt=MULTIPOLYGON_WKT).polygon_wkt == MULTIPOLYGON_WKT


@pytest.mark.parametrize(
    "wkt",
    [
        "POINT(-96.80 32.78)",
        "LINESTRING(-96.80 32.78, -96.70 32.78)",
        "not wkt at all",
    ],
)
def test_wkt_must_be_a_polygon_or_multipolygon(wkt):
    with pytest.raises(ValidationError) as excinfo:
        build(polygon_wkt=wkt)

    assert "polygon_wkt must start with" in str(excinfo.value)


def test_unbalanced_parentheses_are_rejected():
    with pytest.raises(ValidationError) as excinfo:
        build(polygon_wkt="POLYGON((-96.80 32.78, -96.70 32.78, -96.80 32.78)")

    assert "unbalanced parentheses" in str(excinfo.value)


def test_wkt_shorter_than_ten_characters_is_rejected():
    with pytest.raises(ValidationError):
        build(polygon_wkt="POLYGON()")


def test_leading_whitespace_and_lowercase_wkt_are_accepted():
    # _check_wkt upper-cases and lstrips before matching the prefix.
    poi = build(polygon_wkt="  polygon((-96.80 32.78, -96.70 32.78, -96.80 32.78))")

    assert poi.polygon_wkt.startswith("polygon((")


# --------------------------------------------------------------------------- #
# geometry_type consistency
# --------------------------------------------------------------------------- #


def test_declared_geometry_type_must_match_the_wkt():
    with pytest.raises(ValidationError) as excinfo:
        build(geometry_type="POLYGON", polygon_wkt=MULTIPOLYGON_WKT)

    assert "geometry_type is POLYGON" in str(excinfo.value)


def test_explicit_matching_geometry_type_is_accepted():
    poi = build(geometry_type="MULTIPOLYGON", polygon_wkt=MULTIPOLYGON_WKT)

    assert poi.geometry_type == "MULTIPOLYGON"


def test_default_geometry_type_skips_the_wkt_consistency_check():
    """A MULTIPOLYGON stored as the default POLYGON passes validation.

    Not the documented intent, but the real behaviour: pydantic does not
    validate defaults, so ``geometry_type`` stays the ``GeometryType`` member
    rather than becoming "POLYGON" under ``use_enum_values``. The check reads
    ``str(self.geometry_type)``, which is "GeometryType.POLYGON" for an
    unvalidated member, so the ``declared in ("POLYGON", "MULTIPOLYGON")``
    guard is False and the comparison never runs.

    Contrast with test_declared_geometry_type_must_match_the_wkt, where the
    same mismatch is caught purely because the caller spelled the field out.
    """
    poi = build(polygon_wkt=MULTIPOLYGON_WKT)

    assert poi.geometry_type is GeometryType.POLYGON
    assert poi.polygon_wkt.startswith("MULTIPOLYGON")


# --------------------------------------------------------------------------- #
# Market normalization
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ("dallas", "dallas"),
        ("Dallas", "dallas"),
        ("DALLAS", "dallas"),
        ("Kansas City", "kansas_city"),
        ("new york nj", "new_york_nj"),
        ("new-york-nj", "new_york_nj"),
        ("  Los Angeles  ", "los_angeles"),
    ],
)
def test_market_spellings_normalize_to_the_market_code(supplied, expected):
    assert build(market=supplied).market == expected


def test_unknown_market_is_rejected():
    with pytest.raises(ValidationError):
        build(market="atlantis")


def test_market_code_defaults_to_market():
    poi = build(market="Houston")

    assert poi.market == MarketCode.HOUSTON.value
    assert poi.market_code == MarketCode.HOUSTON.value


def test_market_code_is_kept_when_it_differs_from_market():
    # _check_consistency only backfills a missing side; it does not reconcile
    # two values that disagree.
    poi = build(market="houston", market_code="dallas")

    assert poi.market == "houston"
    assert poi.market_code == "dallas"


# --------------------------------------------------------------------------- #
# region / iso_country_code
# --------------------------------------------------------------------------- #


def test_region_is_upper_cased():
    assert build(region="tx").region == "TX"


def test_iso_country_code_is_upper_cased():
    assert build(iso_country_code="us").iso_country_code == "US"


@pytest.mark.parametrize("region", ["T1", "T", "TXX", "1 "])
def test_region_must_be_two_letters(region):
    with pytest.raises(ValidationError):
        build(region=region)


# --------------------------------------------------------------------------- #
# List coercion
# --------------------------------------------------------------------------- #


def test_comma_separated_string_becomes_a_list():
    assert build(brands="Chipotle, Panera").brands == ["Chipotle", "Panera"]


def test_json_array_string_becomes_a_list():
    assert build(category_tags='["Coffee", "Bakery"]').category_tags == [
        "Coffee",
        "Bakery",
    ]


def test_list_entries_are_stripped_deduplicated_and_order_preserved():
    assert build(brands=" b , a , b ,  ").brands == ["b", "a"]


@pytest.mark.parametrize("value", ["", "   ", ",", " , "])
def test_a_list_with_nothing_usable_becomes_none(value):
    assert build(domains=value).domains is None


def test_malformed_json_array_falls_back_to_comma_splitting():
    # The JSON branch swallows the decode error and drops through, so the
    # brackets survive as literal text rather than raising.
    assert build(brands='["unclosed').brands == ['["unclosed']


def test_list_fields_default_to_none():
    poi = build()

    assert poi.brands is None
    assert poi.category_tags is None
    assert poi.domains is None


# --------------------------------------------------------------------------- #
# open_hours
# --------------------------------------------------------------------------- #


def test_open_hours_accepts_a_json_string():
    poi = build(open_hours='{"Mon": [["9:00", "17:00"]]}')

    assert poi.open_hours == {"Mon": [["9:00", "17:00"]]}


def test_open_hours_accepts_a_mapping():
    hours = {"Tue": [["8:00", "12:00"], ["13:00", "18:00"]]}

    assert build(open_hours=hours).open_hours == hours


def test_open_hours_rejects_invalid_json():
    with pytest.raises(ValidationError) as excinfo:
        build(open_hours="{not json")

    assert "open_hours must be valid JSON" in str(excinfo.value)


def test_blank_open_hours_becomes_none():
    assert build(open_hours="   ").open_hours is None


# --------------------------------------------------------------------------- #
# phone_number / website
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ("+1 (713) 555-0142", "+17135550142"),
        ("713-555-0142", "7135550142"),
        ("713.555.0142 ext", "7135550142"),
    ],
)
def test_phone_number_keeps_digits_and_a_leading_plus(supplied, expected):
    assert build(phone_number=supplied).phone_number == expected


@pytest.mark.parametrize("supplied", ["12345", "1" * 16])
def test_phone_number_outside_seven_to_fifteen_digits_is_rejected(supplied):
    with pytest.raises(ValidationError) as excinfo:
        build(phone_number=supplied)

    assert "expected 7-15" in str(excinfo.value)


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ("rice.edu", "https://rice.edu"),
        ("www.rice.edu", "https://www.rice.edu"),
        ("http://rice.edu", "http://rice.edu"),
        ("https://rice.edu", "https://rice.edu"),
    ],
)
def test_website_gets_an_https_scheme_when_it_has_none(supplied, expected):
    assert build(website=supplied).website == expected


def test_blank_website_becomes_none():
    assert build(website="").website is None


# --------------------------------------------------------------------------- #
# placekey
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("placekey", ["222-223-224", "abc-def@222-223-224"])
def test_well_formed_placekeys_are_accepted(placekey):
    assert build(placekey=placekey).placekey == placekey


@pytest.mark.parametrize("placekey", ["222-223", "222_223_224", "222-223-224-225"])
def test_malformed_placekeys_are_rejected(placekey):
    with pytest.raises(ValidationError) as excinfo:
        build(placekey=placekey)

    assert "Malformed placekey" in str(excinfo.value)


def test_blank_placekey_becomes_none():
    assert build(placekey="   ").placekey is None


def test_parent_placekey_may_not_equal_placekey():
    with pytest.raises(ValidationError) as excinfo:
        build(placekey="222-223-224", parent_placekey="222-223-224")

    assert "parent_placekey must differ" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# Date consistency and codes
# --------------------------------------------------------------------------- #


def test_tracking_closed_since_may_not_precede_opened_on():
    with pytest.raises(ValidationError) as excinfo:
        build(opened_on=date(2020, 5, 1), tracking_closed_since=date(2019, 5, 1))

    assert "tracking_closed_since precedes opened_on" in str(excinfo.value)


def test_tracking_closed_since_after_opened_on_is_accepted():
    poi = build(opened_on=date(2019, 5, 1), tracking_closed_since=date(2020, 5, 1))

    assert poi.opened_on == date(2019, 5, 1)
    assert poi.tracking_closed_since == date(2020, 5, 1)


@pytest.mark.parametrize("code", [99999, 1000000])
def test_naics_code_must_be_six_digits(code):
    with pytest.raises(ValidationError):
        build(naics_code=code)


def test_negative_area_is_rejected():
    with pytest.raises(ValidationError):
        build(wkt_area_sq_meters=-1.0)


# --------------------------------------------------------------------------- #
# Serialization for the repository
# --------------------------------------------------------------------------- #


def test_to_row_renders_enums_as_strings():
    row = build().to_row()

    assert row["geometry_type"] == "POLYGON"
    assert row["polygon_class"] == "OWNED_POLYGON"
    assert row["market"] == "dallas"
    assert isinstance(row["geometry_type"], str)


def test_to_row_keeps_nulls_so_defaulted_columns_are_written_explicitly():
    row = build().to_row()

    assert "placekey" in row and row["placekey"] is None
    assert "brands" in row and row["brands"] is None


def test_to_row_serializes_dates_as_iso_strings():
    row = build(opened_on=date(2019, 5, 1)).to_row()

    assert row["opened_on"] == "2019-05-01"


def test_model_dump_leaves_the_default_geometry_type_as_an_enum_member():
    """The router serializes with ``model_dump()``, not ``to_row()``.

    ``to_row()`` uses mode="json" and yields the plain string "POLYGON"; a bare
    ``model_dump()`` hands back the ``GeometryType`` member whenever the field
    was defaulted, because ``use_enum_values`` only applies to values that go
    through validation.

    It compares and inserts the same, since the enum subclasses ``str``. What
    differs is how it renders: ``str()`` gives "GeometryType.POLYGON", which is
    what any format string, log line or non-pydantic JSON encoder downstream
    would see.
    """
    dumped = build().model_dump()

    assert dumped["geometry_type"] is GeometryType.POLYGON
    assert isinstance(dumped["geometry_type"], GeometryType)
    assert dumped["geometry_type"] == "POLYGON"  # str subclass, so equality holds
    assert str(dumped["geometry_type"]) == "GeometryType.POLYGON"

    row = build().to_row()
    assert type(row["geometry_type"]) is str
    assert str(row["geometry_type"]) == "POLYGON"


def test_model_dump_renders_an_explicitly_supplied_enum_as_a_string():
    dumped = build(geometry_type="MULTIPOLYGON", polygon_wkt=MULTIPOLYGON_WKT).model_dump()

    assert dumped["geometry_type"] == "MULTIPOLYGON"
