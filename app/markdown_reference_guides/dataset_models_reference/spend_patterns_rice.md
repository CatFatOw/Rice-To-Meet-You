# Core Dataset Reference Guide: `spend_patterns_rice`

---

## Overview

`spend_patterns_rice` contains detailed consumer spending and shopping behavior for individual businesses. In addition to spending metrics, it includes customer demographics, online purchasing activity, visit frequency, and business information.

For the FIFA 2026 HeatSafe project, this dataset helps measure the **economic and behavioral impact** of extreme heat. It can be combined with weather and POI datasets to estimate how heat influences customer activity, spending, and business performance.

---

# ⭐ Most Useful Columns for the FIFA HeatSafe Project

| Column | Why It Matters |
|----------|----------------|
| `latitude` / `longitude` | Maps businesses onto predicted heat-risk grids. |
| `raw_total_spend` | Measures total economic activity. |
| `raw_num_customers` | Estimates customer/visitor volume. |
| `raw_num_transactions` | Estimates business activity. |
| `online_spend` | Detects shifts from in-person shopping to online shopping. |
| `spend_pct_change_vs_prev_month` | Identifies recent changes in spending. |
| `spend_pct_change_vs_prev_year` | Compares spending to historical trends. |
| `top_category` / `sub_category` | Determines which industries are most affected by heat. |
| `market` | Enables comparisons across FIFA host cities. |
| `spend_date_range_start` / `spend_date_range_end` | Connects spending with weather observations over time. |

---

# Column Reference

| Column | SQLAlchemy Type | Example | Explanation |
|----------|----------------|----------|-------------|
| `id` | `Integer` | `1` | Internal database primary key. |
| `brands` | `Text` | `"Sprouts Farmers Market"` | Name of the business or brand. |
| `bucketed_customer_frequency` | `JSON` | `{"1":611,"2":146}` | Number of customers grouped by visit frequency. |
| `bucketed_customer_incomes` | `JSON` | `{"75-100k":138}` | Customer counts grouped by income bracket. |
| `city` | `Text` | `"Daly City"` | City where the business is located. |
| `customer_home_city` | `JSON` | `{"San Francisco, CA":231}` | Distribution of customer home cities. |
| `day_counts` | `JSON` | `{"Monday":4,"Tuesday":4}` | Number of observations by weekday. |
| `iso_country_code` | `Text` | `"US"` | Country code. |
| `latitude` | `Float` | `37.668486` | Latitude of the business. |
| `longitude` | `Float` | `-122.466474` | Longitude of the business. |
| `location_name` | `Text` | `"Sprouts Farmers Market"` | Name of the physical business location. |
| `market` | `Text` | `"San Francisco Bay Area"` | Metropolitan market or region. |
| `mean_spend_per_customer_by_frequency` | `JSON` | `{"1":49.26}` | Average customer spending grouped by visit frequency. |
| `mean_spend_per_customer_by_income` | `JSON` | `{"75-100k":72.48}` | Average customer spending grouped by income bracket. |
| `median_spend_per_customer` | `Float` | `38.23` | Median spending per customer. |
| `median_spend_per_transaction` | `Float` | `30.61` | Median spending per transaction. |
| `naics_code` | `Integer` | `445110` | Standard North American Industry Classification System (NAICS) business code. |
| `online_spend` | `Float` | `235.90` | Estimated online spending. |
| `online_transactions` | `Float` | `3.42` | Estimated number of online transactions. |
| `parent_placekey` | `Text` | `"223-222@..."` | Parent location identifier if the business belongs to a larger location. |
| `placekey` | `Text` | `"223-222@8fc-9qc"` | Unique identifier for the physical business location. |
| `postal_code` | `Text` | `"94015"` | ZIP/postal code. |
| `raw_num_customers` | `Float` | `786.24` | Estimated number of customers. |
| `raw_num_transactions` | `Float` | `1232.10` | Estimated number of transactions. |
| `raw_total_spend` | `Float` | `68275.66` | Estimated total spending. |
| `region` | `Text` | `"CA"` | State or region abbreviation. |
| `related_buynowpaylater_service_pct` | `JSON` | `{"Affirm":2}` | Customer overlap with Buy Now Pay Later services. |
| `related_cross_shopping_local_brands_pct` | `JSON` | `{...}` | Customer overlap with nearby/local brands. |
| `related_cross_shopping_online_merchants_pct` | `JSON` | `{...}` | Customer overlap with online merchants. |
| `related_cross_shopping_physical_brands_pct` | `JSON` | `{...}` | Customer overlap with physical retailers. |
| `related_cross_shopping_same_category_brands_pct` | `JSON` | `{...}` | Customer overlap with businesses in the same category. |
| `related_delivery_service_pct` | `JSON` | `{"DoorDash":4}` | Delivery service usage percentages. |
| `related_payment_platform_pct` | `JSON` | `{"PayPal":2}` | Payment platform usage percentages. |
| `related_rideshare_service_pct` | `JSON` | `{"Uber":7}` | Ride-sharing service usage percentages. |
| `related_streaming_cable_pct` | `JSON` | `{...}` | Streaming and cable subscription overlap. |
| `related_wireless_carrier_pct` | `JSON` | `{...}` | Wireless carrier overlap. |
| `spend_by_day` | `JSON` | `[1803.36,2109.45,...]` | Spending values for each day in the reporting period. |
| `spend_by_day_of_week` | `JSON` | `{"Monday":14932}` | Spending totals grouped by weekday. |
| `spend_by_transaction_intermediary` | `JSON` | `{"No intermediary":65024}` | Spending grouped by payment intermediary. |
| `spend_date_range_start` | `Date` | `2020-07-01` | Beginning of the reporting period. |
| `spend_date_range_end` | `Date` | `2020-08-01` | End of the reporting period. |
| `spend_pct_change_vs_prev_month` | `Float` | `-8.0` | Spending percentage change compared to the previous month. |
| `spend_pct_change_vs_prev_year` | `Float` | `-42.0` | Spending percentage change compared to the previous year. |
| `spend_per_transaction_by_day` | `JSON` | `[33.19,43.51,...]` | Average spending per transaction for each day. |
| `spend_per_transaction_percentiles` | `JSON` | `{"25":15.98,"75":60.54}` | Distribution of spending per transaction. |
| `street_address` | `Text` | `"301 Gellert Blvd"` | Business street address. |
| `sub_category` | `Text` | `"Supermarkets"` | Specific business category. |
| `top_category` | `Text` | `"Grocery Stores"` | Broad business category. |
| `transaction_intermediary` | `JSON` | `{"No intermediary":1369}` | Number of transactions by payment intermediary. |

