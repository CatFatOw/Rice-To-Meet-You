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
 */
export function deltaTMaxFromWeather(weather: WeatherParams): number {
  const { temperatureC, relativeHumidity, fSolar = 1, fWind = 1 } = weather;

  const vpd = vaporPressureDeficit(temperatureC, relativeHumidity);
  const fVPD = Math.min(vpd / VPD_REF, 1.0);

  return DELTA_T_MAX_ANCHOR * fVPD * fSolar * fWind;
}

/**
 * Compute vegetation cooling for one cell.
 * @returns { finalTemp, deltaT } — deltaT is the SIGNED change (negative = cooling).
 */
export function vegetationCooling(
  initialTemp: number,
  params: VegetationCoolingParams,
  deltaTMax: number | WeatherParams = DELTA_T_MAX_ANCHOR,
): { finalTemp: number; deltaT: number } {
  const { vegetatedCoverage, canopyFraction, lai, waterFactor } = params;

  const deltaTMaxC =
    typeof deltaTMax === 'number' ? deltaTMax : deltaTMaxFromWeather(deltaTMax);

  // Step 1 — saturating LAI transform (Beer–Lambert), not linear.
  const fLAI = 1 - Math.exp(-LAI_EXTINCTION * lai);

  // Step 2 — the two cooling channels.
  const latent = vegetatedCoverage * fLAI * waterFactor;
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

  return { finalTemp, deltaT: -deltaT };
}

// Simulated network latency so callers can exercise their loading states.
const MOCK_LATENCY_MS = 150;
const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));


// --- High-albedo (cool surface) cooling model -------------------------------
// Cool coatings/pavements reflect more solar: absorbed solar = (1 − albedo) ×
// irradiance, so raising albedo by Δalbedo cuts surface heating proportionally.

/** Planner-chosen inputs for a high-albedo surface. All fractions are 0–1. */
export interface AlbedoCoolingParams {
  deltaAlbedo: number;   // 0–1  increase in solar reflectance vs baseline
  areaCoverage: number;  // 0–1  treated fraction of the cell (linear)
}

/** Environmental inputs — albedo cooling scales with SOLAR loading (temp proxy). */
export interface AlbedoWeatherParams {
  temperatureC: number;  // °C   air temperature (solar-loading proxy)
  fSolar?: number;       // 0–1  insolation multiplier (default 1)
}

const DELTA_T_MAX_ANCHOR_ALBEDO = 4;  // °C: pedestrian-air cooling asymptote
const DELTA_ALBEDO_REF = 0.7;         // peak realistic albedo increase (→ f_albedo = 1)
const SOLAR_PROXY_T_LOW = 20;         // °C at/below which thermal loading ≈ minimal
const SOLAR_PROXY_T_HIGH = 38;        // °C at/above which thermal loading ≈ peak

/**
 * Weather ceiling: ΔT_max = 4 °C × f_thermal × f_solar.
 */
export function deltaTMaxFromWeatherAlbedo(weather: AlbedoWeatherParams): number {
  const { temperatureC, fSolar = 1 } = weather;

  const span = SOLAR_PROXY_T_HIGH - SOLAR_PROXY_T_LOW;
  const fThermal = Math.min(
    Math.max((temperatureC - SOLAR_PROXY_T_LOW) / span, 0),
    1,
  );

  return DELTA_T_MAX_ANCHOR_ALBEDO * fThermal * fSolar;
}

/**
 * Compute high-albedo surface cooling for one cell.
 * @returns { finalTemp, deltaT } — deltaT is the SIGNED change (negative = cooling).
 */
export function albedoCooling(
  initialTemp: number,
  params: AlbedoCoolingParams,
  deltaTMax: number | AlbedoWeatherParams = DELTA_T_MAX_ANCHOR_ALBEDO,
): { finalTemp: number; deltaT: number } {
  const { deltaAlbedo, areaCoverage } = params;

  const deltaTMaxC =
    typeof deltaTMax === 'number'
      ? deltaTMax
      : deltaTMaxFromWeatherAlbedo(deltaTMax);

  // Normalized reflectance gain (linear in Δalbedo, capped at 1).
  const fAlbedo = Math.min(Math.max(deltaAlbedo, 0) / DELTA_ALBEDO_REF, 1);

  // Intensity (0–1): reflectance gain scaled linearly by treated area.
  const intensity = fAlbedo * Math.min(Math.max(areaCoverage, 0), 1);

  const deltaT = deltaTMaxC * intensity;
  const finalTemp = initialTemp - deltaT;

  return { finalTemp, deltaT: -deltaT };
}

