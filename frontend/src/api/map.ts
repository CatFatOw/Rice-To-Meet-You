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
// Heatmap API — returns raw measured anchors, keyed city -> [date -> metrics].
// Interpolation is NOT done here; the client interpolates on demand (see utils).
// ============================================================================

// ---------------------------------------------------------------------------
// Source of truth: one physical reading per location, shaped as a
// GridCellMetricResponse. The published metrics (temperature, visitor density)
// read straight off these fields, so the layers stay consistent.
// ---------------------------------------------------------------------------

// Heat-warning cutoff on air temperature (°C) ≈ 95 °F.
const HEAT_THRESHOLD_C = 35;

const DEFAULT_READING_DATE = "2026-07-05";
const DEFAULT_MARKET = "Houston";

// Monotonic id so each mock reading looks like a distinct DB row.
let nextReadingId = 1;

function visitorCategory(density: number): string {
  if (density >= 90) return "Match venue / fan zone";
  if (density >= 75) return "Major attraction";
  if (density >= 55) return "Busy district";
  if (density >= 35) return "Residential";
  return "Low activity";
}

// ---------------------------------------------------------------------------
// Convenience factory: keeps the mock's human-friendly inputs (°F, a 0–100
// visitor density, and land-cover %) and maps them onto the
// GridCellMetricResponse schema. The heat_weather_point fields (humidity, UHI,
// wind) are derived from land cover so that data isn't lost in the migration.
// reading(name, lon, lat, temperatureF, visitorDensity, treeCanopy%, impervious%)
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Literal factory: takes exactly the fields the temperature + visitor_density
// anchors read off a reading, and maps them straight onto the
// GridCellMetricResponse schema. No derivation.
// ---------------------------------------------------------------------------
function reading(
  name: string,
  lon: number,
  lat: number,
  avgTemperatureC: number,
  relativeHumidity: number,
  uhi: number,
  windSpeedKnots: number,
  source: "measured" | "interpolated",
  visitorCount: number,
  category: string,
  market: string,
  visitorCountSource: string,
): LocationReading {
  return {
    id: nextReadingId++,
    date: DEFAULT_READING_DATE,
    latitude: lat,
    longitude: lon,
    name,

    // --- heat_weather_point fields (read by temperatureAnchor) ---
    avg_temperature_c: avgTemperatureC,
    relative_humidity: relativeHumidity,
    uhi,
    wind_speed_knots: windSpeedKnots,
    source,

    // --- visitor_poi fields (read by visitorDensityAnchor) ---
    visitor_count: visitorCount,
    category,
    market,
    visitor_count_source: visitorCountSource,
  };
}

// ---- Builders: one reading -> one anchor per metric ------------------------
// Fields now come off the GridCellMetricResponse directly (no derivation).

const coordsOf = (r: LocationReading): [number, number] => [
  r.longitude,
  r.latitude,
];

function temperatureAnchor(r: LocationReading): HeatmapMetricValue {
  const tempC = r.avg_temperature_c ?? 0;

  return {
    value: tempC, // temperature layer is now in °C (avg_temperature_c)
    location_coordinates: coordsOf(r),
    individual_metrics: {
      avg_temperature_c: `${tempC.toFixed(1)}°C`,
      relative_humidity:
        r.relative_humidity != null ? `${Math.round(r.relative_humidity)}%` : "—",
      uhi: r.uhi != null ? `${r.uhi.toFixed(1)}°C` : "—",
      wind_speed_knots:
        r.wind_speed_knots != null ? `${r.wind_speed_knots.toFixed(1)} kn` : "—",
      source: r.source ?? "—",
    },
  };
}

function visitorDensityAnchor(r: LocationReading): HeatmapMetricValue {
  const count = r.visitor_density ?? 0;
  return {
    value: count, // now a raw visitor_count, not the old 0–100 density
    location_coordinates: coordsOf(r),
    individual_metrics: {
      visitor_count: count.toLocaleString("en-US"),
      category: r.category ?? "—",
      market: r.market ?? "—",
      visitor_count_source: r.visitor_count_source ?? "—",
    },
  };
}

function changeInTemperatureAnchor(r: LocationReading): HeatmapMetricValue {
  const tempC = r.avg_temperature_c ?? 0;

  return {
    value: 0, // baseline: no change until a simulation runs
    location_coordinates: coordsOf(r),
    // Share the temperature layer's weather fields so the simulation can read
    // the true local temp + humidity (the `value` is 0 and can't drive the
    // weather ceiling on its own).
    individual_metrics: {
      avg_temperature_c: `${tempC.toFixed(1)}°C`,
      relative_humidity:
        r.relative_humidity != null ? `${Math.round(r.relative_humidity)}%` : "—",
    },
  };
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

export const availableMetrics = [{"average_temperature_c": ["maximum_temperature_c", "minimum_temperature_c", "average_relative_humidity_pct", "average_wind_speed_knots", "precipitation_3d_sum_mm"]}];

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