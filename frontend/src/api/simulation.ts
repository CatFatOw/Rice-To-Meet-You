import type { HeatmapPointsByDate, HeatmapMetricValue } from '../types/heatmap';
import type { BasePlacedObjectCategorized } from '../hooks/usePlacedObjects';
import type { Polygon } from '../types/heatmap';

// --- Vegetation cooling model ------------------------------------------------
// Estimates the pedestrian-level temperature drop from vegetation via two
// channels — latent (transpiration) and shade — combined into a 0–1 intensity
// and scaled to a ΔT. See derivation for the physics behind each step.

/** Planner-chosen inputs for a cell/archetype. All fractions are 0–1. */
export interface VegetationCoolingParams {
  vegetatedCoverage: number; // 0–1  fraction of ground with vegetation
  canopyFraction: number;    // 0–1  fraction of that vegetation under crown
  lai: number;               // ~0–6 Leaf Area Index (dimensionless)
  waterFactor: number;       // 0–1  water availability / irrigation gate
}

/**
 * Environmental inputs that set the cooling ceiling (ΔT_max). Temperature and
 * humidity drive the ET potential via VPD; solar and wind are held at 1 unless
 * you have data to scale them.
 */
export interface WeatherParams {
  temperatureC: number;      // °C   air temperature
  relativeHumidity: number;  // 0–100 (percent) relative humidity
  fSolar?: number;           // 0–1  insolation multiplier (default 1 — see note)
  fWind?: number;            // 0–1  wind multiplier      (default 1 — see note)
}




// --- Model constants (the real calibration knobs) ---------------------------
// These encode model physics, not planner choices — point literature-fitting
// here rather than at the four inputs.
const SHADE_DROUGHT_SURVIVAL = 0.8; // g: fraction of shade effect that survives WaterFactor=0 (~0.7–0.85)
const WEIGHT_LATENT = 0.4;          // w_L: relative weight of the latent/ET channel
const WEIGHT_SHADE = 0.6;           // w_S: relative weight of the shade channel  (w_L + w_S = 1)
const LAI_EXTINCTION = 0.5;         // Beer–Lambert extinction coefficient in f_LAI
const DELTA_T_MAX_ANCHOR = 5;       // °C: cooling asymptote under hot-dry-sunny-calm conditions
const VPD_REF = 4.5;                // kPa: peak-case VPD used to normalize f_VPD (38 °C / 28% RH ≈ 4.8)

/** Saturation vapor pressure (kPa) from air temperature (°C) — Tetens. */
export function saturationVaporPressure(temperatureC: number): number {
  return 0.6108 * Math.exp((17.27 * temperatureC) / (temperatureC + 237.3));
}

/** Vapor pressure deficit (kPa) from temperature (°C) and RH (0–100). */
export function vaporPressureDeficit(temperatureC: number, relativeHumidity: number): number {
  return saturationVaporPressure(temperatureC) * (1 - relativeHumidity / 100);
}

/**
 * Weather-dependent cooling ceiling:
 *   ΔT_max = 5 °C × f_VPD × f_solar × f_wind
 *
 * f_VPD normalizes VPD against the peak-case reference and caps at 1 so extreme
 * dryness doesn't imply unbounded cooling (stomatal-closure downslope).
 *
 * f_solar / f_wind: the schema carries no insolation or wind field, so both
 * default to 1. ASSUMPTION — a humid day is often overcast, which would also cut
 * the shade channel; pass a lower f_solar if you can infer cloud cover.
 */
export function deltaTMaxFromWeather(weather: WeatherParams): number {
  const { temperatureC, relativeHumidity, fSolar = 1, fWind = 1 } = weather;

  const vpd = vaporPressureDeficit(temperatureC, relativeHumidity);
  const fVPD = Math.min(vpd / VPD_REF, 1.0);

  return DELTA_T_MAX_ANCHOR * fVPD * fSolar * fWind;
}

/**
 * Compute vegetation cooling for one cell.
 *
 * @param initialTemp  Baseline temperature (°C) before vegetation cooling.
 * @param params       Planner-chosen vegetation inputs.
 * @param deltaTMax    Peak achievable cooling (°C). Pass a number directly, or a
 *                     WeatherParams to derive it from temperature/humidity via
 *                     deltaTMaxFromWeather. Defaults to the 5 °C hot-dry-sunny-
 *                     calm anchor.
 * @returns            The final temperature (°C) after vegetation cooling.
 */
