-- Replace one state's placeholder metric snapshot with metrics backed by its
-- NWS observations.  Values with no authoritative, same-location source are
-- deliberately left NULL; do not substitute random/demo values.
--
-- Usage:
--   psql "$DATABASE_URL" -v state=Texas -f scripts/refresh_live_nws_metrics.sql

BEGIN;

-- The old seeded/demo snapshot is the only pre-NWS snapshot in this database.
-- Scope the deletion to the selected state so other history is preserved.
DELETE FROM grid_cell_metrics AS metric
USING grid_cell_geometry AS cell
WHERE metric.grid_cell_id = cell.id
  AND cell.state = :'state'
  AND metric.timestamp = TIMESTAMPTZ '2026-06-29 17:00:00+00';

-- Make the script repeatable when NWS returns the same forecast period again.
DELETE FROM grid_cell_metrics AS metric
USING grid_cell_geometry AS cell, weather_observation AS observation
WHERE metric.grid_cell_id = cell.id
  AND observation.grid_cell_id = cell.id
  AND metric.timestamp = observation.timestamp
  AND cell.state = :'state'
  AND observation.source = 'NWS';

WITH latest_nws AS (
    SELECT DISTINCT ON (observation.grid_cell_id)
        observation.grid_cell_id,
        observation.timestamp,
        observation.temperature,
        observation.humidity
    FROM weather_observation AS observation
    JOIN grid_cell_geometry AS cell ON cell.id = observation.grid_cell_id
    WHERE cell.state = :'state'
      AND observation.source = 'NWS'
    ORDER BY observation.grid_cell_id, observation.timestamp DESC, observation.id DESC
), heat AS (
    SELECT
        grid_cell_id,
        timestamp,
        CASE
            WHEN temperature IS NULL OR humidity IS NULL THEN NULL
            WHEN temperature < 80 OR humidity < 40 THEN temperature
            ELSE (
                -42.379
                + 2.04901523 * temperature
                + 10.14333127 * humidity
                - 0.22475541 * temperature * humidity
                - 0.00683783 * temperature * temperature
                - 0.05481717 * humidity * humidity
                + 0.00122874 * temperature * temperature * humidity
                + 0.00085282 * temperature * humidity * humidity
                - 0.00000199 * temperature * temperature * humidity * humidity
            )
        END AS heat_index
    FROM latest_nws
), normalized AS (
    SELECT
        grid_cell_id,
        timestamp,
        ROUND(heat_index::numeric, 1)::double precision AS heat_index,
        CASE
            WHEN heat_index IS NULL THEN NULL
            WHEN heat_index >= 125 THEN 100
            WHEN heat_index >= 112 THEN 90
            WHEN heat_index >= 103 THEN 80
            WHEN heat_index >= 96 THEN 65
            WHEN heat_index >= 91 THEN 50
            WHEN heat_index >= 80 THEN 30
            ELSE 0
        END::double precision AS heat_risk
    FROM heat
)
INSERT INTO grid_cell_metrics (
    grid_cell_id, timestamp, heat_index, heat_risk,
    crowd_density, population, cooling_centers, cooling_centers_impact_radius,
    infrastructure_strain, heat_index_color, heat_risk_color,
    crowd_density_color, population_color, cooling_centers_color,
    infrastructure_strain_color, overall_risk_color
)
SELECT
    grid_cell_id,
    timestamp,
    heat_index,
    heat_risk,
    NULL, NULL, NULL, NULL, NULL,
    CASE
        WHEN heat_index >= 110 THEN '#8B0000'
        WHEN heat_index >= 103 THEN '#FF4500'
        WHEN heat_index >= 95 THEN '#FFA500'
        WHEN heat_index >= 85 THEN '#FFD700'
        ELSE '#00BFFF'
    END,
    CASE
        WHEN heat_risk >= 80 THEN '#DC2626'
        WHEN heat_risk >= 60 THEN '#F97316'
        WHEN heat_risk >= 40 THEN '#FACC15'
        ELSE '#22C55E'
    END,
    '#BDBDBD', '#BDBDBD', '#BDBDBD', '#BDBDBD',
    CASE
        WHEN heat_risk >= 80 THEN '#DC2626'
        WHEN heat_risk >= 60 THEN '#F97316'
        WHEN heat_risk >= 40 THEN '#FACC15'
        ELSE '#22C55E'
    END
FROM normalized;

COMMIT;
