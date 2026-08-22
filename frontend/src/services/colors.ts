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
// Continuous ramps for the interpolated raster surface
// ---------------------------------------------------------------------------
// getColor above returns banded colors (one flat color per threshold), which is
// right for the legend's discrete stops. The raster renderer needs a *smooth*
// lookup instead, so a continuously interpolated value field does not come out
// as visible contour bands.

/** Map a raw metric key onto the ramp family it should be drawn with. */
export function colorMetricKey(metric: string): string {
  if (metric === 'heat_risk_score') return 'heat_risk';
  if (metric === 'heat_index') return 'heat_risk';
  if (metric === 'visitor_density' || metric === 'visitor_activity') return 'crowd_density';
  return metric;
}

// Ramp stops per metric family, sorted by descending threshold.
const RAMPS: Record<string, Stop[]> = {
  temperature: [
    // Standard weather-forecast temperature ramp (°F): cold → hot
    [100, [153, 0, 38]], // extreme heat, dark red
    [90, [189, 0, 38]], // very hot, red
    [80, [240, 59, 32]], // hot, orange-red
    [70, [253, 141, 60]], // warm, orange
    [60, [254, 178, 76]], // mild, amber
    [50, [255, 237, 160]], // cool, pale yellow
    [40, [161, 218, 180]], // chilly, green
    [32, [65, 182, 196]], // cold, cyan
    [20, [44, 127, 184]], // freezing, blue
    [0, [37, 52, 148]], // frigid, deep blue
  ],
  heat_risk: [
    [90, [127, 29, 29]],
    [75, [220, 38, 38]],
    [60, [249, 115, 22]],
    [45, [245, 158, 11]],
    [30, [234, 179, 8]],
    [15, [132, 204, 22]],
    [0, [20, 184, 166]],
  ],
  crowd_density: [
    [90, [236, 72, 153]],
    [75, [168, 85, 247]],
    [60, [99, 102, 241]],
    [45, [59, 130, 246]],
    [30, [14, 165, 233]],
    [15, [45, 212, 191]],
    [0, [15, 118, 110]],
  ],
  cooling_centers: [
    [90, [14, 165, 233]],
    [75, [6, 182, 212]],
    [60, [34, 211, 238]],
    [45, [103, 232, 249]],
    [30, [125, 211, 252]],
    [15, [186, 230, 253]],
    [0, [30, 64, 175]],
  ],
  infrastructure_strain: [
    [90, [190, 18, 60]],
    [75, [225, 29, 72]],
    [60, [251, 113, 133]],
    [45, [251, 146, 60]],
    [30, [250, 204, 21]],
    [15, [163, 230, 53]],
    [0, [22, 163, 74]],
  ],
  population: [
    [90, [109, 40, 217]],
    [75, [124, 58, 237]],
    [60, [139, 92, 246]],
    [45, [168, 85, 247]],
    [30, [192, 132, 252]],
    [15, [216, 180, 254]],
    [0, [59, 130, 246]],
  ],
  default: [
    [90, [239, 68, 68]],
    [75, [249, 115, 22]],
    [60, [245, 158, 11]],
    [45, [234, 179, 8]],
    [30, [132, 204, 22]],
    [15, [20, 184, 166]],
    [0, [37, 99, 235]],
  ],
};

/** True when the metric has a smooth ramp of its own (not the fallback). */
export function hasSmoothRamp(metric: string): boolean {
  return colorMetricKey(metric) in RAMPS;
}

function rampFor(metric: string): Stop[] {
  return RAMPS[colorMetricKey(metric)] ?? RAMPS.default;
}

/**
 * Continuous lookup: linearly blend between the two bracketing stops so a
 * smooth value field renders as a smooth gradient instead of contour bands.
 */
export function getSmoothColor(v: number, metric: string): RGB {
  const stops = rampFor(metric);
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
