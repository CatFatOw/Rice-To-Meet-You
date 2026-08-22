import type { HeatmapMetricValue, HeatmapMetricPoint } from "../types/heatmap";
import type { KernelInput, Kernel, MetricEffectSpec, KernelModel, PlacedObject } from "../types/simulation";
export type { KernelInput, Kernel, MetricEffectSpec, KernelModel, PlacedObject };

// Default daily operating window when a tool omits it.
const DEFAULT_ACTIVE_HOURS = 12;
const DEFAULT_START_HOUR = 8;

// The hour of day at which each simulated day is evaluated. The sim steps
// day-by-day, so we sample the field at one representative time (solar-ish
// noon). Lift into a parameter if you later want a diurnal sweep.
const DEFAULT_EVAL_HOUR = 12;

// ---------------------------------------------------------------------------
// Date helpers
//
// Dates flow through the app as "YYYY-MM-DD" strings (see BACKEND_ANCHOR keys).
// We treat each as a calendar day in UTC to avoid two classic bugs:
//   1. `new Date("2026-07-05")` parses as UTC midnight, but local-time methods
//      (getDate) can then report the previous day for users west of UTC.
//   2. Adding 24*60*60*1000 ms across a DST boundary can skip or repeat a day.
// Working in UTC and stepping by UTC date fields sidesteps both.
// ---------------------------------------------------------------------------

// Parse "YYYY-MM-DD" into a UTC Date at midnight. Returns null on bad input.
function parseISODate(iso: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return null;
  const [, y, mo, d] = m;
  const date = new Date(Date.UTC(+y, +mo - 1, +d));
  // Guard against overflow like "2026-02-30" silently rolling to March.
  if (
    date.getUTCFullYear() !== +y ||
    date.getUTCMonth() !== +mo - 1 ||
    date.getUTCDate() !== +d
  ) {
    return null;
  }
  return date;
}

// Format a UTC Date back to "YYYY-MM-DD".
function formatISODate(date: Date): string {
  const y = date.getUTCFullYear();
  const mo = String(date.getUTCMonth() + 1).padStart(2, "0");
  const d = String(date.getUTCDate()).padStart(2, "0");
  return `${y}-${mo}-${d}`;
}

// Whole calendar days from `fromDate` to `date` (date − fromDate).
// Same day -> 0; the day after -> 1; a day before -> -1.
export function daysBetween(fromDate: string, date: string): number {
  const a = parseISODate(fromDate);
  const b = parseISODate(date);
  if (!a || !b) {
    throw new Error(`daysBetween: invalid date(s) "${fromDate}", "${date}"`);
  }
  const MS_PER_DAY = 24 * 60 * 60 * 1000;
  // Both are UTC midnights, so the difference is an exact multiple of a day;
  // round to shrug off any leap-second / float noise.
  return Math.round((b.getTime() - a.getTime()) / MS_PER_DAY);
}

// Inclusive list of "YYYY-MM-DD" strings from fromDate to toDate.
// eachDay("2026-07-05", "2026-07-08") ->
//   ["2026-07-05", "2026-07-06", "2026-07-07", "2026-07-08"]
// If toDate < fromDate, returns [] (rather than looping forever).
export function eachDay(fromDate: string, toDate: string): string[] {
  const start = parseISODate(fromDate);
  const end = parseISODate(toDate);
  if (!start || !end) {
    throw new Error(`eachDay: invalid date(s) "${fromDate}", "${toDate}"`);
  }

  const days: string[] = [];
  const cursor = new Date(start.getTime());
  while (cursor.getTime() <= end.getTime()) {
    days.push(formatISODate(cursor));
    cursor.setUTCDate(cursor.getUTCDate() + 1); // DST-safe day step
  }
  return days;
}

// ---------------------------------------------------------------------------
// Geo helper
// ---------------------------------------------------------------------------

// Great-circle distance between two [lon, lat] points, in METERS.
// Signature is lon-first to match `...p.location_coordinates` ([lon, lat]).
export function haversine(
  lon1: number,
  lat1: number,
  lon2: number,
  lat2: number,
): number {
  const R = 6_371_000; // Earth mean radius, meters
  const toRad = (deg: number) => (deg * Math.PI) / 180;

  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;

  return 2 * R * Math.asin(Math.sqrt(a));
}

// Constrain n to the inclusive range [lo, hi]. Defaults to the 0–100 scale
// that heatmap metric values live on.
export function clamp(n: number, lo = 0, hi = 100): number {
  return Math.max(lo, Math.min(hi, n));
}

