import type { BasePlacedObject, BasePlacedObjectCategorized } from '../hooks/usePlacedObjects';
import type { HeatmapMetricValue, HeatmapPointsByDate, Polygon } from '../types/heatmap';
import {
  albedoCooling,
  deltaTMaxFromWeather,
  deltaTMaxFromWeatherAlbedo,
  deltaTMaxFromWeatherEvap,
  deltaTMaxFromWeatherShade,
  evaporativeCooling,
  vegetationCooling,
  shadeCooling,
} from './simulation';

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

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

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

function distanceMeters(a: [number, number], b: [number, number]): number {
  const midLatitude = ((a[1] + b[1]) / 2) * (Math.PI / 180);
  return Math.hypot(
    (a[0] - b[0]) * Math.cos(midLatitude) * 111320,
    (a[1] - b[1]) * 110540,
  );
}

function geometryAnchor(object: BasePlacedObject): [number, number] {
  if (object.geometry.kind === 'point') return [object.geometry.longitude, object.geometry.latitude];
  const points = object.geometry.kind === 'line' ? object.geometry.coordinates : object.geometry.ring;
  const total = points.reduce(([lon, lat], point) => [lon + point[0], lat + point[1]], [0, 0]);
  return [total[0] / points.length, total[1] / points.length];
}

function activeOnDate(object: BasePlacedObject, date: string): boolean {
  const time = new Date(date).getTime();
  return time >= (object.activeFrom ? new Date(object.activeFrom).getTime() : -Infinity)
    && time <= (object.activeTo ? new Date(object.activeTo).getTime() : Infinity);
}

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
