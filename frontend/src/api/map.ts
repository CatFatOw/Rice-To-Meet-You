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

  cityName: string

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

// A single measured / interpolated reading at one coordinate.
// ---------------------------------------------------------------------------
// Source of truth: one physical reading per location. All three published
// metrics (temperature, visitor density, heat risk) are derived from these,
// so the layers stay consistent with each other.
// ---------------------------------------------------------------------------

function reading(
  name: string,
  lon: number,
  lat: number,
  temperatureF: number,
  visitorDensity: number,
  treeCanopyPct: number,
  imperviousSurfacePct: number,
): LocationReading {
  return {
    name,
    lon,
    lat,
    temperatureF,
    visitorDensity,
    treeCanopyPct,
    imperviousSurfacePct,
  };
}

const clamp = (n: number, lo = 0, hi = 100): number =>
  Math.max(lo, Math.min(hi, n));

// Map air temperature (°F) onto the shared 0–100 heatmap weight.
const TEMP_MIN_F = 84; // -> 0
const TEMP_MAX_F = 110; // -> 100
const temperatureToWeight = (tempF: number): number =>
  clamp(Math.round(((tempF - TEMP_MIN_F) / (TEMP_MAX_F - TEMP_MIN_F)) * 100));

// Heat risk = weighted blend of how hot it is and how many people are exposed.
// Hotter AND busier => higher risk.
const TEMP_RISK_WEIGHT = 0.6;
const VISITOR_RISK_WEIGHT = 0.4;
const riskFromWeights = (tempWeight: number, visitorDensity: number): number =>
  clamp(
    Math.round(
      TEMP_RISK_WEIGHT * tempWeight + VISITOR_RISK_WEIGHT * visitorDensity,
    ),
  );

// Rough physical sub-metrics derived from the reading, for display only.
function derivedSubMetrics(r: LocationReading) {
  const relativeHumidityPct = clamp(
    Math.round(72 - r.imperviousSurfacePct * 0.12 + r.treeCanopyPct * 0.1),
    30,
    95,
  );
  const heatIndexF = Math.round(
    r.temperatureF + Math.max(0, (relativeHumidityPct - 40) / 4),
  );
  const landSurfaceTempF = Math.round(
    r.temperatureF + r.imperviousSurfacePct * 0.28 - r.treeCanopyPct * 0.2,
  );
  const nighttimeTempF = Math.round(
    r.temperatureF - 15 + r.imperviousSurfacePct * 0.11,
  );
  return { relativeHumidityPct, heatIndexF, landSurfaceTempF, nighttimeTempF };
}

function visitorCategory(density: number): string {
  if (density >= 90) return "Match venue / fan zone";
  if (density >= 75) return "Major attraction";
  if (density >= 55) return "Busy district";
  if (density >= 35) return "Residential";
  return "Low activity";
}

function riskCategory(risk: number): string {
  if (risk >= 85) return "Extreme";
  if (risk >= 70) return "High";
  if (risk >= 55) return "Elevated";
  if (risk >= 40) return "Moderate";
  return "Low";
}

const estimatedFootfall = (density: number): string =>
  `${Math.round(density * 130).toLocaleString("en-US")} people/hr`;

// ---- Builders: one reading -> one anchor per metric ------------------------
function temperatureAnchor(r: LocationReading): HeatmapMetricValue {
  const d = derivedSubMetrics(r);
  return {
    value: r.temperatureF,
    location_name: r.name,
    location_coordinates: [r.lon, r.lat],
    individual_metrics: {
      temperatureF: `${r.temperatureF}°F`,
      heatIndexF: `${d.heatIndexF}°F`,
      relativeHumidityPct: `${d.relativeHumidityPct}%`,
      landSurfaceTempF: `${d.landSurfaceTempF}°F`,
      nighttimeTempF: `${d.nighttimeTempF}°F`,
      treeCanopyPct: `${r.treeCanopyPct}%`,
      imperviousSurfacePct: `${r.imperviousSurfacePct}%`,
    },
  };
}

function visitorDensityAnchor(r: LocationReading): HeatmapMetricValue {
  return {
    value: r.visitorDensity,
    location_name: r.name,
    location_coordinates: [r.lon, r.lat],
    individual_metrics: {
      visitorDensity: `${r.visitorDensity} / 100`,
      category: visitorCategory(r.visitorDensity),
      estimatedFootfall: estimatedFootfall(r.visitorDensity),
    },
  };
}

function heatRiskAnchor(r: LocationReading): HeatmapMetricValue {
  const tempWeight = temperatureToWeight(r.temperatureF);
  const risk = riskFromWeights(tempWeight, r.visitorDensity);
  return {
    value: risk,
    location_name: r.name,
    location_coordinates: [r.lon, r.lat],
    individual_metrics: {
      heatRiskScore: `${risk} / 100`,
      riskCategory: riskCategory(risk),
      temperatureContribution: `${Math.round(TEMP_RISK_WEIGHT * tempWeight)} / 100`,
      visitorContribution: `${Math.round(VISITOR_RISK_WEIGHT * r.visitorDensity)} / 100`,
      temperatureF: `${r.temperatureF}°F`,
      visitorDensity: `${r.visitorDensity} / 100`,
    },
  };
}

