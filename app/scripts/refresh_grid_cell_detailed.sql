-- Rebuilds the production-ready, prediction-free grid-cell table.
BEGIN;
DROP TABLE IF EXISTS production.grid_cell_metrics_detailed;
DROP TABLE IF EXISTS production.grid_cell_detailed;

CREATE TABLE production.grid_cell_metrics_detailed AS
WITH heat_base AS (
    SELECT m.grid_cell_id, d.*
    FROM datasets.heat_weather_points_feature_engineered d
    JOIN production.grid_cell_metrics m
      ON m.metric_source_kind = 'heat_weather_point'
     AND m.date = d.date AND m.latitude = d.latitude AND m.longitude = d.longitude
), heat_summary AS (
    SELECT grid_cell_id, count(*) heat_weather_observation_count,
      min(date) heat_weather_first_date, max(date) heat_weather_last_date,
      avg(avg_temperature_c) heat_weather_avg_temperature_c,
      min(avg_temperature_c) heat_weather_min_temperature_c,
      max(avg_temperature_c) heat_weather_max_temperature_c,
      avg(relative_humidity) heat_weather_avg_relative_humidity,
      avg(wind_speed_knots) heat_weather_avg_wind_speed_knots,
      avg(uhi) heat_weather_avg_uhi, max(uhi) heat_weather_max_uhi,
      avg(distance_to_nearest_station_km) heat_weather_avg_station_distance_km,
      count(*) FILTER (WHERE passed_threshold) heat_weather_threshold_observation_count,
      array_agg(DISTINCT source) FILTER (WHERE source IS NOT NULL) heat_weather_sources
    FROM heat_base GROUP BY grid_cell_id
), latest_heat AS (
    SELECT DISTINCT ON (grid_cell_id) grid_cell_id, date latest_heat_weather_date,
      avg_temperature_c latest_avg_temperature_c, relative_humidity latest_relative_humidity,
      wind_speed_knots latest_wind_speed_knots, uhi latest_uhi,
      source latest_heat_weather_source, distance_to_nearest_station_km latest_station_distance_km,
      passed_threshold latest_passed_threshold
    FROM heat_base ORDER BY grid_cell_id, date DESC
), comfort AS (
    SELECT lh.*, CASE WHEN latest_avg_temperature_c IS NOT NULL AND latest_relative_humidity IS NOT NULL THEN
      latest_avg_temperature_c * atan(0.151977 * sqrt(latest_relative_humidity + 8.313659))
      + atan(latest_avg_temperature_c + latest_relative_humidity)
      - atan(latest_relative_humidity - 1.676331)
      + 0.00391838 * power(latest_relative_humidity, 1.5) * atan(0.023101 * latest_relative_humidity)
      - 4.686035 END AS latest_wet_bulb_temperature_c
    FROM latest_heat lh
), fpi AS (
    SELECT *, latest_wind_speed_knots * 0.514444 AS wind_speed_mps,
      CASE WHEN latest_wet_bulb_temperature_c IS NOT NULL THEN least(100.0, greatest(0.0, 100.0 * (latest_wet_bulb_temperature_c - 18) / 12)) END wet_bulb_heat_stress_score,
      CASE WHEN latest_wind_speed_knots IS NOT NULL THEN least(100.0, greatest(0.0, 100.0 * (3.5 - latest_wind_speed_knots * 0.514444) / 3.5)) END low_wind_risk_score,
      CASE WHEN latest_uhi IS NOT NULL THEN least(100.0, greatest(0.0, 100.0 * (latest_uhi - 1) / 10)) END uhi_exposure_risk_score
    FROM comfort
), visitor_summary AS (
    SELECT grid_cell_id, count(*) visitor_observation_count, min(date) visitor_first_date, max(date) visitor_last_date,
      sum(visitor_count) visitor_total, avg(visitor_count) visitor_avg, max(visitor_count) visitor_max
    FROM production.grid_cell_metrics WHERE metric_source_kind='visitor_poi' GROUP BY grid_cell_id
), latest_visitor AS (
    SELECT DISTINCT ON (grid_cell_id) grid_cell_id, date latest_visitor_date, visitor_count latest_visitor_count,
      name latest_visitor_place_name, category latest_visitor_category, fsq_place_id latest_fsq_place_id,
      placekey latest_placekey, visitor_count_source latest_visitor_count_source,
      source_period_start latest_visitor_period_start, source_period_end latest_visitor_period_end
    FROM production.grid_cell_metrics WHERE metric_source_kind='visitor_poi' ORDER BY grid_cell_id, date DESC, id DESC
), latest_observed_metric AS (
    SELECT DISTINCT ON (grid_cell_id) grid_cell_id, date latest_metric_date, timestamp latest_metric_timestamp,
      heat_index, heat_risk, crowd_density, population, cooling_centers, cooling_centers_impact_radius,
      infrastructure_strain, heat_index_color, heat_risk_color, crowd_density_color, population_color,
      cooling_centers_color, infrastructure_strain_color, overall_risk_color,
      visitor_metric_source, visitor_metric_is_placeholder, population_metric_source, population_metric_is_placeholder
    FROM production.grid_cell_metrics ORDER BY grid_cell_id, coalesce(timestamp, created_at) DESC, id DESC
), latest_interpolation AS (
    SELECT DISTINCT ON (grid_cell_id)
      grid_cell_id,
      timestamp AS interpolated_at,
      interpolation_method,
      source_count AS interpolation_source_count,
      confidence AS interpolation_confidence,
      heat_index AS interpolated_heat_index,
      heat_risk AS interpolated_heat_risk,
      crowd_density AS interpolated_crowd_density,
      population AS interpolated_population,
      cooling_centers AS interpolated_cooling_centers,
      infrastructure_strain AS interpolated_infrastructure_strain
    FROM production.interpolated_points
    ORDER BY grid_cell_id, timestamp DESC, id DESC
)
SELECT g.id grid_cell_id, g.cell_id, g.row grid_row, g.col grid_col,
  -- Plain latitude/longitude are the frontend/backend contract.
  g.grid_centroid_lat AS latitude, g.grid_centroid_lon AS longitude,
  g.geometry cell_geometry, g.state, g.nws_grid_id, g.nws_grid_x, g.nws_grid_y,
  g.forecast_hourly nws_forecast_hourly_url, g.nws_metadata_checked_at,
  hs.heat_weather_observation_count, hs.heat_weather_first_date, hs.heat_weather_last_date,
  hs.heat_weather_avg_temperature_c, hs.heat_weather_min_temperature_c, hs.heat_weather_max_temperature_c,
  hs.heat_weather_avg_relative_humidity, hs.heat_weather_avg_wind_speed_knots, hs.heat_weather_avg_uhi,
  hs.heat_weather_max_uhi, hs.heat_weather_avg_station_distance_km, hs.heat_weather_threshold_observation_count, hs.heat_weather_sources,
  f.latest_heat_weather_date, f.latest_avg_temperature_c, f.latest_relative_humidity, f.latest_wind_speed_knots,
  f.latest_uhi, f.latest_heat_weather_source, f.latest_station_distance_km, f.latest_passed_threshold,
  f.latest_wet_bulb_temperature_c, f.wind_speed_mps, f.wet_bulb_heat_stress_score, f.low_wind_risk_score, f.uhi_exposure_risk_score,
  f.wet_bulb_heat_stress_score * .60 AS heat_load_component,
  f.low_wind_risk_score * .20 AS low_wind_penalty,
  f.uhi_exposure_risk_score * .20 AS uhi_exposure_component,
  CASE WHEN f.wet_bulb_heat_stress_score IS NULL OR f.low_wind_risk_score IS NULL OR f.uhi_exposure_risk_score IS NULL THEN NULL
       ELSE round((100 - (.60*f.wet_bulb_heat_stress_score + .20*f.low_wind_risk_score + .20*f.uhi_exposure_risk_score))::numeric,0)::integer END football_playability_index,
  CASE WHEN f.wet_bulb_heat_stress_score IS NULL OR f.low_wind_risk_score IS NULL OR f.uhi_exposure_risk_score IS NULL THEN NULL
       ELSE round((.60*f.wet_bulb_heat_stress_score + .20*f.low_wind_risk_score + .20*f.uhi_exposure_risk_score)::numeric,0)::integer END football_playability_risk_score,
  CASE WHEN f.wet_bulb_heat_stress_score IS NULL OR f.low_wind_risk_score IS NULL OR f.uhi_exposure_risk_score IS NULL THEN NULL
       WHEN 100 - (.60*f.wet_bulb_heat_stress_score + .20*f.low_wind_risk_score + .20*f.uhi_exposure_risk_score) >= 80 THEN 'excellent'
       WHEN 100 - (.60*f.wet_bulb_heat_stress_score + .20*f.low_wind_risk_score + .20*f.uhi_exposure_risk_score) >= 60 THEN 'playable'
       WHEN 100 - (.60*f.wet_bulb_heat_stress_score + .20*f.low_wind_risk_score + .20*f.uhi_exposure_risk_score) >= 40 THEN 'caution'
       ELSE 'high_stress' END AS football_playability_band,
  vs.visitor_observation_count, vs.visitor_first_date, vs.visitor_last_date, vs.visitor_total, vs.visitor_avg, vs.visitor_max,
  lv.latest_visitor_date, lv.latest_visitor_count, lv.latest_visitor_place_name, lv.latest_visitor_category,
  lv.latest_fsq_place_id, lv.latest_placekey, lv.latest_visitor_count_source, lv.latest_visitor_period_start, lv.latest_visitor_period_end,
  om.latest_metric_date, om.latest_metric_timestamp, om.heat_index, om.heat_risk, om.crowd_density, om.population,
  om.cooling_centers, om.cooling_centers_impact_radius, om.infrastructure_strain, om.heat_index_color, om.heat_risk_color,
  om.crowd_density_color, om.population_color, om.cooling_centers_color, om.infrastructure_strain_color, om.overall_risk_color,
  om.visitor_metric_source, om.visitor_metric_is_placeholder, om.population_metric_source, om.population_metric_is_placeholder,
  (li.grid_cell_id IS NOT NULL) AS has_interpolated_values,
  li.interpolated_at, li.interpolation_method, li.interpolation_source_count, li.interpolation_confidence,
  li.interpolated_heat_index, li.interpolated_heat_risk, li.interpolated_crowd_density,
  li.interpolated_population, li.interpolated_cooling_centers, li.interpolated_infrastructure_strain,
  wf.id nearest_open_meteo_forecast_id, wf.latitude open_meteo_latitude, wf.longitude open_meteo_longitude, wf.fetched_at open_meteo_fetched_at,
  6371.0088 * acos(least(1.0, greatest(-1.0, sin(radians(g.grid_centroid_lat))*sin(radians(wf.latitude)) + cos(radians(g.grid_centroid_lat))*cos(radians(wf.latitude))*cos(radians(wf.longitude-g.grid_centroid_lon))))) AS open_meteo_distance_km
