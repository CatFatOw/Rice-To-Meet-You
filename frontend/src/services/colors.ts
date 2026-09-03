export type Metric =
  | "average_temperature_c"
  | "average_temperature_f"
  | "heat_index_c"
  | "heat_index_f"
  | "average_relative_humidity_pct"
  | "avg_daily_visits"
  | "heat_risk_score"
  | "change_in_temperature"
  | "change_in_average_temperature_c"
  | "change_in_local_temperature_c"
  | "change_in_average_temperature_f"
  | "change_in_local_temperature_f";


type RGBColor = [number, number, number];

export function metricLabel(metricKey: string): string {
  switch (metricKey) {
    case "temperatureF":
      return "Air Temp";
    case "heatIndexF":
      return "Heat Index";
    case "relativeHumidityPct":
      return "Humidity";
    case "landSurfaceTempF":
      return "Surface Temp";
    case "nighttimeTempF":
      return "Night Temp";
    case "treeCanopyPct":
      return "Tree Canopy";
    case "imperviousSurfacePct":
      return "Impervious";
    default:
      return metricKey;
  }
}

export function metricUnit(metricKey: string): string {
  if (metricKey.endsWith("F")) return " deg F";
  if (metricKey.endsWith("Pct")) return "%";
  return "";
}

export function hexToRgb(hex: string): RGBColor {
  const normalized = hex.replace("#", "");
  const red = parseInt(normalized.substring(0, 2), 16);
  const green = parseInt(normalized.substring(2, 4), 16);
  const blue = parseInt(normalized.substring(4, 6), 16);
  return [
    Number.isNaN(red) ? 0 : red,
    Number.isNaN(green) ? 0 : green,
    Number.isNaN(blue) ? 0 : blue,
  ];
}

export function colorMetricKey(metric: string): Metric {
  if (metric === "heat_risk_score") return "average_temperature_c";
  if (metric === "average_temperature_c") return "average_temperature_c";
  if (metric === "average_temperature_f") return "average_temperature_f";
  if (metric === "heat_index_c") return "heat_index_c";
  if (metric === "heat_index_f") return "heat_index_f";
  if (metric === "average_relative_humidity_pct") return "average_relative_humidity_pct";
  if (metric === "avg_daily_visits") return "avg_daily_visits";
  if (
    metric === "change_in_temperature" ||
    metric === "change_in_average_temperature_c" ||
    metric === "change_in_local_temperature_c"
  ) {
    return "change_in_temperature";
  }
  if (
    metric === "change_in_average_temperature_f" ||
    metric === "change_in_local_temperature_f"
  ) {
    return metric;
  }
  return "heat_risk_score";
}

export function rgbaCss(rgb: RGBColor, alpha: number): string {
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
}

export function metricWeightOffset(metric: string): number {
  const colorMetric = colorMetricKey(metric);
  if (
    colorMetric === "change_in_average_temperature_f" ||
    colorMetric === "change_in_local_temperature_f"
  ) {
    return 10;
  }
  return colorMetric === "change_in_temperature" ? 5 : 0;
}

export function metricColorRange(metric: string): [number, number, number, number][] {
  const colorMetric = colorMetricKey(metric);
  const stops = metricStops(colorMetric);
  const fadeFirst = !colorMetric.startsWith("change_in_");

  return stops.map((value, index) => {
    const [red, green, blue] = getColor(value, colorMetric);
    const alpha = index === 0 && fadeFirst ? 0 : 230;
    return [red, green, blue, alpha];
  });
}

export function metricLegendGradient(metric: string): string {
  const colorMetric = colorMetricKey(metric);
  const stops = metricStops(colorMetric);
  const pctStep = 100 / (stops.length - 1);

  const segments = stops.map((value, index) => {
    const color = getColor(value, colorMetric);
    const pct = Math.round(index * pctStep);
    return `${rgbaCss(color, 0.95)} ${pct}%`;
  });

  return `linear-gradient(to right, ${segments.join(", ")})`;
}

function getTemperatureCColor(valueC: number): RGBColor {
  if (valueC >= 40) return [189, 0, 38];
  if (valueC >= 38) return [227, 26, 28];
  if (valueC >= 36) return [240, 59, 32];
  if (valueC >= 34) return [252, 78, 42];
  if (valueC >= 32) return [253, 141, 60];
  if (valueC >= 30) return [253, 174, 97];
  if (valueC >= 28) return [254, 196, 79];
  if (valueC >= 26) return [254, 217, 118];
  if (valueC >= 24) return [255, 237, 160];
  if (valueC >= 21) return [217, 240, 163];
  if (valueC >= 18) return [161, 218, 180];
  if (valueC >= 14) return [102, 194, 165];
  if (valueC >= 10) return [65, 182, 196];
  if (valueC >= 5) return [44, 127, 184];
  if (valueC >= 0) return [37, 66, 154];

  return [20, 30, 100];
}

