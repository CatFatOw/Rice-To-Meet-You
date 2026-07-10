type Polygon = [number, number][];

import { apiBaseUrl } from './base';

const API_BASE_URL = apiBaseUrl();

// Small shared helper for the backend-backed copy of the frontend. Keeping the
// base URL centralized makes it easy to point this copy at a deployed API later
// via VITE_API_BASE_URL without changing call sites.
async function fetchBackendJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export interface CityPOIArea {
  id: string;
  poi_id?: number;
  name: string;
  cityName: string;
  stateName?: string | null;
  category?: string | null;
  color: [number, number, number, number];
  polygon: Polygon;
  properties?: {
    statistics?: Record<string, string | number | boolean | null>;
    [key: string]: unknown;
  } | null;
  polygon_geometry_id?: number;
  impacted_count?: number;
  impacted_grid_cell_ids?: number[];
}

const riceUniversityPolygon: Polygon = [
  [-95.40895, 29.72245],
  [-95.40620, 29.72305],
  [-95.40195, 29.72305],
  [-95.39735, 29.72195],
  [-95.39640, 29.71875],
  [-95.39675, 29.71520],
  [-95.39920, 29.71175],
  [-95.40340, 29.71085],
  [-95.40790, 29.71145],
  [-95.40945, 29.71470],
  [-95.40955, 29.71920],
  [-95.40895, 29.72245],
];

const nrgStadiumPolygon: Polygon = [
  [-95.41195, 29.68655],
  [-95.41040, 29.68635],
  [-95.40935, 29.68545],
  [-95.40920, 29.68410],
  [-95.41025, 29.68310],
  [-95.41195, 29.68285],
  [-95.41360, 29.68310],
  [-95.41460, 29.68405],
  [-95.41450, 29.68545],
  [-95.41345, 29.68635],
  [-95.41195, 29.68655],
];

export async function callMockLocationPOIs(): Promise<CityPOIArea[]> {
  // Simulate network latency
  await new Promise((resolve) => setTimeout(resolve, 500));

  // Prefer saved POI polygons from FastAPI. If the backend is not running yet,
  // or the database has not been seeded, fall back to the original demo POIs so
  // the copied frontend remains usable on its own.
  try {
    const backendPOIs = await fetchBackendJson<CityPOIArea[]>('/heatmap/core-pois?limit=500');
    if (backendPOIs.length > 0) return backendPOIs;
  } catch (error) {
    console.warn('Falling back to saved/mock location POIs', error);
  }

  try {
    const savedPOIs = await fetchBackendJson<CityPOIArea[]>('/heatmap/location-pois');
    if (savedPOIs.length > 0) return savedPOIs;
  } catch {
    /* Keep the original demo fallback below. */
  }

  return [
    {
      id: "nrg-stadium",
      name: "NRG Stadium",
      cityName: "Houston",
      color: [255, 165, 0, 150],
      polygon: nrgStadiumPolygon,
    },
    {
      id: "rice-university",
      name: "Rice University",
      cityName: "Houston",
      color: [70, 130, 180, 150],
      polygon: riceUniversityPolygon,
    },
  ];
}

// ---------------------------------------------------------------------------
// callHeatmapMetricsPoints()
// ---------------------------------------------------------------------------

// A single measured / interpolated reading at one coordinate.
export interface HeatmapMetricValue {
  value: number; // 0–100 weight (heat risk, visitor activity, etc.)
  location_name: string;
  location_coordinates: [number, number]; // [lon, lat]
  individual_metrics?: Record<string, number | null | undefined>;
  is_interpolated?: boolean;
}

// One metric layer (e.g. "heat_risk_score") and all of its points.
export interface HeatmapMetricPoint {
  metric: string; // e.g. "heat_risk_score", "visitor_activity"
  points: HeatmapMetricValue[];
}

// City name -> list of metric layers available for that city.
export type HeatmapMetricsPointResponse = Record<string, HeatmapMetricPoint[]>;

export interface SimulationPlacedObject {
  id: string;
  type: string;
  longitude: number;
  latitude: number;
}

export interface SimulationPolygonCreateRequest {
  name?: string;
  cityName: string;
  stateName?: string | null;
  color?: [number, number, number, number];
  polygon: Polygon;
}

export interface SimulationApplyRequest {
  cityName?: string;
  stateName?: string | null;
  polygonGeometryId?: number;
  impactedGridCellIds?: number[];
  placedObjects: SimulationPlacedObject[];
  timestamp?: string;
}

export interface SimulationApplyResponse {
  timestamp: string;
  objects_applied: number;
  adjustments: Record<string, number>;
  metrics_created: number;
  impacted_count: number;
  impacted_grid_cell_ids: number[];
}

export interface CorePOIImportResponse {
  filename: string;
  imported_count: number;
  skipped_count: number;
  total_rows: number;
  errors: string[];
}

