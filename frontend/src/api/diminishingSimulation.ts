import type { BasePlacedObject, BasePlacedObjectCategorized } from '../hooks/usePlacedObjects';
import type { HeatmapMetricValue, HeatmapPointsByDate, Polygon } from '../types/heatmap';

/** Inputs for the vegetation cooling calculation. Fractions are in the 0–1 range. */
export interface VegetationCoolingParams {
  vegetatedCoverage: number;
  canopyFraction: number;
  lai: number;
  waterFactor: number;
}
/** Weather inputs used to determine vegetation's evaporative cooling capacity. */
export interface WeatherParams {
  temperatureC: number;
  relativeHumidity: number;
  fSolar?: number;
  fWind?: number;
}
/** Inputs for reflective pavement or roofing. Fractions are in the 0–1 range. */
export interface AlbedoCoolingParams {
  deltaAlbedo: number;
  areaCoverage: number;
}
/** Weather inputs used to determine solar-driven reflective-surface cooling. */
export interface AlbedoWeatherParams {
  temperatureC: number;
  fSolar?: number;
}
/** Inputs for an artificial shade structure. Fractions are in the 0–1 range. */
export interface ShadeCoolingParams {
  opacity: number;
  shadedFootprint: number;
}
/** Weather inputs used to determine solar-driven shade cooling. */
export interface ShadeWeatherParams {
  temperatureC: number;
  fSolar?: number;
}
/** Inputs for a fountain, mister, or other free-water cooling source. */
export interface EvaporativeCoolingParams {
  evapRateLpm: number;
  coverageRadiusM: number;
  activeFraction: number;
}
/** Weather inputs used to determine evaporative cooling capacity. */
export interface EvaporativeWeatherParams {
  temperatureC: number;
  relativeHumidity: number;
  fWind?: number;
}

const VEGETATION_DELTA_T_MAX = 5;
const VPD_REFERENCE_KPA = 4.5;
const ALBEDO_DELTA_T_MAX = 4;
const SHADE_DELTA_T_MAX = 5;
const EVAPORATIVE_DELTA_T_MAX = 8;

