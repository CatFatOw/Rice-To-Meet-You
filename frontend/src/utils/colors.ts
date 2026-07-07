type Metric = 'temperature' | string;
type RGB = [number, number, number];
type Stop = [number, RGB];

// Map metric keys onto the color ramp families defined below.
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

function rampFor(metric: Metric): Stop[] {
  return RAMPS[colorMetricKey(metric)] ?? RAMPS.default;
}

// Continuous lookup: linearly blend between the two bracketing stops so a
// smooth value field renders as a smooth gradient instead of contour bands.
export function getSmoothColor(v: number, metric: Metric): RGB {
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
