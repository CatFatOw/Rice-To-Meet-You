# Core Dataset Reference Guide: `store_visits_rice`

---

## Overview

`store_visits_rice` contains estimated daily foot traffic for businesses across multiple markets. Each record represents the estimated number of customer visits to a specific business on a given day.

For the FIFA 2026 HeatSafe project, this dataset is useful for measuring **human mobility**, **commercial activity**, and **visitor density**. Combined with weather and heat predictions, it can help estimate how extreme heat influences where people travel and which commercial areas experience the highest risk.

---

# ⭐ Most Useful Columns for the FIFA HeatSafe Project

| Column | Why It Matters |
|----------|----------------|
| **daily_visits** | Measures estimated customer traffic and crowd density. |
| **local_date** | Allows time-series analysis alongside weather observations. |
| **market** | Compare visitor activity across FIFA host cities. |
| **category** | Analyze which industries experience the most traffic. |
| **sub_category** | Provides more detailed business classifications. |
| **naics_code** | Standard business classification for filtering industries. |
| **brand** | Compare traffic across major businesses and chains. |
| **store_id** | Unique identifier for tracking individual stores over time. |

---

# Column Reference

| Column | SQLAlchemy Type | Example | Explanation |
|----------|----------------|----------|-------------|
| `id` | `Integer` | `1` | Internal database primary key. |
| `brand` | `Text` | `"Burger King"` | Brand associated with the business. |
| `category` | `Text` | `"Restaurants and Other Eating Places"` | High-level business or industry category. |
| `daily_visits` | `Integer` | `2733` | Estimated number of customer visits to the store for that day. |
| `local_date` | `Date` | `2022-10-26` | Local calendar date corresponding to the visit data. |
| `market` | `Text` | `"Miami"` | Metropolitan market or city where the store is located. |
| `naics_code` | `Integer` | `722513` | Standard North American Industry Classification System (NAICS) business code. |
| `business_name` | `Text` | `"Burger King"` | Name of the business or store location. |
| `state` | `Text` | `"FL"` | Two-letter state abbreviation. |
| `stock_exchange` | `Text` | `"NYSE"` | Public stock exchange of the parent company, if applicable. |
| `stock_symbol` | `Text` | `"QSR"` | Parent company's public stock ticker symbol. |
| `store_id` | `Text` | `"3bdb3171-cb36-41b1-b684-c99b191fa733"` | Unique identifier assigned to the store. |
| `sub_category` | `Text` | `"Limited-Service Restaurants"` | More specific business category. |
| `version_id` | `Integer` | `9` | Dataset version number. |

---

# Relationships to Other Datasets

## `daily_weather_rice`

Join by:

- Date
- Market
- State

Useful for studying how temperature, humidity, precipitation, and other weather conditions influence daily store visits.

---

## `core_poi_geometry`

Join by:

- NAICS code
- Business name
- Geographic location

Provides exact business locations, building footprints, and parking lot information.

---

## `spend_patterns_rice`

Join by:

- Brand
- Market
- NAICS code

Allows comparison between customer traffic and consumer spending behavior.

---

## `daily_spend_brand_state_rice`

Join by:

- Brand
- Market
- State
- Date

Provides broader brand-level spending trends to compare against store visit counts.

---

# Possible Uses for the FIFA HeatSafe Project

- Estimate how extreme heat affects customer foot traffic.
- Identify commercial hotspots with high pedestrian density.
- Compare visitor activity before, during, and after FIFA matches.
- Recommend locations for hydration stations and cooling centers.
- Detect businesses most impacted by heat-related reductions in foot traffic.
- Support evacuation and crowd-management planning around commercial districts.
- Analyze mobility trends across FIFA host cities.

---

# Limitations

- Visit counts are estimated rather than exact.
- Does not contain individual visitor information.
- Does not include geographic coordinates directly.
- Best used together with the POI and weather datasets for spatial analysis.

---

# Overall Importance

**Importance for HeatSafe Project:** ★★★★☆ (4/5)

This dataset is one of the strongest indicators of **human mobility**. When combined with weather, POI, and spending datasets, it helps explain how extreme heat affects pedestrian movement, commercial activity, and crowd distribution during large events such as the FIFA World Cup.
```