/**
 * Parses a temperature string such as "13°C" into 13.
 * Returns null when the value is invalid.
 */
export function parseTemperature(value: string): number | null {
  const match = value.trim().match(/^(-?\d+(?:\.\d+)?)\s*°C$/i);
  return match ? Number(match[1]) : null;
}

/**
 * Parses a percentage string such as "49.4%" into 49.4.
 * Returns null when the value is invalid.
 */
export function parsePercentage(value: string): number | null {
  const match = value.trim().match(/^(-?\d+(?:\.\d+)?)\s*%$/);
  return match ? Number(match[1]) : null;
}

// Examples
parseTemperature("13°C");    // 13
parseTemperature("-2.5 °C"); // -2.5
parsePercentage("49.4%");    // 49.4
parsePercentage("80 %");     // 80