function getHeatIndexFColor(valueF: number): RGBColor {
  // NWS-aligned heat-index danger thresholds.
  if (valueF >= 125) return [128, 0, 38];   // extreme danger
  if (valueF >= 115) return [189, 0, 38];
  if (valueF >= 103) return [227, 26, 28];  // danger
  if (valueF >= 95) return [252, 78, 42];
  if (valueF >= 90) return [253, 141, 60];  // extreme caution
  if (valueF >= 85) return [254, 196, 79];
  if (valueF >= 80) return [255, 237, 160]; // caution
  if (valueF >= 70) return [161, 218, 180];
  if (valueF >= 60) return [65, 182, 196];

  return [44, 127, 184];
}

export function getColor(value: number, metric: Metric): RGBColor {
  if (!Number.isFinite(value)) {
    return [128, 128, 128];
  }

  switch (metric) {
    case "average_temperature_c":
      return getTemperatureCColor(value);

    case "average_temperature_f": {
      const valueC = ((value - 32) * 5) / 9;
      return getTemperatureCColor(valueC);
    }

    case "heat_index_f":
      return getHeatIndexFColor(value);

    case "heat_index_c": {
      const valueF = (value * 9) / 5 + 32;
      return getHeatIndexFColor(valueF);
    }

    case "average_relative_humidity_pct":
      // Dry (orange) → moderate (green) → humid (blue)
      if (value >= 90) return [8, 48, 107];
      if (value >= 80) return [33, 102, 172];
      if (value >= 70) return [67, 147, 195];
      if (value >= 60) return [65, 182, 196];
      if (value >= 50) return [102, 194, 165];
      if (value >= 40) return [161, 218, 180];
      if (value >= 30) return [217, 240, 163];
      if (value >= 20) return [254, 217, 118];

      return [253, 174, 97];
    
    case "avg_daily_visits":
      // Visitor activity: 0–50,000 daily visits.
      if (value >= 50_000) return [255, 255, 51];
      if (value >= 45_000) return [236, 247, 65];
      if (value >= 40_000) return [217, 239, 61];
      if (value >= 35_000) return [189, 228, 82];
      if (value >= 30_000) return [166, 217, 106];
      if (value >= 25_000) return [126, 210, 132];
      if (value >= 20_000) return [102, 204, 150];
      if (value >= 15_000) return [65, 182, 196];
      if (value >= 10_000) return [52, 152, 204];
      if (value >= 5_000) return [44, 127, 184];

      return [37, 52, 148];

    case "heat_risk_score":
      // Assumes heat_risk_score ranges from 0 to 100.
      if (value >= 90) return [128, 0, 38];
      if (value >= 80) return [189, 0, 38];
      if (value >= 70) return [227, 26, 28];
      if (value >= 60) return [252, 78, 42];
      if (value >= 50) return [253, 141, 60];
      if (value >= 40) return [254, 196, 79];
      if (value >= 30) return [255, 237, 160];
      if (value >= 20) return [217, 240, 163];
      if (value >= 10) return [161, 218, 180];

      return [102, 194, 165];

    case "change_in_temperature":
    case "change_in_average_temperature_c":
    case "change_in_local_temperature_c":
      // Cooling (blue) → no change (gray) → warming (red)
      if (value >= 5) return [165, 0, 38];
      if (value >= 4) return [215, 48, 39];
      if (value >= 3) return [244, 109, 67];
      if (value >= 2) return [253, 174, 97];
      if (value >= 1) return [254, 224, 144];
      if (value > -1) return [247, 247, 247];
      if (value > -2) return [209, 229, 240];
      if (value > -3) return [146, 197, 222];
      if (value > -4) return [67, 147, 195];
      if (value > -5) return [33, 102, 172];

      return [8, 48, 107];

    case "change_in_average_temperature_f":
    case "change_in_local_temperature_f":
      // Same cooling/warming gradient as Celsius, with Fahrenheit stops.
      if (value >= 10) return [165, 0, 38];
      if (value >= 8) return [215, 48, 39];
      if (value >= 6) return [244, 109, 67];
      if (value >= 4) return [253, 174, 97];
      if (value >= 2) return [254, 224, 144];
      if (value > -2) return [247, 247, 247];
      if (value > -4) return [209, 229, 240];
      if (value > -6) return [146, 197, 222];
      if (value > -8) return [67, 147, 195];
      if (value > -10) return [33, 102, 172];

      return [8, 48, 107];

    default:
      return [128, 128, 128];
  }
}