FROM production.grid_cell_geometry g
LEFT JOIN heat_summary hs ON hs.grid_cell_id=g.id LEFT JOIN fpi f ON f.grid_cell_id=g.id
LEFT JOIN visitor_summary vs ON vs.grid_cell_id=g.id LEFT JOIN latest_visitor lv ON lv.grid_cell_id=g.id
LEFT JOIN latest_observed_metric om ON om.grid_cell_id=g.id
LEFT JOIN latest_interpolation li ON li.grid_cell_id=g.id
LEFT JOIN LATERAL (SELECT * FROM api_data.open_meteo_forecasts ORDER BY sin(radians(g.grid_centroid_lat))*sin(radians(latitude)) + cos(radians(g.grid_centroid_lat))*cos(radians(latitude))*cos(radians(longitude-g.grid_centroid_lon)) DESC, fetched_at DESC LIMIT 1) wf ON true;

ALTER TABLE production.grid_cell_metrics_detailed ADD PRIMARY KEY (grid_cell_id);
CREATE INDEX grid_cell_metrics_detailed_state_idx ON production.grid_cell_metrics_detailed(state);
CREATE INDEX grid_cell_metrics_detailed_fpi_idx ON production.grid_cell_metrics_detailed(football_playability_index);
COMMENT ON TABLE production.grid_cell_metrics_detailed IS 'Frontend/backend-ready per-grid-cell aggregate. Each row has latitude, longitude, state, grid geometry, observed/derived metrics, and the latest saved interpolation metadata/values when available. It intentionally excludes prediction columns.';
COMMIT;
