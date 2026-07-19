// api/placedObjects.ts
import type { Geometry } from '../types/simulation';
import type { BasePlacedObject } from '../hooks/usePlacedObjects';

// date (ISO day) -> city name -> the tools placed for that city on that day.
export type PlacedObjectsByDateCity = Record<string, Record<string, BasePlacedObject[]>>;

// --- Geometry builders (keep the seed data below readable) ---
const point = (longitude: number, latitude: number): Geometry => ({
  kind: 'point',
  longitude,
  latitude,
});

const polygon = (ring: [number, number][]): Geometry => ({
  kind: 'polygon',
  ring,
});

// The Houston tool set. misting_station -> point (icon), shade_canopy +
// cool_roof -> polygon (fill), so both layers have something to render.
// Same set is used for every date in the range below.
// The Houston tool set: a single street-tree polygon.
const HOUSTON_TOOLS: BasePlacedObject[] = [
  {
    id: 'placed-hou-1',
    type: 'street_trees',
    category: 'Vegetation',
    name: 'Rice University street trees',
    color: '#22c55e',
    geometry: polygon([
      [-95.400412, 29.718285],
      [-95.400347, 29.718055],
      [-95.399941, 29.718152],
      [-95.400023, 29.718413],
    ]),
    params: {
        coverPct: 0.4, // 0–1  fraction of cell under canopy (scale)
        lai: 4, //         ~0–6 Leaf Area Index — transpiring surface (intensity)
        irrigation: 0.6, // 0–1  irrigation level committed to (lever)
      },
    activeFrom: '2026-07-05',
    activeTo: '2026-07-07'
  },
];

const HOUSTON_DATES = ['2026-07-05', '2026-07-06', '2026-07-07', '2026-07-08'];

const clone = <T,>(value: T): T =>
  typeof structuredClone === 'function'
    ? structuredClone(value)
    : JSON.parse(JSON.stringify(value));

// Build date -> { Houston: tools } for each date, cloning the tool set so the
// four dates don't share the same object references.
const MOCK_PLACED_OBJECTS: PlacedObjectsByDateCity = Object.fromEntries(
  HOUSTON_DATES.map((date) => [date, { Houston: clone(HOUSTON_TOOLS) }]),
);

// Simulate network latency so callers exercise their loading states.
const LATENCY_MS = 300;

/** Full map: every date -> every city -> tools. */
export async function fetchPlacedObjects(): Promise<PlacedObjectsByDateCity> {
  await new Promise((resolve) => setTimeout(resolve, LATENCY_MS));
  return clone(MOCK_PLACED_OBJECTS);
}

/** Tools for one date across all cities. Empty object if the date is unknown. */
export async function fetchPlacedObjectsByDate(
  date: string,
): Promise<Record<string, BasePlacedObject[]>> {
  await new Promise((resolve) => setTimeout(resolve, LATENCY_MS));
  return clone(MOCK_PLACED_OBJECTS[date] ?? {});
}

/** Tools for one city on one date. Empty array if either is unknown. */
export async function fetchPlacedObjectsForCity(
  date: string,
  city: string,
): Promise<BasePlacedObject[]> {
  await new Promise((resolve) => setTimeout(resolve, LATENCY_MS));
  return clone(MOCK_PLACED_OBJECTS[date]?.[city] ?? []);
}