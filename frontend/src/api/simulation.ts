// /**
//  * =============================================================================
//  * Urban heat intervention simulation
//  * =============================================================================
//  *
//  * Estimates how planner-placed cooling interventions change pedestrian-level
//  * temperature (and, where relevant, relative humidity) across a heatmap of
//  * point readings grouped by date.
//  *
//  * Four intervention archetypes are modelled, each with its own physics:
//  *   1. Vegetation        — latent (transpiration) + shade cooling over a polygon
//  *   2. High-albedo surface — reflects more solar over a polygon
//  *   3. Shade structure   — blocks the direct solar beam over a polygon
//  *   4. Evaporative/water — misting/fountain plume from a point source
//  *
//  * Shared shape of every model:
//  *   - A weather-derived ceiling ΔT_max (the most cooling physically available
//  *     under the current conditions).
//  *   - A dimensionless intensity in [0, 1] derived from the planner's inputs.
//  *   - deltaT = ΔT_max × intensity, applied to the initial temperature.
//  *
//  * Sign convention (IMPORTANT): every model returns `finalTemp` plus a SIGNED
//  * `deltaT`, where negative means cooling. The internal `deltaT` variable used
//  * before the return is the positive magnitude; the returned field negates it.
//  *
//  * The public entry point is `getSimulatedPointsByDate`, which applies every
//  * placed object to a cloned copy of the readings and returns the result.
//  */

// import type { HeatmapPointsByDate, HeatmapMetricValue } from '../types/heatmap';
// import type { BasePlacedObject, BasePlacedObjectCategorized } from '../hooks/usePlacedObjects';
// import type { Polygon } from '../types/heatmap';
// import { parseTemperature, parsePercentage } from '../services/parsers';

// // --- Vegetation cooling model ------------------------------------------------
// // Estimates the pedestrian-level temperature drop from vegetation via two
// // channels — latent (transpiration) and shade — combined into a 0–1 intensity
// // and scaled to a ΔT. See derivation for the physics behind each step.

// /** Planner-chosen inputs for a cell/archetype. All fractions are 0–1. */
// export interface VegetationCoolingParams {
//   vegetatedCoverage: number; // 0–1  fraction of ground with vegetation
//   canopyFraction: number;    // 0–1  fraction of that vegetation under crown
//   lai: number;               // ~0–6 Leaf Area Index (dimensionless)
//   waterFactor: number;       // 0–1  water availability / irrigation gate
// }

// /**
//  * Environmental inputs that set the cooling ceiling (ΔT_max). Temperature and
//  * humidity drive the ET potential via VPD; solar and wind are held at 1 unless
//  * you have data to scale them.
//  */
// export interface WeatherParams {
//   temperatureC: number;      // °C   air temperature
//   relativeHumidity: number;  // 0–100 (percent) relative humidity
//   fSolar?: number;           // 0–1  insolation multiplier (default 1 — see note)
//   fWind?: number;            // 0–1  wind multiplier      (default 1 — see note)
// }

// // --- Model constants (the real calibration knobs) ---------------------------
// // These encode model physics, not planner choices — point literature-fitting
// // here rather than at the four inputs.
// const SHADE_DROUGHT_SURVIVAL = 0.8; // g: fraction of shade effect that survives WaterFactor=0 (~0.7–0.85)
// const WEIGHT_LATENT = 0.4;          // w_L: relative weight of the latent/ET channel
// const WEIGHT_SHADE = 0.6;           // w_S: relative weight of the shade channel  (w_L + w_S = 1)
// const LAI_EXTINCTION = 0.5;         // Beer–Lambert extinction coefficient in f_LAI
// const DELTA_T_MAX_ANCHOR = 5;       // °C: cooling asymptote under hot-dry-sunny-calm conditions
// const VPD_REF = 4.5;                // kPa: peak-case VPD used to normalize f_VPD (38 °C / 28% RH ≈ 4.8)

// /**
//  * Saturation vapor pressure (kPa) from air temperature (°C) — Tetens equation.
//  * The maximum water vapor the air can hold at the given temperature; rises
//  * steeply with heat, which is why hot air has more evaporative "room".
//  */
// export function saturationVaporPressure(temperatureC: number): number {
//   return 0.6108 * Math.exp((17.27 * temperatureC) / (temperatureC + 237.3));
// }

// /**
//  * Vapor pressure deficit (kPa) — the gap between how much moisture the air
//  * could hold and how much it currently holds. Larger VPD = drier air = more
//  * evaporative cooling potential.
//  *
//  * @param temperatureC     air temperature (°C)
//  * @param relativeHumidity relative humidity (0–100)
//  */
// export function vaporPressureDeficit(temperatureC: number, relativeHumidity: number): number {
//   return saturationVaporPressure(temperatureC) * (1 - relativeHumidity / 100);
// }

// /**
//  * Weather-dependent cooling ceiling for vegetation:
//  *   ΔT_max = 5 °C × f_VPD × f_solar × f_wind
//  *
//  * f_VPD scales the anchor by how dry the air is (capped at 1 at the reference
//  * VPD); f_solar and f_wind default to 1 unless real data is supplied.
//  */
// export function deltaTMaxFromWeather(weather: WeatherParams): number {
//   const { temperatureC, relativeHumidity, fSolar = 1, fWind = 1 } = weather;

//   const vpd = vaporPressureDeficit(temperatureC, relativeHumidity);
//   const fVPD = Math.min(vpd / VPD_REF, 1.0); // normalize to [0, 1] against the peak-case VPD

//   return DELTA_T_MAX_ANCHOR * fVPD * fSolar * fWind;
// }

// /**
//  * Compute vegetation cooling for one cell.
//  *
//  * @param initialTemp starting temperature at the cell (°C)
//  * @param params      planner-chosen vegetation inputs
//  * @param deltaTMax   either a fixed ceiling (°C) or WeatherParams to derive one
//  * @returns { finalTemp, deltaT } — deltaT is the SIGNED change (negative = cooling).
//  */
// export function vegetationCooling(
//   initialTemp: number,
//   params: VegetationCoolingParams,
//   deltaTMax: number | WeatherParams = DELTA_T_MAX_ANCHOR,
// ): { finalTemp: number; deltaT: number } {
//   const { vegetatedCoverage, canopyFraction, lai, waterFactor } = params;

//   // Accept a precomputed ceiling, or derive it from weather.
//   const deltaTMaxC =
//     typeof deltaTMax === 'number' ? deltaTMax : deltaTMaxFromWeather(deltaTMax);