// ---------------------------------------------------------------------------
// The readings: landmark cluster around the venue + regional spread.
// reading(name, lon, lat, temperatureF, visitorDensity, treeCanopy%, impervious%)
// ---------------------------------------------------------------------------
const HOUSTON_READINGS: LocationReading[] = [
  // --- Match venue cluster (dense, for smooth interpolation near NRG) --------
  reading("NRG Stadium", -95.4109, 29.6847, 99, 100, 5, 90),
  reading("NRG Park Fan Fest", -95.412, 29.6855, 98, 95, 6, 88),
  reading("NRG Park Entrance Plaza", -95.4095, 29.6825, 99, 93, 4, 92),
  reading("NRG Park Parking (South)", -95.4145, 29.684, 101, 60, 2, 96),
  reading("NRG Park Parking (North)", -95.41, 29.687, 100, 58, 3, 94),

  // --- Texas Medical Center -------------------------------------------------
  reading("Texas Medical Center", -95.3992, 29.7067, 98, 70, 10, 85),
  reading("TMC South", -95.3962, 29.7082, 97, 68, 12, 82),
  reading("TMC West", -95.4015, 29.709, 99, 66, 8, 88),

  // --- Rice / parks / museums (leafier, big draws) --------------------------
  reading("Rice University", -95.4018, 29.7174, 92, 66, 35, 55),
  reading("Rice University West", -95.404, 29.716, 93, 60, 32, 58),
  reading("Museum District", -95.3893, 29.724, 93, 88, 25, 68),
  reading("Houston Zoo", -95.3925, 29.721, 91, 87, 40, 45),
  reading("Hermann Park", -95.387, 29.7154, 89, 84, 45, 35),

  // --- Downtown / urban core (busy + low canopy) ----------------------------
  reading("Downtown Houston", -95.3698, 29.7604, 98, 96, 8, 92),
  reading("Discovery Green", -95.3585, 29.7527, 93, 94, 30, 60),
  reading("George R. Brown Convention Center", -95.3577, 29.7517, 97, 93, 6, 90),
  reading("Avenida Houston / Toyota Center", -95.362, 29.756, 96, 92, 7, 88),
  reading("Midtown", -95.378, 29.742, 95, 86, 14, 80),
  reading("Montrose", -95.39, 29.743, 93, 85, 28, 62),
  reading("EaDo / Shell Energy Stadium", -95.351, 29.749, 96, 85, 10, 86),
  reading("The Heights", -95.398, 29.801, 93, 82, 30, 60),
  reading("Third Ward", -95.355, 29.735, 96, 55, 15, 78),
  reading("Buffalo Bayou Park", -95.39, 29.76, 89, 83, 42, 30),

  // --- West side / Galleria / affluent leafy --------------------------------
  reading("Galleria / Uptown", -95.4614, 29.7397, 96, 90, 12, 84),
  reading("River Oaks", -95.42, 29.755, 89, 68, 48, 40),
  reading("Memorial Park", -95.43, 29.765, 88, 72, 55, 22),
  reading("Memorial (residential)", -95.55, 29.77, 88, 45, 50, 32),
  reading("Bellaire", -95.46, 29.705, 91, 50, 30, 58),
  reading("Meyerland", -95.46, 29.68, 92, 48, 28, 60),
  reading("West University Place", -95.4315, 29.718, 90, 52, 38, 50),
  reading("Gulfton", -95.48, 29.71, 98, 45, 8, 88),
  reading("Sharpstown", -95.53, 29.7, 96, 42, 12, 82),
  reading("Alief", -95.58, 29.7, 95, 40, 14, 80),
  reading("Energy Corridor", -95.6349, 29.783, 94, 60, 20, 66),

  // --- East side industrial (very hot, few visitors) ------------------------
  reading("Houston Ship Channel", -95.28, 29.73, 106, 20, 2, 95),
  reading("Galena Park Refineries", -95.23, 29.74, 107, 18, 1, 97),
  reading("Pasadena Industrial", -95.21, 29.69, 105, 16, 2, 96),
  reading("Baytown Industrial", -94.98, 29.74, 104, 15, 3, 94),
  reading("Deer Park", -95.13, 29.7, 102, 30, 6, 88),
  reading("Channelview", -95.11, 29.78, 101, 28, 8, 85),
  reading("Fifth Ward", -95.33, 29.78, 98, 45, 10, 84),
  reading("Denver Harbor", -95.3, 29.78, 99, 40, 9, 85),
  reading("Sunnyside", -95.36, 29.66, 100, 38, 12, 82),

  // --- Airports -------------------------------------------------------------
  reading("George Bush Intercontinental (IAH)", -95.3414, 29.9902, 97, 86, 8, 88),
  reading("Hobby Airport", -95.2789, 29.6454, 97, 80, 7, 89),

  // --- Suburban rings -------------------------------------------------------
  reading("Katy", -95.82, 29.79, 93, 58, 20, 62),
  reading("Sugar Land", -95.62, 29.62, 92, 68, 25, 58),
  reading("Missouri City", -95.54, 29.62, 93, 40, 22, 60),
  reading("Pearland", -95.29, 29.56, 94, 46, 18, 64),
  reading("League City", -95.09, 29.51, 92, 44, 22, 58),
  reading("Spring", -95.42, 30.08, 93, 41, 25, 58),
  reading("Cypress", -95.7, 29.97, 93, 39, 22, 56),
  reading("The Woodlands (forested)", -95.45, 30.16, 89, 66, 55, 30),
  reading("Kingwood (forested)", -95.18, 30.05, 88, 40, 58, 28),

  // --- Clear Lake / NASA ----------------------------------------------------
  reading("Space Center Houston", -95.092, 29.552, 90, 84, 20, 60),
  reading("Clear Lake / NASA", -95.09, 29.56, 90, 64, 28, 50),

  // --- Water / reservoirs (coolest, sparse visitors) ------------------------
  reading("Addicks / Barker Reservoir", -95.63, 29.77, 86, 22, 45, 12),
  reading("George Bush Park", -95.68, 29.72, 86, 30, 50, 10),
  reading("Lake Houston", -95.14, 29.92, 85, 18, 30, 8),
  reading("Galveston Bay shoreline", -94.9, 29.53, 87, 24, 10, 15),
];

