# Spatial Metric Interpolation: Backend to Frontend

This guide describes how the application turns sparse, grid-cell metric observations into a continuous heatmap surface. The backend uses **ordinary kriging** to fill missing grid-centroid values. The frontend then uses **bilinear interpolation** to color the map and show a value at the cursor's exact location.

## Pipeline at a glance

```text
GridCellMetrics + optional request points
        │
        ▼
POST /grid_interpolation/interpolate
        │  ordinary kriging at unsampled grid centroids
        ▼
InterpolatedPoint rows (timestamped, with variance/confidence)
        │
        ├── GET /grid_interpolation/heatmap  → point GeoJSON
        ├── GET /grid_interpolation/mesh     → grid-cell polygon GeoJSON
        └── GET /heatmap/metrics/grid        → city raster lattice
                                                    │
                                                    ▼
                                      React BitmapLayer + cursor sampling
```

There are two related backend paths:

1. **Saved interpolation run**: `POST /grid_interpolation/interpolate` explicitly runs kriging, saves `InterpolatedPoint` rows, and can be retrieved as point or polygon GeoJSON.
2. **Frontend heatmap grid**: `GET /heatmap/metrics/grid` starts with the latest `GridCellMetrics` snapshots. For each metric, it fills only missing lattice cells with the same kriging helper and returns the complete grid directly to React.

## Data model

`GridCellGeometry` supplies the spatial layout:

- `id`, `cell_id`, `row`, `col`
- `grid_centroid_lon`, `grid_centroid_lat`
- polygon `geometry`
- `state`

`GridCellMetrics` stores observed or derived metric snapshots per cell and timestamp. Supported interpolation keys are:

```text
heat_index, heat_risk, crowd_density, population,
cooling_centers, infrastructure_strain,
predicted_heat_index, predicted_heat_risk,
predicted_crowd_density, predicted_population,
predicted_visitor_count
```

An `InterpolatedPoint` is the persisted output of an explicit interpolation run. It stores the target grid cell, latitude/longitude, metric values, source count, confidence, method label, and timestamp.

## Backend: ordinary kriging

Implementation: `app/services/grid_interpolation_service.py`.

### 1. Gather known values

`grid_metrics_to_known_points()` joins saved metric rows to their grid-cell centroids. The request can add ad-hoc `known_points` containing a coordinate and one or more metric values.

For a single metric, `interpolate_grid_centroids()` accepts points in any of these forms:

- `lon`/`lat`, `longitude`/`latitude`, or centroid fields;
- a GeoJSON `Point` geometry;
- the requested metric property, either at the top level or in `properties`.

It discards points with no value for the metric. At least **two** known values are required.

### 2. Preserve measured grid values

If a known point identifies a target `grid_cell_id`, the service emits its value directly with `variance: 0`; kriging is not used for that cell. After multi-metric interpolation, `apply_exact_grid_metrics()` again overwrites those cells with their saved metric values. This prevents an estimate from replacing an observation.

### 3. Run the estimate only where data is absent

For each target centroid without an exact value, the service builds:

```python
x = known longitudes
y = known latitudes
z = known metric values
target_x, target_y = missing-cell centroids
```

It then calls PyKrige:

```python
kriging = OrdinaryKriging(
    x, y, z,
    variogram_model="linear",
    verbose=False,
    enable_plotting=False,
)
interpolated_values, variance = kriging.execute("points", target_x, target_y)
```

Ordinary kriging assumes an unknown but spatially constant local mean. The linear variogram tells the estimator how similarity changes with geographic separation. It produces both a predicted metric value and kriging variance.

If all known `z` values are equal, the code bypasses PyKrige and fills every target with that same value and zero variance. This avoids an unnecessary/unstable variogram fit for a flat field.

### 4. Run independently for each usable metric

`interpolate_available_metrics()` finds every supported metric with at least two known values. It runs each metric's interpolation independently in a `ThreadPoolExecutor`, beginning with the requested metric, then merges each result set by `grid_cell_id`.

Metrics with fewer than two observations remain explicitly `null`; the service does not invent a value for them.

### 5. Turn kriging variance into relative confidence

`add_relative_confidence()` rescales non-negative variances **within that response only**:

```text
confidence = 1 - (variance - min_variance) / (max_variance - min_variance)
```

Therefore, `1` means the least uncertain cell in that run and `0` means the most uncertain cell in that run. It is a relative display score, not a calibrated probability and not comparable across runs. If all variances match, all cells receive confidence `1`.

## Explicit interpolation API

### Request

`POST /grid_interpolation/interpolate`

```json
{
  "city": "Houston",
  "state": "Texas",
  "timestamp": "2026-07-13T12:00:00Z",
  "metric_key": "predicted_heat_risk",
  "replace_existing": true,
  "known_points": [
    {
      "lat": 29.7604,
      "lon": -95.3698,
      "predicted_heat_risk": 0.78,
      "predicted_visitor_count": 4250
    },
    {
      "lat": 29.7804,
      "lon": -95.3498,
      "predicted_heat_risk": 0.62,
      "predicted_visitor_count": 3100
    }
  ]
}
```