//   // Step 1 — saturating LAI transform (Beer–Lambert), not linear.
//   // Extra leaf area gives diminishing returns as the canopy closes.
//   const fLAI = 1 - Math.exp(-LAI_EXTINCTION * lai);

//   // Step 2 — the two cooling channels.
//   // Latent: transpiration, gated fully by water availability.
//   const latent = vegetatedCoverage * fLAI * waterFactor;
//   // Shade: canopy blocking sun; partly survives drought (leaves still cast shade
//   // even when transpiration stops), controlled by SHADE_DROUGHT_SURVIVAL.
//   const shade =
//     vegetatedCoverage *
//     canopyFraction *
//     fLAI *
//     (SHADE_DROUGHT_SURVIVAL + (1 - SHADE_DROUGHT_SURVIVAL) * waterFactor);

//   // Step 3 — combine into normalized intensity (0–1) via the channel weights.
//   const intensity = WEIGHT_LATENT * latent + WEIGHT_SHADE * shade;

//   // Step 4 — scale to a temperature drop, then apply to the initial temp.
//   const deltaT = deltaTMaxC * intensity; // positive magnitude
//   const finalTemp = initialTemp - deltaT;

//   return { finalTemp, deltaT: -deltaT }; // negate so callers see cooling as < 0
// }

// // Simulated network latency so callers can exercise their loading states.
// const MOCK_LATENCY_MS = 150;
// const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));


// // --- High-albedo (cool surface) cooling model -------------------------------
// // Cool coatings/pavements reflect more solar: absorbed solar = (1 − albedo) ×
// // irradiance, so raising albedo by Δalbedo cuts surface heating proportionally.

// /** Planner-chosen inputs for a high-albedo surface. All fractions are 0–1. */
// export interface AlbedoCoolingParams {
//   deltaAlbedo: number;   // 0–1  increase in solar reflectance vs baseline
//   areaCoverage: number;  // 0–1  treated fraction of the cell (linear)
// }

// /** Environmental inputs — albedo cooling scales with SOLAR loading (temp proxy). */
// export interface AlbedoWeatherParams {
//   temperatureC: number;  // °C   air temperature (solar-loading proxy)
//   fSolar?: number;       // 0–1  insolation multiplier (default 1)
// }

// const DELTA_T_MAX_ANCHOR_ALBEDO = 4;  // °C: pedestrian-air cooling asymptote
// const DELTA_ALBEDO_REF = 0.7;         // peak realistic albedo increase (→ f_albedo = 1)
// const SOLAR_PROXY_T_LOW = 20;         // °C at/below which thermal loading ≈ minimal
// const SOLAR_PROXY_T_HIGH = 38;        // °C at/above which thermal loading ≈ peak

// /**
//  * Weather ceiling for high-albedo surfaces:
//  *   ΔT_max = 4 °C × f_thermal × f_solar
//  *
//  * There is no VPD term (reflectance doesn't depend on humidity); instead a
//  * temperature-based f_thermal ramps linearly from 0 at SOLAR_PROXY_T_LOW to 1
//  * at SOLAR_PROXY_T_HIGH, standing in for solar loading.
//  */
// export function deltaTMaxFromWeatherAlbedo(weather: AlbedoWeatherParams): number {
//   const { temperatureC, fSolar = 1 } = weather;

//   const span = SOLAR_PROXY_T_HIGH - SOLAR_PROXY_T_LOW;
//   const fThermal = Math.min(
//     Math.max((temperatureC - SOLAR_PROXY_T_LOW) / span, 0),
//     1,
//   ); // clamp the linear ramp to [0, 1]

//   return DELTA_T_MAX_ANCHOR_ALBEDO * fThermal * fSolar;
// }

// /**
//  * Compute high-albedo surface cooling for one cell.
//  *
//  * @param initialTemp starting temperature at the cell (°C)
//  * @param params      planner-chosen albedo inputs
//  * @param deltaTMax   either a fixed ceiling (°C) or AlbedoWeatherParams
//  * @returns { finalTemp, deltaT } — deltaT is the SIGNED change (negative = cooling).
//  */
// export function albedoCooling(
//   initialTemp: number,
//   params: AlbedoCoolingParams,
//   deltaTMax: number | AlbedoWeatherParams = DELTA_T_MAX_ANCHOR_ALBEDO,
// ): { finalTemp: number; deltaT: number } {
//   const { deltaAlbedo, areaCoverage } = params;

//   const deltaTMaxC =
//     typeof deltaTMax === 'number'
//       ? deltaTMax
//       : deltaTMaxFromWeatherAlbedo(deltaTMax);

//   // Normalized reflectance gain (linear in Δalbedo, capped at 1).
//   const fAlbedo = Math.min(Math.max(deltaAlbedo, 0) / DELTA_ALBEDO_REF, 1);

//   // Intensity (0–1): reflectance gain scaled linearly by treated area.
//   const intensity = fAlbedo * Math.min(Math.max(areaCoverage, 0), 1);

//   const deltaT = deltaTMaxC * intensity;
//   const finalTemp = initialTemp - deltaT;

//   return { finalTemp, deltaT: -deltaT };
// }

// // --- Shade structure cooling model ------------------------------------------
// // Blocks the direct solar beam over a footprint (no evaporation).

// /** Planner-chosen inputs for a shade structure. All fractions are 0–1. */
// export interface ShadeCoolingParams {
//   opacity: number;         // 0–1  fraction of the direct beam blocked
//   shadedFootprint: number; // 0–1  shaded ground as a fraction of the cell (linear)
// }

// /** Environmental inputs — shade cooling scales with SOLAR loading (temp proxy). */
// export interface ShadeWeatherParams {
//   temperatureC: number;    // °C   air temperature (solar-loading proxy)
//   fSolar?: number;         // 0–1  insolation multiplier (default 1)
// }

// const DELTA_T_MAX_ANCHOR_SHADE = 5;  // °C: pedestrian-air cooling asymptote
// const DIRECT_BEAM_FRACTION = 0.85;   // max blockable share of global irradiance
// const SHADE_SOLAR_T_LOW = 20;        // °C floor of the solar-proxy ramp
// const SHADE_SOLAR_T_HIGH = 38;       // °C ceiling of the solar-proxy ramp

