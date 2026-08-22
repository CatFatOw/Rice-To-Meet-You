export type Polygon = [number, number][];

export interface CityPOIArea {

  id: string;

  name: string;

  color: [number, number, number, number];

  polygon: Polygon;

  // Optional fields returned by the backend POI/simulation routes. They are
  // absent on the built-in demo areas, so every one of them is optional.
  poi_id?: number;
  cityName?: string;
  stateName?: string | null;
  category?: string | null;
  properties?: {
    statistics?: Record<string, string | number | boolean | null>;
    [key: string]: unknown;
  } | null;
  polygon_geometry_id?: number;
  impacted_count?: number;
  impacted_grid_cell_ids?: number[];
}

export type CityPOIAreaMap = Record<string, CityPOIArea[]>;

// A single measured / interpolated reading at one coordinate.
export interface HeatmapMetricValue {
  value: number; // 0–100 weight used for heatmap coloring
  location_coordinates: [number, number]; // [lon, lat]
  // Set when the reading was sampled off the interpolated raster surface
  // rather than read from a measured point.
  location_name?: string;
  is_interpolated?: boolean;
  // Open bag of human-readable sub-metrics. Any key is allowed; every value is
  // a string so it can carry its own unit (e.g. "97°F", "62%", "88 / 100").
  individual_metrics?: Record<string, string>;
}

// ---------------------------------------------------------------------------
// Kriged surfaces (backend POST /grid_interpolation/surface)
// ---------------------------------------------------------------------------

/** A city's interpolation rectangle, as a closed GeoJSON Polygon ring. */
export interface BoundaryGeometry {
  type: 'Polygon';
  coordinates: number[][][];
}

/**
 * A continuous value field produced by ordinary kriging, as a regular lattice
 * pinned to geographic bounds. values[row][col] holds the interpolated value at
 * that cell's centroid; row 0 is the southernmost row.
 *
 * Values are in the metric's own units (degrees C), not a normalized score.
 *
 * A surface is scoped to one city: `bounds` is that city's rectangle, and the
 * lattice spans exactly that rectangle, so the drawn surface stops at the city
 * edge instead of bleeding across the country.
 */
export interface MetricSurface {
  metric_key: string;
  bounds: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
  rows: number;
  cols: number;
  // values[row][col]; row 0 is the southernmost row. Every cell carries a
  // value - the lattice and the city rectangle are the same shape.
  values: number[][];
  min: number;
  max: number;
  variance_mean: number;
  /** Readings inside the city rectangle that fed this surface's fit. */
  source_count: number;
  /** Resolved city name, null when the request carried no city. */
  city: string | null;
  /** The city rectangle as GeoJSON, for stroking the edge. Null when unscoped. */
  boundary: BoundaryGeometry | null;
  interpolation_method: string;
}

// One metric's readings for a single day.
export interface HeatmapMetricSnapshot {
  metric: string; // "temperature" | "visitor_density" | "heat_risk_score"
  points: HeatmapMetricValue[];
}

// Date -> all metric layers available for that day.
export interface HeatmapMetricPoint {
  [date: string]: HeatmapMetricSnapshot[];
}

// City name -> array of its date-keyed metric layers.
export interface HeatmapMetricPointByCity {
  [city: string]: HeatmapMetricPoint[];
}

// Mirrors HeatmapMetricValue, but carries the POI polygon (poi_coordinates)
// instead of a single point, plus the fill color used to render the area.
export interface HeatmapMetricPOIValue {
  value: number; // 0–100 aggregated weight for the POI
  location_name: string; // POI name, e.g. "NRG Stadium"
  poi_coordinates: Polygon; // the POI outline ([lon, lat] ring)
  color: [number, number, number, number];
  individual_metrics?: Record<string, string>;
}

// One metric's POI readings for a single day.
export interface HeatmapMetricPOISnapshot {
  metric: string;
  points: HeatmapMetricPOIValue[];
}

export interface HeatmapMetricPOIPoint {
  [date: string]: HeatmapMetricPOISnapshot[];
}

export interface HeatmapMetricPOIByCity {
  [city: string]: HeatmapMetricPOIPoint[];
}

export interface LocationReading {
  id: number;
  date: string;         // ISO date, e.g. "2026-07-05"
  latitude: number;
  longitude: number;

  // --- HeatWeatherPoint fields (set when metric_source_kind === "heat_weather_point") ---
  avg_temperature_c?: number | null;
  relative_humidity?: number | null;
  wind_speed_knots?: number | null;
  uhi?: number | null;
  source?: "measured" | "interpolated" | null;
  distance_to_nearest_station_km?: number | null;
  passed_threshold?: boolean | null;

  // --- VisitorPOI fields (set when metric_source_kind === "visitor_poi") ---
  market?: string | null;
  source_market?: string | null;
  fsq_place_id?: string | null;
  placekey?: string | null;
  name?: string | null;
  category?: string | null;
  visitor_count?: number | null;
  visitor_density?: number | null;
  visitor_count_source?: string | null;
  source_period_start?: string | null;  // ISO datetime
  source_period_end?: string | null;    // ISO datetime
}



// This is used for simulation api call


export interface HeatmapPointsByDate {
  [date: string]: HeatmapMetricValue[];
}


/** [longitude, latitude] — GeoJSON order, note it's lng first */
export type Coordinates = [number, number];

/** All values arrive pre-formatted as display strings, e.g. "91.5%", "12.2 mph" */
export interface IndividualMetrics {
  average_dew_point_f: string;
  average_relative_humidity_pct: string;
  average_sea_level_pressure_mbar: string;
  average_temperature_c: string;
  average_visibility_km: string;
  average_wind_speed_knots: string;
  cooling_degree_days_c: string;
  heating_degree_days_c: string;
  maximum_temperature_c: string;
  minimum_temperature_c: string;
  raw_precipitation_hundredths_mm: string;
  station_count: string;
  temperature_range_c: string;
  dew_point_depression_c: string;
  wet_bulb_temperature_c: string;
  heat_stress_flag: string;
  cold_stress_flag: string;
  wind_speed_mps: string;
  high_wind_flag: string;
  precipitation_mm_clean: string;
  precipitation_3d_sum_mm: string;
  market_relative_heavy_rain_flag: string;
  low_visibility_flag: string;
  planning_weather_completeness_pct: string;
  major_event_weather_readiness_score: string;
  major_event_weather_readiness_band: string;
  uhi: string;
  [key: string]: string; // tolerate new metrics without a type change
}

export interface HeatmapPoint {
  location_coordinates: Coordinates;
  individual_metrics: IndividualMetrics;
}

/** Keyed by date, e.g. { "2020-01-01": [...] } */
export type HeatmapResponse = Record<string, HeatmapPoint[]>;