/** Returns saturation vapor pressure in kPa using the Tetens approximation. */
export function saturationVaporPressure(temperatureC: number): number { return 0.6108 * Math.exp((17.27 * temperatureC) / (temperatureC + 237.3)); }
/** Returns vapor-pressure deficit (kPa), the atmospheric demand for evaporation. */
export function vaporPressureDeficit(temperatureC: number, relativeHumidity: number): number { return saturationVaporPressure(temperatureC) * (1 - relativeHumidity / 100); }
/** Calculates the weather-limited maximum cooling available to vegetation. */
export function deltaTMaxFromWeather({ temperatureC, relativeHumidity, fSolar = 1, fWind = 1 }: WeatherParams): number { return VEGETATION_DELTA_T_MAX * Math.min(vaporPressureDeficit(temperatureC, relativeHumidity) / VPD_REFERENCE_KPA, 1) * fSolar * fWind; }
/** Calculates a saturating vegetation cooling effect; `deltaT` is negative when cooling occurs. */
export function vegetationCooling(initialTemp: number, params: VegetationCoolingParams, ceiling: number | WeatherParams = VEGETATION_DELTA_T_MAX): { finalTemp: number; deltaT: number } { const maxCooling = typeof ceiling === 'number' ? ceiling : deltaTMaxFromWeather(ceiling); const leafEffect = 1 - Math.exp(-0.5 * params.lai); const latent = params.vegetatedCoverage * leafEffect * params.waterFactor; const shade = params.vegetatedCoverage * params.canopyFraction * leafEffect * (0.8 + 0.2 * params.waterFactor); const cooling = maxCooling * (0.4 * latent + 0.6 * shade); return { finalTemp: initialTemp - cooling, deltaT: -cooling }; }
/** Calculates the weather-limited maximum cooling available to a reflective surface. */
export function deltaTMaxFromWeatherAlbedo({ temperatureC, fSolar = 1 }: AlbedoWeatherParams): number { return ALBEDO_DELTA_T_MAX * clamp((temperatureC - 20) / 18, 0, 1) * fSolar; }
/** Calculates reflective-surface cooling; `deltaT` is negative when cooling occurs. */
export function albedoCooling(initialTemp: number, params: AlbedoCoolingParams, ceiling: number | AlbedoWeatherParams = ALBEDO_DELTA_T_MAX): { finalTemp: number; deltaT: number } { const maxCooling = typeof ceiling === 'number' ? ceiling : deltaTMaxFromWeatherAlbedo(ceiling); const cooling = maxCooling * clamp(params.deltaAlbedo / 0.7, 0, 1) * clamp(params.areaCoverage, 0, 1); return { finalTemp: initialTemp - cooling, deltaT: -cooling }; }
/** Calculates the weather-limited maximum cooling available to shade. */
export function deltaTMaxFromWeatherShade({ temperatureC, fSolar = 1 }: ShadeWeatherParams): number { return SHADE_DELTA_T_MAX * clamp((temperatureC - 20) / 18, 0, 1) * fSolar * 0.85; }
/** Calculates shade cooling; `deltaT` is negative when cooling occurs. */
export function shadeCooling(initialTemp: number, params: ShadeCoolingParams, ceiling: number | ShadeWeatherParams = SHADE_DELTA_T_MAX * 0.85): { finalTemp: number; deltaT: number } { const maxCooling = typeof ceiling === 'number' ? ceiling : deltaTMaxFromWeatherShade(ceiling); const cooling = maxCooling * clamp(params.opacity, 0, 1) * clamp(params.shadedFootprint, 0, 1); return { finalTemp: initialTemp - cooling, deltaT: -cooling }; }
/** Calculates the weather-limited maximum cooling available to an evaporative source. */
export function deltaTMaxFromWeatherEvap({ temperatureC, relativeHumidity, fWind = 1 }: EvaporativeWeatherParams): number { return EVAPORATIVE_DELTA_T_MAX * Math.min(vaporPressureDeficit(temperatureC, relativeHumidity) / VPD_REFERENCE_KPA, 1) * fWind; }
/** Calculates distance-faded evaporative cooling; `deltaT` is negative when cooling occurs. */
export function evaporativeCooling(initialTemp: number, params: EvaporativeCoolingParams, distanceM: number, ceiling: number | EvaporativeWeatherParams = EVAPORATIVE_DELTA_T_MAX): { finalTemp: number; deltaT: number } { const maxCooling = typeof ceiling === 'number' ? ceiling : deltaTMaxFromWeatherEvap(ceiling); const powerW = (Math.max(params.evapRateLpm, 0) / 60) * 2.45e6; const sourceStrength = Math.min(powerW / 50000, 1); const falloff = params.coverageRadiusM > 0 ? Math.max(1 - Math.max(distanceM, 0) / params.coverageRadiusM, 0) : 0; const cooling = maxCooling * sourceStrength * clamp(params.activeFraction, 0, 1) * falloff; return { finalTemp: initialTemp - cooling, deltaT: -cooling }; }

const VEGETATION = 'Vegetation';
const ALBEDO = 'High-albedo surface';
const SHADE = 'Shade structure';
const EVAPORATIVE = 'Evaporative / water';
const FALLBACK_TEMPERATURE_C = 34;

/**
 * `standard` preserves the original independent, diminishing-return model.
 * `contextual` additionally adjusts overlapping interventions according to
 * simple, inspectable urban-design interaction rules.
 */
export type SimulationMode = 'standard' | 'contextual';