// /**
//  * Weather ceiling for shade structures:
//  *   ΔT_max = 5 °C × f_thermal × f_solar × f_direct
//  *
//  * Like albedo, uses a temperature-based solar proxy (f_thermal). The extra
//  * DIRECT_BEAM_FRACTION caps the effect at the blockable (direct-beam) share of
//  * irradiance — diffuse sky radiation still reaches the ground under shade.
//  */
// export function deltaTMaxFromWeatherShade(weather: ShadeWeatherParams): number {
//   const { temperatureC, fSolar = 1 } = weather;
//   const span = SHADE_SOLAR_T_HIGH - SHADE_SOLAR_T_LOW;
//   const fThermal = Math.min(Math.max((temperatureC - SHADE_SOLAR_T_LOW) / span, 0), 1);
//   return DELTA_T_MAX_ANCHOR_SHADE * fThermal * fSolar * DIRECT_BEAM_FRACTION;
// }

// /**
//  * Compute shade-structure cooling for one cell.
//  *
//  * @param initialTemp starting temperature at the cell (°C)
//  * @param params      planner-chosen shade inputs
//  * @param deltaTMax   either a fixed ceiling (°C) or ShadeWeatherParams. The
//  *                    numeric default already folds in DIRECT_BEAM_FRACTION.
//  * @returns { finalTemp, deltaT } — deltaT is the SIGNED change (negative = cooling).
//  */
// export function shadeCooling(
//   initialTemp: number,
//   params: ShadeCoolingParams,
//   deltaTMax: number | ShadeWeatherParams = DELTA_T_MAX_ANCHOR_SHADE * DIRECT_BEAM_FRACTION,
// ): { finalTemp: number; deltaT: number } {
//   const { opacity, shadedFootprint } = params;

//   const deltaTMaxC =
//     typeof deltaTMax === 'number' ? deltaTMax : deltaTMaxFromWeatherShade(deltaTMax);

//   // Opacity is already the 0–1 blocked fraction — no normalization.
//   const fShade = Math.min(Math.max(opacity, 0), 1);
//   const intensity = fShade * Math.min(Math.max(shadedFootprint, 0), 1);

//   const deltaT = deltaTMaxC * intensity;
//   const finalTemp = initialTemp - deltaT;
//   return { finalTemp, deltaT: -deltaT };
// }


// // --- Evaporative / free-water cooling model ---------------------------------
// // Misting + fountains: latent heat from evaporating free water. VPD-gated, and a
// // point-source plume that falls off with distance.

// /** Planner-chosen inputs for an evaporative source (misting/fountain). */
// export interface EvaporativeCoolingParams {
//   evapRateLpm: number;      // L/min  effective evaporation
//   coverageRadiusM: number;  // m      plume reach — distance-falloff scale
//   activeFraction: number;   // 0–1    duty cycle
// }

// /** Environmental inputs — evaporation is VPD-gated and wind-dispersed. */
// export interface EvaporativeWeatherParams {
//   temperatureC: number;      // °C
//   relativeHumidity: number;  // 0–100  drives VPD, like ET
//   fWind?: number;            // 0–1    wind disperses the plume (default 1)
// }

// const LATENT_HEAT_VAPORIZATION = 2.45e6; // J/kg at ~25 °C
// const WATER_DENSITY_KG_PER_L = 1;        // kg/L
// const EVAP_POWER_REF_W = 50000;          // W: latent budget that saturates I_source (calib knob)
// const DELTA_T_MAX_ANCHOR_EVAP = 8;       // °C: peak-source cooling under hot, DRY conditions
// const VPD_REF_EVAP = 4.5;                // kPa: peak-case VPD normalizer

// /**
//  * Weather ceiling for evaporative sources:
//  *   ΔT_max = 8 °C × f_VPD × f_wind
//  *
//  * VPD-gated like vegetation's latent channel; wind lowers the ceiling by
//  * dispersing the plume before it can cool the air.
//  */
// export function deltaTMaxFromWeatherEvap(weather: EvaporativeWeatherParams): number {
//   const { temperatureC, relativeHumidity, fWind = 1 } = weather;
//   const vpd = vaporPressureDeficit(temperatureC, relativeHumidity);
//   const fVPD = Math.min(vpd / VPD_REF_EVAP, 1);
//   return DELTA_T_MAX_ANCHOR_EVAP * fVPD * fWind;
// }

// /**
//  * Evaporative cooling at a point `distanceM` from the source.
//  *
//  * Combines a source-strength term (how much latent power the emitter provides,
//  * saturating at EVAP_POWER_REF_W) with a linear distance falloff and a duty
//  * cycle. Points beyond the coverage radius receive nothing.
//  *
//  * @param initialTemp starting temperature at the point (°C)
//  * @param params      planner-chosen evaporative inputs
//  * @param distanceM   distance from the source to this point (m)
//  * @param deltaTMax   either a fixed ceiling (°C) or EvaporativeWeatherParams
//  * @returns { finalTemp, deltaT } — deltaT is the SIGNED change (negative = cooling).
//  */
// export function evaporativeCooling(
//   initialTemp: number,
//   params: EvaporativeCoolingParams,
//   distanceM: number,
//   deltaTMax: number | EvaporativeWeatherParams = DELTA_T_MAX_ANCHOR_EVAP,
// ): { finalTemp: number; deltaT: number } {
//   const { evapRateLpm, coverageRadiusM, activeFraction } = params;

//   const deltaTMaxC =
//     typeof deltaTMax === 'number' ? deltaTMax : deltaTMaxFromWeatherEvap(deltaTMax);

//   // Latent cooling power: P = ṁ · L_v  (kg/s × J/kg = W).
//   const massRateKgS = (Math.max(evapRateLpm, 0) * WATER_DENSITY_KG_PER_L) / 60;
//   const powerW = massRateKgS * LATENT_HEAT_VAPORIZATION;
//   const iSource = Math.min(powerW / EVAP_POWER_REF_W, 1); // normalize to [0, 1]

//   // Linear plume falloff: full at the source, 0 at/beyond the coverage radius.
//   const r = Math.max(distanceM, 0);
//   const falloff = coverageRadiusM > 0 ? Math.max(1 - r / coverageRadiusM, 0) : 0;

//   const duty = Math.min(Math.max(activeFraction, 0), 1); // fraction of time active

//   const deltaT = deltaTMaxC * iSource * duty * falloff;
//   const finalTemp = initialTemp - deltaT;
//   return { finalTemp, deltaT: -deltaT };
// }

// // --- Polygon spatial filtering ----------------------------------------------
// // Helpers to decide which readings fall inside a drawn intervention footprint.

