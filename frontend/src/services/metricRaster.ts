import type { MetricSurface } from '../types/heatmap';
import { getSmoothColor } from './colors';

// Rendered raster for one city's kriged surface: a fixed-size colorized image
// anchored to geographic bounds (so it never resamples with zoom). The bounds
// are the rectangle through the outermost lattice centroids, so every rendered
// pixel is a true interpolation between kriged values.
//
// The image covers the city rectangle and nothing beyond it: one city, one
// rectangle, one image.
export interface MetricRaster {
  canvas: HTMLCanvasElement;
  bounds: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
  width: number;
  height: number;
}

const PIXELS_PER_CELL = 12;
const MIN_RASTER_WIDTH = 256;
const MAX_RASTER_WIDTH = 960;
const MAX_RASTER_HEIGHT = 1280;
const RASTER_ALPHA = 210;

const RASTER_CACHE = new Map<string, MetricRaster>();
const MAX_RASTER_CACHE_ENTRIES = 24;

function clamp(value: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, value));
}

// The contiguous rectangle spanning all lattice centroids: the surface bbox
// inset by half a cell on every side.
export function centroidBounds(surface: MetricSurface): [number, number, number, number] {
  const [minLon, minLat, maxLon, maxLat] = surface.bounds;
  const halfLon = (maxLon - minLon) / surface.cols / 2;
  const halfLat = (maxLat - minLat) / surface.rows / 2;
  return [minLon + halfLon, minLat + halfLat, maxLon - halfLon, maxLat - halfLat];
}

/**
 * Bilinear sample of the rows x cols value lattice at a lon/lat. Values sit at
 * cell centroids (row 0 = southernmost). Returns null outside the city
 * rectangle, which is how the caller knows a coordinate belongs to no city.
 */
export function sampleSurface(
  surface: MetricSurface,
  lon: number,
  lat: number,
): number | null {
  const [minLon, minLat, maxLon, maxLat] = surface.bounds;
  if (lon < minLon || lon > maxLon || lat < minLat || lat > maxLat) return null;

  const lonSpan = maxLon - minLon;
  const latSpan = maxLat - minLat;
  if (lonSpan <= 0 || latSpan <= 0) return null;

  // Fractional lattice position; the 0.5 shift puts integer positions on cell
  // centroids, and clamping holds edge half-cells at the edge value.
  const colF = clamp(((lon - minLon) / lonSpan) * surface.cols - 0.5, 0, surface.cols - 1);
  const rowF = clamp(((lat - minLat) / latSpan) * surface.rows - 0.5, 0, surface.rows - 1);
  const col0 = Math.floor(colF);
  const row0 = Math.floor(rowF);
  const col1 = Math.min(col0 + 1, surface.cols - 1);
  const row1 = Math.min(row0 + 1, surface.rows - 1);
  const tCol = colF - col0;
  const tRow = rowF - row0;

  const v00 = surface.values[row0]?.[col0];
  const v01 = surface.values[row0]?.[col1];
  const v10 = surface.values[row1]?.[col0];
  const v11 = surface.values[row1]?.[col1];
  // Guards a malformed lattice only; a well-formed surface always has all four.
  if (v00 === undefined || v01 === undefined || v10 === undefined || v11 === undefined) {
    return null;
  }

  const top = v00 * (1 - tCol) + v01 * tCol;
  const bottom = v10 * (1 - tCol) + v11 * tCol;
  return top * (1 - tRow) + bottom * tRow;
}

function renderRaster(surface: MetricSurface): MetricRaster {
  const bounds = centroidBounds(surface);
  const [minLon, minLat, maxLon, maxLat] = bounds;
  const lonSpan = Math.max(maxLon - minLon, 1e-9);
  const latSpan = Math.max(maxLat - minLat, 1e-9);
  const width = clamp(surface.cols * PIXELS_PER_CELL, MIN_RASTER_WIDTH, MAX_RASTER_WIDTH);
  const height = clamp(Math.round((width * latSpan) / lonSpan), 1, MAX_RASTER_HEIGHT);

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return { canvas, bounds, width, height };
  }

  const image = ctx.createImageData(width, height);

  for (let y = 0; y < height; y += 1) {
    // Canvas y = 0 is the top (north); the value lattice's row 0 is south.
    const lat = maxLat - ((y + 0.5) / height) * latSpan;
    for (let x = 0; x < width; x += 1) {
      const lon = minLon + ((x + 0.5) / width) * lonSpan;
      const value = sampleSurface(surface, lon, lat);
      if (value === null) continue; // outside the rectangle: leave transparent

      // Colored by the real interpolated value in the metric's own units, so
      // the same temperature is the same color on every date and in every city.
      const [r, g, b] = getSmoothColor(value, surface.metric_key);
      const offset = (y * width + x) * 4;
      image.data[offset] = r;
      image.data[offset + 1] = g;
      image.data[offset + 2] = b;
      image.data[offset + 3] = RASTER_ALPHA;
    }
  }

  ctx.putImageData(image, 0, 0);
  return { canvas, bounds, width, height };
}

/** Build (or reuse from cache) the rendered raster for one kriged surface. */
export function buildMetricRaster(cacheKey: string, surface: MetricSurface): MetricRaster {
  const cached = RASTER_CACHE.get(cacheKey);
  if (cached) return cached;

  const raster = renderRaster(surface);
  RASTER_CACHE.set(cacheKey, raster);
  if (RASTER_CACHE.size > MAX_RASTER_CACHE_ENTRIES) {
    const oldestKey = RASTER_CACHE.keys().next().value;
    if (oldestKey) RASTER_CACHE.delete(oldestKey);
  }

  return raster;
}

/** True when the coordinate lands inside the rendered surface rectangle. */
export function isInsideRaster(raster: MetricRaster, lon: number, lat: number): boolean {
  const [minLon, minLat, maxLon, maxLat] = raster.bounds;
  return lon >= minLon && lon <= maxLon && lat >= minLat && lat <= maxLat;
}