const CONTEXTUAL_INTERACTIONS: Array<{
  categories: [string, string];
  factor: number;
  label: string;
  mapLabel: string;
}> = [
  {
    categories: [VEGETATION, EVAPORATIVE],
    factor: 1.25,
    label: 'Vegetation + water: irrigation and evapotranspiration reinforce cooling (+25%).',
    mapLabel: 'Tree + water\nsynergy +25%',
  },
  {
    categories: [VEGETATION, ALBEDO],
    factor: 0.82,
    label: 'Vegetation + reflective concrete: overlapping benefits are less complementary (-18%).',
    mapLabel: 'Tree + pavement\nrestraint −18%',
  },
  {
    categories: [VEGETATION, SHADE],
    factor: 0.86,
    label: 'Vegetation + shade: shared solar blocking produces partial redundancy (-14%).',
    mapLabel: 'Tree + shade\nshared effect −14%',
  },
  {
    categories: [SHADE, EVAPORATIVE],
    factor: 0.92,
    label: 'Shade + water: lower airflow modestly limits the evaporative plume (-8%).',
    mapLabel: 'Shade + water\nairflow −8%',
  },
];

export interface SimulationFeedback {
  mode: SimulationMode;
  affectedPoints: number;
  overlapPoints: number;
  maxObjectsAtPoint: number;
  averageCoolingC: number;
  maxCapacityUsed: number;
  affectedLocations: string[];
  overlapLocations: string[];
  contributingInterventions: string[];
  interventionsWithoutEffect: string[];
  contextualInteractions: string[];
}

export interface DiminishingSimulationResult {
  pointsByDate: HeatmapPointsByDate;
  feedback: SimulationFeedback;
}

/** Limits a value to an inclusive range before it is used by a physical model. */
function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Tests whether a heatmap sample coordinate is inside a polygon intervention. */
function pointInPolygon([lon, lat]: [number, number], polygon: Polygon): boolean {
  let inside = false;
  for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index++) {
    const [currentLon, currentLat] = polygon[index];
    const [previousLon, previousLat] = polygon[previous];
    if (
      currentLat > lat !== previousLat > lat
      && lon < ((previousLon - currentLon) * (lat - currentLat)) / (previousLat - currentLat) + currentLon
    ) inside = !inside;
  }
  return inside;
}

/** Approximates a short city-scale longitude/latitude distance in metres. */
function distanceMeters(a: [number, number], b: [number, number]): number {
  const midLatitude = ((a[1] + b[1]) / 2) * (Math.PI / 180);
  return Math.hypot(
    (a[0] - b[0]) * Math.cos(midLatitude) * 111320,
    (a[1] - b[1]) * 110540,
  );
}

/** Returns a point intervention's location or the centroid of a line/polygon. */
function geometryAnchor(object: BasePlacedObject): [number, number] {
  if (object.geometry.kind === 'point') return [object.geometry.longitude, object.geometry.latitude];
  const points = object.geometry.kind === 'line' ? object.geometry.coordinates : object.geometry.ring;
  const total = points.reduce(([lon, lat], point) => [lon + point[0], lat + point[1]], [0, 0]);
  return [total[0] / points.length, total[1] / points.length];
}

/** Returns whether an intervention is active on the supplied ISO date. */
function activeOnDate(object: BasePlacedObject, date: string): boolean {
  const time = new Date(date).getTime();
  return time >= (object.activeFrom ? new Date(object.activeFrom).getTime() : -Infinity)
    && time <= (object.activeTo ? new Date(object.activeTo).getTime() : Infinity);
}

/** Extracts weather from a point, with a hot-day fallback for change-only layers. */
function baselineWeather(point: HeatmapMetricValue, isChangeMetric: boolean) {
  const sourceTemperature = parseFloat(point.individual_metrics?.avg_temperature_c ?? '');
  const humidity = parseFloat(point.individual_metrics?.relative_humidity ?? '');
  return {
    temperatureC: isChangeMetric
      ? (Number.isFinite(sourceTemperature) ? sourceTemperature : FALLBACK_TEMPERATURE_C)
      : point.value,
    relativeHumidity: Number.isFinite(humidity) ? humidity : undefined,
  };
}

