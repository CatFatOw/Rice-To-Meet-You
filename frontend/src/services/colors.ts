type RGB = [number, number, number];
type Stop = [number, RGB];

type Metric = 'temperature' | string;

export function getColor(v: number, metric: Metric): [number, number, number] {
  if (metric === 'average_temperature_c') {

  // Temperature ramp (°C): blue → green → yellow → orange → red

  // 30°C is distinctly orange, 40°C is fully red.

  if (v >= 40) return [189, 0, 38];      // deep red

  if (v >= 38) return [227, 26, 28];     // red

  if (v >= 36) return [240, 59, 32];     // strong red-orange

  if (v >= 34) return [252, 78, 42];     // red-orange

  if (v >= 32) return [253, 141, 60];    // dark orange

  if (v >= 30) return [253, 174, 97];    // orange

  if (v >= 28) return [254, 196, 79];    // amber

  if (v >= 26) return [254, 217, 118];   // yellow-orange

  if (v >= 24) return [255, 237, 160];   // pale yellow

  if (v >= 21) return [217, 240, 163];   // yellow-green

  if (v >= 18) return [161, 218, 180];   // green

  if (v >= 14) return [102, 194, 165];   // green-cyan

  if (v >= 10) return [65, 182, 196];    // cyan

  if (v >= 5)  return [44, 127, 184];    // blue

  if (v >= 0)  return [37, 66, 154];     // dark blue

  return [20, 30, 100];                  // deep blue

}

  if (metric === 'visitor_density') {
    // Visitor density ramp (0–100): least dense (blue) → most dense (yellow)
    if (v >= 90) return [255, 255, 51];   // most dense, bright yellow
    if (v >= 80) return [217, 239, 61];   // yellow-green
    if (v >= 70) return [166, 217, 106];  // green
    if (v >= 60) return [102, 204, 150];  // teal-green
    if (v >= 50) return [65, 182, 196];   // cyan
    if (v >= 40) return [52, 152, 204];   // light blue
    if (v >= 30) return [44, 127, 184];   // blue
    if (v >= 20) return [40, 94, 168];    // deeper blue
    if (v >= 10) return [37, 66, 154];    // dark blue
    return [37, 52, 148];                 // least dense, deep blue
  }

  if (metric === 'change_in_temperature') {
    // Diverging ΔT ramp (°C): blue (cooling) → gray (no change) → red (warming)
    if (v >= 5)  return [165, 0, 38];      // dark red — strong warming
    if (v >= 4)  return [215, 48, 39];     // red
    if (v >= 3)  return [244, 109, 67];    // red-orange
    if (v >= 2)  return [253, 174, 97];    // orange
    if (v >= 1)  return [254, 224, 144];   // yellow
    if (v > -1)  return [247, 247, 247];   // light gray/white — no change
    if (v > -2)  return [209, 229, 240];   // pale cyan
    if (v > -3)  return [146, 197, 222];   // cyan
    if (v > -4)  return [67, 147, 195];    // light blue
    if (v > -5)  return [33, 102, 172];    // blue
    return [8, 48, 107];                   // dark blue — very strong cooling
  }

  // Fallback for metrics not yet handled — your original YlOrRd ramp
  if (v > 80) return [189, 0, 38];
  if (v > 60) return [240, 59, 32];
  if (v > 40) return [253, 141, 60];
  if (v > 20) return [254, 178, 76];
  return [255, 255, 178];
}

// ---------------------------------------------------------------------------
// Continuous ramps for the interpolated kriged surface
// ---------------------------------------------------------------------------
// getColor above returns banded colors (one flat color per threshold), which is
// right for a legend's discrete stops. The kriged surface needs a *smooth*
// lookup instead, so a continuously interpolated field does not come out as
// visible contour bands.
//
// Stops are in each metric's own units - degrees Celsius here, not a 0-100
// score - so the renderer colors the real interpolated value directly.

const RAMPS: Record<string, Stop[]> = {
  // Absolute temperature (degrees C): blue -> green -> yellow -> orange -> red.
  // Mirrors the banded getColor stops above so the surface and the legend agree.
  average_temperature_c: [
    [40, [189, 0, 38]], // deep red
    [38, [227, 26, 28]],
    [36, [240, 59, 32]],
    [34, [252, 78, 42]],
    [32, [253, 141, 60]],
    [30, [253, 174, 97]], // orange
    [28, [254, 196, 79]],
    [26, [254, 217, 118]],
    [24, [255, 237, 160]], // pale yellow
    [21, [217, 240, 163]],
    [18, [161, 218, 180]], // green
    [14, [102, 194, 165]],
    [10, [65, 182, 196]], // cyan
    [5, [44, 127, 184]], // blue
    [0, [37, 66, 154]], // dark blue
    [-10, [20, 30, 100]], // deep blue
  ],
  // Diverging delta-T (degrees C): blue (cooling) -> neutral -> red (warming).
  // The midpoint is deliberately a light neutral so "no change" reads as
  // absence rather than as a color of its own.
  change_in_temperature: [
    [5, [165, 0, 38]], // strong warming
    [4, [215, 48, 39]],
    [3, [244, 109, 67]],
    [2, [253, 174, 97]],
    [1, [254, 224, 144]],
    [0, [247, 247, 247]], // no change
    [-1, [209, 229, 240]],
    [-2, [146, 197, 222]],
    [-3, [67, 147, 195]],
    [-4, [33, 102, 172]],
    [-5, [8, 48, 107]], // strong cooling
  ],
};

/** True when the metric has a continuous surface ramp of its own. */
export function hasSmoothRamp(metric: string): boolean {
  return metric in RAMPS;
}

/**
 * Value range a metric's ramp spans, used to lay out the legend gradient.
 * Returns null for metrics without a ramp.
 */
export function rampDomain(metric: string): [number, number] | null {
  const stops = RAMPS[metric];
  if (!stops) return null;
  return [stops[stops.length - 1][0], stops[0][0]];
}

/**
 * Continuous lookup in the metric's own units: linearly blend between the two
 * bracketing stops so a smooth field renders as a smooth gradient instead of
 * contour bands. Values outside the ramp clamp to its end colors.
 */
export function getSmoothColor(v: number, metric: string): RGB {
  const stops = RAMPS[metric];
  if (!stops) return getColor(v, metric);
  if (v >= stops[0][0]) return stops[0][1];

  for (let i = 0; i < stops.length - 1; i += 1) {
    const [hi, hiColor] = stops[i];
    const [lo, loColor] = stops[i + 1];
    if (v >= lo) {
      const t = hi === lo ? 0 : (v - lo) / (hi - lo);
      return [
        Math.round(loColor[0] + (hiColor[0] - loColor[0]) * t),
        Math.round(loColor[1] + (hiColor[1] - loColor[1]) * t),
        Math.round(loColor[2] + (hiColor[2] - loColor[2]) * t),
      ];
    }
  }
  return stops[stops.length - 1][1];
}
