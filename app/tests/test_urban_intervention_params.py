"""``validate_parameters`` — the write-time guard on intervention parameters.

Reached from POST /urban_intervention/create-urban-intervention: the repository
calls this before inserting and turns any problem into
``InvalidParametersError``. It matters because the simulation skips an object
whose parameters it cannot read *without raising*, so an unvalidated body would
store fine and then quietly contribute nothing.

``validate_geometry`` sits beside it in the same module but nothing calls it —
not the repository, not the router — so it is out of scope here.
"""

from __future__ import annotations

import pytest

from schemas.urban_intervention import (
    ALLOWED_GEOMETRY_KINDS,
    ARCHETYPE_CODE_BY_INTERVENTION,
    OPTIONAL_PARAM_KEYS,
    PARAM_BOUNDS,
    REQUIRED_PARAM_KEYS,
    SIMULATION_CATEGORY_BY_ARCHETYPE_CODE,
    validate_parameters,
)

VALID = {
    "cool_roof": {"deltaAlbedo": 0.5, "coverPct": 0.3},
    "cool_pavement": {"deltaAlbedo": 0.5, "coverPct": 0.3},
    "street_tree": {"coverPct": 0.4, "lai": 3.0, "irrigation": 0.8},
    "shade_structure": {"opacity": 0.95, "footprintFraction": 0.6},
    "misting_station": {
        "evapRateLpm": 1.0,
        "coverageRadiusM": 8.0,
        "activeFraction": 0.5,
    },
}


# --------------------------------------------------------------------------- #
# Accepting a well-formed blob
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("intervention_type", sorted(VALID))
def test_a_valid_parameter_blob_reports_no_problems(intervention_type):
    assert validate_parameters(intervention_type, VALID[intervention_type]) == []


def test_an_optional_parameter_is_accepted():
    parameters = {**VALID["street_tree"], "canopyFraction": 0.7}

    assert validate_parameters("street_tree", parameters) == []


def test_omitting_an_optional_parameter_is_not_a_problem():
    assert "canopyFraction" not in VALID["street_tree"]
    assert validate_parameters("street_tree", VALID["street_tree"]) == []


def test_integers_are_accepted_where_floats_are_expected():
    assert validate_parameters("cool_roof", {"deltaAlbedo": 1, "coverPct": 0}) == []


def test_the_input_mapping_is_not_mutated():
    parameters = dict(VALID["cool_roof"])

    validate_parameters("cool_roof", parameters)

    assert parameters == VALID["cool_roof"]


# --------------------------------------------------------------------------- #
# Missing required keys
# --------------------------------------------------------------------------- #


def test_a_missing_required_key_is_reported():
    problems = validate_parameters("cool_roof", {"coverPct": 0.3})

    assert problems == [
        "missing required parameter 'deltaAlbedo' — "
        "cool_roof will be skipped by the simulation"
    ]


def test_every_missing_key_is_reported_in_sorted_order():
    problems = validate_parameters("street_tree", {})

    assert [problem.split("'")[1] for problem in problems] == [
        "coverPct",
        "irrigation",
        "lai",
    ]


def test_the_message_names_the_consequence_not_just_the_key():
    problems = validate_parameters("shade_structure", {"opacity": 0.9})

    assert "will be skipped by the simulation" in problems[0]


# --------------------------------------------------------------------------- #
# Unrecognized keys
# --------------------------------------------------------------------------- #


def test_an_unrecognized_key_is_reported():
    # `albedo` is the finished reflectance, not the gain the model wants; the
    # simulation would ignore it and use nothing.
    problems = validate_parameters("cool_roof", {**VALID["cool_roof"], "albedo": 0.9})

    assert problems == ["unrecognized parameter 'albedo' — it will be ignored"]


def test_a_key_valid_for_another_type_is_still_unrecognized():
    problems = validate_parameters("cool_roof", {**VALID["cool_roof"], "lai": 3.0})

    assert problems == ["unrecognized parameter 'lai' — it will be ignored"]


