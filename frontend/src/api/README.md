# Diminishing simulation API

`diminishingSimulation.ts` is the only frontend heat-intervention simulation module. It accepts date-keyed heatmap points and placed interventions, calculates cooling at each affected point, and returns a cloned result plus summary feedback. Input data is not mutated.

## Runner

### `runDiminishingReturnSimulation(metric, pointsByDate, categorizedObjects, mode)`

The main function.

1. Returns cloned points unchanged unless `metric` contains `temp`.
2. For each date and heatmap point, ignores interventions outside their active date window.
3. Calculates the cooling from every intervention covering that point.
4. Combines overlapping cooling with the diminishing-return formula below.
5. Writes these fields to `individual_metrics`: `simulation_cooling_c`, baseline/result temperature, overlap count, capacity used, and contextual interaction label.
6. Returns `{ pointsByDate, feedback }`. `feedback` reports affected points, overlaps, average cooling, maximum capacity use, contributing interventions, and interventions with no effect.

`mode` is `standard` by default. `contextual` applies the pair rules in [Contextual adjustments](#contextual-adjustments) before the overlap formula.

## Shared math

### `saturationVaporPressure(temperatureC)`

Returns saturation vapour pressure in kPa using Tetens' equation:

`es = 0.6108 × exp(17.27 × T / (T + 237.3))`

### `vaporPressureDeficit(temperatureC, relativeHumidity)`

Returns VPD in kPa:

`VPD = es × (1 - RH / 100)`

VPD controls the weather ceiling for vegetation and evaporative cooling. All fraction-like inputs are clamped to 0–1 where the implementation uses `clamp`.

## Individual intervention models

### Vegetation

`deltaTMaxFromWeather(weather)` returns the vegetation ceiling:

`ceiling = 5°C × min(VPD / 4.5, 1) × fSolar × fWind`

`vegetationCooling(initialTemp, params, ceiling)` uses a saturating leaf-area response:

`leafEffect = 1 - exp(-0.5 × LAI)`

`latent = coverage × leafEffect × waterFactor`

`shade = coverage × canopyFraction × leafEffect × (0.8 + 0.2 × waterFactor)`

`cooling = ceiling × (0.4 × latent + 0.6 × shade)`

It returns `{ finalTemp: initialTemp - cooling, deltaT: -cooling }`.

### High-albedo surface

`deltaTMaxFromWeatherAlbedo(weather)` derives solar loading from temperature:

`ceiling = 4°C × clamp((T - 20) / 18, 0, 1) × fSolar`

`albedoCooling(initialTemp, params, ceiling)` uses:

`cooling = ceiling × clamp(deltaAlbedo / 0.7, 0, 1) × areaCoverage`

### Shade structure

`deltaTMaxFromWeatherShade(weather)` uses:

`ceiling = 5°C × clamp((T - 20) / 18, 0, 1) × fSolar × 0.85`

The `0.85` is the model's maximum direct-beam share. `shadeCooling(initialTemp, params, ceiling)` uses:

`cooling = ceiling × opacity × shadedFootprint`

### Evaporative / water

`deltaTMaxFromWeatherEvap(weather)` uses:

`ceiling = 8°C × min(VPD / 4.5, 1) × fWind`

`evaporativeCooling(initialTemp, params, distanceM, ceiling)` converts flow to latent heat power:

`powerW = max(evapRateLpm, 0) / 60 × 2.45e6`

`sourceStrength = min(powerW / 50000, 1)`

`falloff = max(1 - distanceM / coverageRadiusM, 0)`

`cooling = ceiling × sourceStrength × activeFraction × falloff`

Evaporative interventions use their point location or line/polygon centroid as the source. The other three intervention types only affect points inside their polygon.

## Overlap formula

The runner selects one ceiling per point: the maximum of the four weather ceilings (with 5°C vegetation and 8°C evaporative fallbacks when humidity is unavailable).

For contributions `c₁…cₙ` and ceiling `C`:

`impact = 1 - Π(1 - clamp(cᵢ / C, 0, 1))`

`combinedCooling = C × impact`

This keeps combined cooling at or below `C`; overlapping interventions have progressively smaller marginal effect.

## Contextual adjustments

In `contextual` mode, every applicable contribution at an overlapping point is multiplied by the product of matching pair factors before overlap is calculated:

| Pair | Factor |
| --- | ---: |
| Vegetation + evaporative/water | 1.25 |
| Vegetation + high-albedo surface | 0.82 |
| Vegetation + shade structure | 0.86 |
| Shade structure + evaporative/water | 0.92 |

These are explicit scenario assumptions, not inferred physics. Change `CONTEXTUAL_INTERACTIONS` to calibrate them.
