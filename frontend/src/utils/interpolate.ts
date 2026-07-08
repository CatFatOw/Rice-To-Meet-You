import type {
  HeatmapMetricPointByCity,
  HeatmapMetricSnapshot,
  HeatmapMetricValue,
} from '../api/map';

// ---------------------------------------------------------------------------
// Interpolation config (client-side "how to interpolate" knobs).
// ---------------------------------------------------------------------------
const INTERP_CENTER: [number, number] = [-95.37, 29.76];
const INTERP_HALF_SPAN_LON = 0.55; // ≈ 53 km E–W each way
const INTERP_HALF_SPAN_LAT = 0.45; // ≈ 50 km N–S each way
const INTERP_STEP = 0.01; // ≈ 1.1 km lattice spacing
const HEAT_IDW_POWER = 3.2;
const VISITOR_IDW_POWER = 2.6;
const MIN_SCORE = 0;
const MAX_SCORE = 100;

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

function buildIndividualMetrics(
  point: HeatmapMetricValue,
): HeatmapMetricValue['individual_metrics'] {
  const [lon, lat] = point.location_coordinates;
  const noise = Math.sin(lon * 17.3) * Math.cos(lat * 14.1);

  const temperatureF = Math.round(clamp(74 + point.value * 0.28 + noise * 1.8, 70, 115));
  const relativeHumidityPct = Math.round(
    clamp(86 - point.value * 0.35 + Math.sin((lon + lat) * 12) * 2.2, 30, 95),
  );
  const heatIndexF = Math.round(
    clamp(temperatureF + (relativeHumidityPct - 45) * 0.22 + point.value * 0.04, 72, 135),
  );
  const treeCanopyPct = Math.round(clamp(42 - point.value * 0.28 - noise * 2.5, 3, 48));
  const imperviousSurfacePct = Math.round(clamp(18 + point.value * 0.72 + noise * 3, 12, 98));
  const landSurfaceTempF = Math.round(
    clamp(temperatureF + 0.16 * imperviousSurfacePct - 0.11 * treeCanopyPct, 72, 150),
  );
  const nighttimeTempF = Math.round(
    clamp(70 + point.value * 0.17 + (imperviousSurfacePct - treeCanopyPct) * 0.06, 65, 100),
  );

  return {
    temperatureF,
    heatIndexF,
    relativeHumidityPct,
    landSurfaceTempF,
    nighttimeTempF,
    treeCanopyPct,
    imperviousSurfacePct,
  };
}

/**
 * Inverse-distance-weighted score at an arbitrary coordinate.
 */
function interpolate(
  lon: number,
  lat: number,
  anchors: HeatmapMetricValue[],
  power: number,
): number {
  let weightedSum = 0;
  let weightTotal = 0;

  for (const a of anchors) {
    const [aLon, aLat] = a.location_coordinates;
    const dLon = lon - aLon;
    const dLat = lat - aLat;
    const distSq = dLon * dLon + dLat * dLat;

    if (distSq < 1e-8) return a.value; // sitting on an anchor

    const weight = 1 / Math.pow(distSq, power / 2);
    weightedSum += weight * a.value;
    weightTotal += weight;
  }

  return weightedSum / weightTotal;
}

/**
 * Builds a full interpolated field: the measured anchors plus a dense lattice
 * of interpolated points spanning the metro bounding box. `valueScale` shifts
 * every anchor value before interpolation so the same anchors can vary per day.
 */
function buildField(
  anchors: HeatmapMetricValue[],
  power: number,
  options?: { attachIndividualMetrics?: boolean; rippleAmp?: number; valueScale?: number },
): HeatmapMetricValue[] {
  const rippleAmp = options?.rippleAmp ?? 1.5;
  const valueScale = options?.valueScale ?? 1;

  const scaledAnchors: HeatmapMetricValue[] =
    valueScale === 1
      ? anchors
      : anchors.map((a) => ({
          ...a,
          value: clamp(a.value * valueScale, MIN_SCORE, MAX_SCORE),
        }));

  const points: HeatmapMetricValue[] = scaledAnchors.map((a) => ({
    ...a,
    value: Math.round(a.value),
  }));

  const minLon = INTERP_CENTER[0] - INTERP_HALF_SPAN_LON;
  const maxLon = INTERP_CENTER[0] + INTERP_HALF_SPAN_LON;
  const minLat = INTERP_CENTER[1] - INTERP_HALF_SPAN_LAT;
  const maxLat = INTERP_CENTER[1] + INTERP_HALF_SPAN_LAT;

  for (let lat = minLat; lat <= maxLat + 1e-9; lat += INTERP_STEP) {
    for (let lon = minLon; lon <= maxLon + 1e-9; lon += INTERP_STEP) {
      const roundedLon = Number(lon.toFixed(3));
      const roundedLat = Number(lat.toFixed(3));

      const ripple = Math.sin(roundedLon * 20) * Math.cos(roundedLat * 20) * rippleAmp;
      const value = clamp(
        Math.round(interpolate(roundedLon, roundedLat, scaledAnchors, power) + ripple),
        MIN_SCORE,
        MAX_SCORE,
      );

      points.push({
        value,
        location_name: 'Interpolated',
        location_coordinates: [roundedLon, roundedLat],
      });
    }
  }

  if (!options?.attachIndividualMetrics) return points;

  return points.map((point) => ({
    ...point,
    individual_metrics: point.individual_metrics ?? buildIndividualMetrics(point),
  }));
}

// ---------------------------------------------------------------------------
// Per-metric interpolation config, keyed by metric name.
// ---------------------------------------------------------------------------
interface MetricConfig {
  power: number;
  scales: Record<string, number>; // date -> value scale
  options?: { attachIndividualMetrics?: boolean; rippleAmp?: number };
}

const METRIC_CONFIG: Record<string, MetricConfig> = {
  heat_risk_score: {
    power: HEAT_IDW_POWER,
    scales: { '2026-07-05': 0.80, '2026-07-06': 0.94, '2026-07-07': 1.00, '2026-07-08': 0.88 },
    options: { attachIndividualMetrics: true },
  },
  visitor_activity: {
    power: VISITOR_IDW_POWER,
    scales: { '2026-07-05': 0.35, '2026-07-06': 0.65, '2026-07-07': 0.85, '2026-07-08': 1.00 },
  },
};

/**
 * Interpolate a single city + date. Pulls that slice's raw anchors from the
 * backend response and returns one interpolated field per metric.
 *
 * @param source  the raw anchors from callHeatmapAnchors()
 * @param city    e.g. "Houston"
 * @param date    e.g. "2026-07-07"
 */
export function interpolateByCity(
  source: HeatmapMetricPointByCity,
  city: string,
  date: string,
): HeatmapMetricSnapshot[] {
  const dateRecords = source[city];
  if (!dateRecords) return [];

  // A city can hold multiple date-records; gather this date's snapshots from each.
  const snapshots = dateRecords.flatMap((byDate) => byDate[date] ?? []);
  if (snapshots.length === 0) return [];

  return snapshots.map((snapshot) => {
    const config = METRIC_CONFIG[snapshot.metric];
    return {
      metric: snapshot.metric,
      points: buildField(snapshot.points, config?.power ?? HEAT_IDW_POWER, {
        ...config?.options,
        valueScale: config?.scales[date] ?? 1,
      }),
    };
  });
}