---

# Relationships to Other Datasets

## `daily_weather_rice`

Join by:

- Date
- City
- Market
- Region

Enables analysis of how weather conditions affect spending, customer traffic, and business performance.

---

## `core_poi_geometry`

Join by:

- `placekey`
- `parent_placekey`
- Geographic coordinates
- Business category

Provides building footprints, parking lots, and physical business locations.

---

## `daily_spend_brand_state_rice`

Join by:

- Brand
- Market
- State
- Date

Allows comparison between individual business spending and aggregated brand-level spending.

---

# Possible Uses for the FIFA HeatSafe Project

- Estimate the economic impact of extreme heat.
- Measure changes in customer activity during heat waves.
- Detect shifts from in-person shopping to online shopping.
- Identify businesses most vulnerable to heat.
- Prioritize cooling infrastructure around high-value commercial districts.
- Compare spending patterns across FIFA host cities.
- Support urban planning decisions using business activity and weather data.

---

# Limitations

- Spending values are estimated rather than exact.
- Customer data is aggregated for privacy.
- Many behavioral features are stored as JSON and require parsing.
- Date fields represent reporting periods rather than individual transactions.
- Does not directly measure weather and should be combined with the weather dataset.

---

# Overall Importance

**Importance for HeatSafe Project:** ★★★★☆ (4/5)

This dataset is one of the strongest for measuring the **economic and behavioral impacts** of extreme heat. While it is not used directly to predict heat, it provides valuable insight into how businesses and consumers respond to extreme weather conditions, making it an excellent complement to the weather and POI datasets.