// --- Shade structure cooling model ------------------------------------------
// Blocks the direct solar beam over a footprint (no evaporation).

export interface ShadeCoolingParams {
  opacity: number;         // 0–1  fraction of the direct beam blocked
  shadedFootprint: number; // 0–1  shaded ground as a fraction of the cell (linear)
}

export interface ShadeWeatherParams {
  temperatureC: number;    // °C   air temperature (solar-loading proxy)
  fSolar?: number;         // 0–1  insolation multiplier (default 1)
}

const DELTA_T_MAX_ANCHOR_SHADE = 5;  // °C: pedestrian-air cooling asymptote
const DIRECT_BEAM_FRACTION = 0.85;   // max blockable share of global irradiance
const SHADE_SOLAR_T_LOW = 20;
const SHADE_SOLAR_T_HIGH = 38;

/**
 * Weather ceiling: ΔT_max = 5 °C × f_thermal × f_solar × f_direct.
 */
export function deltaTMaxFromWeatherShade(weather: ShadeWeatherParams): number {
  const { temperatureC, fSolar = 1 } = weather;
  const span = SHADE_SOLAR_T_HIGH - SHADE_SOLAR_T_LOW;
  const fThermal = Math.min(Math.max((temperatureC - SHADE_SOLAR_T_LOW) / span, 0), 1);
  return DELTA_T_MAX_ANCHOR_SHADE * fThermal * fSolar * DIRECT_BEAM_FRACTION;
}

/**
 * Compute shade-structure cooling for one cell.
 * @returns { finalTemp, deltaT } — deltaT is the SIGNED change (negative = cooling).
 */
export function shadeCooling(
  initialTemp: number,
  params: ShadeCoolingParams,
  deltaTMax: number | ShadeWeatherParams = DELTA_T_MAX_ANCHOR_SHADE * DIRECT_BEAM_FRACTION,
): { finalTemp: number; deltaT: number } {
  const { opacity, shadedFootprint } = params;

  const deltaTMaxC =
    typeof deltaTMax === 'number' ? deltaTMax : deltaTMaxFromWeatherShade(deltaTMax);

  // Opacity is already the 0–1 blocked fraction — no normalization.
  const fShade = Math.min(Math.max(opacity, 0), 1);
  const intensity = fShade * Math.min(Math.max(shadedFootprint, 0), 1);

  const deltaT = deltaTMaxC * intensity;
  const finalTemp = initialTemp - deltaT;
  return { finalTemp, deltaT: -deltaT };
}


// --- Evaporative / free-water cooling model ---------------------------------
// Misting + fountains: latent heat from evaporating free water. VPD-gated, and a
// point-source plume that falls off with distance.

export interface EvaporativeCoolingParams {
  evapRateLpm: number;      // L/min  effective evaporation
  coverageRadiusM: number;  // m      plume reach — distance-falloff scale
  activeFraction: number;   // 0–1    duty cycle
}

export interface EvaporativeWeatherParams {
  temperatureC: number;      // °C
  relativeHumidity: number;  // 0–100  drives VPD, like ET
  fWind?: number;            // 0–1    wind disperses the plume (default 1)
}

const LATENT_HEAT_VAPORIZATION = 2.45e6; // J/kg at ~25 °C
const WATER_DENSITY_KG_PER_L = 1;        // kg/L
const EVAP_POWER_REF_W = 50000;          // W: latent budget that saturates I_source (calib knob)
const DELTA_T_MAX_ANCHOR_EVAP = 8;       // °C: peak-source cooling under hot, DRY conditions
const VPD_REF_EVAP = 4.5;                // kPa: peak-case VPD normalizer

/**
 * Weather ceiling: ΔT_max = 8 °C × f_VPD × f_wind.
 */
export function deltaTMaxFromWeatherEvap(weather: EvaporativeWeatherParams): number {
  const { temperatureC, relativeHumidity, fWind = 1 } = weather;
  const vpd = vaporPressureDeficit(temperatureC, relativeHumidity);
  const fVPD = Math.min(vpd / VPD_REF_EVAP, 1);
  return DELTA_T_MAX_ANCHOR_EVAP * fVPD * fWind;
}

/**
 * Evaporative cooling at a point `distanceM` from the source.
 * @returns { finalTemp, deltaT } — deltaT is the SIGNED change (negative = cooling).
 */