function anchor(
  lon: number,
  lat: number,
  value: number,
  location_name: string,
): HeatmapMetricValue {
  return { value, location_name, location_coordinates: [lon, lat] };
}

// ---------------------------------------------------------------------------
// Heat-risk anchors: hand-authored readings at known Houston landmarks. These
// are the "measured" values the interpolation is built from.
// ---------------------------------------------------------------------------
const HOUSTON_ANCHORS: HeatmapMetricValue[] = [
  // Texas Medical Center
  anchor(-95.3992, 29.7067, 91, 'Texas Medical Center'),
  anchor(-95.3962, 29.7082, 88, 'Texas Medical Center'),
  anchor(-95.4015, 29.7090, 93, 'Texas Medical Center'),
  anchor(-95.3975, 29.7045, 90, 'Texas Medical Center'),
  anchor(-95.4020, 29.7050, 86, 'Texas Medical Center'),

  // NRG Stadium
  anchor(-95.4109, 29.6847, 85, 'NRG Stadium'),
  anchor(-95.4085, 29.6860, 82, 'NRG Stadium'),
  anchor(-95.4130, 29.6835, 88, 'NRG Stadium'),
  anchor(-95.4095, 29.6825, 84, 'NRG Stadium'),
  anchor(-95.4125, 29.6865, 80, 'NRG Stadium'),

  // NRG Park Parking Area
  anchor(-95.4120, 29.6855, 82, 'NRG Park Parking Area'),
  anchor(-95.4145, 29.6840, 79, 'NRG Park Parking Area'),
  anchor(-95.4100, 29.6870, 84, 'NRG Park Parking Area'),
  anchor(-95.4160, 29.6865, 80, 'NRG Park Parking Area'),
  anchor(-95.4095, 29.6840, 83, 'NRG Park Parking Area'),

  // Museum District
  anchor(-95.3893, 29.7240, 74, 'Museum District'),
  anchor(-95.3870, 29.7255, 71, 'Museum District'),
  anchor(-95.3915, 29.7228, 77, 'Museum District'),
  anchor(-95.3880, 29.7218, 72, 'Museum District'),
  anchor(-95.3910, 29.7258, 76, 'Museum District'),

  // Rice University
  anchor(-95.4018, 29.7174, 68, 'Rice University'),
  anchor(-95.3995, 29.7190, 65, 'Rice University'),
  anchor(-95.4040, 29.7160, 71, 'Rice University'),
  anchor(-95.4005, 29.7155, 67, 'Rice University'),
  anchor(-95.4035, 29.7188, 70, 'Rice University'),

  // West University Place
  anchor(-95.4315, 29.7180, 63, 'West University Place'),
  anchor(-95.4290, 29.7195, 60, 'West University Place'),
  anchor(-95.4340, 29.7168, 66, 'West University Place'),
  anchor(-95.4300, 29.7162, 62, 'West University Place'),
  anchor(-95.4335, 29.7195, 64, 'West University Place'),

  // Hermann Park
  anchor(-95.3870, 29.7154, 57, 'Hermann Park'),
  anchor(-95.3848, 29.7168, 54, 'Hermann Park'),
  anchor(-95.3892, 29.7142, 60, 'Hermann Park'),
  anchor(-95.3858, 29.7138, 55, 'Hermann Park'),
  anchor(-95.3888, 29.7170, 58, 'Hermann Park'),
];