export function vegetationCooling(
  initialTemp: number,
  params: VegetationCoolingParams,
  deltaTMax: number | WeatherParams = DELTA_T_MAX_ANCHOR,
): number {
  const { vegetatedCoverage, canopyFraction, lai, waterFactor } = params;

  // Resolve the cooling ceiling: a raw °C number, or derived from weather.
  const deltaTMaxC =
    typeof deltaTMax === 'number' ? deltaTMax : deltaTMaxFromWeather(deltaTMax);

  // Step 1 — saturating LAI transform (Beer–Lambert), not linear.
  const fLAI = 1 - Math.exp(-LAI_EXTINCTION * lai);

  // Step 2 — the two cooling channels.
  // Latent is fully water-gated (no water → collapses to 0).
  const latent = vegetatedCoverage * fLAI * waterFactor;
  // Shade is only weakly gated: it keeps g of its effect at WaterFactor = 0.
  const shade =
    vegetatedCoverage *
    canopyFraction *
    fLAI *
    (SHADE_DROUGHT_SURVIVAL + (1 - SHADE_DROUGHT_SURVIVAL) * waterFactor);

  // Step 3 — combine into normalized intensity (0–1).
  const intensity = WEIGHT_LATENT * latent + WEIGHT_SHADE * shade;

  // Step 4 — scale to a temperature drop, then apply to the initial temp.
  const deltaT = deltaTMaxC * intensity;
  const finalTemp = initialTemp - deltaT;

  return finalTemp;
}

// Simulated network latency so callers can exercise their loading states.
const MOCK_LATENCY_MS = 150;
const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));


// --- Polygon spatial filtering ----------------------------------------------
// For a placed object's footprint (polygon), keep only the heatmap points that
// fall inside it. bbox pre-check first (cheap), then exact ray-cast.

type BoundingBox = {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
};

function getBoundingBox(polygon: Polygon): BoundingBox {
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;

  for (const [lon, lat] of polygon) {
    minLon = Math.min(minLon, lon);
    minLat = Math.min(minLat, lat);
    maxLon = Math.max(maxLon, lon);
    maxLat = Math.max(maxLat, lat);
  }

  return { minLon, minLat, maxLon, maxLat };
}

function isInsideBoundingBox(
  lon: number,
  lat: number,
  bbox: BoundingBox,
): boolean {
  return (
    lon >= bbox.minLon &&
    lon <= bbox.maxLon &&
    lat >= bbox.minLat &&
    lat <= bbox.maxLat
  );
}

function pointInPolygon(
  lon: number,
  lat: number,
  polygon: Polygon,
): boolean {
  let inside = false;

  for (
    let i = 0, j = polygon.length - 1;
    i < polygon.length;
    j = i++
  ) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];

    const crossesRay =
      yi > lat !== yj > lat &&
      lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;

    if (crossesRay) {
      inside = !inside;
    }
  }

  return inside;
}

/** True if a single reading's coordinates fall inside the polygon. */
function isPointInsidePolygon(
  point: HeatmapMetricValue,
  polygon: Polygon,
  bbox: BoundingBox,
): boolean {
  const [lon, lat] = point.location_coordinates;
  if (!isInsideBoundingBox(lon, lat, bbox)) {
    return false;
  }
  return pointInPolygon(lon, lat, polygon);
}

/**
 * Filter a by-date reading set down to the points that fall inside `polygon`,
 * preserving the by-date grouping. Each date maps to only its interior points;
 * dates left with no interior points are dropped from the result.
 *
 * The polygon bounding box is computed once and reused across every date/point.
 */
function pointsInsidePolygonByDate(
  pointsByDate: HeatmapPointsByDate,
  polygon: Polygon,
): HeatmapPointsByDate {
  const bbox = getBoundingBox(polygon);
  const result: HeatmapPointsByDate = {};

  for (const [date, points] of Object.entries(pointsByDate)) {
    const inside = points.filter((point) =>
      isPointInsidePolygon(point, polygon, bbox),
    );

    if (inside.length > 0) {
      result[date] = inside;
    }
  }

  return result;
}


// --- Assumptions about the placed-object + reading shapes -------------------
// Field names below track the toolbox schema (archetype 'Vegetation', a placed
// object's `kind`/`polygon`, and `params: { coverPct, lai, irrigation }`). If
// the real placed-object type diverges, this block is the only thing to touch.

/** Archetype key (in BasePlacedObjectCategorized) whose objects cool via ET/shade. */
const VEGETATION_CATEGORY = 'Vegetation';

