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

function toNumber(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function getToolAnchor(tool: PlacedObject): [number, number] {
  const g = tool.geometry;
  if (g.kind === 'point') return [g.longitude, g.latitude];
  if (g.kind === 'line') {
    const first = g.coordinates[0];
    return first ?? [0, 0];
  }

  // Polygon: quick centroid by average vertex position.
  if (!g.ring.length) return [0, 0];
  const [sumLon, sumLat] = g.ring.reduce(
    ([lon, lat], [x, y]) => [lon + x, lat + y],
    [0, 0],
  );
  return [sumLon / g.ring.length, sumLat / g.ring.length];
}

function getScheduleWindow(tool: PlacedObject): {
  startHour: number;
  dutyHours: number;
} {
  const schedule = tool.schedule;
  if (schedule.mode === 'daily' && schedule.windows.length > 0) {
    const window = schedule.windows[0];
    const dutyHours = Math.max(1, window.endHour - window.startHour);
    return { startHour: window.startHour, dutyHours };
  }

  if (schedule.mode === 'adaptive' && schedule.windows && schedule.windows.length > 0) {
    const window = schedule.windows[0];
    const dutyHours = Math.max(1, window.endHour - window.startHour);
    return { startHour: window.startHour, dutyHours };
  }

  return { startHour: DEFAULT_START_HOUR, dutyHours: DEFAULT_ACTIVE_HOURS };
}

function bearingDegrees(
  lon1: number,
  lat1: number,
  lon2: number,
  lat2: number,
): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const toDeg = (rad: number) => (rad * 180) / Math.PI;

  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const lambda1 = toRad(lon1);
  const lambda2 = toRad(lon2);

  const y = Math.sin(lambda2 - lambda1) * Math.cos(phi2);
  const x =
    Math.cos(phi1) * Math.sin(phi2) -
    Math.sin(phi1) * Math.cos(phi2) * Math.cos(lambda2 - lambda1);
  return (toDeg(Math.atan2(y, x)) + 360) % 360;
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

    const { startHour, dutyHours } = getScheduleWindow(tool);
    // Intraday hours into the operating window (not lifetime days). Before the
    // tool switches on this is <= 0, and the temporal kernel handles that.
    const elapsedHours = evalHour - startHour;

    const [toolLon, toolLat] = getToolAnchor(tool);
    const [pointLon, pointLat] = p.location_coordinates;

    const dist = haversine(toolLon, toolLat, pointLon, pointLat);
    const bearing = bearingDegrees(toolLon, toolLat, pointLon, pointLat);
    const env = {
      hourOfDay: evalHour,
      airTemp_C: toNumber(p.individual_metrics?.average_temperature_c, p.value),
      relativeHumidity_pct: toNumber(
        p.individual_metrics?.average_relative_humidity_pct,
        50,
      ),
      windSpeed_m_s: toNumber(p.individual_metrics?.wind_speed_mps, 1),
      windDirection_deg: 0,
    };

    const gate = spec.kernels.reduce(
      (acc, k) =>
        acc *
        k({
          dist_m: dist,
          bearing_deg: bearing,
          elapsedHours,
          dutyHours,
          baseValue: p.value,
          metrics: p.individual_metrics,
          metric,
          param: tool.param as never,
          env,
        }),
      1,
    );

    const intensity =
      typeof spec.intensity === 'function'
        ? spec.intensity({ param: tool.param as never, env, metric })
        : spec.intensity;

    totalEffect += intensity * gate; // sum across tools

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