// ---------------------------------------------------------------------------
// Regional heat anchors spread across the whole metro so the interpolation has
// real structure: HOT downtown/industrial, MILD suburbs, COOL parks/water.
// ---------------------------------------------------------------------------
const HOUSTON_REGIONAL_ANCHORS: HeatmapMetricValue[] = [
  // --- Very hot: ship channel, refineries, treeless industrial (90–98) ------
  anchor(-95.2800, 29.7300, 96, 'Houston Ship Channel'),
  anchor(-95.2300, 29.7400, 97, 'Galena Park Refineries'),
  anchor(-95.2100, 29.6900, 95, 'Pasadena Industrial'),
  anchor(-94.9800, 29.7400, 93, 'Baytown Industrial'),
  anchor(-95.1300, 29.7000, 92, 'Deer Park'),
  anchor(-95.1100, 29.7800, 91, 'Channelview'),
  anchor(-95.0200, 29.6600, 90, 'La Porte'),
  anchor(-95.2400, 29.7700, 92, 'Jacinto City'),

  // --- Hot: dense/low-canopy urban core + airports (84–90) ------------------
  anchor(-95.3698, 29.7604, 89, 'Downtown Houston'),
  anchor(-95.3100, 29.7300, 90, 'Magnolia Park / East End'),
  anchor(-95.3300, 29.7800, 88, 'Fifth Ward'),
  anchor(-95.3200, 29.8000, 88, 'Kashmere Gardens'),
  anchor(-95.3000, 29.7800, 89, 'Denver Harbor'),
  anchor(-95.3550, 29.7350, 86, 'Third Ward'),
  anchor(-95.3600, 29.6600, 90, 'Sunnyside'),
  anchor(-95.4800, 29.7100, 89, 'Gulfton'),
  anchor(-95.5300, 29.7000, 87, 'Sharpstown'),
  anchor(-95.5800, 29.7000, 85, 'Alief'),
  anchor(-95.4100, 29.9400, 87, 'Greenspoint'),
  anchor(-95.3800, 29.9200, 86, 'Aldine'),
  anchor(-95.4300, 29.8600, 85, 'Acres Homes'),
  anchor(-95.3414, 29.9902, 86, 'George Bush Intercontinental (IAH)'),
  anchor(-95.2789, 29.6454, 87, 'Hobby Airport'),
  anchor(-95.3100, 29.8100, 84, 'Northside / I-45 Corridor'),

  // --- Mild: suburban rings (65–80) -----------------------------------------
  anchor(-95.4614, 29.7397, 80, 'Galleria / Uptown'),
  anchor(-95.5100, 29.7900, 76, 'Spring Branch'),
  anchor(-95.5300, 29.9600, 72, 'Willowbrook'),
  anchor(-95.5800, 29.8900, 73, 'Jersey Village'),
  anchor(-95.8200, 29.7900, 68, 'Katy'),
  anchor(-95.7500, 29.7400, 67, 'Cinco Ranch'),
  anchor(-95.6300, 29.6800, 71, 'Mission Bend'),
  anchor(-95.6200, 29.6200, 69, 'Sugar Land'),
  anchor(-95.5400, 29.6200, 70, 'Missouri City'),
  anchor(-95.5600, 29.6300, 71, 'Stafford'),
  anchor(-95.2900, 29.5600, 72, 'Pearland'),
  anchor(-95.2000, 29.5300, 66, 'Friendswood'),
  anchor(-95.0900, 29.5100, 65, 'League City'),
  anchor(-95.1800, 29.9900, 68, 'Atascocita'),
  anchor(-95.2600, 29.9900, 70, 'Humble'),
  anchor(-95.6200, 30.1000, 66, 'Tomball'),
  anchor(-95.5200, 30.0200, 67, 'Klein'),
  anchor(-95.4200, 30.0800, 66, 'Spring'),
  anchor(-95.7000, 29.9700, 65, 'Cypress'),
  anchor(-95.6349, 29.7830, 71, 'Energy Corridor'),
  anchor(-95.1900, 29.6600, 74, 'Pasadena (residential)'),

  // --- Cool: affluent leafy, parks, forested north (50–60) ------------------
  anchor(-95.4200, 29.7550, 52, 'River Oaks'),
  anchor(-95.5500, 29.7700, 55, 'Memorial (residential)'),
  anchor(-95.4300, 29.7650, 50, 'Memorial Park'),
  anchor(-95.4600, 29.7050, 56, 'Bellaire'),
  anchor(-95.4600, 29.6800, 58, 'Meyerland'),
  anchor(-95.3900, 29.7600, 56, 'Buffalo Bayou Park'),
  anchor(-95.4500, 30.1600, 55, 'The Woodlands (forested)'),
  anchor(-95.1800, 30.0500, 54, 'Kingwood (forested)'),
  anchor(-95.0900, 29.5600, 60, 'Clear Lake / NASA'),

  // --- Very cool: reservoirs, lakes, open water (42–48) ---------------------
  anchor(-95.6300, 29.7700, 44, 'Addicks / Barker Reservoir'),
  anchor(-95.6800, 29.7200, 46, 'George Bush Park'),
  anchor(-95.1400, 29.9200, 42, 'Lake Houston'),
  anchor(-95.1700, 29.8600, 45, 'Sheldon Lake'),
  anchor(-94.9000, 29.5300, 48, 'Galveston Bay shoreline'),
  anchor(-95.0500, 29.5500, 47, 'Clear Lake (open water)'),
];

// Everything the heat interpolation samples from: landmark cluster + regional.
const ALL_HEAT_ANCHORS: HeatmapMetricValue[] = [
  ...HOUSTON_ANCHORS,
  ...HOUSTON_REGIONAL_ANCHORS,
];