// /** Axis-aligned lon/lat extent of a polygon — a cheap pre-filter. */
// type BoundingBox = {
//   minLon: number;
//   minLat: number;
//   maxLon: number;
//   maxLat: number;
// };

// /** Compute the bounding box (min/max lon & lat) enclosing a polygon's vertices. */
// function getBoundingBox(polygon: Polygon): BoundingBox {
//   let minLon = Infinity;
//   let minLat = Infinity;
//   let maxLon = -Infinity;
//   let maxLat = -Infinity;

//   for (const [lon, lat] of polygon) {
//     minLon = Math.min(minLon, lon);
//     minLat = Math.min(minLat, lat);
//     maxLon = Math.max(maxLon, lon);
//     maxLat = Math.max(maxLat, lat);
//   }

//   return { minLon, minLat, maxLon, maxLat };
// }

// /** Fast rejection test: is (lon, lat) within the polygon's bounding box? */
// function isInsideBoundingBox(
//   lon: number,
//   lat: number,
//   bbox: BoundingBox,
// ): boolean {
//   return (
//     lon >= bbox.minLon &&
//     lon <= bbox.maxLon &&
//     lat >= bbox.minLat &&
//     lat <= bbox.maxLat
//   );
// }

// /**
//  * Ray-casting point-in-polygon test. Counts how many polygon edges a horizontal
//  * ray from the point crosses; an odd count means the point is inside.
//  */
// function pointInPolygon(
//   lon: number,
//   lat: number,
//   polygon: Polygon,
// ): boolean {
//   let inside = false;

//   // Walk each edge (i, j) where j trails i by one, wrapping at the end.
//   for (
//     let i = 0, j = polygon.length - 1;
//     i < polygon.length;
//     j = i++
//   ) {
//     const [xi, yi] = polygon[i];
//     const [xj, yj] = polygon[j];

//     // Edge straddles the ray's latitude AND the crossing is to the point's right.
//     const crossesRay =
//       yi > lat !== yj > lat &&
//       lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;

//     if (crossesRay) {
//       inside = !inside; // toggle on each crossing
//     }
//   }

//   return inside;
// }

// /**
//  * True if a single reading's coordinates fall inside the polygon. Applies the
//  * cheap bounding-box check first, then the exact ray-cast test.
//  */
// function isPointInsidePolygon(
//   point: HeatmapMetricValue,
//   polygon: Polygon,
//   bbox: BoundingBox,
// ): boolean {
//   const [lon, lat] = point.location_coordinates;
//   if (!isInsideBoundingBox(lon, lat, bbox)) {
//     return false; // outside the box → cannot be inside the polygon
//   }
//   return pointInPolygon(lon, lat, polygon);
// }

// /**
//  * Approx great-circle distance in meters (equirectangular; fine at city scale).
//  * Projects lon/lat to local meters using the mean latitude, then Pythagoras.
//  */
// function distanceMeters(a: [number, number], b: [number, number]): number {
//   const [lon1, lat1] = a;
//   const [lon2, lat2] = b;
//   const midLat = ((lat1 + lat2) / 2) * (Math.PI / 180);
//   const dx = (lon2 - lon1) * Math.cos(midLat) * 111320; // meters per degree lon at this lat
//   const dy = (lat2 - lat1) * 110540;                    // meters per degree lat
//   return Math.hypot(dx, dy);
// }

// /**
//  * Filter a by-date reading set down to the points that fall inside `polygon`,
//  * preserving the by-date grouping. Dates with no interior points are dropped.
//  */
// function pointsInsidePolygonByDate(
//   pointsByDate: HeatmapPointsByDate,
//   polygon: Polygon,
// ): HeatmapPointsByDate {
//   const bbox = getBoundingBox(polygon); // compute once, reuse across all points
//   const result: HeatmapPointsByDate = {};

//   for (const [date, points] of Object.entries(pointsByDate)) {
//     const inside = points.filter((point) =>
//       isPointInsidePolygon(point, polygon, bbox),
//     );

//     if (inside.length > 0) {
//       result[date] = inside;
//     }
//   }

//   return result;
// }

// /**
//  * Source anchor for radius-based archetypes: a point's coords, or the centroid
//  * of a line/polygon. Used to locate the emitter for evaporative sources.
//  */
// function geometryAnchor(geometry: {
//   kind?: string;
//   longitude?: number;
//   latitude?: number;
//   coordinates?: [number, number][];
//   ring?: Polygon;
// }): [number, number] {
//   // A point geometry is its own anchor.
//   if (geometry.kind === 'point' && geometry.longitude != null && geometry.latitude != null) {
//     return [geometry.longitude, geometry.latitude];
//   }
//   // Otherwise average the vertices (line coordinates or polygon ring).
//   const pts = geometry.kind === 'line' ? geometry.coordinates : geometry.ring;
//   if (!pts || pts.length === 0) return [0, 0];
//   const total = pts.reduce(
//     (acc, [lng, lat]) => ({ lng: acc.lng + lng, lat: acc.lat + lat }),
//     { lng: 0, lat: 0 },
//   );
//   return [total.lng / pts.length, total.lat / pts.length];
// }


// // --- Assumptions about the placed-object + reading shapes -------------------
// // Category keys and param mappings that bridge the toolbox's placed objects to
// // the physics models above. Adjust the *_CATEGORY strings to match your toolbox.

// /** Archetype key whose objects cool via ET/shade. */
// const VEGETATION_CATEGORY = 'Vegetation';

// /** Archetype key whose objects cool by raising solar reflectance. */
// const HIGH_ALBEDO_CATEGORY = 'High-albedo surface'; // ← set to your toolbox archetype key

// /** Archetype key whose objects cool by blocking the direct solar beam. */
// const SHADE_CATEGORY = 'Shade structure'; // ← set to your toolbox archetype key

// /** Archetype key whose objects cool by free-water evaporation. */
// const EVAPORATIVE_CATEGORY = 'Evaporative / water'; // ← set to your toolbox archetype key

// /**
//  * `change_in_temperature` points carry value 0 and no real temperature, so the
//  * weather-derived ceilings (especially the solar-proxy ones) would collapse.
//  * Use a representative hot-day temperature as a stopgap. The honest fix is to
//  * look up the co-located temperature reading and pass that instead.
//  */
// const CHANGE_IN_TEMP_ASSUMED_C = 34;

// /** Canopy fraction default when the toolbox param omits it. */
// const DEFAULT_CANOPY_FRACTION = 1;