/**
 * Canopy fraction isn't in the toolbox params, so assume the placed vegetation
 * cover is fully canopied unless the object overrides it.
 */
const DEFAULT_CANOPY_FRACTION = 1;

/** Toolbox param bag on a placed vegetation object. */
type PlacedVegetationParams = {
  coverPct?: number;      // -> vegetatedCoverage
  lai?: number;           // -> lai
  irrigation?: number;    // -> waterFactor
  canopyFraction?: number;// -> canopyFraction (optional; not in toolbox schema)
};

/** A placed object contributes a footprint only if it is a drawn polygon. */
function getObjectPolygon(object: { kind?: string; ring?: Polygon }): Polygon | null {
  return object.kind === 'polygon' && object.ring ? object.ring : null;
}

/** Map a placed object's toolbox params onto the cooling model's inputs. */
function getCoolingParams(
  object: { params?: PlacedVegetationParams },
): VegetationCoolingParams | null {
  const p = object.params;
  if (!p || p.coverPct == null || p.lai == null || p.irrigation == null) {
    return null;
  }
  return {
    vegetatedCoverage: p.coverPct,
    canopyFraction: p.canopyFraction ?? DEFAULT_CANOPY_FRACTION,
    lai: p.lai,
    waterFactor: p.irrigation,
  };
}

/** This model only moves temperature; leave other metrics untouched. */
function metricIsTemperature(metric: string): boolean {
  return /temp/i.test(metric);
}

/**
 * Run the intervention simulation for one metric.
 *
 * 1. For every placed object with a polygon footprint, find the baseline points
 *    it covers via pointsInsidePolygonByDate.
 * 2. For vegetation objects (when the metric is temperature), walk each covered
 *    date/point and replace its reading with the vegetation-cooled value.
 * 3. Return the full reading set with those in-place modifications applied.
 *
 * Works on a clone so the caller's baseline pointsByDate is never mutated.
 */
export async function getSimulatedPointsByDate(
  metric: string,
  pointsByDate: HeatmapPointsByDate,
  placedObjects: BasePlacedObjectCategorized,
): Promise<HeatmapPointsByDate> {
  await delay(MOCK_LATENCY_MS);

  // Clone up front. pointsInsidePolygonByDate returns references into this
  // clone, so mutating a covered point below updates the value we return.
  const simulated: HeatmapPointsByDate = structuredClone(pointsByDate);
  const affectsTemperature = metricIsTemperature(metric);

  for (const [category, objects] of Object.entries(placedObjects)) {
    
    const isVegetation = category === VEGETATION_CATEGORY;

    for (const object of objects) {
      console.log(JSON.stringify(object))
      const polygon = getObjectPolygon(object.geometry);

      console.log(`Polygon: ${polygon}`)
      if (!polygon) continue;

      // Baseline points this object covers, grouped by date.
      const covered = pointsInsidePolygonByDate(simulated, polygon);

      console.log(`Covered: ${JSON.stringify(covered)}`)

      if (!isVegetation || !affectsTemperature) continue;

      const params = getCoolingParams(object);

      console.log(`Params: ${JSON.stringify(params)}`)
      if (!params) continue;
      
      for (const points of Object.values(covered)) {
        for (const point of points) {
          const beforeC = point.value;
          const rhBefore = parseFloat(point.individual_metrics?.relative_humidity ?? '');
          const hasRh = Number.isFinite(rhBefore);

          // The point's own temp + humidity set the weather-driven cooling ceiling.
          // If RH is missing, fall back to vegetationCooling's default (5 °C anchor).
          const afterC = hasRh
            ? vegetationCooling(beforeC, params, {
                temperatureC: beforeC,
                relativeHumidity: rhBefore,
              })
            : vegetationCooling(beforeC, params);

          // Cooling at ~constant vapor content raises RH: RH2 = RH1 * es(T1)/es(T2).
          const rhAfter = hasRh
            ? Math.min(
                100,
                rhBefore *
                  (saturationVaporPressure(beforeC) / saturationVaporPressure(afterC)),
              )
            : rhBefore;

          // Cooled temperature drives both the layer value and the displayed metrics.
          point.value = afterC;
          if (point.individual_metrics) {
            point.individual_metrics.avg_temperature_c = `${afterC.toFixed(1)}°C`;
            if (hasRh) {
              point.individual_metrics.relative_humidity = `${Math.round(rhAfter)}%`;
            }
          }
        }
      }
    }
  }

  return simulated;
}