# Core Dataset Reference Guide: `daily_weather_rice`

---

## Overview

`daily_weather_rice` contains daily weather observations from weather stations.

For the Rice FIFA 2026 HeatSafe project, this is one of the most important datasets because it provides the core environmental features needed to predict heat risk, estimate heat stress, and identify dangerous weather conditions during large events.

---

## Most Useful Columns for FIFA HeatSafe

| Column | Why It Matters |
|---|---|
| `average_temperature_c` | Main feature for general heat level |
| `max_temperature_c` | Captures peak daytime heat risk |
| `min_temperature_c` | Useful for overnight heat recovery analysis |
| `average_relative_humidity` | Critical for estimating heat index and human discomfort |
| `average_dew_point_f` | Measures atmospheric moisture |
| `average_wind_speed_knots` | Wind affects how efficiently people cool down |
| `cooling_degree_days_c` | Proxy for cooling/AC demand |
| `precipitation` | Rain can temporarily reduce surface heat |
| `valid_date` | Enables time-series modeling |
| `city_location_identifier` | Connects weather observations to station/city location |

---

## Column Reference

| Column | SQLAlchemy Type | Example | Explanation |
|---|---|---|---|
| `id` | `Integer` | `1` | Internal database primary key |
| `average_dew_point_f` | `Float` | `0.49` | Average daily dew point in Fahrenheit; indicates atmospheric moisture |
| `average_relative_humidity` | `Float` | `47.64` | Average daily relative humidity percentage |
| `average_sea_level_pressure_millibars` | `Float` | `1018.64` | Average daily sea-level atmospheric pressure in millibars |
| `average_temperature_c` | `Float` | `12.5` | Average daily temperature in Celsius |
| `average_visibility_km` | `Float` | `16.1` | Average daily visibility in kilometers |
| `average_wind_speed_knots` | `Float` | `3.68` | Average daily wind speed in knots |
| `city_location_identifier` | `Text` | `"K3J7"` | Weather station or city location identifier |
| `cooling_degree_days_c` | `Float` | `0.0` | Cooling demand indicator; higher values suggest more need for air conditioning |
| `heating_degree_days_c` | `Float` | `5.06` | Heating demand indicator; higher values suggest more need for heating |
| `max_temperature_c` | `Float` | `21.2` | Maximum daily temperature in Celsius |
| `min_temperature_c` | `Float` | `5.1` | Minimum daily temperature in Celsius |
| `precipitation` | `Integer` | `-1` | Daily precipitation. `0` may indicate trace precipitation, and `-1` may indicate no precipitation |
| `valid_date` | `Date` | `2021-02-23` | Date of the weather observation |

---

## Relationships to Other Datasets

### `core_poi_geometry`

Can be combined by:

- City
- Region
- Nearby location/station
- Weather grid assignment

Useful for identifying which places, buildings, and public areas are exposed to high heat risk.

---

### `daily_spend_brand_state_rice`

Can be combined by:

- Date
- Market/city
- State

Useful for studying whether extreme heat reduces consumer spending or transaction activity.

---

### Predicted Heat Grid

Can be combined by:

- Date
- City/station
- Interpolated geographic grid cell

Useful for generating red/orange/green heat-risk maps.

---

## Possible Uses for the FIFA HeatSafe Project

1. Train a machine learning model to predict heat risk.
2. Estimate heat index using temperature and humidity.
3. Identify dangerous days with high maximum temperature.
4. Estimate cooling demand using cooling degree days.
5. Compare weather risk across FIFA host cities.
6. Connect heat risk to POIs, parking lots, stadium areas, and commercial zones.
7. Support recommendations for hydration stations, cooling centers, medical staffing, and shaded routes.

---

## Limitations

- Weather data is station-level, not exact street-level data.
- Does not directly include land surface temperature.
- Does not directly include shade, trees, pavement type, or building density.
- Needs to be combined with geographic datasets to create detailed urban heat maps.

---

## Overall Importance

**Importance for HeatSafe Project:** ★★★★★ (5/5)

This is a core modeling dataset. It provides the primary environmental signals needed to predict heat risk and support public-health planning during FIFA 2026 events.