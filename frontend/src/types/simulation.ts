import type { HeatmapMetricValue } from './heatmap';
// import type { Polygon } from './heatmap';

export interface KernelInput {
  dist: number;          // meters from tool to point (haversine)
  elapsedHours: number;  // hours into the operating window (intraday, not lifetime)
  activeHours: number;   // tool's daily operating duration
  baseValue: number;     // the point's current metric value (0–100)
  metrics: HeatmapMetricValue["individual_metrics"]; // unit-tagged sub-metrics
  metric: string;        // the metric being computed, e.g. "temperature"
}

// A kernel returns a dimensionless [0,1] multiplier. All magnitude/sign lives
// in `intensity`, so the product of kernels only ever scales the effect down.
export type Kernel = (input: KernelInput) => number;

// One tool's effect on one metric.
export interface MetricEffectSpec {
  intensity: number;   // signed; carries units (negative = cooling, etc.)
  kernels: Kernel[];   // each returns [0,1]; multiplied together into a gate
  floor?: number;      // optional hard limit the effect cannot push past
}

// toolType -> metric -> spec.
export type KernelModel = Record<string, Record<string, MetricEffectSpec>>;

// An object dropped on the map from the toolbox (simulation-extended version).
export interface PlacedObject {
  id: string;
  type: string;              // e.g. "misting_station" — must match a KernelModel key
  longitude: number;
  latitude: number;
  param: Record<string, Any>;
  placedAt?: string;         // ISO; when the tool became active
  activeHours?: number;      // daily operating duration (hours)
  startHour?: number;        // hour of day the tool switches on (0–23), default 8
}