// ---------------------------------------------------------------------------
// Visitor-activity anchors: how busy each area is with visitors/fans. HIGH at
// match venues, downtown, entertainment + shopping districts, airports, marquee
// attractions; LOW in industrial zones, plain residential, parks, and water.
// ---------------------------------------------------------------------------
const HOUSTON_VISITOR_ANCHORS: HeatmapMetricValue[] = [
  // --- Very high: match venue + surrounding fan zone (92–100) ----------------
  anchor(-95.4109, 29.6847, 100, 'NRG Stadium'),
  anchor(-95.4120, 29.6855, 95, 'NRG Park Fan Fest'),
  anchor(-95.4095, 29.6825, 93, 'NRG Park Entrance Plaza'),
  anchor(-95.3698, 29.7604, 96, 'Downtown Houston'),
  anchor(-95.3585, 29.7527, 94, 'Discovery Green'),
  anchor(-95.3577, 29.7517, 93, 'George R. Brown Convention Center'),
  anchor(-95.3620, 29.7560, 92, 'Avenida Houston / Toyota Center'),

  // --- High: nightlife, shopping, marquee attractions (82–90) ---------------
  anchor(-95.4614, 29.7397, 90, 'Galleria / Uptown'),
  anchor(-95.3780, 29.7420, 86, 'Midtown'),
  anchor(-95.3510, 29.7490, 85, 'EaDo / Shell Energy Stadium'),
  anchor(-95.3893, 29.7240, 88, 'Museum District'),
  anchor(-95.3925, 29.7210, 87, 'Houston Zoo'),
  anchor(-95.3870, 29.7154, 84, 'Hermann Park'),
  anchor(-95.3980, 29.8010, 82, 'The Heights'),
  anchor(-95.3900, 29.7430, 85, 'Montrose'),
  anchor(-95.3900, 29.7600, 83, 'Buffalo Bayou Park'),
  anchor(-95.0920, 29.5520, 84, 'Space Center Houston'),

  // --- Airports + major transit (78–86) -------------------------------------
  anchor(-95.3414, 29.9902, 86, 'George Bush Intercontinental (IAH)'),
  anchor(-95.2789, 29.6454, 80, 'Hobby Airport'),

  // --- Medium: busy but not tourist-driven (60–75) --------------------------
  anchor(-95.3992, 29.7067, 70, 'Texas Medical Center'),
  anchor(-95.4018, 29.7174, 66, 'Rice University'),
  anchor(-95.4200, 29.7550, 68, 'River Oaks District'),
  anchor(-95.4300, 29.7650, 72, 'Memorial Park'),
  anchor(-95.6200, 29.6200, 68, 'Sugar Land Town Square'),
  anchor(-95.4500, 30.1600, 66, 'The Woodlands / Market Street'),
  anchor(-95.8200, 29.7900, 58, 'Katy Mills'),
  anchor(-95.0900, 29.5600, 64, 'Kemah / Clear Lake'),

  // --- Low: plain residential rings (35–50) ---------------------------------
  anchor(-95.5300, 29.7000, 42, 'Sharpstown'),
  anchor(-95.5800, 29.7000, 40, 'Alief'),
  anchor(-95.4300, 29.8600, 38, 'Acres Homes'),
  anchor(-95.2900, 29.5600, 46, 'Pearland'),
  anchor(-95.0900, 29.5100, 44, 'League City'),
  anchor(-95.2600, 29.9900, 43, 'Humble'),
  anchor(-95.4200, 30.0800, 41, 'Spring'),
  anchor(-95.7000, 29.9700, 39, 'Cypress'),

  // --- Very low: industrial, reservoirs, open water (12–28) ------------------
  anchor(-95.2300, 29.7400, 18, 'Galena Park Refineries'),
  anchor(-95.2100, 29.6900, 16, 'Pasadena Industrial'),
  anchor(-94.9800, 29.7400, 15, 'Baytown Industrial'),
  anchor(-95.2800, 29.7300, 20, 'Houston Ship Channel'),
  anchor(-95.6300, 29.7700, 22, 'Addicks / Barker Reservoir'),
  anchor(-95.1400, 29.9200, 18, 'Lake Houston'),
  anchor(-94.9000, 29.5300, 24, 'Galveston Bay shoreline'),
];

// ---------------------------------------------------------------------------
// Interpolation config. The bounding box spans the greater Houston metro so
// the generated field covers the whole city, not just the anchor cluster.
// ---------------------------------------------------------------------------
const INTERP_CENTER: [number, number] = [-95.37, 29.76];
const INTERP_HALF_SPAN_LON = 0.55; // ≈ 53 km E–W each way (reaches Katy ↔ Baytown)
const INTERP_HALF_SPAN_LAT = 0.45; // ≈ 50 km N–S each way (reaches Woodlands ↔ coast)
const INTERP_STEP = 0.01; // ≈ 1.1 km lattice spacing
const HEAT_IDW_POWER = 3.2; // higher = anchors hold local value; more contrast
const VISITOR_IDW_POWER = 2.6; // slightly smoother spread for activity
const MIN_SCORE = 0;
const MAX_SCORE = 100;

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

