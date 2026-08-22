import type { HeatmapMetricValue } from "../types/heatmap";
import type { MetricEffectModel, Tool, KernelModel } from '../types/kernel';
export type { MetricEffectModel, Tool, KernelModel };



// ============================================================================
// Shared Types
// ============================================================================

// ---------------------------------------------------------------------------
// Kernel model: toolType -> metric -> MetricEffectModel.
// Only temperature is defined here (that's what the misting-station math covers).
// Spatial distances are METERS to match haversine(). intensity is signed:
// negative = cooling.
// ---------------------------------------------------------------------------

// --- small parsers for individual_metrics (values are unit-tagged strings) ---
function parseNumericMetric(
  metrics: HeatmapMetricValue['individual_metrics'],
  key: string,
): number | null {
  const raw = metrics?.[key];
  if (raw == null) return null;
  const n = parseFloat(raw); // parseFloat stops at the unit: "98°F" -> 98, "62%" -> 62
  return Number.isNaN(n) ? null : n;
}

// --- misting station, temperature -------------------------------------------
const MISTING_SIGMA_M = 25;      // Gaussian characteristic radius, meters
const MISTING_TAU_UP = 0.15;     // ramp-up time constant, hours
const MISTING_TAU_DOWN = 0.2;    // post-shutdown decay constant, hours
const MISTING_VPD_REF = 4;       // kPa, normalizes the VPD gate to ~[0,1]

const mistingStationTemperature: MetricEffectModel = {
  intensity: -35, // dry-air ceiling (~9°F) before kernels scale it down
  floor: 40,      // wet-bulb wall (~94.4°F): misting can't push below this

  // S(d) = exp(-d^2 / (2σ^2)), d in meters
  spatial: (distanceMeters: number): number =>
    Math.exp(-(distanceMeters * distanceMeters) / (2 * MISTING_SIGMA_M ** 2)),

  // Fast ramp to steady state, fast decay after shutdown.
  temporal: (elapsedHours: number, activeHours: number): number => {
    if (elapsedHours <= 0) return 0;
    if (elapsedHours <= activeHours) {
      return 1 - Math.exp(-elapsedHours / MISTING_TAU_UP);
    }
    const atShutdown = 1 - Math.exp(-activeHours / MISTING_TAU_UP);
    return atShutdown * Math.exp(-(elapsedHours - activeHours) / MISTING_TAU_DOWN);
  },

  // More sensible heat when hotter -> slightly more effective. Gentle by design.
  response: (baseValue: number): number => 0.6 + 0.4 * (baseValue / 100),

  // VPD gate: dry AND hot air raise achievable evaporative cooling; humid kills it.
  environmental: (metrics): number => {
    const tempF = parseNumericMetric(metrics, 'temperatureF');
    const rh = parseNumericMetric(metrics, 'relativeHumidityPct');
    if (tempF == null || rh == null) return 1; // no data -> don't gate

    const tC = (tempF - 32) / 1.8;
    const esat = 0.6108 * Math.exp((17.27 * tC) / (tC + 237.3)); // kPa (Tetens)
    const vpd = esat * (1 - rh / 100);
    return Math.max(0, Math.min(vpd / MISTING_VPD_REF, 1));
  },
};

export const KERNEL_MODEL: KernelModel = {
  misting_station: {
    temperature: mistingStationTemperature,
  },
};