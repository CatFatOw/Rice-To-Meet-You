type Metric = 'temperature' | string;

function ramp(v: number, stops: Array<[number, [number, number, number]]>): [number, number, number] {
  for (const [threshold, color] of stops) {
    if (v >= threshold) return color;
  }
  return stops[stops.length - 1][1];
}

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

  if (metric === 'heat_risk' || metric === 'heat_index') {
    return ramp(v, [
      [90, [127, 29, 29]],
      [75, [220, 38, 38]],
      [60, [249, 115, 22]],
      [45, [245, 158, 11]],
      [30, [234, 179, 8]],
      [15, [132, 204, 22]],
      [0, [20, 184, 166]],
    ]);
  }

  if (metric === 'visitor_density' || metric === 'visitor_activity' || metric === 'crowd_density') {
    return ramp(v, [
      [90, [236, 72, 153]],
      [75, [168, 85, 247]],
      [60, [99, 102, 241]],
      [45, [59, 130, 246]],
      [30, [14, 165, 233]],
      [15, [45, 212, 191]],
      [0, [15, 118, 110]],
    ]);
  }

  if (metric === 'cooling_centers') {
    return ramp(v, [
      [90, [14, 165, 233]],
      [75, [6, 182, 212]],
      [60, [34, 211, 238]],
      [45, [103, 232, 249]],
      [30, [125, 211, 252]],
      [15, [186, 230, 253]],
      [0, [30, 64, 175]],
    ]);
  }

  if (metric === 'infrastructure_strain') {
    return ramp(v, [
      [90, [190, 18, 60]],
      [75, [225, 29, 72]],
      [60, [251, 113, 133]],
      [45, [251, 146, 60]],
      [30, [250, 204, 21]],
      [15, [163, 230, 53]],
      [0, [22, 163, 74]],
    ]);
  }

  if (metric === 'population') {
    return ramp(v, [
      [90, [109, 40, 217]],
      [75, [124, 58, 237]],
      [60, [139, 92, 246]],
      [45, [168, 85, 247]],
      [30, [192, 132, 252]],
      [15, [216, 180, 254]],
      [0, [59, 130, 246]],
    ]);
  }

  return ramp(v, [
    [90, [239, 68, 68]],
    [75, [249, 115, 22]],
    [60, [245, 158, 11]],
    [45, [234, 179, 8]],
    [30, [132, 204, 22]],
    [15, [20, 184, 166]],
    [0, [37, 99, 235]],
  ]);
}
