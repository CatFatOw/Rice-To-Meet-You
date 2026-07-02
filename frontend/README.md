# HeatSafe AI Frontend

React + TypeScript frontend for exploring heat risk across host cities, viewing POIs, and rendering map-based risk layers.

## Run Locally

```bash
npm install
npm run dev
```

## Frontend API Reference

The frontend currently uses local mock API modules under `src/api`.

### Map API (`src/api/map.ts`)

#### `callMockLocationPOIs()`

- Purpose: Fetches polygon overlays for known POIs.
- Returns: `Promise<CityPOIArea[]>`
- Current data: Houston polygons (NRG Stadium, Rice University).

**Main shape**

```ts
interface CityPOIArea {
  id: string;
  name: string;
  cityName: string;
  color: [number, number, number, number];
  polygon: [number, number][];
}
```

#### `callHeatmapMetricsPoints()`

- Purpose: Returns point-level heat risk data for map heatmap rendering.
- Returns: `Promise<Record<string, HeatmapMetricPoint[]>>`
- Current data: Dense interpolated field for Houston.

**Main shape**

```ts
interface HeatmapMetricPoint {
  metric: string; // e.g. "heat_risk_score"
  value: number; // 0-100 heat risk weight
  location_name: string;
  location_coordinates: [number, number]; // [lon, lat]
  individual_metrics?: {
    temperatureF: number;
    heatIndexF: number;
    relativeHumidityPct: number;
    landSurfaceTempF: number;
    nighttimeTempF: number;
    treeCanopyPct: number;
    imperviousSurfacePct: number;
  };
}
```

#### `getCoordinateValue()`

- Purpose: Returns dense coordinate-level heat profile values for full-grid analytics.
- Returns: `Promise<MetricCoordinateData[]>`
- Current metric key: `heat_profile`

**Main shape**

```ts
interface MetricCoordinateData {
  metric: 'heat_profile';
  points: CoordinateValue[];
}

interface CoordinateValue {
  coordinate: [number, number];
  value: number; // alias of temperatureF
  temperatureF: number;
  relativeHumidityPct: number;
  heatIndexF: number;
  landSurfaceTempF: number;
  nighttimeTempF: number;
  treeCanopyPct: number;
  imperviousSurfacePct: number;
  heatVulnerabilityIndex: number;
  category: 'low' | 'moderate' | 'high' | 'extreme';
}
```

### Statistics API (`src/api/statistics.ts`)

#### `callMockStatistics(city)`

- Purpose: Fetches dashboard cards + POI statistics for a selected city.
- Input: `city: string`
- Returns: `Promise<CityStatisticsResponse>`
- Fallback behavior: If city is unknown, data falls back to `Nationally`.

**Main shape**

```ts
interface CityStatisticsResponse {
  overallStatistics: OverallStatisticsProps;
  poiStatistics: POIStatisticsProps;
}
```

## Usage Example

```ts
import {
  callMockLocationPOIs,
  callHeatmapMetricsPoints,
  getCoordinateValue,
} from './src/api/map';
import { callMockStatistics } from './src/api/statistics';

const pois = await callMockLocationPOIs();
const pointsByCity = await callHeatmapMetricsPoints();
const coordinateMetrics = await getCoordinateValue();
const stats = await callMockStatistics('Houston');
```

## Notes

- These APIs are asynchronous and include simulated network latency.
- Data is mock data for frontend development and visualization behavior.
- Coordinate order is longitude, latitude across map APIs.
