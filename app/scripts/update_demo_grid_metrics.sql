-- Demo metric refresh for existing grid metric rows only.
-- This does not delete grid cells, delete metric rows, or insert new rows.
-- It gives each metric row a deterministic but varied value based on grid
-- position and row id, so the heatmap has realistic-looking demo variation.

BEGIN;

WITH bounds AS (
    SELECT
        state,
        min(row) AS min_row,
        max(row) AS max_row,
        min(col) AS min_col,
        max(col) AS max_col
    FROM grid_cell_geometry
    GROUP BY state
), positioned AS (
    SELECT
        m.id AS metric_id,
        g.cell_id,
        COALESCE((g.row - b.min_row)::float / NULLIF(b.max_row - b.min_row, 0), 0.5) AS y,
        COALESCE((g.col - b.min_col)::float / NULLIF(b.max_col - b.min_col, 0), 0.5) AS x
    FROM grid_cell_metrics m
    JOIN grid_cell_geometry g ON g.id = m.grid_cell_id
    JOIN bounds b ON b.state = g.state
), scored AS (
    SELECT
        metric_id,
        LEAST(112, GREATEST(82,
            88
            + 10 * (1 - y)
            + 12 * exp(-(power(x - 0.52, 2) + power(y - 0.48, 2)) / 0.030)
            + 7 * exp(-(power(x - 0.68, 2) + power(y - 0.58, 2)) / 0.045)
            + (mod(abs(hashtext(cell_id || '-' || metric_id || '-heat')::bigint), 100) / 100.0) * 4
        )) AS heat_index,
        LEAST(100, GREATEST(8,
            28
            + 42 * exp(-(power(x - 0.52, 2) + power(y - 0.48, 2)) / 0.035)
            + 18 * (1 - y)
            + (mod(abs(hashtext(cell_id || '-' || metric_id || '-risk')::bigint), 100) / 100.0) * 10
        )) AS heat_risk,
        LEAST(100, GREATEST(5,
            12
            + 58 * exp(-(power(x - 0.50, 2) + power(y - 0.50, 2)) / 0.040)
            + 22 * exp(-(power(x - 0.34, 2) + power(y - 0.44, 2)) / 0.030)
            + (mod(abs(hashtext(cell_id || '-' || metric_id || '-crowd')::bigint), 100) / 100.0) * 12
        )) AS crowd_density,
        ROUND((250 + 5200 * exp(-(power(x - 0.52, 2) + power(y - 0.50, 2)) / 0.050))::numeric, 0) AS population,
        LEAST(100, GREATEST(12,
            24
            + 35 * exp(-(power(x - 0.57, 2) + power(y - 0.52, 2)) / 0.050)
            + (mod(abs(hashtext(cell_id || '-' || metric_id || '-infra')::bigint), 100) / 100.0) * 18
        )) AS infrastructure_strain
    FROM positioned
), final_scores AS (
    SELECT
        *,
        CASE
            WHEN heat_risk >= 80 THEN '#DC2626'
            WHEN heat_risk >= 60 THEN '#F97316'
            WHEN heat_risk >= 40 THEN '#FACC15'
            ELSE '#22C55E'
        END AS risk_color
    FROM scored
)
UPDATE grid_cell_metrics m
SET
    heat_index = ROUND(s.heat_index::numeric, 1),
    heat_risk = ROUND(s.heat_risk::numeric, 1),
    crowd_density = ROUND(s.crowd_density::numeric, 1),
    population = s.population,
    cooling_centers = CASE WHEN s.heat_risk >= 75 THEN 1 ELSE 0 END,
    cooling_centers_impact_radius = CASE WHEN s.heat_risk >= 75 THEN 0.75 ELSE 0 END,
    infrastructure_strain = ROUND(s.infrastructure_strain::numeric, 1),
    heat_index_color = s.risk_color,
    heat_risk_color = s.risk_color,
    crowd_density_color = s.risk_color,
    population_color = s.risk_color,
    cooling_centers_color = CASE WHEN s.heat_risk >= 75 THEN '#2563EB' ELSE '#94A3B8' END,
    infrastructure_strain_color = s.risk_color,
    overall_risk_color = s.risk_color
FROM final_scores s
WHERE m.id = s.metric_id;

COMMIT;