export function metricStops(metric: Metric): number[] {
  switch (metric) {
    case "average_temperature_c":
      return [
        0, 5, 10, 14, 18, 21, 24, 26,
        28, 30, 32, 34, 36, 38, 40,
      ];

    case "average_temperature_f":
      return [
        32, 41, 50, 57, 64, 70, 75, 79,
        82, 86, 90, 93, 97, 100, 104,
      ];

    case "heat_index_f":
      return [60, 70, 80, 85, 90, 95, 103, 115, 125];

    case "heat_index_c":
      return [16, 21, 27, 29, 32, 35, 39, 46, 52];

    case "average_relative_humidity_pct":
      return [0, 20, 30, 40, 50, 60, 70, 80, 90, 100];

    case "avg_daily_visits":
      return [
        0,
        5_000,
        10_000,
        15_000,
        20_000,
        25_000,
        30_000,
        35_000,
        40_000,
        45_000,
        50_000,
      ];

    case "heat_risk_score":
      return [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

    case "change_in_temperature":
    case "change_in_average_temperature_c":
    case "change_in_local_temperature_c":
      return [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5];

    case "change_in_average_temperature_f":
    case "change_in_local_temperature_f":
      return [-10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10];

    default:
      return [0, 20, 40, 60, 80, 100];
  }
}


interface ScaleLabels {
  tickLabels: string[];
  lowLabel: string;
  highLabel: string;
}

export function getScaleLabels(
  metricOrLabel: string,
): ScaleLabels {
  

  switch (metricOrLabel) {
    case "average_temperature_c":
      return {
        tickLabels: ["0°C", "10°C", "20°C", "30°C", "40°C"],
        lowLabel: "Cold",
        highLabel: "Hot",
      };

    case "average_temperature_f":
      return {
        tickLabels: ["32°F", "50°F", "70°F", "90°F", "104°F"],
        lowLabel: "Cold",
        highLabel: "Hot",
      };

    case "heat_index_c":
      return {
        tickLabels: ["16°C", "27°C", "32°C", "39°C", "52°C"],
        lowLabel: "Lower Risk",
        highLabel: "Extreme Danger",
      };

    case "heat_index_f":
      return {
        tickLabels: ["60°F", "80°F", "90°F", "103°F", "125°F"],
        lowLabel: "Lower Risk",
        highLabel: "Extreme Danger",
      };

    case "average_relative_humidity_pct":
      return {
        tickLabels: ["0%", "25%", "50%", "75%", "100%"],
        lowLabel: "Dry",
        highLabel: "Humid",
      };

    case "avg_daily_visits":
      return {
        tickLabels: ["0", "12.5K", "25K", "37.5K", "50K"],
        lowLabel: "Low Activity",
        highLabel: "High Activity",
      };

    case "heat_risk_score":
      return {
        tickLabels: ["0", "25", "50", "75", "100"],
        lowLabel: "Low Risk",
        highLabel: "Extreme Risk",
      };

    case "change_in_temperature":
    case "change_in_average_temperature_c":
    case "change_in_local_temperature_c":
      return {
        tickLabels: ["-5°C", "-2.5°C", "0°C", "+2.5°C", "+5°C"],
        lowLabel: "Cooling",
        highLabel: "Warming",
      };

    case "change_in_average_temperature_f":
    case "change_in_local_temperature_f":
      return {
        tickLabels: ["-10°F", "-5°F", "0°F", "+5°F", "+10°F"],
        lowLabel: "Cooling",
        highLabel: "Warming",
      };

    default:
      return {
        tickLabels: ["0", "25", "50", "75", "100"],
        lowLabel: "Low",
        highLabel: "High",
      };
  }
}

export function metricColorDomain(
  metric: Metric,
): [number, number] {
  switch (metric) {
    case "average_temperature_c":
      return [0, 40];

    case "average_temperature_f":
      return [32, 104];

    case "heat_index_c":
      return [16, 52];

    case "heat_index_f":
      return [60, 125];

    case "average_relative_humidity_pct":
      return [0, 100];

    case "avg_daily_visits":
      return [0, 50_000];

    case "heat_risk_score":
      return [0, 100];

    case "change_in_temperature":
    case "change_in_average_temperature_c":
    case "change_in_local_temperature_c":
      // Values are shifted by +5 before being passed to Deck.gl.
      return [0, 10];

    case "change_in_average_temperature_f":
    case "change_in_local_temperature_f":
      // Values are shifted by +10 before being passed to Deck.gl.
      return [0, 20];

    default:
      return [0, 100];
  }
}