// ---------------------------------------------------------------------------
// Simulation
// ---------------------------------------------------------------------------

// Apply every tool's effect on one metric to a single point.
// - Multiplicative across kernels within a tool (each gates the effect down).
// - Additive across tools (two nearby stations stack).
// - Clamped to [0,100], then floored to the strongest applicable floor.
function getResultMetric(
  p: HeatmapMetricValue,
  metric: string,
  tools: PlacedObject[],
  evalHour: number,
  model: KernelModel,
): HeatmapMetricValue {
  let totalEffect = 0;
  let activeFloor: number | null = null;

  for (const tool of tools) {
    const spec = model[tool.type]?.[metric];
    if (!spec) continue; // this tool doesn't touch this metric

    const activeHours = tool.activeHours ?? DEFAULT_ACTIVE_HOURS;
    const startHour = tool.startHour ?? DEFAULT_START_HOUR;
    // Intraday hours into the operating window (not lifetime days). Before the
    // tool switches on this is <= 0, and the temporal kernel handles that.
    const elapsedHours = evalHour - startHour;

    const dist = haversine(
      tool.longitude,
      tool.latitude,
      ...p.location_coordinates,
    );

    const gate = spec.kernels.reduce(
      (acc, k) =>
        acc *
        k({
          dist,
          elapsedHours,
          activeHours,
          baseValue: p.value,
          metrics: p.individual_metrics,
          metric,
        }),
      1,
    );

    totalEffect += spec.intensity * gate; // sum across tools

    // Track the most restrictive floor among tools that define one.
    if (spec.floor !== undefined) {
      activeFloor =
        activeFloor === null ? spec.floor : Math.max(activeFloor, spec.floor);
    }
  }

  if (totalEffect === 0) return p; // untouched by every tool

  let nextValue = clamp(Math.round(p.value + totalEffect), 0, 100);
  // Floor is a physical wall (e.g. wet-bulb): cooling can't cross it. Only
  // apply when the effect is pushing the value down toward/through it.
  if (activeFloor !== null && nextValue < activeFloor && p.value >= activeFloor) {
    nextValue = activeFloor;
  }

  return { ...p, value: nextValue };
}

// Run the intervention simulation for one city over [fromDate, toDate].
// Recomputes each day from the immutable baseline (no accumulation), so
// re-running or scrubbing dates is deterministic.
export function runSimulation(
  baselineByCity: Record<string, HeatmapMetricPoint>, // date-keyed anchors
  city: string,
  tools: PlacedObject[],
  fromDate: string,
  toDate: string,
  model: KernelModel,
  evalHour: number = DEFAULT_EVAL_HOUR,
): HeatmapMetricPoint {
  const cityBaseline = baselineByCity[city];
  if (!cityBaseline) {
    throw new Error(`runSimulation: no baseline for city "${city}"`);
  }

  const out: HeatmapMetricPoint = {};

  for (const date of eachDay(fromDate, toDate)) {
    const baselineDay = cityBaseline[date];
    // No anchors for this date: reuse the fromDate baseline but only because
    // anchors are held constant across the sample window. If that assumption
    // ever changes, this is the line to revisit.
    const sourceDay = baselineDay ?? cityBaseline[fromDate];
    if (!sourceDay) {
      throw new Error(
        `runSimulation: no baseline for "${date}" or fallback "${fromDate}"`,
      );
    }

    out[date] = sourceDay.map((snap) => ({
      metric: snap.metric,
      points: snap.points.map((p) =>
        getResultMetric(p, snap.metric, tools, evalHour, model),
      ),
    }));
  }

  return out;
}



// heatmapMetricSimulation.ts
//
// Mock cooling simulation that takes a list of HeatmapMetricPoint and produces
// one cooled list per day, keyed by date — ready to feed into
// useSimulationRunner's runTimeline() as `framesByDate`.
//
// Here TFrame = HeatmapMetricPoint[] (each frame is the whole cooled list).
//
// Cooling schedule (each day compounds on the PREVIOUS day's values):
//   day 1: -2%   day 2: -4%   day 3: -6%   day 4: -8%   ...
//   i.e. the per-day decrease grows by 2 percentage points each day.

// NOTE: assumed shape — swap in your real type if it differs. The only field
// the simulation touches is `temperature`.
export interface HeatmapMetricPoint {
  x: number;
  y: number;
  temperature: number;
}