export function evaporativeCooling(
  initialTemp: number,
  params: EvaporativeCoolingParams,
  distanceM: number,
  deltaTMax: number | EvaporativeWeatherParams = DELTA_T_MAX_ANCHOR_EVAP,
): { finalTemp: number; deltaT: number } {
  const { evapRateLpm, coverageRadiusM, activeFraction } = params;

  const deltaTMaxC =
    typeof deltaTMax === 'number' ? deltaTMax : deltaTMaxFromWeatherEvap(deltaTMax);

  // Latent cooling power: P = ṁ · L_v  (kg/s × J/kg = W).
  const massRateKgS = (Math.max(evapRateLpm, 0) * WATER_DENSITY_KG_PER_L) / 60;
  const powerW = massRateKgS * LATENT_HEAT_VAPORIZATION;
  const iSource = Math.min(powerW / EVAP_POWER_REF_W, 1);

  // Linear plume falloff: full at the source, 0 at/beyond the coverage radius.
  const r = Math.max(distanceM, 0);
  const falloff = coverageRadiusM > 0 ? Math.max(1 - r / coverageRadiusM, 0) : 0;

  const duty = Math.min(Math.max(activeFraction, 0), 1);

  const deltaT = deltaTMaxC * iSource * duty * falloff;
  const finalTemp = initialTemp - deltaT;
  return { finalTemp, deltaT: -deltaT };
}

// --- Polygon spatial filtering ----------------------------------------------

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

/** Approx great-circle distance in meters (equirectangular; fine at city scale). */
function distanceMeters(a: [number, number], b: [number, number]): number {
  const [lon1, lat1] = a;
  const [lon2, lat2] = b;
  const midLat = ((lat1 + lat2) / 2) * (Math.PI / 180);
  const dx = (lon2 - lon1) * Math.cos(midLat) * 111320;
  const dy = (lat2 - lat1) * 110540;
  return Math.hypot(dx, dy);
}

/**
 * Filter a by-date reading set down to the points that fall inside `polygon`,
 * preserving the by-date grouping.
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

/** Source anchor for radius-based archetypes: a point's coords, or the centroid
 *  of a line/polygon. */
function geometryAnchor(geometry: {
  kind?: string;
  longitude?: number;
  latitude?: number;
  coordinates?: [number, number][];
  ring?: Polygon;
}): [number, number] {
  if (geometry.kind === 'point' && geometry.longitude != null && geometry.latitude != null) {
    return [geometry.longitude, geometry.latitude];
  }
  const pts = geometry.kind === 'line' ? geometry.coordinates : geometry.ring;
  if (!pts || pts.length === 0) return [0, 0];
  const total = pts.reduce(
    (acc, [lng, lat]) => ({ lng: acc.lng + lng, lat: acc.lat + lat }),
    { lng: 0, lat: 0 },
  );
  return [total.lng / pts.length, total.lat / pts.length];
}


// --- Assumptions about the placed-object + reading shapes -------------------

/** Archetype key whose objects cool via ET/shade. */
const VEGETATION_CATEGORY = 'Vegetation';

/** Archetype key whose objects cool by raising solar reflectance. */
const HIGH_ALBEDO_CATEGORY = 'High-albedo surface'; // ← set to your toolbox archetype key

/** Archetype key whose objects cool by blocking the direct solar beam. */
const SHADE_CATEGORY = 'Shade structure'; // ← set to your toolbox archetype key

/** Archetype key whose objects cool by free-water evaporation. */
const EVAPORATIVE_CATEGORY = 'Evaporative / water'; // ← set to your toolbox archetype key

/**
 * `change_in_temperature` points carry value 0 and no real temperature, so the
 * weather-derived ceilings (especially the solar-proxy ones) would collapse.
 * Use a representative hot-day temperature as a stopgap. The honest fix is to
 * look up the co-located temperature reading and pass that instead.
 */
const CHANGE_IN_TEMP_ASSUMED_C = 34;

/** Canopy fraction default when the toolbox param omits it. */
const DEFAULT_CANOPY_FRACTION = 1;

/** Toolbox param bag on a placed vegetation object. */
type PlacedVegetationParams = {
  coverPct?: number;      // -> vegetatedCoverage
  lai?: number;           // -> lai
  irrigation?: number;    // -> waterFactor
  canopyFraction?: number;// -> canopyFraction (optional)
};

