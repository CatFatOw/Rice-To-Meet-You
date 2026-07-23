# Local data layers and `grid_cell_detailed`

The local `RiceFifaHackathon` database uses this search path by default:

```text
production, api_data, datasets, public
```

Existing PyCharm/FastAPI models keep using unqualified names such as
`grid_cell_metrics` and `open_meteo_forecasts`; PostgreSQL resolves them to the
canonical schema first. No backend code change is required.

## Table layers

| Schema | Purpose | Tables |
| --- | --- | --- |
| `production` | Stable application-facing tables used by the frontend/backend. | `grid_cell_geometry`, `grid_cell_metrics`, `interpolated_points`, `polygon_geometry`, `polygon_impact_grids`, `grid_cell_metrics_detailed` |
| `api_data` | Raw external API responses; retain provenance and payloads. | `open_meteo_forecasts`, `weather_observation`, `urban_heat_index` |
| `datasets` | Imported historical/ML source data; not an API contract. | `heat_weather_points_feature_engineered`, `core_poi_geometry`, `daily_*`, `spend_patterns_rice`, `store_visits_rice`, `heat_data_ml`, `visitor_data_ml`, `prediction_table` |
| `public` | Authentication and migration metadata only. | `user`, `alembic_version` |

## `production.grid_cell_metrics_detailed`

One row represents one grid cell. It contains observed/derived data only; it
intentionally has **no `predicted_*` columns**.

| Columns | Meaning |
| --- | --- |
| `grid_cell_id`, `cell_id`, `grid_row`, `grid_col` | Stable numeric and readable grid identifiers plus row/column position. |
| `latitude`, `longitude`, `state`, `cell_geometry` | **Backend/frontend-compatible location contract**: point coordinate, state, and GeoJSON cell boundary. No centroid-named coordinate columns exist in this table. |
| `nws_grid_id`, `nws_grid_x`, `nws_grid_y`, `nws_forecast_hourly_url`, `nws_metadata_checked_at` | Cached National Weather Service grid mapping and its refresh time. |
| `heat_weather_observation_count`, `heat_weather_first_date`, `heat_weather_last_date` | Number and date coverage of engineered heat-weather observations for this cell. |
| `heat_weather_avg_temperature_c`, `heat_weather_min_temperature_c`, `heat_weather_max_temperature_c` | Mean, minimum, and maximum observed air temperature in Celsius. |
| `heat_weather_avg_relative_humidity`, `heat_weather_avg_wind_speed_knots` | Mean relative humidity (%) and wind speed (knots). |
| `heat_weather_avg_uhi`, `heat_weather_max_uhi` | Mean and maximum urban-heat-island value. |
| `heat_weather_avg_station_distance_km`, `heat_weather_threshold_observation_count`, `heat_weather_sources` | Average station distance, count of records meeting the source threshold, and source labels. |
| `latest_heat_weather_date`, `latest_avg_temperature_c`, `latest_relative_humidity`, `latest_wind_speed_knots`, `latest_uhi` | Most recent engineered heat-weather observation. |
| `latest_heat_weather_source`, `latest_station_distance_km`, `latest_passed_threshold` | Provenance, station distance, and threshold flag for that latest heat row. |
| `latest_wet_bulb_temperature_c`, `wind_speed_mps` | Humidity-adjusted heat estimate and wind converted from knots to metres/second. |
| `wet_bulb_heat_stress_score` | 0–100 heat/humidity risk; higher is worse. |
| `low_wind_risk_score` | 0–100 low-wind risk after converting knots to metres/second; higher is worse. |
| `uhi_exposure_risk_score` | 0–100 urban-heat-island exposure risk; higher is worse. |
| `heat_load_component`, `low_wind_penalty`, `uhi_exposure_component` | The weighted 60%, 20%, and 20% contributions to total football heat risk. |
| `football_playability_index` | 0–100 outdoor-football condition score: higher is more playable. Formula: `100 − (0.60 × wet-bulb risk + 0.20 × low-wind risk + 0.20 × UHI risk)`. |
| `football_playability_risk_score`, `football_playability_band` | The inverse FPI risk score and its label: `excellent` (80–100), `playable` (60–79), `caution` (40–59), or `high_stress` (0–39). |
| `visitor_observation_count`, `visitor_first_date`, `visitor_last_date`, `visitor_total`, `visitor_avg`, `visitor_max` | Coverage and summary statistics for visitor/POI observations. |
| `latest_visitor_date`, `latest_visitor_count`, `latest_visitor_place_name`, `latest_visitor_category` | Most recent visitor observation and its POI label/category. |
| `latest_fsq_place_id`, `latest_placekey`, `latest_visitor_count_source`, `latest_visitor_period_start`, `latest_visitor_period_end` | Visitor-data identifiers, provenance, and source period. |
| `latest_metric_date`, `latest_metric_timestamp` | Timestamp of the most recent non-prediction metric snapshot. |
| `heat_index`, `heat_risk`, `crowd_density`, `population`, `cooling_centers`, `cooling_centers_impact_radius`, `infrastructure_strain` | Latest observed operational metrics already used by the frontend. |
| `heat_index_color`, `heat_risk_color`, `crowd_density_color`, `population_color`, `cooling_centers_color`, `infrastructure_strain_color`, `overall_risk_color` | Frontend map/display colors for the corresponding observed metrics. |
| `visitor_metric_source`, `visitor_metric_is_placeholder`, `population_metric_source`, `population_metric_is_placeholder` | Provenance and placeholder disclosure for visitor/population metrics. |
| `has_interpolated_values`, `interpolated_at`, `interpolation_method`, `interpolation_source_count`, `interpolation_confidence` | Whether a saved interpolation exists for the grid cell, when/how it was created, and its source/quality metadata. |
| `interpolated_heat_index`, `interpolated_heat_risk`, `interpolated_crowd_density`, `interpolated_population`, `interpolated_cooling_centers`, `interpolated_infrastructure_strain` | Latest saved interpolated operational values. They remain `NULL` until the backend runs and saves an interpolation; no fake values are inserted. |
| `nearest_open_meteo_forecast_id`, `open_meteo_latitude`, `open_meteo_longitude`, `open_meteo_fetched_at`, `open_meteo_distance_km` | Link to the nearest raw Open-Meteo record in `api_data.open_meteo_forecasts`, plus its location, freshness, and great-circle distance. Join on the ID when the full JSON payload is needed. |

## Refreshing after new data arrives

Run the aggregate refresh after loading new engineered weather, visitor, or
Open-Meteo data:

```bash
psql -h 127.0.0.1 -U postgres -d RiceFifaHackathon \
  -f app/scripts/refresh_grid_cell_detailed.sql
```

The refresh is replace-in-place, so application queries see one consistent
production table after the transaction commits.
