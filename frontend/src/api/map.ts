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

import { polygonCenter } from '../services/toolbox';

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

const BASE_URL = "http://127.0.0.1:8000";

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

export interface CorePOIResponse {
  id: number | string;
  location_name: string;
  city: string;
  color: string;
  polygon_wkt: string;
}

// ============================================================================
// Polygon / Color Parsing
// ============================================================================

function parseRGBColor(value?: string | null): [number, number, number, number] {
  if (!value) {
    return [34, 197, 94, 160];
  }
  const match = value.match(/^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/i);
  if (match) {
    return [Number(match[1]), Number(match[2]), Number(match[3]), 160];
  }
  const matchRgba = value.match(/^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)$/i);
  if (matchRgba) {
    const a = parseFloat(matchRgba[4]);
    return [Number(matchRgba[1]), Number(matchRgba[2]), Number(matchRgba[3]), a <= 1 ? Math.round(a * 255) : Number(a)];
  }
  if (value.startsWith('#')) {
    const hex = value.slice(1);
    const expanded = hex.length === 3 ? hex.split('').map((c) => c + c).join('') : hex;
    const int = parseInt(expanded, 16);
    if (!Number.isNaN(int)) {
      return [(int >> 16) & 255, (int >> 8) & 255, int & 255, 160];
    }
  }

  return [34, 197, 94, 160];
}

/**
 * Parses a bare coordinate list — no WKT keyword or parentheses — into a ring.
 *
 * Accepts both shapes people actually type:
 *   "-96.80 32.78, -96.79 32.79, -96.78 32.77"   (space between lng/lat)
 *   "-96.80,32.78,-96.79,32.79,-96.78,32.77"     (flat comma-separated list)
 */
function parsePolygonBody(value: string): Polygon {
  // Tolerate a caller who wrapped the list in its own parens.
  const cleaned = value.trim().replace(/^\(+/, '').replace(/\)+$/, '').trim();

  if (!cleaned) {
    throw new Error('Invalid POI polygon: coordinate list is empty');
  }

  const chunks = cleaned
    .split(',')
    .map((chunk) => chunk.trim())
    .filter(Boolean);

  if (chunks.length === 0) {
    throw new Error('Invalid POI polygon: coordinate list is empty');
  }

  const ring: Polygon = [];

  // If no chunk holds two numbers, this is a flat list and pairs straddle commas.
  const isFlatList = chunks.every((chunk) => !/\s/.test(chunk));

  if (isFlatList) {
    if (chunks.length % 2 !== 0) {
      throw new Error(
        `Invalid POI polygon: expected an even number of values, got ${chunks.length}`,
      );
    }

    for (let i = 0; i < chunks.length; i += 2) {
      ring.push(toCoordinate(chunks[i], chunks[i + 1], `${chunks[i]},${chunks[i + 1]}`));
    }
  } else {
    for (const chunk of chunks) {
      const parts = chunk.split(/\s+/);
      if (parts.length !== 2) {
        throw new Error(`Invalid POI polygon coordinate: ${chunk}`);
      }
      ring.push(toCoordinate(parts[0], parts[1], chunk));
    }
  }

  // A closing vertex is optional on input, so count distinct points.
  const first = ring[0];
  const last = ring[ring.length - 1];
  const distinct =
    ring.length > 1 && first[0] === last[0] && first[1] === last[1]
      ? ring.length - 1
      : ring.length;

  if (distinct < 3) {
    throw new Error(
      `Invalid POI polygon: a ring needs at least 3 distinct points, got ${distinct}`,
    );
  }

  return ring;
}

function toCoordinate(
  rawLongitude: string,
  rawLatitude: string,
  context: string,
): [number, number] {
  const longitude = Number(rawLongitude);
  const latitude = Number(rawLatitude);

  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
    throw new Error(`Invalid POI polygon coordinate: ${context}`);
  }

  return [longitude, latitude];
}