// Three published metric layers, all derived from the same readings.
const TEMPERATURE_ANCHORS: HeatmapMetricValue[] =
  HOUSTON_READINGS.map(temperatureAnchor);
const VISITOR_DENSITY_ANCHORS: HeatmapMetricValue[] =
  HOUSTON_READINGS.map(visitorDensityAnchor);
const HEAT_RISK_ANCHORS: HeatmapMetricValue[] =
  HOUSTON_READINGS.map(heatRiskAnchor);

// A day's worth of layers (same anchors reused across the sample dates).
const daySnapshots = (): HeatmapMetricSnapshot[] => [
  { metric: "temperature", points: TEMPERATURE_ANCHORS },
  { metric: "visitor_density", points: VISITOR_DENSITY_ANCHORS },
  { metric: "heat_risk_score", points: HEAT_RISK_ANCHORS },
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

// Mirrors HeatmapMetricValue, but carries the POI polygon (poi_coordinates)
// instead of a single point, plus the fill color used to render the area.

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
    pointInPolygon(r.lon, r.lat, polygon),
  );
  if (inside.length > 0) return inside;

  const [cx, cy] = polygonCentroid(polygon);
  let nearest = HOUSTON_READINGS[0];
  let best = Infinity;
  for (const r of HOUSTON_READINGS) {
    const d = (r.lon - cx) ** 2 + (r.lat - cy) ** 2;
    if (d < best) {
      best = d;
      nearest = r;
    }
  }
  return [nearest];
}

// Mean of the readings, positioned at the polygon centroid. Building a metric
// anchor from this yields the POI aggregate (the weight functions are linear,
// so the built value equals the mean of the individual point values).
function meanReading(
  readings: LocationReading[],
  name: string,
  at: [number, number],
): LocationReading {
  const n = readings.length;
  const acc = readings.reduce(
    (a, r) => {
      a.temperatureF += r.temperatureF;
      a.visitorDensity += r.visitorDensity;
      a.treeCanopyPct += r.treeCanopyPct;
      a.imperviousSurfacePct += r.imperviousSurfacePct;
      return a;
    },
    { temperatureF: 0, visitorDensity: 0, treeCanopyPct: 0, imperviousSurfacePct: 0 },
  );
  return reading(
    name,
    at[0],
    at[1],
    acc.temperatureF / n,
    acc.visitorDensity / n,
    acc.treeCanopyPct / n,
    acc.imperviousSurfacePct / n,
  );
}

// metric name -> the same builder used for point anchors.
const POI_METRIC_BUILDERS: Record<
  string,
  (r: LocationReading) => HeatmapMetricValue
> = {
  temperature: temperatureAnchor,
  visitor_density: visitorDensityAnchor,
  heat_risk_score: heatRiskAnchor,
};

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
export async function callHeatmapPOIAnchors(): Promise<HeatmapMetricPOIByCity> {
  await new Promise((resolve) => setTimeout(resolve, 500));
  return BACKEND_POI_ANCHOR;
}