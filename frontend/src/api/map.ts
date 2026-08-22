// ============================================================================
// Mock POI Polygon Inputs by City
// ============================================================================

import type {
  Polygon,
  CityPOIArea,
  CityPOIAreaMap,
  LocationReading,
  HeatmapMetricValue,
  HeatmapMetricSnapshot,
  HeatmapMetricPoint,
  HeatmapMetricPointByCity,
  HeatmapMetricPOIValue,
  HeatmapMetricPOISnapshot,
  HeatmapMetricPOIPoint,
  HeatmapMetricPOIByCity,
  HeatmapPointsByDate,
  MetricGrid,
  CityMetricGrid,
  HeatmapMetricGridResponse,
} from '../types/heatmap';



export type {
  CityPOIArea,
  CityPOIAreaMap,
  HeatmapMetricValue,
  HeatmapMetricSnapshot,
  HeatmapMetricPoint,
  HeatmapMetricPointByCity,
  HeatmapMetricPOIValue,
  HeatmapMetricPOISnapshot,
  HeatmapMetricPOIPoint,
  HeatmapMetricPOIByCity,
  Polygon,
  LocationReading,
  MetricGrid,
  CityMetricGrid,
  HeatmapMetricGridResponse,
};

// Centralizing the base URL makes it easy to point a build at a deployed API
// via VITE_API_BASE_URL without touching call sites.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

async function fetchBackendJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

// ============================================================================
// Houston POIs
// ============================================================================

const riceUniversityPolygon: Polygon = [
  [-95.40895, 29.72245],
  [-95.4062, 29.72305],
  [-95.40195, 29.72305],
  [-95.39735, 29.72195],
  [-95.3964, 29.71875],
  [-95.39675, 29.7152],
  [-95.3992, 29.71175],
  [-95.4034, 29.71085],
  [-95.4079, 29.71145],
  [-95.40945, 29.7147],
  [-95.40955, 29.7192],
  [-95.40895, 29.72245],
];

const nrgStadiumPolygon: Polygon = [
  [-95.41195, 29.68655],
  [-95.4104, 29.68635],
  [-95.40935, 29.68545],
  [-95.4092, 29.6841],
  [-95.41025, 29.6831],
  [-95.41195, 29.68285],
  [-95.4136, 29.6831],
  [-95.4146, 29.68405],
  [-95.4145, 29.68545],
  [-95.41345, 29.68635],
  [-95.41195, 29.68655],
];

// ============================================================================
// City → Key POI Areas
// ============================================================================

const cityPOIAreas: CityPOIAreaMap = {
  Houston: [
    {
      id: "nrg-stadium",
      name: "NRG Stadium",
      color: [255, 165, 0, 0],
      polygon: nrgStadiumPolygon,
    },
    {
      id: "rice-university",
      name: "Rice University",
      color: [70, 130, 180, 0],
      polygon: riceUniversityPolygon,
    },
  ],
  // Add additional FIFA host cities here.
  Dallas: [],
  Atlanta: [],
  Miami: [],
  "New York/New Jersey": [],
};

// ============================================================================
// Mock API Calls
// ============================================================================

export async function callMockCityPOIs(
  cityName: string,
): Promise<CityPOIArea[]> {
  // Simulate network latency
  await new Promise((resolve) => setTimeout(resolve, 500));
  return cityPOIAreas[cityName] ?? [];
}

interface CorePOIResponse {
  id: number | string;
  location_name: string;
  city: string;
  color: string;
  polygon_wkt: string;
}

function parseRGBColor(value: string): [number, number, number, number] {
  const match = value.match(/^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/i);
  if (!match) {
    throw new Error(`Invalid POI color: ${value}`);
  }

  return [Number(match[1]), Number(match[2]), Number(match[3]), 160];
}

