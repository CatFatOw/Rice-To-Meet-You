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
};

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

async function getFinalVisitorPointsByCityDate(
  path: string,
  city: string,
  date: string,
): Promise<HeatmapMetricValue[]> {
  const cityVariants = Array.from(new Set([city, toMarketCode(city)]));

  for (const cityVariant of cityVariants) {
    const params = new URLSearchParams({ city: cityVariant, date });
    const response = await fetch(`${BASE_URL}${path}?${params}`);

    if (response.status === 404) {
      continue;
    }

    if (!response.ok) {
      throw new Error(
        `Failed to load final visitor data: ${response.status} ${response.statusText}`,
      );
    }

    const raw = (await response.json()) as HeatmapPointsByDate;
    const points = raw[date] ?? [];
    if (points.length > 0) {
      return points;
    }
  }

  return [];
}

export async function getVisitorDataByCityDate(
  city: string,
  date: string,
): Promise<HeatmapMetricValue[]> {
  return getFinalVisitorPointsByCityDate(
    "/final_visitor/get-visitor-by-city-date",
    city,
    date,
  );
}

export async function getHeatRiskDataByCityDate(
  city: string,
  date: string,
): Promise<HeatmapMetricValue[]> {
  return getFinalVisitorPointsByCityDate(
    "/final_visitor/get-heat-risk-score-by-city-date",
    city,
    date,
  );
}

export const availableMetrics = [
  {
    average_temperature_c: [
      "maximum_temperature_c",
      "minimum_temperature_c",
      "average_relative_humidity_pct",
      "average_wind_speed_knots",
      "precipitation_3d_sum_mm",
      "average_temperature_c",
    ],
  },
  {
    average_temperature_f: [
      "maximum_temperature_c",
      "minimum_temperature_c",
      "average_relative_humidity_pct",
      "average_wind_speed_knots",
      "precipitation_3d_sum_mm",
      "average_temperature_f",
    ],
  },
  {
    heat_index_f: [
      "average_temperature_f",
      "average_relative_humidity_pct",
      "heat_index_f",
    ],
  },
  {
    heat_index_c: [
      "average_temperature_c",
      "average_relative_humidity_pct",
      "heat_index_c",
    ],
  },
  {
    average_relative_humidity_pct: [
      "average_temperature_c",
      "average_temperature_f",
      "average_dew_point_f",
      "dew_point_depression_c",
      "average_relative_humidity_pct",
    ],
  },
  {
    change_in_temperature: [
      "maximum_temperature_c",
      "minimum_temperature_c",
      "average_relative_humidity_pct",
      "average_wind_speed_knots",
      "precipitation_3d_sum_mm",
      "average_temperature_c",
    ],
  },
  {
    avg_daily_visits: [
      "avg_daily_visits",
      "heat_risk_score",
    ],
  },
  {
    heat_risk_score: [
      "heat_risk_score",
      "avg_daily_visits",
    ],
  },
  {

    local_temperature_c: [

      "local_temperature_c",

      "local_temperature_f",

      "average_temperature_c",

      "average_relative_humidity_pct",

    ],

  },

  {

    local_temperature_f: [

      "local_temperature_f",

      "local_temperature_c",

      "average_temperature_f",

      "average_relative_humidity_pct",

    ],

  },
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


export interface LocalTemperatureOptions {
  /** Temperature column the backend reads from. Defaults to `average_temperature_c`. */
  metric?: string;
  /** Humidity column the backend reads from. Defaults to `average_relative_humidity_pct`. */
  humidityMetric?: string;
  signal?: AbortSignal;
}

async function getLocalTemperaturePointsByCityDate(
  path: string,
  city: string,
  date: string, // "YYYY-MM-DD"
  options: LocalTemperatureOptions = {},
): Promise<HeatmapMetricValue[]> {
  const {
    metric = "average_temperature_c",
    humidityMetric = "average_relative_humidity_pct",
    signal,
  } = options;

  const params = new URLSearchParams({
    city: toMarketCode(city),
    date,
    metric,
    humidity_metric: humidityMetric,
  });

  const response = await fetch(`${BASE_URL}${path}?${params}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  // 404 means no rows matched, which is an empty result rather than a failure.
  if (response.status === 404) {
    return [];
  }

  if (!response.ok) {
    throw new Error(
      `Local temperature request failed: ${response.status} ${response.statusText}`,
    );
  }

  const raw = (await response.json()) as HeatmapPointsByDate;
  return raw[date] ?? [];
}

export async function getLocalTemperatureCByCityDate(
  city: string,
  date: string,
  options: LocalTemperatureOptions = {},
): Promise<HeatmapMetricValue[]> {
  return getLocalTemperaturePointsByCityDate(
    "/heatmap/get-heat-index-c-by-city-date",
    city,
    date,
    options,
  );
}

export async function getLocalTemperatureFByCityDate(
  city: string,
  date: string,
  options: LocalTemperatureOptions = {},
): Promise<HeatmapMetricValue[]> {
  return getLocalTemperaturePointsByCityDate(
    "/heatmap/get-heat-index-f-by-city-date",
    city,
    date,
    options,
  );
}