-- Populate grid crowd metrics from the newest geographically matched local
-- customer-activity data. This is a proxy, not an observed visitor count.
-- A neutral placeholder is used only where no 2025 customer record lies within
-- 5 km of a grid centroid, and every row carries explicit provenance.

BEGIN;

WITH candidates AS (
    SELECT
        metric.id AS metric_id,
        metric.grid_cell_id,
        cell.state,
        spend.raw_num_customers,
        spend.raw_num_transactions,
        spend.spend_date_range_end,
        6371 * acos(least(1.0, greatest(-1.0,
            cos(radians(cell.grid_centroid_lat)) * cos(radians(spend.latitude)) *
            cos(radians(spend.longitude) - radians(cell.grid_centroid_lon)) +
            sin(radians(cell.grid_centroid_lat)) * sin(radians(spend.latitude))
        ))) AS distance_km,
        row_number() OVER (
            PARTITION BY metric.id
            ORDER BY spend.spend_date_range_end DESC,
                     6371 * acos(least(1.0, greatest(-1.0,
                         cos(radians(cell.grid_centroid_lat)) * cos(radians(spend.latitude)) *
                         cos(radians(spend.longitude) - radians(cell.grid_centroid_lon)) +
                         sin(radians(cell.grid_centroid_lat)) * sin(radians(spend.latitude))
                     ))) ASC
        ) AS row_num
    FROM grid_cell_metrics AS metric
    JOIN grid_cell_geometry AS cell ON cell.id = metric.grid_cell_id
    JOIN spend_patterns_rice AS spend
      ON ((cell.state = 'Texas' AND spend.market = 'Houston')
       OR (cell.state = 'Georgia' AND spend.market = 'Atlanta'))
     AND spend.spend_date_range_end >= DATE '2025-01-01'
     AND spend.latitude BETWEEN 20 AND 50
     AND spend.longitude BETWEEN -130 AND -60
    WHERE metric.timestamp >= TIMESTAMPTZ '2026-07-14'
), matched AS (
    SELECT * FROM candidates WHERE row_num = 1 AND distance_km <= 5
), scored AS (
    SELECT
        metric_id,
        raw_num_customers,
        raw_num_transactions,
        spend_date_range_end,
        distance_km,
        percent_rank() OVER (PARTITION BY state ORDER BY raw_num_customers) AS activity_rank
    FROM matched
)
UPDATE grid_cell_metrics AS metric
SET
    crowd_density = ROUND((10 + 80 * scored.activity_rank)::numeric, 1),
    predicted_visitor_count = scored.raw_num_customers,
    visitor_metric_source = 'Customer-activity proxy from spend_patterns_rice ('
        || scored.spend_date_range_end::text
        || '; ' || round(scored.distance_km::numeric, 1)::text
        || ' km away). Not an observed visitor count.',
    visitor_metric_is_placeholder = FALSE,
    crowd_density_color = '#60A5FA'
FROM scored
WHERE metric.id = scored.metric_id;

UPDATE grid_cell_metrics AS metric
SET
    crowd_density = 50,
    predicted_visitor_count = NULL,
    visitor_metric_source = 'Placeholder: no 2025 Houston/Atlanta customer or visitor record was found within 5 km of this grid centroid.',
    visitor_metric_is_placeholder = TRUE,
    crowd_density_color = '#94A3B8'
WHERE metric.timestamp >= TIMESTAMPTZ '2026-07-14'
  AND metric.visitor_metric_source IS NULL;

COMMIT;