/** One weather-sensitive carrying capacity for an interpolation point. */
function coolingCeiling(temperatureC: number, relativeHumidity?: number): number {
  const vegetation = relativeHumidity == null
    ? 5
    : deltaTMaxFromWeather({ temperatureC, relativeHumidity });
  const evaporative = relativeHumidity == null
    ? 8
    : deltaTMaxFromWeatherEvap({ temperatureC, relativeHumidity });
  return Math.max(
    vegetation,
    evaporative,
    deltaTMaxFromWeatherAlbedo({ temperatureC }),
    deltaTMaxFromWeatherShade({ temperatureC }),
    0.1,
  );
}

/** Computes a single intervention's positive cooling contribution at one point. */
function objectCooling(
  category: string,
  object: BasePlacedObject,
  point: HeatmapMetricValue,
  temperatureC: number,
  relativeHumidity?: number,
): number | null {
  const params = object.params ?? {};
  if (category === EVAPORATIVE) {
    const evapRateLpm = params.evapRateLpm ?? params.flowRate;
    const coverageRadiusM = params.coverageRadiusM ?? params.radius;
    if (evapRateLpm == null || coverageRadiusM == null || params.activeFraction == null) return null;
    const distance = distanceMeters(geometryAnchor(object), point.location_coordinates);
    if (distance > coverageRadiusM) return null;
    const result = relativeHumidity == null
      ? evaporativeCooling(temperatureC, { evapRateLpm, coverageRadiusM, activeFraction: params.activeFraction }, distance)
      : evaporativeCooling(temperatureC, { evapRateLpm, coverageRadiusM, activeFraction: params.activeFraction }, distance, { temperatureC, relativeHumidity });
    return Math.max(0, -result.deltaT);
  }

  if (object.geometry.kind !== 'polygon' || !pointInPolygon(point.location_coordinates, object.geometry.ring)) return null;
  if (category === VEGETATION) {
    if (params.coverPct == null || params.lai == null || params.irrigation == null) return null;
    const input = { vegetatedCoverage: params.coverPct, canopyFraction: params.canopyFraction ?? 1, lai: params.lai, waterFactor: params.irrigation };
    const result = relativeHumidity == null
      ? vegetationCooling(temperatureC, input)
      : vegetationCooling(temperatureC, input, { temperatureC, relativeHumidity });
    return Math.max(0, -result.deltaT);
  }
  if (category === ALBEDO) {
    if (params.deltaAlbedo == null || params.coverPct == null) return null;
    return Math.max(0, -albedoCooling(temperatureC, { deltaAlbedo: params.deltaAlbedo, areaCoverage: params.coverPct }, { temperatureC }).deltaT);
  }
  if (category === SHADE) {
    const footprint = params.footprintFraction ?? params.coverPct;
    if (params.opacity == null || footprint == null) return null;
    return Math.max(0, -shadeCooling(temperatureC, { opacity: params.opacity, shadedFootprint: footprint }, { temperatureC }).deltaT);
  }
  return null;
}

/**
 * Runs the four existing archetype models from an unchanged baseline, then
 * combines overlapping cooling at each interpolation point using
 * 1 - product(1 - contribution). The weather-dependent ceiling is carrying
 * capacity: combined cooling cannot exceed it.
 */
