"""Simulation-result section for the urban-heat chat briefing.

craftContext() produces a briefing whose section 4 carries *projected* cooling —
arithmetic done inside the context builder itself. Once the real simulator has
run, `extendContext` folds a SimulationFeedback into the briefing as an
additional, authoritative section, and `editContext` swaps that section out when
the planner re-runs with different interventions.

The section is delimited by sentinel lines rather than by its heading, so
editing never depends on section numbering or on the wording of the title.

Feedback is read by duck typing (`getattr`, falling back to `dict.get`), so the
SimulationFeedback dataclass, a `dataclasses.asdict` of it, or a JSON payload
round-tripped through the browser all work. That also keeps this module free of
an import from the simulation module, so neither has to know about the other.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from services.craft_context import MODEL_RULES


# Sentinels bounding the section. Kept deliberately ugly so they cannot collide
# with anything craftContext emits or a planner types into an object name.
SIMULATION_SECTION_BEGIN = "<<<SIMULATION RESULT>>>"
SIMULATION_SECTION_END = "<<<END SIMULATION RESULT>>>"

SIMULATION_SECTION_TITLE = (
	"5. SIMULATION RESULT — measured by the simulator, authoritative. These figures "
	"supersede the projected cooling in section 4."
)

# First line of the model-rules block, used to find the insertion point so the
# rules stay at the end of the briefing.
_MODEL_RULES_HEADER = MODEL_RULES.split("\n", 1)[0]

# Only these two metrics report their per-object deltas in °F; the three
# top-level temperature averages in feedback are always °C.
_FAHRENHEIT_CHANGE_METRICS = {
	"change_in_average_temperature_f",
	"change_in_local_temperature_f",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _field(source: Any, name: str, default: Any = None) -> Any:
	"""Read `name` off a dataclass, an object, or a mapping."""
	if isinstance(source, dict):
		value = source.get(name, default)
	else:
		value = getattr(source, name, default)
	return default if value is None else value


def _num(value: Any, default: float = 0.0) -> float:
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


def _signed(value: Any, digits: int = 2, suffix: str = "") -> str:
	"""Always show the sign, so a cooling delta reads unambiguously."""
	return f"{_num(value):+.{digits}f}{suffix}"


def _metric_unit(metric_name: Any) -> str:
	return "°F" if str(metric_name) in _FAHRENHEIT_CHANGE_METRICS else "°C"


def _coordinates_label(coordinates: Any) -> Optional[str]:
	if isinstance(coordinates, (list, tuple)) and len(coordinates) >= 2:
		return f"({_num(coordinates[0]):.5f}, {_num(coordinates[1]):.5f})"
	return None


def _location_label(entry: Any) -> str:
	"""Render `{'location', 'coordinates'}`, tolerating the older bare-name shape."""
	if isinstance(entry, dict):
		name = entry.get("location") or "unnamed location"
		coordinates = _coordinates_label(entry.get("coordinates"))
		return f"{name} @ {coordinates}" if coordinates else str(name)
	return str(entry)


def _names(values: Any) -> List[str]:
	if not isinstance(values, (list, tuple)):
		return []
	return [str(value) for value in values]


# ---------------------------------------------------------------------------
# Section rendering
# ---------------------------------------------------------------------------

def craftSimulationSection(
	feedback: Any,
	max_locations: int = 12,
	max_objects_per_location: int = 6,
	title: str = SIMULATION_SECTION_TITLE,
) -> str:
	"""Render a SimulationFeedback as the sentinel-delimited briefing section.

	:param feedback:                 SimulationFeedback, or any mapping/object with
	                                 the same field names
	:param max_locations:            cap on per-location rows; the rest are counted
	                                 rather than listed, so a dense heatmap does not
	                                 blow out the prompt
	:param max_objects_per_location: cap on interventions listed per location
	:param title:                    heading line, in case the section number moves
	"""
	mode = _field(feedback, "mode", "standard")
	affected_points = int(_num(_field(feedback, "affected_points", 0)))
	overlap_points = int(_num(_field(feedback, "overlap_points", 0)))
	max_objects_at_point = int(_num(_field(feedback, "max_objects_at_point", 0)))
	average_cooling = _num(_field(feedback, "average_cooling_c", 0.0))
	baseline_average = _num(_field(feedback, "baseline_average_temperature_c", 0.0))
	final_average = _num(_field(feedback, "average_temperature_c", 0.0))
	max_capacity_used = _num(_field(feedback, "max_capacity_used", 0.0))

	affected_locations = _field(feedback, "affected_locations", []) or []
	overlap_locations = _field(feedback, "overlap_locations", []) or []
	contributing = _names(_field(feedback, "contributing_interventions", []))
	without_effect = _names(_field(feedback, "interventions_without_effect", []))
	interactions = _names(_field(feedback, "contextual_interactions", []))
	breakdown = _field(feedback, "metric_breakdown", []) or []

	lines: List[str] = [SIMULATION_SECTION_BEGIN, title]

	if affected_points == 0:
		lines.append("   No reading was affected: every intervention was out of its active "
					 "window, missed the readings, or lacked usable params.")
	else:
		lines.append(f"   Mode: {mode}")
		lines.append(
			f"   Affected readings: {affected_points}"
			f" (overlapping: {overlap_points}, up to {max_objects_at_point} intervention(s)"
			f" on a single reading)"
		)
		lines.append(f"   Distinct affected locations: {len(affected_locations)}")
		lines.append(
			f"   Mean cooling where interventions landed: {average_cooling:.2f}°C"
			f"  |  peak ceiling use at any reading: {max_capacity_used:.0f}%"
		)
		lines.append(
			f"   Field mean temperature: {baseline_average:.2f}°C → {final_average:.2f}°C"
			f" ({_signed(final_average - baseline_average, 2, '°C')} across every reading with a"
			f" real value, affected or not)"
		)

	if contributing:
		lines.append("   Interventions that produced cooling: " + ", ".join(contributing))
	if without_effect:
		lines.append(
			"   Interventions with no effect anywhere: " + ", ".join(without_effect)
			+ " — outside the active window, no readings in reach, or missing required params"
		)
	if interactions:
		lines.append("   Contextual interactions applied:")
		for interaction in interactions:
			lines.append(f"     - {interaction}")
	elif str(mode) == "contextual":
		lines.append("   Contextual mode ran, but no interacting category pair was co-present.")

	if overlap_locations:
		shown = [_location_label(entry) for entry in overlap_locations[:max_locations]]
		suffix = "" if len(overlap_locations) <= max_locations else \
			f" (+{len(overlap_locations) - max_locations} more)"
		lines.append(f"   Locations with overlapping interventions: {'; '.join(shown)}{suffix}")

	if breakdown:
		total = len(breakdown)
		shown_rows = breakdown[:max_locations]
		header = f"   Per-location results ({total} affected location(s)"
		if total > len(shown_rows):
			header += f", {len(shown_rows)} shown, ordered as simulated"
		lines.append(header + "):")
		for rank, row in enumerate(shown_rows, start=1):
			lines.extend(_render_breakdown_row(rank, row, max_objects_per_location))
		if total > len(shown_rows):
			lines.append(
				f"     … {total - len(shown_rows)} further affected location(s) not listed;"
				f" ask for a specific location by name and it can be looked up."
			)

	lines.append(SIMULATION_SECTION_END)
	return "\n".join(lines)


def _render_breakdown_row(rank: int, row: Any, max_objects: int) -> List[str]:
	"""One per-location block: the metric change, then each contributing object."""
	location = _field(row, "location", "unnamed location")
	coordinates = _coordinates_label(_field(row, "coordinates"))
	metric_name = _field(row, "metric_name", "temperature")
	unit = _metric_unit(metric_name)
	point_count = int(_num(_field(row, "point_count", 0)))
	dates = _field(row, "dates", []) or []
	baseline = _num(_field(row, "metric", 0.0))
	new_value = _num(_field(row, "new_metric", 0.0))
	change = _num(_field(row, "change_in_metric", 0.0))
	placed_objects = _field(row, "placed_objects", []) or []

	head = f"     {rank}. {location}"
	if coordinates:
		head += f" @ {coordinates}"
	head += f" — {point_count} reading(s)"
	if dates:
		head += f" over {len(dates)} date(s): {', '.join(str(d) for d in dates[:4])}"
		if len(dates) > 4:
			head += f", +{len(dates) - 4} more"
	lines = [head]
	lines.append(
		f"        {metric_name}: {baseline:.2f} → {new_value:.2f}"
		f" ({_signed(change, 2, unit)}; mean over those readings)"
	)

	for contribution in placed_objects[:max_objects]:
		label = _field(contribution, "label", _field(contribution, "id", "unnamed"))
		category = _field(contribution, "category", "unknown archetype")
		share = _num(_field(contribution, "contribution", 0.0))
		standalone = _num(_field(contribution, "standalone_change", 0.0))
		share_pct = _num(_field(contribution, "share_pct", 0.0))
		lines.append(
			f"        + {label} ({category}): {_signed(share, 2, unit)} of that change"
			f" ({share_pct:.0f}%), standalone {_signed(standalone, 2, unit)} before the"
			f" overlap trim"
		)
	if len(placed_objects) > max_objects:
		lines.append(f"        + {len(placed_objects) - max_objects} further intervention(s) not listed")
	return lines


# ---------------------------------------------------------------------------
# Context extension / editing
# ---------------------------------------------------------------------------

def findSimulationSection(context: str) -> Optional[tuple[int, int]]:
	"""Character span of the existing section, or None if the briefing has none."""
	start = context.find(SIMULATION_SECTION_BEGIN)
	if start == -1:
		return None
	end = context.find(SIMULATION_SECTION_END, start)
	if end == -1:
		return None  # truncated section — treated as absent, then overwritten
	return (start, end + len(SIMULATION_SECTION_END))


def hasSimulationSection(context: str) -> bool:
	return findSimulationSection(context) is not None


def extendContext(
	context: str,
	feedback: Any,
	max_locations: int = 12,
	max_objects_per_location: int = 6,
) -> str:
	"""Add the simulation-result section to a briefing from craftContext.

	Inserted just above the MODEL RULES block so the rules stay last; appended to
	the end if the briefing has no rules block. If a section is already present
	this delegates to `editContext`, so calling it twice never duplicates.

	:param context:  the briefing string craftContext returned
	:param feedback: SimulationFeedback (or an equivalent mapping) from the run
	:returns: a new briefing string — the input is not modified
	"""
	if not isinstance(context, str) or not context.strip():
		raise ValueError("extendContext requires the briefing text from craftContext")

	if hasSimulationSection(context):
		return editContext(context, feedback, max_locations, max_objects_per_location)

	section = craftSimulationSection(
		feedback,
		max_locations=max_locations,
		max_objects_per_location=max_objects_per_location,
	)

	anchor = context.rfind(_MODEL_RULES_HEADER)
	if anchor == -1:
		return context.rstrip("\n") + "\n\n" + section + "\n"
	return context[:anchor].rstrip("\n") + "\n\n" + section + "\n\n" + context[anchor:]


def editContext(
	context: str,
	feedback: Any,
	max_locations: int = 12,
	max_objects_per_location: int = 6,
) -> str:
	"""Replace the simulation-result section with the results of a newer run.

	Everything outside the sentinels is left byte-identical, so the weather,
	scenario and destination sections stay exactly as craftContext wrote them.
	Falls through to `extendContext` when there is no section to replace, which
	makes the call safe to issue after every run without tracking whether one has
	happened yet.

	:param context:  a briefing that already carries a simulation section
	:param feedback: SimulationFeedback (or an equivalent mapping) from the new run
	:returns: a new briefing string — the input is not modified
	"""
	if not isinstance(context, str) or not context.strip():
		raise ValueError("editContext requires the briefing text to edit")

	span = findSimulationSection(context)
	if span is None:
		return extendContext(context, feedback, max_locations, max_objects_per_location)

	section = craftSimulationSection(
		feedback,
		max_locations=max_locations,
		max_objects_per_location=max_objects_per_location,
	)
	start, end = span
	return context[:start] + section + context[end:]


def stripSimulationSection(context: str) -> str:
	"""Remove the section entirely — for reverting to the pre-run briefing."""
	span = findSimulationSection(context)
	if span is None:
		return context
	start, end = span
	return (context[:start].rstrip("\n") + "\n\n" + context[end:].lstrip("\n")).strip("\n") + "\n"