def test_an_optional_key_from_another_type_is_unrecognized():
    problems = validate_parameters(
        "cool_roof", {**VALID["cool_roof"], "canopyFraction": 0.5}
    )

    assert problems == ["unrecognized parameter 'canopyFraction' — it will be ignored"]


def test_unrecognized_keys_are_reported_in_sorted_order():
    problems = validate_parameters(
        "cool_roof", {**VALID["cool_roof"], "zeta": 1, "alpha": 1}
    )

    assert [problem.split("'")[1] for problem in problems] == ["alpha", "zeta"]


# --------------------------------------------------------------------------- #
# Types and bounds
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("value", "type_name"),
    [("0.5", "str"), (None, "NoneType"), ([0.5], "list"), ({"a": 1}, "dict")],
)
def test_a_non_numeric_value_is_reported_with_its_type(value, type_name):
    problems = validate_parameters(
        "cool_roof", {"deltaAlbedo": value, "coverPct": 0.3}
    )

    assert problems == [f"parameter 'deltaAlbedo' must be a number, got {type_name}"]


@pytest.mark.parametrize("value", [True, False])
def test_a_boolean_is_rejected_even_though_bool_subclasses_int(value):
    problems = validate_parameters("cool_roof", {"deltaAlbedo": value, "coverPct": 0.3})

    assert problems == ["parameter 'deltaAlbedo' must be a number, got bool"]


def test_a_non_numeric_value_is_not_also_bounds_checked():
    # The type failure short-circuits, so exactly one problem comes back.
    problems = validate_parameters("cool_roof", {"deltaAlbedo": "big", "coverPct": 0.3})

    assert len(problems) == 1


@pytest.mark.parametrize("value", [-0.1, 1.1, 100])
def test_a_zero_to_one_parameter_outside_its_range_is_reported(value):
    problems = validate_parameters("cool_roof", {"deltaAlbedo": value, "coverPct": 0.3})

    assert problems == [f"parameter 'deltaAlbedo' = {value} is outside [0.0, 1.0]"]


@pytest.mark.parametrize("value", [0.0, 1.0, 0.5])
def test_the_zero_to_one_range_is_inclusive(value):
    assert validate_parameters("cool_roof", {"deltaAlbedo": value, "coverPct": 0.3}) == []


def test_an_unbounded_parameter_reports_only_its_lower_bound():
    problems = validate_parameters(
        "street_tree", {**VALID["street_tree"], "lai": -1.0}
    )

    assert problems == ["parameter 'lai' = -1.0 is outside >= 0.0"]


def test_a_large_leaf_area_index_is_accepted():
    # lai has no upper bound: the model saturates rather than clipping.
    assert validate_parameters("street_tree", {**VALID["street_tree"], "lai": 50.0}) == []


def test_bounds_problems_are_reported_in_sorted_key_order():
    problems = validate_parameters("cool_roof", {"deltaAlbedo": 5.0, "coverPct": 5.0})

    assert [problem.split("'")[1] for problem in problems] == ["coverPct", "deltaAlbedo"]


def test_missing_and_unrecognized_problems_are_reported_together():
    problems = validate_parameters("cool_roof", {"coverPct": 0.3, "albedo": 0.9})

    assert len(problems) == 2
    assert any("missing required parameter 'deltaAlbedo'" in p for p in problems)
    assert any("unrecognized parameter 'albedo'" in p for p in problems)


# --------------------------------------------------------------------------- #
# misting_station's extra rule
# --------------------------------------------------------------------------- #


def test_a_zero_coverage_radius_is_reported_even_though_it_is_in_bounds():
    # PARAM_BOUNDS allows 0.0, but a zero radius means the source cools
    # nothing, so the type-specific rule catches it.
    problems = validate_parameters(
        "misting_station", {**VALID["misting_station"], "coverageRadiusM": 0.0}
    )

    assert problems == ["coverageRadiusM must be greater than 0 to have any effect"]


def test_a_negative_coverage_radius_is_reported_twice():
    problems = validate_parameters(
        "misting_station", {**VALID["misting_station"], "coverageRadiusM": -5.0}
    )

    assert "parameter 'coverageRadiusM' = -5.0 is outside >= 0.0" in problems
    assert "coverageRadiusM must be greater than 0 to have any effect" in problems


