import type { HeatmapMetricValue } from "./map";

// ============================================================================
// Shared Types
// ============================================================================

type IndividualMetrics = HeatmapMetricValue["individual_metrics"];

type SpatialKernel = (distanceMeters: number) => number;

type TemporalKernel = (
  elapsedHours: number,
  activeHours: number
) => number;

type ResponseKernel = (baseValue: number) => number;

type SuitabilityKernel = (metrics: IndividualMetrics) => number;

type EnvironmentalKernel = (
  metrics: IndividualMetrics,
  time: string
) => number;

interface MetricEffectModel {
  intensity: number;
  floor: number;

  spatial: SpatialKernel;
  temporal: TemporalKernel;
  response: ResponseKernel;

  suitability?: SuitabilityKernel;
  environmental?: EnvironmentalKernel;
}

interface Tool {
  id: string;
  toolType: string;
  location: [number, number];
  placedAt: string;
  activeHours: number;
  effects: Record<string, MetricEffectModel>;
}

// ============================================================================
// Helpers
// ============================================================================

const clamp = (value: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, value));

const clamp01 = (value: number): number => clamp(value, 0, 1);

const hoursBetween = (start: string, end: string): number => {
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();

  return Math.max(0, (endMs - startMs) / (1000 * 60 * 60));
};

// ============================================================================
// Mock Street Tree Canopy Kernels
// ============================================================================

const TREE_CANOPY_SIGMA_METERS = 12;
const TREE_MATURITY_YEARS = 7.83;
const TREE_SOLAR_REFERENCE = 800; // W/m²

/**
 * Gaussian shade footprint.
 *
 * At 8 meters:
 * exp(-(8²) / (2 × 12²)) ≈ 0.80
 */
const streetTreeSpatialKernel: SpatialKernel = (distanceMeters) => {
  const sigmaSquared = TREE_CANOPY_SIGMA_METERS ** 2;

  return Math.exp(
    -(distanceMeters ** 2) / (2 * sigmaSquared)
  );
};

/**
 * Slow clock: canopy maturity over years.
 *
 * activeHours is unused because the tree is not modeled as switching off
 * after a fixed operating duration.
 */
const streetTreeTemporalKernel: TemporalKernel = (
  elapsedHours,
  _activeHours
) => {
  const treeAgeYears = elapsedHours / (24 * 365.25);

  return clamp01(
    1 - Math.exp(-treeAgeYears / TREE_MATURITY_YEARS)
  );
};

/**
 * More cooling is possible when the current temperature is farther above
 * the metric's lower bound.
 *
 * For a heat range of 20–45°C and base value 36°C:
 * (36 - 20) / (45 - 20) = 0.64
 */
const streetTreeResponseKernel: ResponseKernel = (baseValue) => {
  const minimumHeat = 20;
  const maximumHeat = 45;

  return clamp01(
    (baseValue - minimumHeat) /
      (maximumHeat - minimumHeat)
  );
};

/**
 * Mock placement suitability.
 *
 * A site must be a street and have a usable tree pit.
 */
const streetTreeSuitabilityKernel: SuitabilityKernel = (metrics) => {
  const isStreet = metrics.is_street === 1;
  const hasTreePit = metrics.has_tree_pit === 1;

  if (!isStreet || !hasTreePit) {
    return 0;
  }

  // Good but not perfectly ideal site.
  return 0.85;
};

/**
 * Fast clock: current solar radiation.
 *
 * Shade cooling is strongest under high solar radiation and approaches
 * zero at night.
 *
 * solar_radiation is expected in W/m².
 */
const streetTreeEnvironmentalKernel: EnvironmentalKernel = (
  metrics,
  _time
) => {
  const solarRadiation = metrics.solar_radiation ?? 0;

  return clamp01(
    solarRadiation / TREE_SOLAR_REFERENCE
  );
};

// ============================================================================
// Mock Street Tree Tool
// ============================================================================

const streetTree: Tool = {
  id: "street-tree-001",
  toolType: "street_tree_canopy",
  location: [-95.3698, 29.7604],
  placedAt: "2022-07-01T12:00:00Z",

  // Trees do not have a short operational lifetime in this mock.
  activeHours: Number.POSITIVE_INFINITY,

  effects: {
    heat: {
      intensity: -4,
      floor: 20,

      spatial: streetTreeSpatialKernel,
      temporal: streetTreeTemporalKernel,
      response: streetTreeResponseKernel,
      suitability: streetTreeSuitabilityKernel,
      environmental: streetTreeEnvironmentalKernel,
    },
  },
};

// ============================================================================
// Mock Effect Calculation
// ============================================================================

interface CalculateMetricEffectParams {
  tool: Tool;
  metricName: string;
  baseValue: number;
  distanceMeters: number;
  currentTime: string;
  metrics: IndividualMetrics;
}

interface MetricEffectResult {
  originalValue: number;
  resultingValue: number;
  effect: number;

  kernels: {
    spatial: number;
    temporal: number;
    response: number;
    suitability: number;
    environmental: number;
  };
}

const calculateMetricEffect = ({
  tool,
  metricName,
  baseValue,
  distanceMeters,
  currentTime,
  metrics,
}: CalculateMetricEffectParams): MetricEffectResult => {
  const model = tool.effects[metricName];

  if (!model) {
    throw new Error(
      `Tool "${tool.id}" does not affect metric "${metricName}".`
    );
  }

  const elapsedHours = hoursBetween(
    tool.placedAt,
    currentTime
  );

  const spatial = model.spatial(distanceMeters);

  const temporal = model.temporal(
    elapsedHours,
    tool.activeHours
  );

  const response = model.response(baseValue);

  const suitability =
    model.suitability?.(metrics) ?? 1;

  const environmental =
    model.environmental?.(metrics, currentTime) ?? 1;

  const effect =
    model.intensity *
    spatial *
    temporal *
    response *
    suitability *
    environmental;

  const resultingValue =
    model.intensity < 0
      ? Math.max(model.floor, baseValue + effect)
      : baseValue + effect;

  return {
    originalValue: baseValue,
    resultingValue,
    effect,
    kernels: {
      spatial,
      temporal,
      response,
      suitability,
      environmental,
    },
  };
};

// ============================================================================
// Young Tree at Clear Solar Noon
// ============================================================================

const targetCellMetrics = {
  is_street: 1,
  has_tree_pit: 1,

  // 760 / 800 = 0.95 environmental multiplier.
  solar_radiation: 760,
} as IndividualMetrics;

const result = calculateMetricEffect({
  tool: streetTree,
  metricName: "heat",
  baseValue: 36,
  distanceMeters: 8,

  // Approximately four years after placement.
  currentTime: "2026-07-01T12:00:00Z",

  metrics: targetCellMetrics,
});

console.log({
  spatialKernel: result.kernels.spatial.toFixed(2),
  temporalKernel: result.kernels.temporal.toFixed(2),
  responseKernel: result.kernels.response.toFixed(2),
  suitabilityKernel:
    result.kernels.suitability.toFixed(2),
  environmentalKernel:
    result.kernels.environmental.toFixed(2),

  effectCelsius: result.effect.toFixed(2),
  resultingHeat: result.resultingValue.toFixed(1),
});