export async function runDiminishingReturnSimulation(
  metric: string,
  pointsByDate: HeatmapPointsByDate,
  categorizedObjects: BasePlacedObjectCategorized,
  mode: SimulationMode = 'standard',
): Promise<DiminishingSimulationResult> {
  const isTemperatureMetric = /temp/i.test(metric);
  const isChangeMetric = metric === 'change_in_temperature';
  const feedback: SimulationFeedback = {
    mode,
    affectedPoints: 0,
    overlapPoints: 0,
    maxObjectsAtPoint: 0,
    averageCoolingC: 0,
    maxCapacityUsed: 0,
    affectedLocations: [],
    overlapLocations: [],
    contributingInterventions: [],
    interventionsWithoutEffect: [],
    contextualInteractions: [],
  };
  let totalCoolingC = 0;
  const affectedLocations = new Set<string>();
  const overlapLocations = new Set<string>();
  const contributingInterventionIds = new Set<string>();
  const interventionLabels = new Map<string, string>();

  for (const [category, objects] of Object.entries(categorizedObjects)) {
    for (const object of objects) {
      interventionLabels.set(object.id, object.name ?? object.type ?? category);
    }
  }

  const pointsByDateResult = Object.fromEntries(Object.entries(pointsByDate).map(([date, points]) => [date, points.map((sourcePoint) => {
    const point = structuredClone(sourcePoint);
    if (!isTemperatureMetric) return point;
    const weather = baselineWeather(sourcePoint, isChangeMetric);
    const ceiling = coolingCeiling(weather.temperatureC, weather.relativeHumidity);
    const rawContributions = Object.entries(categorizedObjects).flatMap(([category, objects]) => objects
      .filter((object) => activeOnDate(object, date))
      .map((object) => ({
        object,
        category,
        cooling: objectCooling(category, object, sourcePoint, weather.temperatureC, weather.relativeHumidity),
      }))
      .filter((contribution): contribution is { object: BasePlacedObject; category: string; cooling: number } =>
        contribution.cooling != null && contribution.cooling > 0,
      ));

    const categoriesAtPoint = new Set(rawContributions.map((contribution) => contribution.category));
    const matchingInteractions = mode === 'contextual'
      ? CONTEXTUAL_INTERACTIONS.filter(({ categories: [first, second] }) =>
        categoriesAtPoint.has(first) && categoriesAtPoint.has(second),
      )
      : [];
    const contextualFactor = matchingInteractions.reduce((factor, interaction) => factor * interaction.factor, 1);
    const contributions = rawContributions.map((contribution) => ({
      ...contribution,
      cooling: contribution.cooling * contextualFactor,
    }));

    if (contributions.length === 0) return point;
    const pointImpact = 1 - contributions.reduce(
      (remaining, contribution) => remaining * (1 - clamp(contribution.cooling / ceiling, 0, 1)),
      1,
    );
    const coolingC = ceiling * pointImpact;
    const finalTemperature = weather.temperatureC - coolingC;

    feedback.affectedPoints += 1;
    feedback.maxObjectsAtPoint = Math.max(feedback.maxObjectsAtPoint, contributions.length);
    feedback.maxCapacityUsed = Math.max(feedback.maxCapacityUsed, pointImpact * 100);
    affectedLocations.add(sourcePoint.location_name);
    contributions.forEach(({ object }) => contributingInterventionIds.add(object.id));
    matchingInteractions.forEach((interaction) => {
      if (!feedback.contextualInteractions.includes(interaction.label)) {
        feedback.contextualInteractions.push(interaction.label);
      }
    });
    if (contributions.length > 1) {
      feedback.overlapPoints += 1;
      overlapLocations.add(sourcePoint.location_name);
    }
    totalCoolingC += coolingC;

    point.value = isChangeMetric ? -coolingC : finalTemperature;
    point.individual_metrics = {
      ...point.individual_metrics,
      avg_temperature_c: `${finalTemperature.toFixed(1)}°C`,
      simulation_cooling_c: `${coolingC.toFixed(2)}°C`,
      simulation_baseline_temperature_c: `${weather.temperatureC.toFixed(2)}°C`,
      simulation_result_temperature_c: `${finalTemperature.toFixed(2)}°C`,
      simulation_overlap_count: String(contributions.length),
      simulation_capacity_used: `${(pointImpact * 100).toFixed(0)}%`,
      simulation_interaction: matchingInteractions.map((interaction) => interaction.mapLabel).join(' | '),
    };
    return point;
  })]));

  feedback.averageCoolingC = feedback.affectedPoints ? totalCoolingC / feedback.affectedPoints : 0;
  feedback.affectedLocations = [...affectedLocations];
  feedback.overlapLocations = [...overlapLocations];
  feedback.contributingInterventions = [...contributingInterventionIds]
    .map((id) => interventionLabels.get(id) ?? id);
  feedback.interventionsWithoutEffect = [...interventionLabels]
    .filter(([id]) => !contributingInterventionIds.has(id))
    .map(([, label]) => label);
  return { pointsByDate: pointsByDateResult, feedback };
}
