# Core Dataset Reference Guide: `urban_heat_index`

---

## Overview

`urban_heat_index` contains geographic measurements of Urban Heat Island (UHI) intensity across multiple metropolitan areas. Each record represents a specific geographic point and its associated UHI score.

For the FIFA 2026 HeatSafe project, this is one of the **most important datasets** because it provides direct measurements of urban heat intensity. It can be used to identify urban hotspots, validate machine learning predictions, and support city planning decisions.

---

# ⭐ Most Useful Columns for the FIFA HeatSafe Project

| Column | Why It Matters |
|----------|----------------|
| `latitude` | Geographic coordinate used to map heat intensity. |
| `longitude` | Geographic coordinate used to map heat intensity. |
| `uhi` | Direct measurement of Urban Heat Island intensity. |
| `market` | Compare heat conditions across FIFA host cities. |
| `point_geometry` | Exact GIS point used for spatial analysis and mapping. |

---

# Column Reference

| Column | SQLAlchemy Type | Example | Explanation |
|----------|----------------|----------|-------------|
| `id` | `Integer` | `1` | Internal database primary key. |
| `latitude` | `Float` | `32.8170` | Latitude of the UHI measurement point. |
| `longitude` | `Float` | `-96.9565` | Longitude of the UHI measurement point. |
| `market` | `Text` | `"Dallas"` | Metropolitan market or city where the measurement was collected. |
| `point_geometry` | `Text` | `"0101000000F0A7C64B373D58C07F6ABC7493684040"` | Geographic point stored in Well-Known Binary (WKB) hexadecimal format for GIS applications. |
| `uhi` | `Integer` | `7` | Urban Heat Island intensity score. Larger values indicate stronger urban heat effects. |

---

# Relationships to Other Datasets

## `daily_weather_rice`

Join by:

- Market
- Geographic location

Useful for combining atmospheric conditions with measured urban heat intensity.

---

## `core_poi_geometry`

Join by:

- Latitude
- Longitude
- Geographic proximity
- Market

Allows buildings, businesses, parking lots, and public spaces to be assigned measured UHI values.

---

## `store_visits_rice`

Join by:

- Market
- Geographic proximity

Useful for studying how urban heat affects pedestrian traffic and business visits.

---

## `spend_patterns_rice`

Join by:

- Geographic proximity
- Market

Allows comparison between consumer spending and surrounding urban heat intensity.

---

# Possible Uses for the FIFA HeatSafe Project

- Identify urban heat hotspots around FIFA venues.
- Train and validate machine learning models that predict heat risk.
- Generate interactive Urban Heat Island maps.
- Recommend locations for cooling centers and hydration stations.
- Prioritize tree planting, shade structures, and cooling infrastructure.
- Compare urban heat intensity across FIFA host cities.
- Overlay heat intensity with businesses, hospitals, parks, and transportation hubs.

---

# Limitations

- Represents point measurements rather than complete city coverage.
- Does not contain timestamps, so temporal analysis requires combining with the weather dataset.
- Measures Urban Heat Island intensity rather than direct human heat stress.

---

# Overall Importance

**Importance for HeatSafe Project:** ★★★★★ (5/5)

This is one of the core datasets for the project. It provides direct measurements of Urban Heat Island intensity and serves as an excellent foundation for heat-risk mapping, model validation, and urban planning recommendations.