import type { BoundaryGeometry, HeatmapMetricValue, MetricSurface } from '../types/heatmap';

export type { MetricSurface };

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

/**
 * Metrics the backend will krige into a continuous surface. Kept in sync with
 * SURFACE_METRICS in app/services/grid_interpolation_service.py; anything else
 * is rejected with a 400.
 */
export const SURFACE_METRICS = ['average_temperature_c', 'change_in_temperature'] as const;

export type SurfaceMetric = (typeof SURFACE_METRICS)[number];

export function isSurfaceMetric(metric: string): metric is SurfaceMetric {
  return (SURFACE_METRICS as readonly string[]).includes(metric);
}

// Lattice resolution. Higher looks smoother but costs a larger kriging solve on
// every request; 48x48 renders cleanly at city zoom levels.
const DEFAULT_RESOLUTION = 48;

export interface SurfaceOptions {
  rows?: number;
  cols?: number;
  bounds?: [number, number, number, number];
  signal?: AbortSignal;
}

/**
 * The city outline a surface is clipped to, fetched on its own. Useful for
 * drawing the extent before any surface has loaded; the surface response
 * carries the same geometry, so this is not needed on the render path.
 */
export async function fetchCityBoundary(
  city: string,
  signal?: AbortSignal,
): Promise<CityBoundary | null> {
  const response = await fetch(
    `${API_BASE_URL}/grid_interpolation/city_boundary?city=${encodeURIComponent(city)}`,
    { headers: { Accept: 'application/json' }, signal },
  );

  // An unknown city is a 400 here, not an error worth throwing on: the map
  // simply has no outline to draw for it.
  if (!response.ok) return null;

  return response.json() as Promise<CityBoundary>;
}

export interface CityBoundary {
  city: string;
  state: string;
  bounds: [number, number, number, number];
  geometry: BoundaryGeometry;
}

/**
 * Ordinary-krige the given readings into a continuous surface.
 *
 * Points are sent from the client rather than read server-side on purpose:
 * during a simulation run the adjusted readings exist only in the browser, and
 * they must be drawn through exactly the same path as saved data.
 *
 * `city` scopes the surface: the backend takes the lattice extent from that
 * city's outline and clips the result to it. Returns null when there is no
 * city selected, which is the zoomed-out view where no surface belongs.
 */
export async function fetchInterpolatedSurface(
  metricKey: string,
  city: string | null,
  points: HeatmapMetricValue[],
  options: SurfaceOptions = {},
): Promise<MetricSurface | null> {
  // No city means no scoped extent to draw within, so there is no surface to
  // ask for. This is the zoomed-out national view.
  if (!city || !isSurfaceMetric(metricKey) || points.length === 0) return null;

  const { rows = DEFAULT_RESOLUTION, cols = DEFAULT_RESOLUTION, bounds, signal } = options;

  const body = {
    metric_key: metricKey,
    city,
    rows,
    cols,
    bounds,
    points: points.map((point) => ({
      longitude: point.location_coordinates[0],
      latitude: point.location_coordinates[1],
      value: point.value,
    })),
  };

  const response = await fetch(`${API_BASE_URL}/grid_interpolation/surface`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new Error(
      `Interpolated surface request failed: ${response.status} ${response.statusText}`,
    );
  }

  return response.json() as Promise<MetricSurface>;
}

export interface CitySurfaces {
  metric_key: string;
  surfaces: MetricSurface[];
  /** City -> why it produced no surface (too few readings inside its outline). */
  skipped: Record<string, string>;
}

/**
 * Krige one independent surface per city.
 *
 * The backend partitions the readings by city outline and fits each city on its
 * own readings alone, so every city gets a surface generated from its own data
 * rather than a slice of one wider fit. Cities without enough readings inside
 * them are reported in `skipped` instead of being drawn.
 *
 * Pass `cities` to restrict the set; omit it to build a surface for whichever
 * cities the supplied readings actually fall inside.
 */
export async function fetchInterpolatedCitySurfaces(
  metricKey: string,
  points: HeatmapMetricValue[],
  options: SurfaceOptions & { cities?: string[] } = {},
): Promise<CitySurfaces | null> {
  if (!isSurfaceMetric(metricKey) || points.length === 0) return null;

  const { rows = DEFAULT_RESOLUTION, cols = DEFAULT_RESOLUTION, cities, signal } = options;

  const response = await fetch(`${API_BASE_URL}/grid_interpolation/surfaces`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      metric_key: metricKey,
      rows,
      cols,
      cities,
      points: points.map((point) => ({
        longitude: point.location_coordinates[0],
        latitude: point.location_coordinates[1],
        value: point.value,
      })),
    }),
    signal,
  });

  if (!response.ok) {
    throw new Error(
      `City surfaces request failed: ${response.status} ${response.statusText}`,
    );
  }

  return response.json() as Promise<CitySurfaces>;
}