// /** Toolbox param bag on a placed vegetation object. */
// type PlacedVegetationParams = {
//   coverPct?: number;      // -> vegetatedCoverage
//   lai?: number;           // -> lai
//   irrigation?: number;    // -> waterFactor
//   canopyFraction?: number;// -> canopyFraction (optional)
// };

// /** A placed object contributes a footprint only if it is a drawn polygon. */
// function getObjectPolygon(object: { kind?: string; ring?: Polygon }): Polygon | null {
//   return object.kind === 'polygon' && object.ring ? object.ring : null;
// }

// /**
//  * Map a placed object's toolbox params onto the vegetation model's inputs.
//  * Returns null if any required field is missing, so callers can skip the object.
//  */
// function getCoolingParams(
//   object: { params?: PlacedVegetationParams },
// ): VegetationCoolingParams | null {
//   const p = object.params;
//   if (!p || p.coverPct == null || p.lai == null || p.irrigation == null) {
//     return null;
//   }
//   return {
//     vegetatedCoverage: p.coverPct,
//     canopyFraction: p.canopyFraction ?? DEFAULT_CANOPY_FRACTION,
//     lai: p.lai,
//     waterFactor: p.irrigation,
//   };
// }

// /**
//  * Map a placed object's params onto the albedo model's inputs.
//  * Returns null if required fields are missing.
//  */
// function getAlbedoParams(
//   object: { params?: { deltaAlbedo?: number; coverPct?: number } },
// ): AlbedoCoolingParams | null {
//   const p = object.params;
//   if (!p || p.deltaAlbedo == null || p.coverPct == null) return null;
//   return { deltaAlbedo: p.deltaAlbedo, areaCoverage: p.coverPct };
// }

// /**
//  * Map a placed shade object's params onto the shade model's inputs.
//  * Returns null if required fields are missing.
//  */
// function getShadeParams(
//   object: { params?: { opacity?: number; footprintFraction?: number } },
// ): ShadeCoolingParams | null {
//   const p = object.params;
//   if (!p || p.opacity == null || p.footprintFraction == null) return null;
//   return { opacity: p.opacity, shadedFootprint: p.footprintFraction };
// }

// /**
//  * Map a placed object's params onto the evaporative model's inputs.
//  * Returns null if required fields are missing.
//  */
// function getEvaporativeParams(
//   object: {
//     params?: { evapRateLpm?: number; coverageRadiusM?: number; activeFraction?: number };
//   },
// ): EvaporativeCoolingParams | null {
//   const p = object.params;
//   if (!p || p.evapRateLpm == null || p.coverageRadiusM == null || p.activeFraction == null) {
//     return null;
//   }
//   return {
//     evapRateLpm: p.evapRateLpm,
//     coverageRadiusM: p.coverageRadiusM,
//     activeFraction: p.activeFraction,
//   };
// }

// /** This model only moves temperature; leave other metrics untouched. */
// function metricIsTemperature(metric: string): boolean {
//   return metric === 'average_temperature_c' || metric === 'change_in_temperature';
// }

// /**
//  * Keep only the dates that fall within an intervention's [activeFrom, activeTo]
//  * window (either bound optional → open-ended on that side). The point arrays are
//  * kept by reference so downstream mutations propagate back to `simulated`.
//  */
// function filterByActiveWindow(
//   pointsByDate: HeatmapPointsByDate,
//   activeFrom?: string,
//   activeTo?: string,
// ): HeatmapPointsByDate {
//   const from = activeFrom ? new Date(activeFrom).getTime() : -Infinity;
//   const to = activeTo ? new Date(activeTo).getTime() : Infinity;

//   const result: HeatmapPointsByDate = {};
//   for (const [date, points] of Object.entries(pointsByDate)) {
//     const t = new Date(date).getTime();
//     if (t >= from && t <= to) {
//       result[date] = points; // keep reference so mutations propagate
//     }
//   }
//   return result;
// }

// /**
//  * Run the intervention simulation for one metric.
//  *
//  * Deep-clones the input readings, then for every placed object whose category
//  * moves temperature, applies the matching model to the readings inside its
//  * footprint (polygon archetypes) or plume (evaporative) and within its active
//  * date window. Mutates only the clone, so the caller's baseline `pointsByDate`
//  * is never touched.
//  *
//  * Two output modes per point:
//  *   - `change_in_temperature` metric → point.value is set to the signed ΔT.
//  *   - any other temperature metric → point.value becomes the new temperature,
//  *     and (for vegetation/evaporative only) relative_humidity is bumped up.
//  *
//  * @param metric        the heatmap metric being simulated
//  * @param pointsByDate  baseline readings grouped by date (not mutated)
//  * @param placedObjects planner's interventions, grouped by archetype category
//  * @returns a new by-date reading set with the interventions applied
//  */
// export async function getSimulatedPointsByDate(
//   metric: string,
//   pointsByDate: HeatmapPointsByDate,
//   placedObjects: BasePlacedObjectCategorized,
// ): Promise<HeatmapPointsByDate> {
//   console.log('[Simulation 00] entered getSimulatedPointsByDate', {
//     metric,
//     dates: Object.keys(pointsByDate),
//     placedObjectCategories: Object.keys(placedObjects),
//   });
//   await delay(MOCK_LATENCY_MS); // simulate network latency for loading states

//   console.log('[Simulation 01] delay complete');

//   // Deep clone so we never mutate the caller's baseline readings.
//   const simulated: HeatmapPointsByDate = Object.fromEntries(
//     Object.entries(pointsByDate).map(([date, points]) => [
//       date,
//       points.map((p) => structuredClone(p)),
//     ]),
//   );
//   console.log('[Simulation 02] baseline cloned', {
//     pointsByDate: Object.fromEntries(
//       Object.entries(simulated).map(([date, points]) => [date, points.length]),
//     ),
//   });
//   const affectsTemperature = metricIsTemperature(metric);
//   const isChangeInTemp = metric === 'change_in_temperature';
//   console.log('[Simulation 03] metric flags resolved', {
//     affectsTemperature,
//     isChangeInTemp,
//   });

//   for (const [category, objects] of Object.entries(placedObjects)) {
//     console.log('[Simulation 04] category reached', {
//       category,
//       objectCount: objects.length,
//     });
//     // Route each category to its model.
//     const isVegetation = category === VEGETATION_CATEGORY;
//     const isHighAlbedo = category === HIGH_ALBEDO_CATEGORY;
//     const isShade = category === SHADE_CATEGORY;
//     const isEvaporative = category === EVAPORATIVE_CATEGORY;

