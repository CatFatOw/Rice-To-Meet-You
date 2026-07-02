type Metric = 'temperature' | string;

export function getColor(v: number, metric: Metric): [number, number, number] {
  if (metric === 'temperature') {
    // Standard weather-forecast temperature ramp (°F): cold → hot
    if (v >= 100) return [153, 0, 38];    // extreme heat, dark red
    if (v >= 90) return [189, 0, 38];     // very hot, red
    if (v >= 80) return [240, 59, 32];    // hot, orange-red
    if (v >= 70) return [253, 141, 60];   // warm, orange
    if (v >= 60) return [254, 178, 76];   // mild, amber
    if (v >= 50) return [255, 237, 160];  // cool, pale yellow
    if (v >= 40) return [161, 218, 180];  // chilly, green
    if (v >= 32) return [65, 182, 196];   // cold, cyan
    if (v >= 20) return [44, 127, 184];   // freezing, blue
    return [37, 52, 148];                 // frigid, deep blue
  }

  // Fallback for metrics not yet handled — your original YlOrRd ramp
  if (v > 80) return [189, 0, 38];
  if (v > 60) return [240, 59, 32];
  if (v > 40) return [253, 141, 60];
  if (v > 20) return [254, 178, 76];
  return [255, 255, 178];
}