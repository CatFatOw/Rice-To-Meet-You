type Polygon = [number, number][];

export interface CityPOIArea {
  id: string;
  name: string;
  cityName: string;
  color: [number, number, number, number];
  polygon: Polygon;
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



export interface HeatmapMetricPoint {
  metric: string;
  value: number; // heat risk score (0–100); used as the point's weight
  location_name: string; // the destination this point belongs to
  location_coordinates: [number, number]; // [longitude, latitude]
}
 
export type HeatmapMetricsPointResponse = Record<string, HeatmapMetricPoint[]>;
 
export async function callHeatmapMetricsPoints(): Promise<HeatmapMetricsPointResponse> {
  await new Promise((resolve) => setTimeout(resolve, 500));
 
  return {
    Houston: [
      // Texas Medical Center
      { metric: 'heat_risk_score', value: 91, location_name: 'Texas Medical Center', location_coordinates: [-95.3992, 29.7067] },
      { metric: 'heat_risk_score', value: 88, location_name: 'Texas Medical Center', location_coordinates: [-95.3962, 29.7082] },
      { metric: 'heat_risk_score', value: 93, location_name: 'Texas Medical Center', location_coordinates: [-95.4015, 29.7090] },
      { metric: 'heat_risk_score', value: 90, location_name: 'Texas Medical Center', location_coordinates: [-95.3975, 29.7045] },
      { metric: 'heat_risk_score', value: 86, location_name: 'Texas Medical Center', location_coordinates: [-95.4020, 29.7050] },
 
      // NRG Stadium
      { metric: 'heat_risk_score', value: 85, location_name: 'NRG Stadium', location_coordinates: [-95.4109, 29.6847] },
      { metric: 'heat_risk_score', value: 82, location_name: 'NRG Stadium', location_coordinates: [-95.4085, 29.6860] },
      { metric: 'heat_risk_score', value: 88, location_name: 'NRG Stadium', location_coordinates: [-95.4130, 29.6835] },
      { metric: 'heat_risk_score', value: 84, location_name: 'NRG Stadium', location_coordinates: [-95.4095, 29.6825] },
      { metric: 'heat_risk_score', value: 80, location_name: 'NRG Stadium', location_coordinates: [-95.4125, 29.6865] },
 
      // NRG Park Parking Area
      { metric: 'heat_risk_score', value: 82, location_name: 'NRG Park Parking Area', location_coordinates: [-95.4120, 29.6855] },
      { metric: 'heat_risk_score', value: 79, location_name: 'NRG Park Parking Area', location_coordinates: [-95.4145, 29.6840] },
      { metric: 'heat_risk_score', value: 84, location_name: 'NRG Park Parking Area', location_coordinates: [-95.4100, 29.6870] },
      { metric: 'heat_risk_score', value: 80, location_name: 'NRG Park Parking Area', location_coordinates: [-95.4160, 29.6865] },
      { metric: 'heat_risk_score', value: 83, location_name: 'NRG Park Parking Area', location_coordinates: [-95.4095, 29.6840] },
 
      // Museum District
      { metric: 'heat_risk_score', value: 74, location_name: 'Museum District', location_coordinates: [-95.3893, 29.7240] },
      { metric: 'heat_risk_score', value: 71, location_name: 'Museum District', location_coordinates: [-95.3870, 29.7255] },
      { metric: 'heat_risk_score', value: 77, location_name: 'Museum District', location_coordinates: [-95.3915, 29.7228] },
      { metric: 'heat_risk_score', value: 72, location_name: 'Museum District', location_coordinates: [-95.3880, 29.7218] },
      { metric: 'heat_risk_score', value: 76, location_name: 'Museum District', location_coordinates: [-95.3910, 29.7258] },
 
      // Rice University
      { metric: 'heat_risk_score', value: 68, location_name: 'Rice University', location_coordinates: [-95.4018, 29.7174] },
      { metric: 'heat_risk_score', value: 65, location_name: 'Rice University', location_coordinates: [-95.3995, 29.7190] },
      { metric: 'heat_risk_score', value: 71, location_name: 'Rice University', location_coordinates: [-95.4040, 29.7160] },
      { metric: 'heat_risk_score', value: 67, location_name: 'Rice University', location_coordinates: [-95.4005, 29.7155] },
      { metric: 'heat_risk_score', value: 70, location_name: 'Rice University', location_coordinates: [-95.4035, 29.7188] },
 
      // West University Place
      { metric: 'heat_risk_score', value: 63, location_name: 'West University Place', location_coordinates: [-95.4315, 29.7180] },
      { metric: 'heat_risk_score', value: 60, location_name: 'West University Place', location_coordinates: [-95.4290, 29.7195] },
      { metric: 'heat_risk_score', value: 66, location_name: 'West University Place', location_coordinates: [-95.4340, 29.7168] },
      { metric: 'heat_risk_score', value: 62, location_name: 'West University Place', location_coordinates: [-95.4300, 29.7162] },
      { metric: 'heat_risk_score', value: 64, location_name: 'West University Place', location_coordinates: [-95.4335, 29.7195] },
 
      // Hermann Park
      { metric: 'heat_risk_score', value: 57, location_name: 'Hermann Park', location_coordinates: [-95.3870, 29.7154] },
      { metric: 'heat_risk_score', value: 54, location_name: 'Hermann Park', location_coordinates: [-95.3848, 29.7168] },
      { metric: 'heat_risk_score', value: 60, location_name: 'Hermann Park', location_coordinates: [-95.3892, 29.7142] },
      { metric: 'heat_risk_score', value: 55, location_name: 'Hermann Park', location_coordinates: [-95.3858, 29.7138] },
      { metric: 'heat_risk_score', value: 58, location_name: 'Hermann Park', location_coordinates: [-95.3888, 29.7170] },
    ],
  };
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

export type MetricType = 'temperature'; // widen later: | 'humidity' | 'precipitation'

export interface CoordinateValue {
  /** [longitude, latitude] — matches the map's coordinate ordering */
  coordinate: [number, number];
  /** metric value at this coordinate (for temperature: °F) */
  value: number;
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

// Smooth temperature field (°F) as a function of position.
function temperatureAt(lon: number, lat: number): number {
  const base = 90;

  // Urban heat island: a warm bump peaking over downtown Houston.
  const heatCenter: [number, number] = [-95.37, 29.75];
  const dLon = lon - heatCenter[0];
  const dLat = lat - heatCenter[1];
  const urbanDistSq = dLon * dLon + dLat * dLat;
  const urbanBump = 9 * Math.exp(-urbanDistSq / (2 * 0.18 * 0.18));

  // Coastal cooling: temperatures ease off toward Galveston Bay (SE).
  const coast: [number, number] = [-94.95, 29.45];
  const cLon = lon - coast[0];
  const cLat = lat - coast[1];
  const coastDistSq = cLon * cLon + cLat * cLat;
  const coastalCooling = 9 * Math.exp(-coastDistSq / (2 * 0.45 * 0.45));

  // Gentle deterministic ripple so the field has some local texture.
  const ripple = Math.sin(lon * 18) * Math.cos(lat * 18) * 0.8;

  return Math.round(base + urbanBump - coastalCooling + ripple);
}

/**
 * Mock backend call. Simulates fetching a dense coordinate-level metric field
 * covering the entire Houston metro area — one value per lattice point.
 * Returns a list of metrics; each metric has coordinate -> value points.
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

      points.push({
        coordinate: [roundedLon, roundedLat],
        value: temperatureAt(roundedLon, roundedLat),
      });
    }
  }

  const data: MetricCoordinateData[] = [
    {
      metric: 'temperature',
      points,
    },
  ];

  // Simulate network latency.
  await new Promise((resolve) => setTimeout(resolve, 300));

  return data;
}