function buildIndividualMetrics(point: HeatmapMetricValue): HeatmapMetricValue['individual_metrics'] {
  const [lon, lat] = point.location_coordinates;
  const noise = Math.sin(lon * 17.3) * Math.cos(lat * 14.1);

  const temperatureF = Math.round(clamp(74 + point.value * 0.28 + noise * 1.8, 70, 115));
  const relativeHumidityPct = Math.round(
    clamp(86 - point.value * 0.35 + Math.sin((lon + lat) * 12) * 2.2, 30, 95),
  );
  const heatIndexF = Math.round(
    clamp(temperatureF + (relativeHumidityPct - 45) * 0.22 + point.value * 0.04, 72, 135),
  );
  const treeCanopyPct = Math.round(clamp(42 - point.value * 0.28 - noise * 2.5, 3, 48));
  const imperviousSurfacePct = Math.round(clamp(18 + point.value * 0.72 + noise * 3, 12, 98));
  const landSurfaceTempF = Math.round(
    clamp(temperatureF + 0.16 * imperviousSurfacePct - 0.11 * treeCanopyPct, 72, 150),
  );
  const nighttimeTempF = Math.round(
    clamp(70 + point.value * 0.17 + (imperviousSurfacePct - treeCanopyPct) * 0.06, 65, 100),
  );

  return {
    temperatureF,
    heatIndexF,
    relativeHumidityPct,
    landSurfaceTempF,
    nighttimeTempF,
    treeCanopyPct,
    imperviousSurfacePct,
  };
}

/**
 * Inverse-distance-weighted score at an arbitrary coordinate, derived from a
 * set of measured anchor points. Points near an anchor take on that anchor's
 * value; elsewhere the surrounding anchors blend for a continuous field.
 */
function interpolate(
  lon: number,
  lat: number,
  anchors: HeatmapMetricValue[],
  power: number,
): number {
  let weightedSum = 0;
  let weightTotal = 0;

  for (const a of anchors) {
    const [aLon, aLat] = a.location_coordinates;
    const dLon = lon - aLon;
    const dLat = lat - aLat;
    const distSq = dLon * dLon + dLat * dLat;

    if (distSq < 1e-8) return a.value; // sitting on an anchor

    const weight = 1 / Math.pow(distSq, power / 2);
    weightedSum += weight * a.value;
    weightTotal += weight;
  }

  return weightedSum / weightTotal;
}

/**
 * Builds a full interpolated field for one metric: the measured anchors plus a
 * dense lattice of interpolated points spanning the whole metro bounding box.
 */
function buildField(
  anchors: HeatmapMetricValue[],
  power: number,
  options?: { attachIndividualMetrics?: boolean; rippleAmp?: number },
): HeatmapMetricValue[] {
  const rippleAmp = options?.rippleAmp ?? 1.5;
  const points: HeatmapMetricValue[] = anchors.map((a) => ({ ...a }));

  const minLon = INTERP_CENTER[0] - INTERP_HALF_SPAN_LON;
  const maxLon = INTERP_CENTER[0] + INTERP_HALF_SPAN_LON;
  const minLat = INTERP_CENTER[1] - INTERP_HALF_SPAN_LAT;
  const maxLat = INTERP_CENTER[1] + INTERP_HALF_SPAN_LAT;

  for (let lat = minLat; lat <= maxLat + 1e-9; lat += INTERP_STEP) {
    for (let lon = minLon; lon <= maxLon + 1e-9; lon += INTERP_STEP) {
      const roundedLon = Number(lon.toFixed(3));
      const roundedLat = Number(lat.toFixed(3));

      // Gentle deterministic ripple so the far field isn't a dead-flat plateau.
      const ripple = Math.sin(roundedLon * 20) * Math.cos(roundedLat * 20) * rippleAmp;
      const value = clamp(
        Math.round(interpolate(roundedLon, roundedLat, anchors, power) + ripple),
        MIN_SCORE,
        MAX_SCORE,
      );

      points.push({
        value,
        location_name: 'Interpolated',
        location_coordinates: [roundedLon, roundedLat],
      });
    }
  }

  if (!options?.attachIndividualMetrics) return points;

  return points.map((point) => ({
    ...point,
    individual_metrics: point.individual_metrics ?? buildIndividualMetrics(point),
  }));
}

// ---------------------------------------------------------------------------
// callHeatmapMetricsGrid()
// ---------------------------------------------------------------------------

// One metric's interpolated value lattice for a city. values[row][col] holds
// the metric value at that grid cell centroid; row 0 is the southernmost row.
export interface MetricGrid {
  min: number;
  max: number;
  values: (number | null)[][];
}

// A city's full interpolated raster grid for continuous map rendering.
export interface CityMetricGrid {
  state?: string | null;
  bounds: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
  rows: number;
  cols: number;
  timestamp: string;
  metrics: Record<string, MetricGrid>;
}

