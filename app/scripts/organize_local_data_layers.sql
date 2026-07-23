-- Canonical local data layers. Run against RiceFifaHackathon as the database owner.
BEGIN;

CREATE SCHEMA IF NOT EXISTS production;
CREATE SCHEMA IF NOT EXISTS api_data;
CREATE SCHEMA IF NOT EXISTS datasets;

-- Application-facing operational tables.
ALTER TABLE IF EXISTS public.grid_cell_geometry SET SCHEMA production;
ALTER TABLE IF EXISTS public.grid_cell_metrics SET SCHEMA production;
ALTER TABLE IF EXISTS public.interpolated_points SET SCHEMA production;
ALTER TABLE IF EXISTS public.polygon_geometry SET SCHEMA production;
ALTER TABLE IF EXISTS public.polygon_impact_grids SET SCHEMA production;

-- Raw responses fetched from external APIs.
ALTER TABLE IF EXISTS public.open_meteo_forecasts SET SCHEMA api_data;
ALTER TABLE IF EXISTS public.weather_observation SET SCHEMA api_data;
ALTER TABLE IF EXISTS public.urban_heat_index SET SCHEMA api_data;

-- Imported, historical, or ML-training data. These are never frontend contracts.
ALTER TABLE IF EXISTS public.core_poi_geometry SET SCHEMA datasets;
ALTER TABLE IF EXISTS public.daily_spend_brand_state_rice SET SCHEMA datasets;
ALTER TABLE IF EXISTS public.daily_weather_rice SET SCHEMA datasets;
ALTER TABLE IF EXISTS public.heat_data_ml SET SCHEMA datasets;
ALTER TABLE IF EXISTS public.heat_weather_points_feature_engineered SET SCHEMA datasets;
ALTER TABLE IF EXISTS public.prediction_table SET SCHEMA datasets;
ALTER TABLE IF EXISTS public.spend_patterns_rice SET SCHEMA datasets;
ALTER TABLE IF EXISTS public.store_visits_rice SET SCHEMA datasets;
ALTER TABLE IF EXISTS public.visitor_data_ml SET SCHEMA datasets;

-- The previous aggregate is replaced by production.grid_cell_detailed.
DROP TABLE IF EXISTS public.grid_cell_plus_detailed;

-- New app connections resolve canonical tables first. `public` remains last for
-- authentication metadata and legacy migrations such as alembic_version.
ALTER DATABASE "RiceFifaHackathon"
    SET search_path = production, api_data, datasets, public;

COMMIT;
