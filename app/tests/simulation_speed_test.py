import copy

from simulation_sample_tests import (
	heatmap_point,
	metric,
	placed_object,
	placed_object_2,
)
from services.simulation_services import run_diminishing_return_simulation


def test_simulation_does_not_mutate_baseline():
	point_date = "2025-07-17"
	points_by_date = {point_date: [copy.deepcopy(heatmap_point)]}
	categorized_objects = {
		"Vegetation": [copy.deepcopy(placed_object), copy.deepcopy(placed_object_2)],
		"High-albedo surface": [],
		"Shade structure": [],
		"Evaporative / water": [],
	}
	for placed_object_fixture in categorized_objects["Vegetation"]:
		placed_object_fixture["activeFrom"] = "2025-07-01"
		placed_object_fixture["activeTo"] = "2025-07-31"

	baseline = copy.deepcopy(points_by_date)

	result, feedback = run_diminishing_return_simulation(
		metric,
		points_by_date,
		categorized_objects,
		"contextual",
	)

	assert points_by_date == baseline
	assert feedback.affected_points > 0, "fixture never triggers the mutation path"
	assert feedback.overlap_points > 0, "fixture never exercises overlapping contributions"


if __name__ == "__main__":
	test_simulation_does_not_mutate_baseline()