// City name -> interpolated raster grid available for that city.
export type HeatmapMetricGridResponse = Record<string, CityMetricGrid>;

const MOCK_GRID_ROWS = 64;
const MOCK_GRID_COLS = 64;

// Sample the hand-authored IDW anchor field onto a regular lattice so the mock
// keeps the same raster-grid shape the backend serves.
function buildMockMetricGrid(
  anchors: HeatmapMetricValue[],
  power: number,
  bounds: [number, number, number, number],
): MetricGrid {
  const [minLon, minLat, maxLon, maxLat] = bounds;
  const lonStep = (maxLon - minLon) / MOCK_GRID_COLS;
  const latStep = (maxLat - minLat) / MOCK_GRID_ROWS;
  const values: number[][] = [];
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;

  for (let row = 0; row < MOCK_GRID_ROWS; row += 1) {
    const lat = minLat + (row + 0.5) * latStep;
    const rowValues: number[] = [];
    for (let col = 0; col < MOCK_GRID_COLS; col += 1) {
      const lon = minLon + (col + 0.5) * lonStep;
      const value = clamp(
        Math.round(interpolate(lon, lat, anchors, power)),
        MIN_SCORE,
        MAX_SCORE,
      );
      min = Math.min(min, value);
      max = Math.max(max, value);
      rowValues.push(value);
    }
    values.push(rowValues);
  }

  return { min, max, values };
}

function buildMockHeatmapMetricsGrid(): HeatmapMetricGridResponse {
  const bounds: [number, number, number, number] = [
    INTERP_CENTER[0] - INTERP_HALF_SPAN_LON,
    INTERP_CENTER[1] - INTERP_HALF_SPAN_LAT,
    INTERP_CENTER[0] + INTERP_HALF_SPAN_LON,
    INTERP_CENTER[1] + INTERP_HALF_SPAN_LAT,
  ];

  return {
    Houston: {
      state: 'Texas',
      bounds,
      rows: MOCK_GRID_ROWS,
      cols: MOCK_GRID_COLS,
      timestamp: 'mock',
      metrics: {
        heat_risk_score: buildMockMetricGrid(ALL_HEAT_ANCHORS, HEAT_IDW_POWER, bounds),
        visitor_activity: buildMockMetricGrid(HOUSTON_VISITOR_ANCHORS, VISITOR_IDW_POWER, bounds),
      },
    },
  };
}

export async function callHeatmapMetricsGrid(): Promise<HeatmapMetricGridResponse> {
  // Use interpolated raster grids from the backend when available. Empty `{}`
  // is treated as "not seeded yet" so the map still displays the mock Houston
  // surface during local demos.
  try {
    const cityGrids = await fetchBackendJson<HeatmapMetricGridResponse>('/heatmap/metrics/grid');
    if (Object.keys(cityGrids).length > 0) return cityGrids;
  } catch (error) {
    console.warn('Falling back to mock heatmap metric grid', error);
  }

  return buildMockHeatmapMetricsGrid();
}

export async function callHeatmapMetricsPoints(): Promise<HeatmapMetricsPointResponse> {
  await new Promise((resolve) => setTimeout(resolve, 500));

  // Use interpolated metric rows from the backend when available. Empty `{}` is
  // treated as "not seeded yet" so the map still displays the dense mock heat
  // field during local demos.
  try {
    const backendLayers = await fetchBackendJson<HeatmapMetricsPointResponse>('/heatmap/metrics/points');
    if (Object.keys(backendLayers).length > 0) return backendLayers;
  } catch (error) {
    console.warn('Falling back to mock heatmap metric points', error);
  }

  return {
    Houston: [
      {
        metric: 'heat_risk_score',
        points: buildField(ALL_HEAT_ANCHORS, HEAT_IDW_POWER, {
          attachIndividualMetrics: true,
        }),
      },
      {
        metric: 'visitor_activity',
        points: buildField(HOUSTON_VISITOR_ANCHORS, VISITOR_IDW_POWER),
      },
    ],
  };
}