//     // Only these archetypes move temperature; skip everything else.
//     if (
//       (!isVegetation && !isHighAlbedo && !isShade && !isEvaporative) ||
//       !affectsTemperature
//     ) {
//       console.log('[Simulation 05] category skipped', {
//         category,
//         isVegetation,
//         isHighAlbedo,
//         isShade,
//         isEvaporative,
//         affectsTemperature,
//       });
//       continue;
//     }

//     for (const object of objects) {
//       console.log('[Simulation 06] object reached', {
//         category,
//         id: object.id,
//         type: object.type,
//         activeFrom: object.activeFrom,
//         activeTo: object.activeTo,
//         geometryKind: object.geometry?.kind,
//         params: object.params,
//       });
//       // --- Evaporative: point-source plume, no polygon. Gather points within
//       //     the coverage radius of the source and apply a distance falloff. ---
//       if (isEvaporative) {
//         console.log('[Simulation 07] evaporative branch reached', { id: object.id });
//         const evapParams = getEvaporativeParams(object);
//         console.log('[Simulation 08] evaporative params resolved', { id: object.id, evapParams });
//         if (!evapParams) {
//           console.log('[Simulation 09] evaporative object skipped: missing params', { id: object.id });
//           continue;
//         }

//         const source = geometryAnchor(object.geometry);
//         console.log('[Simulation 10] evaporative source resolved', { id: object.id, source });
//         const activeByDate = filterByActiveWindow(
//           simulated,
//           object.activeFrom,
//           object.activeTo,
//         );
//         console.log('[Simulation 11] evaporative active dates resolved', {
//           id: object.id,
//           dates: Object.keys(activeByDate),
//           pointCount: Object.values(activeByDate).reduce((total, points) => total + points.length, 0),
//         });

//         for (const points of Object.values(activeByDate)) {
//           console.log('[Simulation 12] evaporative date points reached', { id: object.id, pointCount: points.length });
//           for (const point of points) {
//             const dist = distanceMeters(source, point.location_coordinates);
//             if (dist > evapParams.coverageRadiusM) continue; // outside the plume

//             console.log('[Simulation 13] evaporative point covered', {
//               id: object.id,
//               location: point.location_coordinates,
//               distanceM: dist,
//             });

//             const beforeC = point.value;
//             const rhBefore = parsePercentage(
//               point.individual_metrics?.average_relative_humidity_pct ?? '',
//             ) ?? NaN;
//             const hasRh = Number.isFinite(rhBefore);

//             // Weather ceiling needs the real temperature. On the ΔT layer the
//             // point value is 0, so read the temperature shared into the metrics
//             // (fall back to a representative hot day if it's missing).
//             const metricTempC = parseTemperature(
//               point.individual_metrics?.average_temperature_c ?? '',
//             ) ?? NaN;

//             const weatherTempC = isChangeInTemp
//               ? (Number.isFinite(metricTempC) ? metricTempC : CHANGE_IN_TEMP_ASSUMED_C)
//               : beforeC;

//             // Use the weather-aware overload when humidity is available.
//             const { finalTemp: afterC, deltaT } = hasRh
//               ? evaporativeCooling(beforeC, evapParams, dist, {
//                   temperatureC: weatherTempC,
//                   relativeHumidity: rhBefore,
//                 })
//               : evaporativeCooling(beforeC, evapParams, dist);

//             if (isChangeInTemp) {
//               point.value = deltaT; // ΔT layer: store the signed change directly
//               console.log('[Simulation 14] evaporative delta applied', { id: object.id, deltaT });
//               continue;
//             }

//             // Evaporation adds vapor → RH rises (same coupling as vegetation).
//             // Conserve vapor pressure: RH scales by the saturation-pressure ratio.
//             const rhAfter = hasRh
//               ? Math.min(
//                   100,
//                   rhBefore *
//                     (saturationVaporPressure(beforeC) /
//                       saturationVaporPressure(afterC)),
//                 )
//               : rhBefore;

//             point.value = afterC;
//             if (point.individual_metrics) {
//               point.individual_metrics.average_temperature_c = `${afterC.toFixed(1)}°C`;
//               if (hasRh) {
//                 point.individual_metrics.average_relative_humidity_pct = `${Math.round(rhAfter)}%`;
//               }
//             }
//             console.log('[Simulation 15] evaporative temperature applied', { id: object.id, afterC, deltaT });
//           }
//         }

//         console.log('[Simulation 16] evaporative branch complete', { id: object.id });
//         continue; // handled — skip the polygon/footprint path below
//       }

//       // --- Footprint archetypes (vegetation / albedo / shade): polygon path ---
//       const polygon = getObjectPolygon(object.geometry);

//       console.log('[Simulation 17] polygon resolved', { id: object.id, hasPolygon: Boolean(polygon) });
//       if (!polygon) {
//         console.log('[Simulation 18] object skipped: no polygon', { id: object.id });
//         continue;
//       } // these archetypes only act over a drawn polygon

//       const activeByDate = filterByActiveWindow(
//         simulated,
//         object.activeFrom,
//         object.activeTo,
//       );
//       console.log('[Simulation 19] polygon active dates resolved', {
//         id: object.id,
//         dates: Object.keys(activeByDate),
//         pointCount: Object.values(activeByDate).reduce((total, points) => total + points.length, 0),
//       });
//       const covered = pointsInsidePolygonByDate(activeByDate, polygon);
//       console.log('[Simulation 20] polygon coverage resolved', {
//         id: object.id,
//         pointCount: Object.values(covered).reduce((total, points) => total + points.length, 0),
//         dates: Object.keys(covered),
//       });

//       // Resolve params for whichever model this category uses.
//       const vegParams = isVegetation ? getCoolingParams(object) : null;
//       const albedoParams = isHighAlbedo ? getAlbedoParams(object) : null;
//       const shadeParams = isShade ? getShadeParams(object) : null;
//       console.log('[Simulation 21] polygon params resolved', {
//         id: object.id,
//         vegParams,
//         albedoParams,
//         shadeParams,
//       });
//       if (!vegParams && !albedoParams && !shadeParams) {
//         console.log('[Simulation 22] polygon object skipped: missing params', { id: object.id });
//         continue;
//       } // no usable params