def test_a_positive_coverage_radius_is_accepted():
    assert validate_parameters("misting_station", VALID["misting_station"]) == []


def test_the_radius_rule_does_not_fire_when_the_key_is_missing():
    # A missing key is already reported once; it must not also be read as zero.
    problems = validate_parameters(
        "misting_station", {"evapRateLpm": 1.0, "activeFraction": 0.5}
    )

    assert problems == [
        "missing required parameter 'coverageRadiusM' — "
        "misting_station will be skipped by the simulation"
    ]


def test_the_radius_rule_does_not_fire_for_a_non_numeric_value():
    problems = validate_parameters(
        "misting_station", {**VALID["misting_station"], "coverageRadiusM": "wide"}
    )

    assert problems == ["parameter 'coverageRadiusM' must be a number, got str"]


def test_a_zero_radius_only_matters_for_misting_stations():
    # coverPct = 0 is pointless too, but only the evaporative model gets the
    # extra check, so nothing is reported here.
    assert validate_parameters("cool_roof", {"deltaAlbedo": 0.5, "coverPct": 0.0}) == []


# --------------------------------------------------------------------------- #
# Unknown intervention type
# --------------------------------------------------------------------------- #


def test_an_unknown_intervention_type_raises_rather_than_reporting():
    """A type outside the union blows up on the lookup table.

    Not a graceful failure, but it is the safe direction: FastAPI's Literal
    validation rejects the body first, so this is only reachable from Python.
    """
    with pytest.raises(KeyError, match="teleporter"):
        validate_parameters("teleporter", {})


# --------------------------------------------------------------------------- #
# The lookup tables the simulation and frontend agree on
# --------------------------------------------------------------------------- #


def test_every_intervention_type_has_an_entry_in_every_table():
    types = set(REQUIRED_PARAM_KEYS)

    assert set(OPTIONAL_PARAM_KEYS) == types
    assert set(ALLOWED_GEOMETRY_KINDS) == types
    assert set(ARCHETYPE_CODE_BY_INTERVENTION) == types


def test_every_declared_parameter_key_has_bounds():
    for intervention_type, required in REQUIRED_PARAM_KEYS.items():
        keys = required | OPTIONAL_PARAM_KEYS[intervention_type]
        missing = keys - PARAM_BOUNDS.keys()
        assert not missing, f"{intervention_type} keys without bounds: {missing}"


def test_required_and_optional_keys_never_overlap():
    for intervention_type, required in REQUIRED_PARAM_KEYS.items():
        assert not required & OPTIONAL_PARAM_KEYS[intervention_type]


@pytest.mark.parametrize(
    ("intervention_type", "archetype"),
    [
        ("cool_roof", "high_albedo_surface"),
        ("cool_pavement", "high_albedo_surface"),
        ("street_tree", "vegetation"),
        ("shade_structure", "shade_structure"),
        ("misting_station", "evaporative_water"),
    ],
)
def test_each_type_maps_to_its_archetype(intervention_type, archetype):
    assert ARCHETYPE_CODE_BY_INTERVENTION[intervention_type] == archetype


def test_every_archetype_maps_to_a_simulation_category():
    archetypes = set(ARCHETYPE_CODE_BY_INTERVENTION.values())

    assert archetypes <= SIMULATION_CATEGORY_BY_ARCHETYPE_CODE.keys()


def test_the_simulation_categories_are_the_display_names_the_toolbox_uses():
    assert SIMULATION_CATEGORY_BY_ARCHETYPE_CODE == {
        "vegetation": "Vegetation",
        "high_albedo_surface": "High-albedo surface",
        "shade_structure": "Shade structure",
        "evaporative_water": "Evaporative / water",
    }


def test_only_misting_stations_accept_a_non_polygon_geometry():
    for intervention_type, kinds in ALLOWED_GEOMETRY_KINDS.items():
        if intervention_type == "misting_station":
            assert kinds == {"point", "line", "polygon"}
        else:
            assert kinds == {"polygon"}
