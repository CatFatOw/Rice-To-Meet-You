export type Polygon = [number, number][];

export interface CityPOIArea {

  id: string;

  name: string;

  color: [number, number, number, number];

  polygon: Polygon;

}

export type CityPOIAreaMap = Record<string, CityPOIArea[]>;

// A single measured / interpolated reading at one coordinate.
export interface HeatmapMetricValue {
  value: number; // 0–100 weight used for heatmap coloring
  location_name: string;
  location_coordinates: [number, number]; // [lon, lat]
  // Open bag of human-readable sub-metrics. Any key is allowed; every value is
  // a string so it can carry its own unit (e.g. "97°F", "62%", "88 / 100").
  individual_metrics?: Record<string, string>;
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