//       for (const points of Object.values(covered)) {
//         console.log('[Simulation 23] covered date points reached', { id: object.id, pointCount: points.length });
//         for (const point of points) {
//           const beforeC = point.value;
//           const rhBefore = parsePercentage(
//             point.individual_metrics?.average_relative_humidity_pct ?? '',
//           ) ?? NaN;
//           const hasRh = Number.isFinite(rhBefore);

//           // Weather ceiling needs the real temperature. On the ΔT layer the
//           // point value is 0, so read the temperature shared into the metrics
//           // (fall back to a representative hot day if it's missing).
//           const metricTempC = parseTemperature(
//             point.individual_metrics?.average_temperature_c ?? '',
//           ) ?? NaN;
//           const weatherTempC = isChangeInTemp
//             ? (Number.isFinite(metricTempC) ? metricTempC : CHANGE_IN_TEMP_ASSUMED_C)
//             : beforeC;

//           let afterC: number;
//           let deltaT: number;

//           // Dispatch to the model matching this object's category.
//           if (vegParams) {
//             ({ finalTemp: afterC, deltaT } = hasRh
//               ? vegetationCooling(beforeC, vegParams, {
//                   temperatureC: weatherTempC,
//                   relativeHumidity: rhBefore,
//                 })
//               : vegetationCooling(beforeC, vegParams));
//           } else if (albedoParams) {
//             ({ finalTemp: afterC, deltaT } = albedoCooling(beforeC, albedoParams, {
//               temperatureC: weatherTempC,
//             }));
//           } else {
//             // Shade: solar-driven, temperature only, no humidity coupling.
//             ({ finalTemp: afterC, deltaT } = shadeCooling(beforeC, shadeParams!, {
//               temperatureC: weatherTempC,
//             }));
//           }

//           if (isChangeInTemp) {
//             point.value = deltaT; // ΔT layer: store the signed change directly
//             console.log('[Simulation 24] polygon delta applied', { id: object.id, deltaT });
//             continue;
//           }

//           // Humidity rises only for evapotranspiration (vegetation), never for
//           // albedo/shade — those add no water vapor.
//           const rhAfter =
//             vegParams && hasRh
//               ? Math.min(
//                   100,
//                   rhBefore *
//                     (saturationVaporPressure(beforeC) /
//                       saturationVaporPressure(afterC)),
//                 )
//               : rhBefore;

//           point.value = afterC;
//           if (point.individual_metrics) {
//             point.individual_metrics.average_temperature_c = `${afterC.toFixed(1)}°C`;
//             if (vegParams && hasRh) {
//               point.individual_metrics.average_relative_humidity_pct = `${Math.round(rhAfter)}%`;
//             }
//           }
//           console.log('[Simulation 25] polygon temperature applied', { id: object.id, afterC, deltaT });
//         }
//       }
//       console.log('[Simulation 26] polygon branch complete', { id: object.id });
//     }
//   }

//   console.log('[Simulation 27] simulation complete', simulated);
//   return simulated;
// }

// /** The composition model used when several interventions affect one point. */
// export type SimulationMode = 'standard' | 'contextual';

// export interface SimulationFeedback {
//   mode: SimulationMode;
//   affectedPoints: number;
//   overlapPoints: number;
//   maxObjectsAtPoint: number;
//   averageCoolingC: number;
//   maxCapacityUsed: number;
//   affectedLocations: string[];
//   overlapLocations: string[];
//   contributingInterventions: string[];
//   interventionsWithoutEffect: string[];
//   contextualInteractions: string[];
// }

// export interface DiminishingSimulationResult {
//   pointsByDate: HeatmapPointsByDate;
//   feedback: SimulationFeedback;
// }

// const CONTEXTUAL_INTERACTIONS: Array<{ categories: [string, string]; factor: number; label: string }> = [
//   { categories: [VEGETATION_CATEGORY, EVAPORATIVE_CATEGORY], factor: 1.25, label: 'Vegetation + water: irrigation and evapotranspiration reinforce cooling (+25%).' },
//   { categories: [VEGETATION_CATEGORY, HIGH_ALBEDO_CATEGORY], factor: 0.82, label: 'Vegetation + reflective concrete: overlapping benefits are less complementary (-18%).' },
//   { categories: [VEGETATION_CATEGORY, SHADE_CATEGORY], factor: 0.86, label: 'Vegetation + shade: shared solar blocking produces partial redundancy (-14%).' },
//   { categories: [SHADE_CATEGORY, EVAPORATIVE_CATEGORY], factor: 0.92, label: 'Shade + water: lower airflow modestly limits the evaporative plume (-8%).' },
// ];

// function clampSimulation(value: number, minimum: number, maximum: number): number {
//   return Math.min(maximum, Math.max(minimum, value));
// }

// function isActiveOnDate(object: BasePlacedObject, date: string): boolean {
//   const time = new Date(date).getTime();
//   return time >= (object.activeFrom ? new Date(object.activeFrom).getTime() : -Infinity)
//     && time <= (object.activeTo ? new Date(object.activeTo).getTime() : Infinity);
// }

// function coolingCeilingForPoint(temperatureC: number, relativeHumidity?: number): number {
//   const vegetation = relativeHumidity == null ? DELTA_T_MAX_ANCHOR
//     : deltaTMaxFromWeather({ temperatureC, relativeHumidity });
//   const evaporative = relativeHumidity == null ? DELTA_T_MAX_ANCHOR_EVAP
//     : deltaTMaxFromWeatherEvap({ temperatureC, relativeHumidity });
//   return Math.max(vegetation, evaporative, deltaTMaxFromWeatherAlbedo({ temperatureC }), deltaTMaxFromWeatherShade({ temperatureC }), 0.1);
// }

// function individualCooling(
//   category: string,
//   object: BasePlacedObject,
//   point: HeatmapMetricValue,
//   temperatureC: number,
//   relativeHumidity?: number,
// ): number | null {
//   if (category === EVAPORATIVE_CATEGORY) {
//     const params = getEvaporativeParams(object);
//     if (!params) return null;
//     const distance = distanceMeters(geometryAnchor(object.geometry), point.location_coordinates);
//     if (distance > params.coverageRadiusM) return null;
//     const result = relativeHumidity == null
//       ? evaporativeCooling(temperatureC, params, distance)
//       : evaporativeCooling(temperatureC, params, distance, { temperatureC, relativeHumidity });
//     return Math.max(0, -result.deltaT);
//   }