The route loads city grid cells and same-timestamp saved metrics, combines those with `known_points`, runs available metrics, optionally deletes existing rows for the affected cells/timestamp, then persists the new `InterpolatedPoint` rows.

### Read formats

| Endpoint | Purpose | Shape |
|---|---|---|
| `GET /grid_interpolation/all` | all persisted estimates | point GeoJSON |
| `GET /grid_interpolation/heatmap` | one metric's estimates | point GeoJSON with `value`, normalized `intensity`, and `confidence` |
| `GET /grid_interpolation/mesh` | cell-polygon rendering | polygon GeoJSON with chosen metric and color fields |
| `GET /heatmap/metrics/points` | React point-layer adapter | city → metric layers → weighted centroid points |

## Backend grid for the React heatmap

`GET /heatmap/metrics/grid` is the primary path used by the React pages. It fetches the latest metric row per grid cell, groups rows by city, and constructs this contract:

```ts
type CityMetricGrid = {
  state?: string;
  bounds: [minLon, minLat, maxLon, maxLat];
  rows: number;
  cols: number;
  timestamp: string;
  metrics: Record<string, {
    min: number;
    max: number;
    values: (number | null)[][];
  }>;
};
```

`grid_metrics_to_city_grids()` builds `values[row][col]` from saved metrics. If a metric has at least two known cells but some lattice positions are missing, `_fill_metric_grid_with_kriging()` creates target centroids from the bounding box and regular row/column layout, then calls `interpolate_grid_centroids()` to fill only those gaps. Known cells are retained as-is.

The API returns `{}` when there are no latest metric rows. The frontend intentionally treats that as an unseeded demo environment, not an error.

## Frontend: raster rendering and cursor interpolation

Relevant files:

- `frontend/src/api/map.ts`
- `frontend/src/components/Heatmap.tsx`
- `frontend/src/utils/metricRaster.ts`

### Fetch and fallback

`callHeatmapMetricsGrid()` requests `/heatmap/metrics/grid`. When the request fails or returns an empty object, it creates a mock Houston raster using inverse-distance weighting (IDW). That fallback is only frontend demo data; production backend interpolation uses ordinary kriging.

### Render a continuous surface

`buildCityMetricRaster()` converts a selected metric lattice into a canvas. The canvas is anchored to the city's centroid bounds and shown as a Deck.gl `BitmapLayer`.

For every image pixel, `sampleMetricGrid()` computes a bilinear interpolation from the four surrounding centroid values. If one or more neighbors are `null`, their weights are skipped and the remaining weights are renormalized. Outside bounds, it returns `null`, leaving the raster transparent.

This is a second interpolation stage, but it has a different job:

- **Backend ordinary kriging** fills missing grid-cell values from spatial observations.
- **Frontend bilinear interpolation** smoothly samples the already-complete regular grid between adjacent centroids for display and tooltips.

### Tooltip behavior

On hover, `Heatmap.tsx` calls `sampleMetricGrid()` at the cursor coordinate rather than snapping to a stored point. It returns the raw active-metric value, samples all other available metrics at that same location, normalizes the active metric to a 0–100 display score, and marks the tooltip point as `is_interpolated: true`.

## Important caveats

- Geographic longitude/latitude are passed directly to PyKrige. For larger geographic areas, project coordinates to a local metric CRS first; degrees do not represent equal distances everywhere.
- The variogram is fixed to `linear`; there is no fitting, validation, anisotropy setting, neighborhood limit, or nugget configuration exposed by the API.
- The minimum is two points, which is enough for the code path but usually weak evidence for a reliable spatial model. More well-distributed points improve estimates.
- `confidence` is min–max-normalized variance per run, so use it for relative visual cues rather than statistical guarantees.
- Frontend `min`/`max` normalize colors per returned city/metric grid. A score of 80 in two cities need not represent the same raw metric value.
- The backend grid route uses the **latest** metric per cell; the explicit interpolation route is timestamp-specific.
- The metric-grid helper describes `row 0` as south. Canvas drawing reverses y because pixel row 0 is north, preserving correct geographic orientation.

## Practical debugging checklist

1. Verify grid geometry has valid row, column, centroid, polygon geometry, and state.
2. Verify at least two non-null values for the target metric exist.
3. Call `POST /grid_interpolation/interpolate` for a persisted run, or `GET /heatmap/metrics/grid` for the frontend grid contract.
4. Confirm `values` contains numbers rather than only `null` for the selected metric.
5. Check the active metric key matches an entry under `grid.metrics`.
6. If the map shows a demo surface, inspect whether `/heatmap/metrics/grid` returned `{}` or failed; the frontend will intentionally use mock IDW data in that case.
