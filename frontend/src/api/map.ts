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
} from '../types/heatmap';

import type { HeatmapPointsByDate } from '../types/heatmap';

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
      color: [255, 165, 0, 150],
      polygon: nrgStadiumPolygon,
    },
    {
      id: "rice-university",
      name: "Rice University",
      color: [70, 130, 180, 150],
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

export async function callMockAllCityPOIs(): Promise<CityPOIAreaMap> {
  // Simulate network latency
  await new Promise((resolve) => setTimeout(resolve, 500));
  return cityPOIAreas;
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
const labelOf = (r: LocationReading): string =>
  r.name ?? `${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}`;

function temperatureAnchor(r: LocationReading): HeatmapMetricValue {
  const tempC = r.avg_temperature_c ?? 0;

  return {
    value: tempC, // temperature layer is now in °C (avg_temperature_c)
    location_name: labelOf(r),
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
    location_name: labelOf(r),
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
    location_name: labelOf(r),
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

// ---------------------------------------------------------------------------
// The readings: dense clusters over three adjacent areas only —
// Rice University, Texas Medical Center, and Hermann Park.
// reading(name, lon, lat, temperatureF, visitorDensity, treeCanopy%, impervious%)
// ---------------------------------------------------------------------------
const HOUSTON_READINGS: LocationReading[] = [
  // --- Rice University (leafy campus) ---------------------------------------
  reading("Rice University Main Quad", -95.4015, 29.717, 32.8, 69, 1.52, 6.9, "measured", 66, "Busy district", "Houston", "mock"),
  reading("Rice Academic Quad", -95.4008, 29.7175, 33.3, 69, 1.73, 6.8, "measured", 68, "Busy district", "Houston", "mock"),
  reading("Rice Fondren Library", -95.4002, 29.7182, 33.3, 68, 1.89, 6.7, "measured", 70, "Busy district", "Houston", "mock"),
  reading("Rice Student Center", -95.3995, 29.7165, 33.9, 68, 2, 6.7, "measured", 72, "Busy district", "Houston", "mock"),
  reading("Rice Brochstein Pavilion", -95.3999, 29.7178, 33.3, 69, 1.71, 6.8, "measured", 74, "Busy district", "Houston", "mock"),
  reading("Rice Central Campus", -95.402, 29.7168, 32.8, 70, 1.44, 7, "measured", 63, "Busy district", "Houston", "mock"),
  reading("Rice Engineering Quad", -95.3988, 29.7168, 33.9, 68, 1.87, 6.8, "measured", 64, "Busy district", "Houston", "mock"),
  reading("Rice North Colleges", -95.4025, 29.7195, 32.8, 70, 1.26, 7.1, "measured", 58, "Busy district", "Houston", "mock"),
  reading("Rice South Colleges", -95.403, 29.7145, 33.3, 70, 1.39, 7, "measured", 55, "Busy district", "Houston", "mock"),
  reading("Rice Inner Loop (East)", -95.3975, 29.7185, 33.3, 69, 1.55, 6.9, "measured", 56, "Busy district", "Houston", "mock"),
  reading("Rice Inner Loop (West)", -95.4065, 29.7185, 33.3, 69, 1.76, 6.8, "measured", 50, "Residential", "Houston", "mock"),
  reading("Rice Stadium", -95.4075, 29.716, 34.4, 66, 2.6, 6.4, "measured", 60, "Busy district", "Houston", "mock"),
  reading("Rice Tudor Fieldhouse", -95.406, 29.715, 34.4, 67, 2.44, 6.5, "measured", 62, "Busy district", "Houston", "mock"),
  reading("Rice Football Practice Fields", -95.407, 29.714, 33.9, 68, 2.15, 6.7, "measured", 45, "Residential", "Houston", "mock"),
  reading("Rice West Lot", -95.4082, 29.7175, 35, 66, 2.76, 6.4, "measured", 40, "Residential", "Houston", "mock"),
  reading("Rice Entrance (Main St)", -95.4038, 29.7118, 33.9, 68, 2.16, 6.6, "measured", 66, "Busy district", "Houston", "mock"),
 
  // --- Texas Medical Center (hot, dense medical core) -----------------------
  reading("Texas Medical Center Core", -95.3992, 29.7067, 36.7, 63, 3.95, 5.6, "measured", 70, "Busy district", "Houston", "mock"),
  reading("TMC MD Anderson", -95.4015, 29.7075, 37.2, 62, 4.16, 5.5, "measured", 68, "Busy district", "Houston", "mock"),
  reading("TMC Texas Children's", -95.3985, 29.7075, 36.7, 63, 4.03, 5.6, "measured", 72, "Busy district", "Houston", "mock"),
  reading("TMC Houston Methodist", -95.3998, 29.7098, 36.7, 63, 3.95, 5.6, "measured", 71, "Busy district", "Houston", "mock"),
  reading("TMC Memorial Hermann", -95.3968, 29.71, 36.1, 63, 3.87, 5.6, "measured", 69, "Busy district", "Houston", "mock"),
  reading("TMC Baylor College of Medicine", -95.4008, 29.7085, 37.2, 62, 4.16, 5.5, "measured", 66, "Busy district", "Houston", "mock"),
  reading("TMC Metro Rail Station", -95.3978, 29.7085, 36.7, 62, 4.24, 5.4, "measured", 67, "Busy district", "Houston", "mock"),
  reading("TMC Fannin Corridor", -95.397, 29.707, 37.2, 62, 4.32, 5.4, "measured", 64, "Busy district", "Houston", "mock"),
  reading("TMC Dryden Station", -95.3982, 29.7108, 36.1, 63, 3.95, 5.6, "measured", 68, "Busy district", "Houston", "mock"),
  reading("TMC Smith Building", -95.4002, 29.7108, 36.7, 63, 4.03, 5.6, "measured", 66, "Busy district", "Houston", "mock"),
  reading("TMC Ben Taub", -95.3958, 29.7095, 36.1, 63, 3.74, 5.7, "measured", 62, "Busy district", "Houston", "mock"),
  reading("TMC West Extension", -95.4028, 29.7085, 37.2, 62, 4.16, 5.5, "measured", 63, "Busy district", "Houston", "mock"),
  reading("TMC Garage District", -95.402, 29.706, 37.8, 61, 4.45, 5.3, "measured", 58, "Busy district", "Houston", "mock"),
  reading("TMC Holcombe Blvd", -95.403, 29.7048, 37.8, 62, 4.37, 5.4, "measured", 55, "Busy district", "Houston", "mock"),
  reading("TMC South (TMC3)", -95.3995, 29.703, 37.8, 62, 4.32, 5.4, "measured", 60, "Busy district", "Houston", "mock"),
  reading("TMC Braeswood Edge", -95.401, 29.702, 37.2, 63, 4.03, 5.6, "measured", 52, "Residential", "Houston", "mock"),
 
  // --- Hermann Park (green, cooler, big draws) ------------------------------
  reading("Hermann Park Reflection Pool", -95.3905, 29.718, 31.7, 72, 0.44, 7.6, "measured", 84, "Major attraction", "Houston", "mock"),
  reading("Hermann Park McGovern Lake", -95.392, 29.7135, 31.1, 73, 0.15, 7.8, "measured", 80, "Major attraction", "Houston", "mock"),
  reading("Hermann Park Miller Outdoor Theatre", -95.3895, 29.7165, 31.7, 73, 0.28, 7.7, "measured", 86, "Major attraction", "Houston", "mock"),
  reading("Houston Zoo", -95.3925, 29.721, 32.8, 71, 1.05, 7.2, "measured", 88, "Major attraction", "Houston", "mock"),
  reading("Hermann Park Japanese Garden", -95.3888, 29.7168, 31.1, 73, 0, 7.9, "measured", 78, "Major attraction", "Houston", "mock"),
  reading("Hermann Park Golf Course", -95.387, 29.713, 31.1, 75, 0, 8.1, "measured", 60, "Busy district", "Houston", "mock"),
  reading("Hermann Park Centennial Gardens", -95.3892, 29.715, 31.7, 73, 0.12, 7.8, "measured", 82, "Major attraction", "Houston", "mock"),
  reading("Hermann Park Molly Ann Smith Plaza", -95.3908, 29.7188, 32.2, 72, 0.6, 7.6, "measured", 85, "Major attraction", "Houston", "mock"),
  reading("Hermann Park Sam Houston Monument", -95.3908, 29.7205, 32.8, 70, 1.05, 7.3, "measured", 87, "Major attraction", "Houston", "mock"),
  reading("Hermann Park Pinewood Cafe", -95.39, 29.7145, 31.7, 73, 0.18, 7.8, "measured", 79, "Major attraction", "Houston", "mock"),
  reading("Hermann Park Bill Coats Bridge", -95.3918, 29.712, 31.1, 74, 0, 8, "measured", 70, "Busy district", "Houston", "mock"),
  reading("Hermann Park Jones Reflection Pool", -95.3902, 29.7175, 31.7, 72, 0.36, 7.7, "measured", 83, "Major attraction", "Houston", "mock"),
  reading("Hermann Park East Meadow", -95.3878, 29.716, 31.1, 74, 0, 8, "measured", 74, "Busy district", "Houston", "mock"),
  reading("Hermann Park Marvin Taylor Trail", -95.3885, 29.7125, 31.1, 74, 0, 8.1, "measured", 66, "Busy district", "Houston", "mock"),
  reading("Hermann Park Lake Plaza", -95.3915, 29.714, 31.7, 73, 0.15, 7.8, "measured", 81, "Major attraction", "Houston", "mock"),
  reading("Hermann Park Grand Gateway", -95.39, 29.7115, 32.2, 71, 0.86, 7.4, "measured", 76, "Major attraction", "Houston", "mock"),
];

// Two published metric layers, both derived from the same readings.
const TEMPERATURE_ANCHORS: HeatmapMetricValue[] =
  HOUSTON_READINGS.map(temperatureAnchor);
const VISITOR_DENSITY_ANCHORS: HeatmapMetricValue[] =
  HOUSTON_READINGS.map(visitorDensityAnchor);
const CHANGE_IN_TEMPERATURE_ANCHORS: HeatmapMetricValue[] =
  HOUSTON_READINGS.map(changeInTemperatureAnchor);

// A day's worth of layers (same anchors reused across the sample dates).
const daySnapshots = (): HeatmapMetricSnapshot[] => [
  { metric: "temperature", points: TEMPERATURE_ANCHORS },
  { metric: "visitor_density", points: VISITOR_DENSITY_ANCHORS },
  { metric: "change_in_temperature", points: CHANGE_IN_TEMPERATURE_ANCHORS },
];

// ---------------------------------------------------------------------------
// Backend anchor source. Shaped like the API response, but each snapshot's
// `points` holds the raw measured anchors — interpolation happens client-side.
// ---------------------------------------------------------------------------
const BACKEND_ANCHOR: HeatmapMetricPointByCity = {
  Houston: [
    {
      "2026-07-05": daySnapshots(),
      "2026-07-06": daySnapshots(),
      "2026-07-07": daySnapshots(),
      "2026-07-08": daySnapshots(),
    },
  ],
};

// The API call: hands back the raw anchors (no interpolation).
export async function callHeatmapAnchors(): Promise<HeatmapMetricPointByCity> {
  await new Promise((resolve) => setTimeout(resolve, 500));
  return BACKEND_ANCHOR;
}

// ============================================================================
// Heatmap POI API — per-POI aggregated metric values.
//
// Each published metric is aggregated over the raw readings that fall inside a
// POI polygon, producing one value per POI. Same city -> [date -> snapshots]
// shape as the anchor API, but every entry is a whole POI area (carries its
// polygon + fill color instead of a single coordinate).
// ============================================================================

// --- Aggregation helpers ----------------------------------------------------

// Ray-casting point-in-polygon test.
function pointInPolygon(lon: number, lat: number, polygon: Polygon): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    const hit =
      yi > lat !== yj > lat &&
      lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
    if (hit) inside = !inside;
  }
  return inside;
}

function polygonCentroid(polygon: Polygon): [number, number] {
  // Drop the closing vertex if the ring is explicitly closed.
  const closed =
    polygon.length > 1 &&
    polygon[0][0] === polygon[polygon.length - 1][0] &&
    polygon[0][1] === polygon[polygon.length - 1][1];
  const pts = closed ? polygon.slice(0, -1) : polygon;
  const [sx, sy] = pts.reduce(
    (acc, [lon, lat]) => [acc[0] + lon, acc[1] + lat] as [number, number],
    [0, 0] as [number, number],
  );
  return [sx / pts.length, sy / pts.length];
}

// Readings inside the polygon; falls back to the single nearest reading when a
// polygon contains none, so every POI stays populated.
function readingsForPolygon(polygon: Polygon): LocationReading[] {
  const inside = HOUSTON_READINGS.filter((r) =>
    pointInPolygon(r.longitude, r.latitude, polygon),
  );
  if (inside.length > 0) return inside;

  const [cx, cy] = polygonCentroid(polygon);
  let nearest = HOUSTON_READINGS[0];
  let best = Infinity;
  for (const r of HOUSTON_READINGS) {
    const d = (r.longitude - cx) ** 2 + (r.latitude - cy) ** 2;
    if (d < best) {
      best = d;
      nearest = r;
    }
  }
  return [nearest];
}

// Mean of the readings, positioned at the polygon centroid. Building a metric
// anchor from this yields the POI aggregate (the anchor values are read
// straight off numeric fields, so the built value equals the mean of the
// individual point values).
function meanReading(
  readings: LocationReading[],
  name: string,
  at: [number, number],
): LocationReading {
  const n = readings.length || 1;
  const sum = readings.reduce(
    (a, r) => {
      a.avg_temperature_c += r.avg_temperature_c ?? 0;
      a.relative_humidity += r.relative_humidity ?? 0;
      a.wind_speed_knots += r.wind_speed_knots ?? 0;
      a.uhi += r.uhi ?? 0;
      a.distance_to_nearest_station_km += r.distance_to_nearest_station_km ?? 0;
      a.visitor_count += r.visitor_count ?? 0;
      return a;
    },
    {
      avg_temperature_c: 0,
      relative_humidity: 0,
      wind_speed_knots: 0,
      uhi: 0,
      distance_to_nearest_station_km: 0,
      visitor_count: 0,
    },
  );

  const avgTemperatureC = sum.avg_temperature_c / n;
  const visitorCount = sum.visitor_count / n;
  const first = readings[0];

  return {
    id: -1, // synthetic aggregate, not a DB row
    date: first?.date ?? DEFAULT_READING_DATE,
    latitude: at[1],
    longitude: at[0],
    name,

    // --- heat_weather_point fields (averaged) ---
    avg_temperature_c: avgTemperatureC,
    relative_humidity: sum.relative_humidity / n,
    wind_speed_knots: sum.wind_speed_knots / n,
    uhi: sum.uhi / n,
    source: "interpolated", // aggregate over measured points
    distance_to_nearest_station_km: sum.distance_to_nearest_station_km / n,
    passed_threshold: avgTemperatureC >= HEAT_THRESHOLD_C,

    // --- visitor_poi fields (averaged / representative) ---
    market: first?.market ?? DEFAULT_MARKET,
    category: visitorCategory(visitorCount),
    visitor_count: visitorCount,
    visitor_count_source: first?.visitor_count_source ?? "mock",
  };
}

// Aggregate one POI for one metric.
function poiMetricValue(
  area: CityPOIArea,
  build: (r: LocationReading) => HeatmapMetricValue,
): HeatmapMetricPOIValue {
  const contained = readingsForPolygon(area.polygon);
  const mean = meanReading(contained, area.name, polygonCentroid(area.polygon));
  const base = build(mean);
  return {
    value: base.value,
    location_name: area.name,
    poi_coordinates: area.polygon,
    color: area.color,
    individual_metrics: {
      ...base.individual_metrics,
      sampleCount: `${contained.length}`,
    },
  };
}

// metric name -> the same builder used for point anchors.
const POI_METRIC_BUILDERS: Record<
  string,
  (r: LocationReading) => HeatmapMetricValue
> = {
  temperature: temperatureAnchor,
  visitor_density: visitorDensityAnchor,
};

// All metric snapshots for a set of POIs (one day).
function poiDaySnapshots(areas: CityPOIArea[]): HeatmapMetricPOISnapshot[] {
  return Object.entries(POI_METRIC_BUILDERS).map(([metric, build]) => ({
    metric,
    points: areas.map((area) => poiMetricValue(area, build)),
  }));
}

// ---------------------------------------------------------------------------
// Backend POI source. NRG Stadium + Rice University for now; add more POIs to
// cityPOIAreas.Houston and they flow through automatically.
// ---------------------------------------------------------------------------
const HOUSTON_POI_AREAS = cityPOIAreas.Houston;

const BACKEND_POI_ANCHOR: HeatmapMetricPOIByCity = {
  Houston: [
    {
      "2026-07-05": poiDaySnapshots(HOUSTON_POI_AREAS),
      "2026-07-06": poiDaySnapshots(HOUSTON_POI_AREAS),
      "2026-07-07": poiDaySnapshots(HOUSTON_POI_AREAS),
      "2026-07-08": poiDaySnapshots(HOUSTON_POI_AREAS),
    },
  ],
};

// The API call: per-POI aggregated metric values (no interpolation).
export async function callHeatmapPOIAnchors(city: string, date: string, metric: string): Promise<HeatmapMetricPOIByCity> {
  await new Promise((resolve) => setTimeout(resolve, 500));
  return BACKEND_POI_ANCHOR;
}


// ============================================================================
// Heatmap points-by-date API — Houston, a single metric layer flattened to
// date -> points. This is the shape the intervention simulation consumes
// (getSimulatedPointsByDate(metric, pointsByDate, placedObjects)).
// ============================================================================

/**
 * Houston's anchors for one metric, keyed by date.
 *
 * Points are structured-cloned per date: daySnapshots() hands every date the
 * same TEMPERATURE_ANCHORS / CHANGE_IN_TEMPERATURE_ANCHORS array reference, so
 * without the clone a single in-place mutation on 2026-07-05 would silently
 * show up on all four days.
 *
 * @param metric which layer to flatten. Defaults to "change_in_temperature",
 *               the layer the simulation writes its signed ΔT into.
 */
export async function callHeatmapPointByDateHouston(
  metric: string = "change_in_temperature",
): Promise<HeatmapPointsByDate> {
  // Simulate network latency
  await new Promise((resolve) => setTimeout(resolve, 500));

  const byDate = BACKEND_ANCHOR.Houston[0] ?? {};

  return Object.fromEntries(
    Object.entries(byDate).map(([date, snapshots]) => [
      date,
      (snapshots.find((s) => s.metric === metric)?.points ?? []).map((p) =>
        structuredClone(p),
      ),
    ]),
  );
}