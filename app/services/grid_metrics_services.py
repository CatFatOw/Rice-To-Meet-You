"""File handles the core route logic for the grid_metric routes"""


RISK_BUCKETS = [
    ("Extreme (80-100)", 80, 101, "#c43f52"),
    ("High (60-80)", 60, 80, "#e45b3f"),
    ("Moderate (40-60)", 40, 60, "#e8aa35"),
    ("Low (20-40)", 20, 40, "#83bf4f"),
    ("Minimal (0-20)", 0, 20, "#4aa39c"),
]


# Buckets and colors match the OverallStatistics donut legend in the frontend.

def add_cell_id(metric):
    """Attach the readable grid cell_id to a metric response."""
    if metric and metric.grid_cell:
        metric.cell_id = metric.grid_cell.cell_id
    return metric

def add_cell_ids(metrics):
    """Attach readable grid cell_id values to metric responses."""
    return [add_cell_id(metric) for metric in metrics]


def heat_risk_value(metric):
    """Return the preferred heat risk score for a metric row.

    Some metric rows may have heat_index but not heat_risk while data is being
    backfilled, so the statistics panel falls back gracefully.
    """
    value = getattr(metric, "heat_risk", None)
    if value is not None:
        return value
    return getattr(metric, "heat_index", None) or 0


def risk_level_label(score: float) -> str:
    if score >= 80:
        return "Extreme"
    if score >= 60:
        return "High"
    if score >= 40:
        return "Moderate"
    if score >= 20:
        return "Low"
    return "Minimal"


def format_compact_number(value: float | int | None) -> str:
    """Format large counts for compact dashboard cards."""
    value = float(value or 0)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(int(round(value)))


def cell_display_name(metric) -> str:
    """Convert a grid metric row into a readable label for top-risk lists."""
    grid_cell = getattr(metric, "grid_cell", None)
    cell_id = getattr(grid_cell, "cell_id", None)
    if not cell_id:
        return f"Grid Cell {metric.grid_cell_id}"
    return cell_id.replace("_", " ").title()


def build_risk_distribution(metrics):
    """Count latest metric rows into the frontend heat-risk buckets."""
    distribution = []
    for label, lower, upper, color in RISK_BUCKETS:
        count = sum(1 for metric in metrics if lower <= heat_risk_value(metric) < upper)
        distribution.append({"label": label, "value": count, "color": color})
    return distribution


def build_top_destinations(metrics, limit: int = 5):
    """Return the highest-risk grid zones for the top destinations list."""
    sorted_metrics = sorted(metrics, key=heat_risk_value, reverse=True)
    return [
        {"name": cell_display_name(metric), "score": round(heat_risk_value(metric))}
        for metric in sorted_metrics[:limit]
    ]


def build_stat_cards(metrics):
    """Build the four summary cards shown above the donut and rankings."""
    average_heat_risk = round(
        sum(heat_risk_value(metric) for metric in metrics) / len(metrics)
    ) if metrics else 0
    total_visitors = sum(getattr(metric, "crowd_density", None) or 0 for metric in metrics)
    at_risk_population = sum(
        getattr(metric, "population", None) or 0
        for metric in metrics
        if heat_risk_value(metric) >= 60
    )
    extreme_count = sum(1 for metric in metrics if heat_risk_value(metric) >= 80)

    return [
        {
            "icon": "sun",
            "iconClassName": "text-red-400",
            "label": "Average Heat Risk",
            "value": str(average_heat_risk),
            "suffix": risk_level_label(average_heat_risk),
            "suffixClassName": "text-orange-400",
        },
        {
            "icon": "users",
            "iconClassName": "text-indigo-400",
            "label": "Total Visitors (est.)",
            "value": format_compact_number(total_visitors),
        },
        {
            "icon": "users",
            "iconClassName": "text-red-400",
            "label": "At Risk Population",
            "value": format_compact_number(at_risk_population),
        },
        {
            "icon": "wind",
            "iconClassName": "text-yellow-400",
            "label": "Zones in Extreme Risk",
            "value": str(extreme_count),
        },
    ]


def build_overall_statistics(city: str, latest_metrics):
    """Build the frontend overall-statistics panel from latest metrics."""
    is_national = city == "Nationally"
    return {
        "title": "National Summary" if is_national else f"{city} Summary",
        "donutLabel": "Zones",
        "topDestinations": build_top_destinations(latest_metrics),
        "distribution": build_risk_distribution(latest_metrics),
        "statCardsInfo": build_stat_cards(latest_metrics),
    }


def build_poi_statistics(city: str, pois, latest_metrics):
    """Build the frontend POI-statistics panel from saved POI polygons.

    Until POIs have their own visitor/risk fact table, polygon rows receive the
    current city average. If no POI polygons exist, the table falls back to the
    highest-risk grid zones so the panel still has useful data.
    """
    average_heat_risk = round(
        sum(heat_risk_value(metric) for metric in latest_metrics) / len(latest_metrics)
    ) if latest_metrics else 0
    average_visitors = sum(
        getattr(metric, "crowd_density", None) or 0 for metric in latest_metrics
    ) / len(latest_metrics) if latest_metrics else 0

    poi_rows = [
        {
            "name": poi.name or f"Region {poi.id}",
            "type": "POI Polygon",
            "heatRisk": average_heat_risk,
            "visitors": format_compact_number(average_visitors),
        }
        for poi in pois[:5]
    ]

    if not poi_rows:
        poi_rows = [
            {
                "name": destination["name"],
                "type": "Grid Zone",
                "heatRisk": destination["score"],
                "visitors": format_compact_number(average_visitors),
            }
            for destination in build_top_destinations(latest_metrics)
        ]

    return {
        "title": "Key POIs Nationally" if city == "Nationally" else f"Key POIs in {city}",
        "cityName": city,
        "pois": poi_rows,
    }


SIMULATION_OBJECT_EFFECTS = {
    "cooling_station": {
        "heat_index_delta": -5,
        "heat_risk_delta": -7,
        "infrastructure_strain_delta": -4,
        "cooling_centers_delta": 1,
    },
    "shade_canopy": {
        "heat_index_delta": -3,
        "heat_risk_delta": -4,
        "infrastructure_strain_delta": -1,
        "cooling_centers_delta": 0,
    },
    "water_station": {
        "heat_index_delta": -1,
        "heat_risk_delta": -3,
        "infrastructure_strain_delta": -2,
        "cooling_centers_delta": 0,
    },
    "misting_fan": {
        "heat_index_delta": -4,
        "heat_risk_delta": -5,
        "infrastructure_strain_delta": -2,
        "cooling_centers_delta": 0,
    },
    "first_aid": {
        "heat_index_delta": 0,
        "heat_risk_delta": -2,
        "infrastructure_strain_delta": -5,
        "cooling_centers_delta": 0,
    },
    "tree_planting": {
        "heat_index_delta": -2,
        "heat_risk_delta": -3,
        "infrastructure_strain_delta": -1,
        "cooling_centers_delta": 0,
    },
}


def simulation_adjustments_from_objects(placed_objects):
    """Translate frontend toolbox objects into aggregate metric adjustments."""
    adjustments = {
        "heat_index_delta": 0,
        "heat_risk_delta": 0,
        "infrastructure_strain_delta": 0,
        "cooling_centers_delta": 0,
    }

    for placed_object in placed_objects:
        effect = SIMULATION_OBJECT_EFFECTS.get(placed_object.type)
        if not effect:
            continue
        for key, value in effect.items():
            adjustments[key] += value

    return adjustments