function parsePolygonWKT(value: string): Polygon {
  const trimmed = value.trim();
  const match = trimmed.match(
    /^(?:POLYGON\s*\(\(\s*|MULTIPOLYGON\s*\(\s*\(\s*\(\s*)([^()]*)\s*\)/i,
  );
  const body = match?.[1];

  if (!body) {
    throw new Error(`Invalid POI polygon: ${value}`);
  }

  return body.split(',').map((coordinate) => {
    const [longitude, latitude] = coordinate
      .trim()
      .split(/\s+/)
      .map(Number);
    if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
      throw new Error(`Invalid POI polygon coordinate: ${coordinate}`);
    }
    return [longitude, latitude];
  });
}

export async function callAllCityPOIs(): Promise<CityPOIAreaMap> {
  const response = await fetch(`${BASE_URL}/core_poi/get-all-pois`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`POI request failed: ${response.status} ${response.statusText}`);
  }

  const rows = (await response.json()) as CorePOIResponse[];
  return rows.reduce<CityPOIAreaMap>((areasByCity, row) => {
    const area: CityPOIArea = {
      id: String(row.id),
      name: row.location_name,
      color: parseRGBColor(row.color),
      polygon: parsePolygonWKT(row.polygon_wkt),
    };
   
    (areasByCity[row.city] ??= []).push(area);
    return areasByCity;
  }, {});
}



// ============================================================================


const BASE_URL = "http://127.0.0.1:8000";

export interface HeatmapMetricOptions {
  /** Column names to include in `individual_metrics`. Omit for all of them;
   *  pass [] for none. The chosen `metric` is always excluded. */
  additionalMetrics?: string[];
  signal?: AbortSignal;
}

function toMarketCode(city: string): string {
  const normalized = city.trim().toLowerCase();
  const aliases: Record<string, string> = {
    'kansas city': 'kansas_city',
    'los angeles': 'los_angeles',
    'san francisco bay area': 'san_francisco',
    'san francisco': 'san_francisco',
    'new york': 'new_york_nj',
    'new jersey': 'new_york_nj',
    'new york/new jersey': 'new_york_nj',
  };
  return aliases[normalized] ?? normalized.replace(/\s+/g, '_');
}

export async function getHeatmapPointsByCityDateMetric(
  city: string,
  date: string, // "YYYY-MM-DD"
  metric: string,
  options: HeatmapMetricOptions = {}
): Promise<{ points: HeatmapMetricValue[]; raw: HeatmapPointsByDate }> {
  const { additionalMetrics, signal } = options;

  const params = new URLSearchParams({ city: toMarketCode(city), date, metric });
  // Repeat the key per value — that's how FastAPI reads List[str].
  additionalMetrics?.forEach((name) =>
    params.append("additional_metrics", name)
  );

  const url = `${BASE_URL}/heatmap/get-heatmap-points-by-city-date-metric?${params}`;
  console.log(url)
  const res = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  // The endpoint 404s when nothing matches — that's an empty result, not a failure.
  if (res.status === 404) {
    return { points: [], raw: {} };
  }

  if (!res.ok) {
    throw new Error(
      `Heatmap request failed: ${res.status} ${res.statusText}`
    );
  }

  const raw = (await res.json()) as HeatmapPointsByDate;
  return { points: raw[date] ?? [], raw };
}

export const availableMetrics = [
  {
  "average_temperature_c": ["maximum_temperature_c", "minimum_temperature_c", "average_relative_humidity_pct", "average_wind_speed_knots", "precipitation_3d_sum_mm", "average_temperature_c"]
  },
  {
  "change_in_temperature": ["maximum_temperature_c", "minimum_temperature_c", "average_relative_humidity_pct", "average_wind_speed_knots", "precipitation_3d_sum_mm", "average_temperature_c"]
  }
];

const generateAvailableDates = (): string[] => {
  const dates: string[] = [];
  const currentDate = new Date("2020-01-01T00:00:00Z");
  const endDate = new Date("2025-12-31T00:00:00Z");

  while (currentDate <= endDate) {
    dates.push(currentDate.toISOString().split("T")[0]);
    currentDate.setUTCDate(currentDate.getUTCDate() + 1);
  }

  return dates;
};

export const availableDates = generateAvailableDates();

// ============================================================================
// Interpolated raster grids + simulation writes
// ============================================================================

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

/**
 * Interpolated raster grids per city, used to render the continuous metric
 * surface. An empty `{}` means the grid tables are not seeded yet, in which
 * case the caller simply renders no surface.
 */
export async function callHeatmapMetricsGrid(): Promise<HeatmapMetricGridResponse> {
  try {
    const cityGrids = await fetchBackendJson<HeatmapMetricGridResponse>('/heatmap/metrics/grid');
    return cityGrids ?? {};
  } catch (error) {
    console.warn('Failed to load heatmap metric grids', error);
    return {};
  }
}

/** Saved POI polygons for the map. Falls back to the legacy route, then none. */
export async function callCorePOIAreas(): Promise<CityPOIArea[]> {
  try {
    const backendPOIs = await fetchBackendJson<CityPOIArea[]>('/heatmap/core-pois?limit=500');
    if (backendPOIs.length > 0) return backendPOIs;
  } catch (error) {
    console.warn('Falling back to saved location POIs', error);
  }

  try {
    return await fetchBackendJson<CityPOIArea[]>('/heatmap/location-pois');
  } catch {
    return [];
  }
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