export async function importCorePOIFile(file: File): Promise<CorePOIImportResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/core_poi_polygons/import`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Core POI import failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<CorePOIImportResponse>;
}

export async function createSimulationPolygon(
  payload: SimulationPolygonCreateRequest,
): Promise<CityPOIArea> {
  // Save the drawn polygon and let the backend compute impacted grid cells. The
  // response extends CityPOIArea with polygon_geometry_id and impacted ids so
  // later simulation apply calls can target the same grid subset.
  const response = await fetch(`${API_BASE_URL}/heatmap/simulation/polygon`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Create simulation polygon failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<CityPOIArea>;
}

export async function applySimulation(
  payload: SimulationApplyRequest,
): Promise<SimulationApplyResponse> {
  // Apply the placed toolbox interventions to the affected metrics. The backend
  // writes a new timestamped metric snapshot rather than mutating the previous
  // one, which keeps before/after comparison possible.
  const response = await fetch(`${API_BASE_URL}/heatmap/simulation/apply`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Apply simulation failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<SimulationApplyResponse>;
}

// ============================================================================
// Mock API: getCoordinateValue
// Returns a list of metrics. Each metric carries coordinate -> value points.
//
// This version generates a DENSE FIELD: a value at every lattice point across
// the entire Houston metro bounding box, so every grid cell has a value to map.
// The lattice step matches a 2-decimal coordinate key (~0.01° ≈ 1.1 km), so
// each cell centroid (rounded to 2 decimals) finds a matching point. Values are
// temperature (°F) shaped as an urban heat island: hottest near downtown,
// cooler toward Galveston Bay.
// ============================================================================

export type MetricType = 'heat_profile'; // bundled per-point heat attributes

export type HeatCategory = 'low' | 'moderate' | 'high' | 'extreme';

export interface CoordinateValue {
  /** [longitude, latitude] — matches the map's coordinate ordering */
  coordinate: [number, number];

  /** Legacy alias for `temperatureF`, kept so existing callers keep working. */
  value: number;

  /** Dry-bulb air temperature (°F) — the raw thermometer reading. */
  temperatureF: number;

  /** Relative humidity (%). Higher near the coast and water bodies. */
  relativeHumidityPct: number;

  /**
   * Heat index / "feels like" temperature (°F), from the NWS Rothfusz
   * regression on temperature + humidity. This is what heat-health advisories
   * are based on and is usually the single most useful "how hot is it" number.
   */
  heatIndexF: number;

  /**
   * Land surface temperature (°F) — the temperature of the ground itself
   * (asphalt, roofs). Runs far hotter than air over paved, low-canopy areas
   * and is what drives pedestrian-level heat exposure.
   */
  landSurfaceTempF: number;

  /**
   * Overnight low (°F). The urban heat island is strongest at night; areas
   * that stay hot after dark carry the highest heat-mortality risk because
   * residents never get a chance to cool down.
   */
  nighttimeTempF: number;

  /** Tree canopy cover (%). A primary heat-mitigation lever for planners. */
  treeCanopyPct: number;

  /** Impervious surface cover (%) — pavement + rooftops; the main UHI driver. */
  imperviousSurfacePct: number;

  /**
   * Heat Vulnerability Index (0–100): composite of apparent heat, impervious
   * cover, lack of canopy, and nighttime retention. Higher = more intervention
   * priority.
   */
  heatVulnerabilityIndex: number;

  /** NWS-style risk band derived from the heat index. */
  category: HeatCategory;
}

export interface MetricCoordinateData {
  metric: MetricType;
  points: CoordinateValue[];
}

// Bounding box covering the Houston metro grid. Centered on downtown and made
// generous (±0.8° lon, ±0.7° lat) so it fully contains the map's city grid.
const HOUSTON_CENTER: [number, number] = [-95.37, 29.76];
const HALF_SPAN_LON = 0.8;
const HALF_SPAN_LAT = 0.7;

// Lattice step. 0.01° aligns with a 2-decimal coordinate key, guaranteeing a
// point exists for every cell centroid keyed at that precision.
const STEP = 0.01;

// ---------------------------------------------------------------------------
// Spatial driver fields. Everything below is derived from these two so the
// attributes stay physically consistent with one another.
// ---------------------------------------------------------------------------

// Urban-core intensity (0 rural … 1 dense downtown / industrial east).
function urbanIntensity01(lon: number, lat: number): number {
  // Downtown core.
  const dDown = (lon - -95.37) ** 2 + (lat - 29.75) ** 2;
  const downtown = Math.exp(-dDown / (2 * 0.18 * 0.18));
  // Ship-channel / refinery belt to the east — a second hot, paved core.
  const dInd = (lon - -95.25) ** 2 + (lat - 29.73) ** 2;
  const industrial = 0.9 * Math.exp(-dInd / (2 * 0.12 * 0.12));
  return clamp(Math.max(downtown, industrial), 0, 1);
}

// Proximity to Galveston Bay / open water (0 inland … 1 at the coast).
function coastProximity01(lon: number, lat: number): number {
  const d = (lon - -94.95) ** 2 + (lat - 29.45) ** 2;
  return Math.exp(-d / (2 * 0.45 * 0.45));
}

// NWS heat index ("feels like", °F) from air temp (°F) and relative humidity (%).
// Rothfusz regression with the standard low-range and edge adjustments.
function heatIndexF(T: number, RH: number): number {
  // Simple formula, valid when the result is below ~80°F.
  let hi = 0.5 * (T + 61.0 + (T - 68.0) * 1.2 + RH * 0.094);
  hi = (hi + T) / 2;

  if (hi >= 80) {
    hi =
      -42.379 +
      2.04901523 * T +
      10.14333127 * RH -
      0.22475541 * T * RH -
      0.00683783 * T * T -
      0.05481717 * RH * RH +
      0.00122874 * T * T * RH +
      0.00085282 * T * RH * RH -
      0.00000199 * T * T * RH * RH;

    if (RH < 13 && T >= 80 && T <= 112) {
      hi -= ((13 - RH) / 4) * Math.sqrt((17 - Math.abs(T - 95)) / 17);
    } else if (RH > 85 && T >= 80 && T <= 87) {
      hi += ((RH - 85) / 10) * ((87 - T) / 5);
    }
  }
  return hi;
}

// NWS-style risk band from the heat index.
function heatCategory(hi: number): HeatCategory {
  if (hi < 80) return 'low';
  if (hi < 91) return 'moderate'; // "Caution"
  if (hi < 103) return 'high'; // "Extreme Caution"
  return 'extreme'; // "Danger" / "Extreme Danger"
}

/**
 * Mock backend call. Simulates fetching a dense, coordinate-level heat profile
 * covering the entire Houston metro area — one multi-attribute record per
 * lattice point. Every field is derived from the same urban/coastal drivers so
 * they stay mutually consistent (e.g. paved cores are hot, dry, low-canopy,
 * and stay warm at night).
 */
export async function getCoordinateValue(): Promise<MetricCoordinateData[]> {
  const minLon = HOUSTON_CENTER[0] - HALF_SPAN_LON;
  const maxLon = HOUSTON_CENTER[0] + HALF_SPAN_LON;
  const minLat = HOUSTON_CENTER[1] - HALF_SPAN_LAT;
  const maxLat = HOUSTON_CENTER[1] + HALF_SPAN_LAT;

  const points: CoordinateValue[] = [];

  for (let lat = minLat; lat <= maxLat + 1e-9; lat += STEP) {
    for (let lon = minLon; lon <= maxLon + 1e-9; lon += STEP) {
      // Round to 2 decimals so keys line up with a precision-2 coordinate key.
      const roundedLon = Number(lon.toFixed(2));
      const roundedLat = Number(lat.toFixed(2));

      const urban = urbanIntensity01(roundedLon, roundedLat);
      const coast = coastProximity01(roundedLon, roundedLat);
      const ripple = Math.sin(roundedLon * 18) * Math.cos(roundedLat * 18) * 0.8;

      // Air temperature: hot over paved cores, eased by the sea breeze.
      const temperatureF = Math.round(90 + 9 * urban - 9 * coast + ripple);

      // Humidity: humid near the bay, drier over dense urban land.
      const relativeHumidityPct = Math.round(
        clamp(52 + 32 * coast - 12 * urban + Math.sin(roundedLon * 15) * 2, 30, 95),
      );

      // Land cover: cores are paved with little canopy; edges are greener.
      const imperviousSurfacePct = Math.round(clamp(18 + 72 * urban, 12, 95));
      const treeCanopyPct = Math.round(clamp(40 - 32 * urban - 6 * coast, 3, 45));

      // Surface temp: pavement bakes hotter than air; canopy shaves it back.
      const landSurfaceTempF = Math.round(
        temperatureF + 0.18 * imperviousSurfacePct - 0.12 * treeCanopyPct,
      );

      // Overnight low: heat island retains warmth after dark in the core.
      const nighttimeTempF = Math.round(76 + 8 * urban - 3 * coast + ripple * 0.5);

      const hi = heatIndexF(temperatureF, relativeHumidityPct);
      const heatIndexRounded = Math.round(hi);

      // Composite vulnerability: apparent heat + paving + missing canopy +
      // nighttime retention, scaled to 0–100.
      const heatVulnerabilityIndex = Math.round(
        clamp(
          0.9 * (heatIndexRounded - 80) +
            0.35 * (imperviousSurfacePct - 20) +
            0.6 * (45 - treeCanopyPct) +
            1.4 * (nighttimeTempF - 74),
          0,
          100,
        ),
      );

      points.push({
        coordinate: [roundedLon, roundedLat],
        value: temperatureF, // legacy alias
        temperatureF,
        relativeHumidityPct,
        heatIndexF: heatIndexRounded,
        landSurfaceTempF,
        nighttimeTempF,
        treeCanopyPct,
        imperviousSurfacePct,
        heatVulnerabilityIndex,
        category: heatCategory(hi),
      });
    }
  }

  const data: MetricCoordinateData[] = [
    {
      metric: 'heat_profile',
      points,
    },
  ];

  // Simulate network latency.
  await new Promise((resolve) => setTimeout(resolve, 300));

  return data;
}