//   const polygon = getObjectPolygon(object.geometry);
//   if (!polygon || !isPointInsidePolygon(point, polygon, getBoundingBox(polygon))) return null;
//   if (category === VEGETATION_CATEGORY) {
//     const params = getCoolingParams(object);
//     if (!params) return null;
//     const result = relativeHumidity == null ? vegetationCooling(temperatureC, params)
//       : vegetationCooling(temperatureC, params, { temperatureC, relativeHumidity });
//     return Math.max(0, -result.deltaT);
//   }
//   if (category === HIGH_ALBEDO_CATEGORY) {
//     const params = getAlbedoParams(object);
//     return params ? Math.max(0, -albedoCooling(temperatureC, params, { temperatureC }).deltaT) : null;
//   }
//   if (category === SHADE_CATEGORY) {
//     const params = getShadeParams(object);
//     return params ? Math.max(0, -shadeCooling(temperatureC, params, { temperatureC }).deltaT) : null;
//   }
//   return null;
// }

// /**
//  * Applies every active intervention against the same baseline and combines
//  * contributions with 1 - product(1 - contribution / capacity). This prevents
//  * overlapping projects from unrealistically stacking their full cooling effect.
//  */
// export async function runDiminishingReturnSimulation(
//   metric: string,
//   pointsByDate: HeatmapPointsByDate,
//   categorizedObjects: BasePlacedObjectCategorized,
//   mode: SimulationMode = 'standard',
// ): Promise<DiminishingSimulationResult> {
//   const feedback: SimulationFeedback = { mode, affectedPoints: 0, overlapPoints: 0, maxObjectsAtPoint: 0, averageCoolingC: 0, maxCapacityUsed: 0, affectedLocations: [], overlapLocations: [], contributingInterventions: [], interventionsWithoutEffect: [], contextualInteractions: [] };
//   if (!metricIsTemperature(metric)) return { pointsByDate: structuredClone(pointsByDate), feedback };
//   const isChangeMetric = metric === 'change_in_temperature';
//   let totalCooling = 0;
//   const affectedLocations = new Set<string>();
//   const overlapLocations = new Set<string>();
//   const contributors = new Set<string>();
//   const labels = new Map<string, string>();
//   Object.entries(categorizedObjects).forEach(([category, objects]) => objects.forEach((object) => labels.set(object.id, object.name ?? object.type ?? category)));

//   const result = Object.fromEntries(Object.entries(pointsByDate).map(([date, points]) => [date, points.map((sourcePoint, index) => {
//     const point = structuredClone(sourcePoint);
//     const parsedTemperature = parseTemperature(sourcePoint.individual_metrics?.average_temperature_c ?? '');
//     const parsedHumidity = parsePercentage(sourcePoint.individual_metrics?.average_relative_humidity_pct ?? '');
//     const temperatureC = isChangeMetric ? (parsedTemperature ?? CHANGE_IN_TEMP_ASSUMED_C) : sourcePoint.value;
//     const relativeHumidity = parsedHumidity ?? undefined;
//     const ceiling = coolingCeilingForPoint(temperatureC, relativeHumidity);
//     const raw = Object.entries(categorizedObjects).flatMap(([category, objects]) => objects
//       .filter((object) => isActiveOnDate(object, date))
//       .map((object) => ({ object, category, cooling: individualCooling(category, object, sourcePoint, temperatureC, relativeHumidity) }))
//       .filter((item): item is { object: BasePlacedObject; category: string; cooling: number } => item.cooling != null && item.cooling > 0));
//     if (!raw.length) return point;
//     const categories = new Set(raw.map((item) => item.category));
//     const interactions = mode === 'contextual' ? CONTEXTUAL_INTERACTIONS.filter((interaction) => categories.has(interaction.categories[0]) && categories.has(interaction.categories[1])) : [];
//     const factor = interactions.reduce((current, interaction) => current * interaction.factor, 1);
//     const impact = 1 - raw.reduce((remaining, item) => remaining * (1 - clampSimulation((item.cooling * factor) / ceiling, 0, 1)), 1);
//     const coolingC = ceiling * impact;
//     const finalTemperature = temperatureC - coolingC;
//     feedback.affectedPoints += 1;
//     feedback.maxObjectsAtPoint = Math.max(feedback.maxObjectsAtPoint, raw.length);
//     feedback.maxCapacityUsed = Math.max(feedback.maxCapacityUsed, impact * 100);
//     totalCooling += coolingC;
//     const location = sourcePoint.individual_metrics?.location_name ?? `Point ${index + 1}`;
//     affectedLocations.add(location);
//     if (raw.length > 1) { feedback.overlapPoints += 1; overlapLocations.add(location); }
//     raw.forEach((item) => contributors.add(item.object.id));
//     interactions.forEach((interaction) => { if (!feedback.contextualInteractions.includes(interaction.label)) feedback.contextualInteractions.push(interaction.label); });
//     point.value = isChangeMetric ? -coolingC : finalTemperature;
//     point.individual_metrics = { ...point.individual_metrics, average_temperature_c: `${finalTemperature.toFixed(1)}°C`, simulation_cooling_c: `${coolingC.toFixed(2)}°C`, simulation_overlap_count: String(raw.length), simulation_capacity_used: `${(impact * 100).toFixed(0)}%` };
//     return point;
//   })]));
//   feedback.averageCoolingC = feedback.affectedPoints ? totalCooling / feedback.affectedPoints : 0;
//   feedback.affectedLocations = [...affectedLocations];
//   feedback.overlapLocations = [...overlapLocations];
//   feedback.contributingInterventions = [...contributors].map((id) => labels.get(id) ?? id);
//   feedback.interventionsWithoutEffect = [...labels].filter(([id]) => !contributors.has(id)).map(([, label]) => label);
//   return { pointsByDate: result, feedback };
// }

import type { HeatmapPointsByDate } from '../types/heatmap';

const BASE_URL = 'http://127.0.0.1:8000';

export async function getSimulatedPointsByDate(
  metric: string,
  fromDate: string,
  toDate: string,
  city: string,
  additionalMetrics?: string[],
  mode: 'standard' | 'contextual' = 'standard',
): Promise<HeatmapPointsByDate> {
  const response = await fetch(`${BASE_URL}/heatmap/get-simulated-point-by-date`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      from_date: fromDate,
      to_date: toDate,
      city,
      metric,
      additional_metrics: additionalMetrics,
      mode,
    }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Simulation request failed: ${response.status} ${response.statusText}${
        detail ? ` — ${detail}` : ''
      }`,
    );
  }

  return (await response.json()) as HeatmapPointsByDate;
}