/** A placed object contributes a footprint only if it is a drawn polygon. */
function getObjectPolygon(object: { kind?: string; ring?: Polygon }): Polygon | null {
  return object.kind === 'polygon' && object.ring ? object.ring : null;
}

/** Map a placed object's toolbox params onto the vegetation model's inputs. */
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

function getAlbedoParams(
  object: { params?: { deltaAlbedo?: number; coverPct?: number } },
): AlbedoCoolingParams | null {
  const p = object.params;
  if (!p || p.deltaAlbedo == null || p.coverPct == null) return null;
  return { deltaAlbedo: p.deltaAlbedo, areaCoverage: p.coverPct };
}

/** Map a placed shade object's params onto the shade model's inputs. */
function getShadeParams(
  object: { params?: { opacity?: number; footprintFraction?: number } },
): ShadeCoolingParams | null {
  const p = object.params;
  if (!p || p.opacity == null || p.footprintFraction == null) return null;
  return { opacity: p.opacity, shadedFootprint: p.footprintFraction };
}

function getEvaporativeParams(
  object: {
    params?: { evapRateLpm?: number; coverageRadiusM?: number; activeFraction?: number };
  },
): EvaporativeCoolingParams | null {
  const p = object.params;
  if (!p || p.evapRateLpm == null || p.coverageRadiusM == null || p.activeFraction == null) {
    return null;
  }
  return {
    evapRateLpm: p.evapRateLpm,
    coverageRadiusM: p.coverageRadiusM,
    activeFraction: p.activeFraction,
  };
}

/** This model only moves temperature; leave other metrics untouched. */
function metricIsTemperature(metric: string): boolean {
  return /temp/i.test(metric);
}

function filterByActiveWindow(
  pointsByDate: HeatmapPointsByDate,
  activeFrom?: string,
  activeTo?: string,
): HeatmapPointsByDate {
  const from = activeFrom ? new Date(activeFrom).getTime() : -Infinity;
  const to = activeTo ? new Date(activeTo).getTime() : Infinity;

  const result: HeatmapPointsByDate = {};
  for (const [date, points] of Object.entries(pointsByDate)) {
    const t = new Date(date).getTime();
    if (t >= from && t <= to) {
      result[date] = points; // keep reference so mutations propagate
    }
  }
  return result;
}

/**
 * Run the intervention simulation for one metric.
 * Works on a clone so the caller's baseline pointsByDate is never mutated.
 */
/**
 * Run the intervention simulation for one metric.
 * Works on a clone so the caller's baseline pointsByDate is never mutated.
 */
