# Core Dataset Reference Guide: `daily_spend_brand_state_rice`

---

## Overview

`daily_spend_brand_state_rice` contains estimated daily consumer spending aggregated by **brand**, **market**, and **state**.

Unlike the POI dataset, this table focuses on **economic activity** rather than physical locations. It allows us to estimate how consumer spending changes over time and across regions.

For the FIFA 2026 Hackathon, this dataset can help quantify the **economic impact of extreme heat**, evaluate changes in visitor behavior, and estimate business activity before, during, and after World Cup matches.

---

# ⭐ Most Useful Columns for the FIFA HeatSafe Project

| Column | Why It Matters |
|----------|----------------|
| **market** | Compare spending across FIFA host cities (Houston, Dallas, Atlanta, etc.) |
| **trans_date** | Time-series analysis before, during, and after matches or heat waves |
| **spend_amount** | Measures economic activity and visitor spending |
| **trans_count** | Estimates customer traffic / business activity |
| **brand_name** | Identify businesses or industries affected by heat |
| **state_abbr** | Enables state-level aggregation and comparisons |

---

# Column Reference

| Column | SQLAlchemy Type | Example | Description |
|----------|----------------|----------|-------------|
| `id` | `Integer` | `1` | Internal database primary key. |
| `brand_id` | `Integer` | `16000` | Unique identifier assigned to a business or brand. |
| `brand_name` | `Text` | `"ECWID"` | Name of the business or brand. |
| `market` | `Text` | `"Miami"` | Metropolitan market where spending occurred. |
| `spend_amount` | `Float` | `146.7856` | Estimated total consumer spending for that brand on a given day. |
| `state_abbr` | `Text` | `"FL"` | Two-letter state abbreviation. |
| `trans_count` | `Float` | `2.7072` | Estimated number of daily transactions. May be normalized or privacy-adjusted. |
| `trans_date` | `Date` | `2020-08-09` | Date corresponding to the spending data. |
| `version` | `Text` | `"2026-06-21"` | Dataset version or release date. |

---

# Relationships to Other Datasets

This dataset pairs well with:

### `core_poi_geometry`

Join by:
- Brand
- Market
- Geographic region

Provides:
- Exact business locations
- Building footprints
- Parking lots
- Categories

---

### Weather Dataset

Join by:
- Date
- Market
- State

Allows analysis of:

- Spending vs temperature
- Spending vs heat index
- Spending vs humidity
- Spending during heat advisories

---

### Heat Prediction Model

Can be combined with predicted heat risk to estimate:

- Economic losses due to extreme heat
- Visitor behavioral changes
- Reduced business activity
- High-risk commercial districts

---

# Possible Uses for the FIFA HeatSafe Project

### Economic Heat Impact

Estimate how much spending decreases during high heat days.

---

### Visitor Activity

Use transaction counts as a proxy for visitor movement throughout the city.

---

### Commercial Hotspots

Identify markets with unusually high economic activity that may require additional cooling infrastructure or emergency services.

---

### Heat Resilience Dashboard

Display:

- Daily spending
- Transaction volume
- Heat predictions
- Weather
- Risk level

on one interactive map.

---

# Limitations

- Data is aggregated (not individual transactions).
- Spending is estimated rather than exact.
- No precise GPS coordinates.
- Cannot directly locate individual businesses without combining with the POI dataset.

---

# Overall Importance

**Importance for HeatSafe Project:** ★★★☆☆ (3.5/5)

While not essential for predicting heat risk itself, this dataset is extremely valuable for demonstrating the **economic consequences** of extreme heat.

Example insight:

> "Predicted temperatures above 100°F are associated with a 12% reduction in daily consumer spending near commercial districts."

This type of analysis helps translate environmental risk into tangible economic impact for city planners.