/** Strips the POLYGON/MULTIPOLYGON wrapper, then parses the outer ring. */
function parsePolygonWKT(value: string): Polygon {
  const trimmed = value.trim();
  const match = trimmed.match(
    /^(?:POLYGON\s*\(\(\s*|MULTIPOLYGON\s*\(\s*\(\s*\(\s*)([^()]*)\s*\)/i,
  );
  const body = match?.[1];

  if (!body) {
    throw new Error(`Invalid POI polygon: ${value}`);
  }

  return parsePolygonBody(body);
}

/** Accepts either a WKT string or a bare coordinate list. */
export function toPolygonRing(value: string): Polygon {
  return /^\s*(?:MULTI)?POLYGON/i.test(value)
    ? parsePolygonWKT(value)
    : parsePolygonBody(value);
}

/** Serializes a ring as `POLYGON((lng lat, ...))`, closing it if needed. */
export function toPolygonWKT(ring: Polygon): string {
  const first = ring[0];
  const last = ring[ring.length - 1];
  const closed =
    first[0] === last[0] && first[1] === last[1] ? ring : [...ring, first];

  const body = closed.map(([lng, lat]) => `${lng} ${lat}`).join(', ');
  return `POLYGON((${body}))`;
}

export async function callAllCityPOIs(): Promise<CityPOIAreaMap> {
  const response = await fetch(`${BASE_URL}/core_poi/get-all-pois`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });



  if (!response.ok) {
    throw new Error(`POI request failed: ${response.status} ${response.statusText}`);
  }

  const rows = (await response.json()) as (CorePOIResponse & Record<string, any>)[];

  return rows.reduce<CityPOIAreaMap>((areasByCity, row) => {
    const area: CityPOIArea = {
      ...row,
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
// Market Codes
// ============================================================================

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

// ============================================================================
// POI Creation
// ============================================================================

const HEX_COLOR = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i;

/**
 * "#ff0000" | "#f00" -> "rgb(255, 0, 0)".
 * Existing rgb()/rgba() strings pass through unchanged.
 */
function toRgbColor(color: string): string {
  const value = color.trim();
  if (/^rgba?\(/i.test(value)) return value;

  const match = HEX_COLOR.exec(value);
  if (!match) {
    throw new Error(`POI color must be a hex or rgb color: ${color}`);
  }

  const hex =
    match[1].length === 3 ? match[1].replace(/./g, (c) => c + c) : match[1];

  const int = parseInt(hex, 16);
  return `rgb(${(int >> 16) & 255}, ${(int >> 8) & 255}, ${int & 255})`;
}

/** Optional columns the endpoint accepts. Passed through untouched. */
export interface CreatePOIOptionalFields {
  brands?: string[];
  category_tags?: string[];
  domains?: string[];
  enclosed?: boolean;
  naics_code?: number;
  naics_code_2022?: number;
  /** "YYYY-MM-DD" */
  opened_on?: string;
  /** e.g. { Mon: [["9:00", "17:00"]] } */
  open_hours?: Record<string, string[][]>;
  phone_number?: string;
  postal_code?: string;
  street_address?: string;
  sub_category?: string;
  sub_category_2022?: string;
  top_category?: string;
  top_category_2022?: string;
  website?: string;
  wkt_area_sq_meters?: number;
  /** Hex ("#ff0000" or "#f00") or an rgb() string. Sent as "rgb(r, g, b)". */
  color?: string;
}

export interface CreatePOIInput extends CreatePOIOptionalFields {
  /** Display city, e.g. "Kansas City". `market` is derived from this. */
  city: string;
  /** "-96.80 32.78, -96.79 32.79, ..." or a full POLYGON/MULTIPOLYGON WKT. */
  polygon: string;
  location_name: string;
  /** Two-letter state/region code. */
  region: string;
  includes_parking_lot: boolean;
  signal?: AbortSignal;
}

export async function createPOI(
  input: CreatePOIInput,
): Promise<CorePOIResponse> {
  const { city, polygon, region, location_name, signal, color, ...rest } =
    input;

  const ring = toPolygonRing(polygon);
  const [longitude, latitude] = polygonCenter(ring);

  if (!Number.isFinite(longitude) || Math.abs(longitude) > 180) {
    throw new Error(`POI longitude out of range: ${longitude}`);
  }
  if (!Number.isFinite(latitude) || Math.abs(latitude) > 90) {
    throw new Error(`POI latitude out of range: ${latitude}`);
  }

  const normalizedRegion = region.trim().toUpperCase();
  if (normalizedRegion.length !== 2) {
    throw new Error(`POI region must be a two-letter code: ${region}`);
  }

  const trimmedName = location_name.trim();
  if (!trimmedName) {
    throw new Error('POI location_name is required');
  }

  const payload = {
    ...rest,
    ...(color === undefined ? {} : { color: toRgbColor(color) }),
    location_name: trimmedName,
    city: city.trim(),
    market: toMarketCode(city),
    region: normalizedRegion,
    polygon_wkt: toPolygonWKT(ring),
    latitude,
    longitude,
  };
  console.log(payload)

  const response = await fetch(`${BASE_URL}/core_poi/create-poi`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    // FastAPI puts validation errors in `detail`; surface it when present.
    const detail = await response.text().catch(() => '');
    throw new Error(
      `POI creation failed: ${response.status} ${response.statusText}${
        detail ? ` — ${detail}` : ''
      }`,
    );
  }

  return (await response.json()) as CorePOIResponse;
}

// ============================================================================
// Heatmap
// ============================================================================

export interface HeatmapMetricOptions {
  /** Column names to include in `individual_metrics`. Omit for all of them;
   *  pass [] for none. The chosen `metric` is always excluded. */
  additionalMetrics?: string[];
  signal?: AbortSignal;
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
    change_in_average_temperature_c: [
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
      "average_temperature_c",
      "average_relative_humidity_pct",
    ],
  },
  {
    local_temperature_f: [
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
  city: string,
  date: string, // "YYYY-MM-DD"
  temperatureUnit: 'c' | 'f',
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
    temperature_unit: temperatureUnit,
  });

  const response = await fetch(`${BASE_URL}/heatmap/get-local-temperature-by-city-date?${params}`, {
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
    city,
    date,
    'c',
    options,
  );
}

export async function getLocalTemperatureFByCityDate(
  city: string,
  date: string,
  options: LocalTemperatureOptions = {},
): Promise<HeatmapMetricValue[]> {
  return getLocalTemperaturePointsByCityDate(
    city,
    date,
    'f',
    options,
  );
}