export async function getSimulatedPointsByDate(
  metric: string,
  pointsByDate: HeatmapPointsByDate,
  placedObjects: BasePlacedObjectCategorized,
): Promise<HeatmapPointsByDate> {
  await delay(MOCK_LATENCY_MS);

  const simulated: HeatmapPointsByDate = Object.fromEntries(
    Object.entries(pointsByDate).map(([date, points]) => [
      date,
      points.map((p) => structuredClone(p)),
    ]),
  );
  const affectsTemperature = metricIsTemperature(metric);
  const isChangeInTemp = metric === 'change_in_temperature';

  for (const [category, objects] of Object.entries(placedObjects)) {
    const isVegetation = category === VEGETATION_CATEGORY;
    const isHighAlbedo = category === HIGH_ALBEDO_CATEGORY;
    const isShade = category === SHADE_CATEGORY;
    const isEvaporative = category === EVAPORATIVE_CATEGORY;

    // Only these archetypes move temperature; skip everything else.
    if (
      (!isVegetation && !isHighAlbedo && !isShade && !isEvaporative) ||
      !affectsTemperature
    ) {
      continue;
    }

    for (const object of objects) {
      // --- Evaporative: point-source plume, no polygon. Gather points within
      //     the coverage radius of the source and apply a distance falloff. ---
      if (isEvaporative) {
        const evapParams = getEvaporativeParams(object);
        if (!evapParams) continue;

        const source = geometryAnchor(object.geometry);
        const activeByDate = filterByActiveWindow(
          simulated,
          object.activeFrom,
          object.activeTo,
        );

        for (const points of Object.values(activeByDate)) {
          for (const point of points) {
            const dist = distanceMeters(source, point.location_coordinates);
            if (dist > evapParams.coverageRadiusM) continue; // outside the plume

            const beforeC = point.value;
            const rhBefore = parseFloat(
              point.individual_metrics?.relative_humidity ?? '',
            );
            const hasRh = Number.isFinite(rhBefore);

            // Weather ceiling needs the real temperature. On the ΔT layer the
            // point value is 0, so read the temperature shared into the metrics
            // (fall back to a representative hot day if it's missing).
            const metricTempC = parseFloat(
              point.individual_metrics?.avg_temperature_c ?? '',
            );
            const weatherTempC = isChangeInTemp
              ? (Number.isFinite(metricTempC) ? metricTempC : CHANGE_IN_TEMP_ASSUMED_C)
              : beforeC;

            const { finalTemp: afterC, deltaT } = hasRh
              ? evaporativeCooling(beforeC, evapParams, dist, {
                  temperatureC: weatherTempC,
                  relativeHumidity: rhBefore,
                })
              : evaporativeCooling(beforeC, evapParams, dist);

            if (isChangeInTemp) {
              point.value = deltaT;
              continue;
            }

            // Evaporation adds vapor → RH rises (same coupling as vegetation).
            const rhAfter = hasRh
              ? Math.min(
                  100,
                  rhBefore *
                    (saturationVaporPressure(beforeC) /
                      saturationVaporPressure(afterC)),
                )
              : rhBefore;

            point.value = afterC;
            if (point.individual_metrics) {
              point.individual_metrics.avg_temperature_c = `${afterC.toFixed(1)}°C`;
              if (hasRh) {
                point.individual_metrics.relative_humidity = `${Math.round(rhAfter)}%`;
              }
            }
          }
        }

        continue; // handled — skip the polygon/footprint path below
      }

      // --- Footprint archetypes (vegetation / albedo / shade): polygon path ---
      const polygon = getObjectPolygon(object.geometry);
      if (!polygon) continue;

      const activeByDate = filterByActiveWindow(
        simulated,
        object.activeFrom,
        object.activeTo,
      );
      const covered = pointsInsidePolygonByDate(activeByDate, polygon);

      // Resolve params for whichever model this category uses.
      const vegParams = isVegetation ? getCoolingParams(object) : null;
      const albedoParams = isHighAlbedo ? getAlbedoParams(object) : null;
      const shadeParams = isShade ? getShadeParams(object) : null;
      if (!vegParams && !albedoParams && !shadeParams) continue;

      for (const points of Object.values(covered)) {
        for (const point of points) {
          const beforeC = point.value;
          const rhBefore = parseFloat(
            point.individual_metrics?.relative_humidity ?? '',
          );
          const hasRh = Number.isFinite(rhBefore);

          // Weather ceiling needs the real temperature. On the ΔT layer the
          // point value is 0, so read the temperature shared into the metrics
          // (fall back to a representative hot day if it's missing).
          const metricTempC = parseFloat(
            point.individual_metrics?.avg_temperature_c ?? '',
          );
          const weatherTempC = isChangeInTemp
            ? (Number.isFinite(metricTempC) ? metricTempC : CHANGE_IN_TEMP_ASSUMED_C)
            : beforeC;

          let afterC: number;
          let deltaT: number;

          if (vegParams) {
            ({ finalTemp: afterC, deltaT } = hasRh
              ? vegetationCooling(beforeC, vegParams, {
                  temperatureC: weatherTempC,
                  relativeHumidity: rhBefore,
                })
              : vegetationCooling(beforeC, vegParams));
          } else if (albedoParams) {
            ({ finalTemp: afterC, deltaT } = albedoCooling(beforeC, albedoParams, {
              temperatureC: weatherTempC,
            }));
          } else {
            // Shade: solar-driven, temperature only, no humidity coupling.
            ({ finalTemp: afterC, deltaT } = shadeCooling(beforeC, shadeParams!, {
              temperatureC: weatherTempC,
            }));
          }

          if (isChangeInTemp) {
            point.value = deltaT;
            continue;
          }

          // Humidity rises only for evapotranspiration (vegetation), never for
          // albedo/shade — those add no water vapor.
          const rhAfter =
            vegParams && hasRh
              ? Math.min(
                  100,
                  rhBefore *
                    (saturationVaporPressure(beforeC) /
                      saturationVaporPressure(afterC)),
                )
              : rhBefore;

          point.value = afterC;
          if (point.individual_metrics) {
            point.individual_metrics.avg_temperature_c = `${afterC.toFixed(1)}°C`;
            if (vegParams && hasRh) {
              point.individual_metrics.relative_humidity = `${Math.round(rhAfter)}%`;
            }
          }
        }
      }
    }
  }

  return simulated;
}