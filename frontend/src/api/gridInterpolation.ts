import type { HeatmapMetricValue, MetricSurface } from '../types/heatmap';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

/**
 * Metrics the backend will krige into a continuous surface: every metric the
 * map can display except avg_daily_visits and heat_risk_score. Those two are
 * per-POI records rather than samples of a field that exists between the POIs -
 * a visit count, and a score carrying its POI's name, brand and address - so
 * they keep the point-density heatmap. Kept in sync with SURFACE_METRICS in
 * app/services/grid_interpolation_service.py; anything else is rejected with a
 * 400.
 */
const SURFACE_METRICS = [
  'average_temperature_c',
  'average_temperature_f',
  'heat_index_c',
  'heat_index_f',
  'average_relative_humidity_pct',
  'local_temperature_c',
  'local_temperature_f',
  'change_in_temperature',
  'change_in_average_temperature_c',
  'change_in_average_temperature_f',
  'change_in_local_temperature_c',
  'change_in_local_temperature_f',
] as const;

type SurfaceMetric = (typeof SURFACE_METRICS)[number];

function isSurfaceMetric(metric: string): metric is SurfaceMetric {
  return (SURFACE_METRICS as readonly string[]).includes(metric);
}

// Lattice resolution. Higher looks smoother but costs a larger kriging solve on
// every request; 48x48 renders cleanly at city zoom levels.
const DEFAULT_RESOLUTION = 48;

interface SurfaceOptions {
  rows?: number;
  cols?: number;
  bounds?: [number, number, number, number];
  signal?: AbortSignal;
}

/**
 * Fetch a city's kriged surface, computed entirely server-side.
 *
 * The readings never reach the browser: the backend already holds them in
 * memory, so it reads, krige and returns only the lattice. This is the path
 * every non-simulated view should use - it replaces fetching thousands of
 * points and posting them straight back.
 */
export async function fetchCitySurface(
  metricKey: string,
  city: string,
  date: string,
  options: SurfaceOptions & { additionalMetrics?: string[] } = {},
): Promise<MetricSurface | null> {
  if (!isSurfaceMetric(metricKey) || !city || !date) return null;

  const {
    rows = DEFAULT_RESOLUTION,
    cols = DEFAULT_RESOLUTION,
    additionalMetrics,
    signal,
  } = options;
  const query = new URLSearchParams({
    city,
    date,
    metric_key: metricKey,
    rows: String(rows),
    cols: String(cols),
  });
  // Repeated key per value - that is how FastAPI reads List[str]. These are
  // interpolated onto the same lattice and surface in the tooltip.
  additionalMetrics?.forEach((name) => query.append('additional_metrics', name));

  const response = await fetch(
    `${API_BASE_URL}/grid_interpolation/surface?${query.toString()}`,
    { headers: { Accept: 'application/json' }, signal },
  );

  // 404 means no readings for that city/date - an empty result, not a failure.
  if (response.status === 404) return null;

  if (!response.ok) {
    throw new Error(
      `City surface request failed: ${response.status} ${response.statusText}`,
    );
  }

  return response.json() as Promise<MetricSurface>;
}

/**
 * Ordinary-krige readings supplied by the client into a continuous surface.
 *
 * This is the simulation path, and the only reason it exists: a running
 * simulation's adjusted readings live only in the browser, so they have to be
 * posted to be drawn. Every other view names its city/date/metric and lets
 * fetchCitySurface do the reading server-side.
 *
 * `city` scopes the surface - the backend takes the lattice extent from that
 * city's rectangle. Returns null when no city is selected, which is the
 * zoomed-out view where no surface belongs.
 *
 * `date` and `additionalMetrics` drive the tooltip's secondary rows. A
 * simulation only alters the drawn metric, so those rows are read server-side
 * for the city and date instead of being posted alongside the points.
 */
export async function fetchInterpolatedSurface(
  metricKey: string,
  city: string | null,
  points: HeatmapMetricValue[],
  options: SurfaceOptions & { date?: string; additionalMetrics?: string[] } = {},
): Promise<MetricSurface | null> {
  // No city means no scoped extent to draw within, so there is no surface to
  // ask for. This is the zoomed-out national view.
  if (!city || !isSurfaceMetric(metricKey) || points.length === 0) return null;

  const {
    rows = DEFAULT_RESOLUTION,
    cols = DEFAULT_RESOLUTION,
    bounds,
    date,
    additionalMetrics,
    signal,
  } = options;

  const body = {
    metric_key: metricKey,
    city,
    rows,
    cols,
    bounds,
    date,
    additional_metrics: additionalMetrics,
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

// How many frame surfaces to krige at once when prefetching a simulation. Each
// request is a full variogram fit plus a rows x cols solve, so this trades a
// shorter prefetch against not handing the backend a whole timeline at once.
const PREFETCH_CONCURRENCY = 4;

/**
 * Krige every frame of a simulation up front, keyed by frame date.
 *
 * Playback is a local animation: the timeline advances the date, the points and
 * the surface in a single commit, so what is drawn always belongs to the date
 * it is labelled with. Fetching per frame instead would leave the surface a
 * round trip behind the frame on every tick, because the frame advances
 * synchronously and the request cannot.
 *
 * A frame whose surface fails is simply absent from the result - that frame
 * falls back to the point-density heatmap rather than failing the whole run.
 */
export async function fetchSimulationSurfaces(
  metricKey: string,
  city: string | null,
  framesByDate: Record<string, HeatmapMetricValue[]>,
  options: SurfaceOptions & { additionalMetrics?: string[] } = {},
): Promise<Record<string, MetricSurface>> {
  const dates = Object.keys(framesByDate);
  if (!city || !isSurfaceMetric(metricKey) || dates.length === 0) return {};

  const surfaces: Record<string, MetricSurface> = {};
  let cursor = 0;

  // Workers share the cursor; the read and the increment are not separated by
  // an await, so no two workers can claim the same date.
  const worker = async () => {
    while (cursor < dates.length) {
      const date = dates[cursor];
      cursor += 1;
      try {
        const surface = await fetchInterpolatedSurface(
          metricKey,
          city,
          framesByDate[date],
          { ...options, date },
        );
        if (surface) surfaces[date] = surface;
      } catch (error) {
        if (options.signal?.aborted) return;
        console.error(`Failed to interpolate the surface for ${date}`, error);
      }
    }
  };

  await Promise.all(
    Array.from({ length: Math.min(PREFETCH_CONCURRENCY, dates.length) }, worker),
  );

  return surfaces;
}
