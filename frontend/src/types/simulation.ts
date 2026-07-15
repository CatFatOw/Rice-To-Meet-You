import type { HeatmapMetricValue, Polygon } from './heatmap';

/* ------------------------------------------------------------------ */
/* Geometry                                                            */
/* ------------------------------------------------------------------ */

/**
 * An intervention's *footprint* — the thing the user draws.
 * This is NOT the boundary of effect; that is computed by the kernel.
 */
export type Geometry =
  | { kind: 'point'; longitude: number; latitude: number }
  | { kind: 'line'; coordinates: [number, number][] }
  | { kind: 'polygon'; ring: Polygon };

export type GeometryKind = Geometry['kind'];

/* ------------------------------------------------------------------ */
/* Environment (drives the effect boundary)                            */
/* ------------------------------------------------------------------ */

/**
 * Ambient conditions at the moment being simulated. Kernels read from this
 * instead of hard-coding assumptions — e.g. evaporative misting is strongly
 * RH-limited, so its plume shrinks toward zero as `relativeHumidity_pct`
 * approaches saturation.
 */
export interface EnvContext {
  hourOfDay: number;            // 0–23
  airTemp_C: number;
  relativeHumidity_pct: number; // 0–100
  windSpeed_m_s: number;
  windDirection_deg: number;    // meteorological: direction wind blows FROM
  solarElevation_deg?: number;  // for shade geometry
}

/* ------------------------------------------------------------------ */
/* Intervention catalogue                                              */
/* ------------------------------------------------------------------ */

/**
 * Per-type parameters. These are things the person *deploying* the
 * intervention would actually know. Never put an effect radius here —
 * that is the model's job to compute.
 *
 * Units are encoded in field names on purpose. It is ugly and it prevents
 * an entire class of silent bugs.
 */
export interface InterventionParamMap {
  cool_roof: {
    albedo: number;              // 0–1, solar reflectance of the coating
    emissivity: number;          // 0–1, thermal emittance
    // area is DERIVED from geometry.ring — never a free parameter
  };
  misting_station: {
    nozzleCount: number;
    flowRate_L_per_min: number;  // per nozzle
    dropletDiameter_um: number;  // ~10–50 um; smaller = faster evaporation
    mountHeight_m: number;
  };
  street_tree: {
    canopyRadius_m: number;
    canopyHeight_m: number;
    lai: number;                 // leaf area index
    deciduous: boolean;
  };
  shade_structure: {
    transmissivity: number;      // 0–1, fraction of shortwave passing through
    height_m: number;
  };
  cool_pavement: {
    albedo: number;
    width_m: number;             // for line geometry
  };
}

export type InterventionType = keyof InterventionParamMap;
export type ParamsOf<T extends InterventionType> = InterventionParamMap[T];

/** Which footprint each intervention is allowed to have. */
export interface InterventionGeometryMap {
  cool_roof: 'polygon';
  misting_station: 'point';
  street_tree: 'point';
  shade_structure: 'polygon';
  cool_pavement: 'line';
}

export type GeometryOf<T extends InterventionType> = Extract<
  Geometry,
  { kind: InterventionGeometryMap[T] }
>;

/* ------------------------------------------------------------------ */
/* Scheduling                                                          */
/* ------------------------------------------------------------------ */

export interface HourWindow {
  startHour: number; // inclusive, 0–23
  endHour: number;   // exclusive, 1–24
}

/**
 * `always`   — passive interventions (cool roof, trees). No duty cycle.
 * `daily`    — fixed operating windows, possibly several per day.
 * `adaptive` — runs only when a metric crosses a threshold. This is how
 *              misting stations are actually operated, and it lets the
 *              intervention respond to the weather scenario rather than a clock.
 */
export type Schedule =
  | { mode: 'always' }
  | { mode: 'daily'; windows: HourWindow[] }
  | {
      mode: 'adaptive';
      triggerMetric: MetricKey;
      triggerAbove: number;
      windows?: HourWindow[]; // optional outer bound on when it may run at all
    };

/* ------------------------------------------------------------------ */
/* Placed object                                                       */
/* ------------------------------------------------------------------ */

interface PlacedObjectOf<T extends InterventionType> {
  id: string;
  type: T;
  geometry: GeometryOf<T>;
  param: ParamsOf<T>;
  schedule: Schedule;
  activeFrom?: string;  // ISO; when the intervention comes online
  activeUntil?: string; // ISO; supports removal / scenario comparison over time
  label?: string;
}

/**
 * Discriminated union: narrowing on `type` narrows `param` and `geometry` too,
 * so `{ type: 'cool_roof', param: { flowRate_L_per_min: 5 } }` will not compile.
 */
export type PlacedObject = {
  [T in InterventionType]: PlacedObjectOf<T>;
}[InterventionType];

/* ------------------------------------------------------------------ */
/* Kernels                                                             */
/* ------------------------------------------------------------------ */

export type MetricKey = string; // e.g. 'temperature' | 'utci' | 'mrt'

export interface KernelInput<T extends InterventionType = InterventionType> {
  /** Meters from the footprint (nearest edge for line/polygon, not centroid). */
  dist_m: number;
  /** Bearing from footprint to point, degrees clockwise from north. Needed for
   *  wind-skewed effects — a misting plume is not a circle. */
  bearing_deg: number;

  elapsedHours: number; // hours into the current operating window
  dutyHours: number;    // length of the current operating window

  baseValue: number;    // the point's current metric value (0–100)
  metrics: HeatmapMetricValue['individual_metrics'];
  metric: MetricKey;

  param: ParamsOf<T>;   // this intervention's own configuration
  env: EnvContext;      // ambient conditions
}

/** Dimensionless [0,1] multiplier. Magnitude and sign live in `intensity`. */
export type Kernel<T extends InterventionType = InterventionType> = (
  input: KernelInput<T>,
) => number;

/**
 * Signed magnitude, carrying units of the target metric (negative = cooling).
 * May be a function, because peak effect legitimately depends on the params and
 * the environment — a 6-nozzle station cools more than a 2-nozzle one, and
 * neither does much at 90% RH.
 */
export type Intensity<T extends InterventionType> =
  | number
  | ((ctx: { param: ParamsOf<T>; env: EnvContext; metric: MetricKey }) => number);

/** One intervention's effect on one metric. */
export interface MetricEffectSpec<T extends InterventionType = InterventionType> {
  intensity: Intensity<T>;
  kernels: Kernel<T>[]; // each returns [0,1]; multiplied together into a gate
  floor?: number;       // hard limit the effect cannot push the value past
  /** Optional cutoff for spatial indexing only — a performance hint, not physics.
   *  Set it well beyond where the kernel product is negligible. */
  cullRadius_m?: number;
}

/** intervention type -> metric -> spec. Kernels are typed to their own params. */
export type KernelModel = {
  [T in InterventionType]: Partial<Record<MetricKey, MetricEffectSpec<T>>>;
};

/* ------------------------------------------------------------------ */
/* Output                                                              */
/* ------------------------------------------------------------------ */

/**
 * The model produces a continuous field, not a boundary. A "boundary of effect"
 * is just a thresholded contour of this field — and the threshold is a policy
 * choice (what counts as meaningfully affected?), which is the one boundary-ish
 * thing the user *should* control.
 */
export interface EffectField {
  metric: MetricKey;
  delta: number[];        // per-cell change, same units as the metric
  contributions?: Record<string, number[]>; // optional, keyed by PlacedObject.id
}

export interface ContourOptions {
  metric: MetricKey;
  /** e.g. 0.5 °C, or 1 UTCI unit. User-facing, and honest about being a choice. */
  threshold: number;
}