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