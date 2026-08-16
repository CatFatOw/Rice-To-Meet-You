// api/placedObjects.ts
import type { Geometry } from '../types/simulation';
import type { BasePlacedObject } from '../hooks/usePlacedObjects';
import { TOOLBOX_ITEMS } from '../data/toolboxItems';
import type {
  AddToolboxItemInput,
  ToolboxItemDef,
  ToolboxItemsByArchetype,
} from '../types/toolbox';

// date (ISO day) -> city name -> the tools placed for that city on that day.
export type PlacedObjectsByDateCity = Record<string, Record<string, BasePlacedObject[]>>;

// --- Geometry builders (keep the seed data below readable) ---
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
      [-95.401231, 29.718059],
      [-95.401166, 29.717829],
      [-95.400760, 29.717926],
      [-95.400842, 29.718187],
    ]),
    params: {
        coverPct: 0.4, // 0–1  fraction of cell under canopy (scale)
        lai: 4, //         ~0–6 Leaf Area Index — transpiring surface (intensity)
        irrigation: 0.6, // 0–1  irrigation level committed to (lever)
      },
    activeFrom: '2020-07-12',
    activeTo: '2020-07-17'
  },
  // --- Cool roof coating (high-albedo surface) — TMC rooftop -----------------
  {
    id: 'placed-hou-2',
    type: 'cool_roof',
    category: 'High-albedo surface',
    name: 'TMC cool roof coating',
    color: '#e2e8f0',
    geometry: polygon([
      [-95.39960, 29.70700],
      [-95.39880, 29.70700],
      [-95.39880, 29.70640],
      [-95.39960, 29.70640],
    ]),
    params: {
      deltaAlbedo: 0.6, // 0–1  reflectance gain vs baseline (asphalt ~0.1 → cool coat ~0.7)
      coverPct: 0.85,   // 0–1  treated fraction of the cell (scale, linear)
    },
    activeFrom: '2020-07-12',
    activeTo: '2020-07-17'
  },

  // --- Shade sail (shade structure) — Hermann Park plaza ---------------------
  {
    id: 'placed-hou-3',
    type: 'shade_sail',
    category: 'Shade structure',
    name: 'Hermann Park shade sail',
    color: '#a78bfa',
    geometry: polygon([
      [-95.39120, 29.71910],
      [-95.39040, 29.71910],
      [-95.39040, 29.71850],
      [-95.39120, 29.71850],
    ]),
    params: {
      opacity: 0.7,           // 0–1  fraction of the direct beam blocked (sail ~0.7)
      footprintFraction: 0.6, // 0–1  shaded ground as a fraction of the cell (scale, linear)
    },
    activeFrom: '2020-07-12',
    activeTo: '2020-07-17'
  },
    // --- High-pressure misting (evaporative) — Hermann Park, point source ------
  {
    id: 'placed-hou-4',
    type: 'misting_station',
    category: 'Evaporative / water',
    name: 'Hermann Park misting station',
    color: '#38bdf8',
    geometry: { kind: 'point', longitude: -95.3889, latitude: 29.7168 },
    params: {
      evapRateLpm: 2.5,    // L/min  effective evaporation (high-pressure misting)
      coverageRadiusM: 25, // m      plume reach — distance-falloff scale
      activeFraction: 0.8, // 0–1    duty cycle (humidity/temperature gated)
    },
    activeFrom: '2020-07-12',
    activeTo: '2020-07-17'
  },

  
];

const HOUSTON_DATES = [
  '2020-07-12',
  '2020-07-13',
  '2020-07-14',
  '2020-07-15',
  '2020-07-16',
  '2020-07-17',
];

const clone = <T,>(value: T): T =>
  typeof structuredClone === 'function'
    ? structuredClone(value)
    : JSON.parse(JSON.stringify(value));

// Build date -> { Houston: tools } for each date in the active window, cloning
// the tool set so dates do not share the same object references.
const MOCK_PLACED_OBJECTS: PlacedObjectsByDateCity = Object.fromEntries(
  HOUSTON_DATES.map((date) => [date, { Houston: clone(HOUSTON_TOOLS) }]),
);

// Simulate network latency so callers exercise their loading states.
const LATENCY_MS = 300;

// Simulated network latency for toolbox-item APIs.
const TOOLBOX_LATENCY_MS = 150;

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));



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


/** Mock "POST /toolbox-items". */
export async function addPlacedObjects(input: AddToolboxItemInput): Promise<void> {
  await delay(TOOLBOX_LATENCY_MS);
  TOOLBOX_ITEMS[input.category] = [...TOOLBOX_ITEMS[input.category], input];
}

/** Mock "POST /urban-interventions". Empty stub — no-op besides latency. */
export async function createNewUrbanIntervention(input: ToolboxItemDef): Promise<void> {
  await delay(TOOLBOX_LATENCY_MS);
  // TODO: wire to real endpoint. Currently a no-op mock.
  void input;
}

/** Mock "GET /custom-urban-interventions". Empty stub — no items yet. */
export async function fetchCustomUrbanInterventions(): Promise<ToolboxItemsByArchetype> {
  await delay(TOOLBOX_LATENCY_MS);
  return {
    Vegetation: [],
    'High-albedo surface': [],
    'Shade structure': [],
    'Evaporative / water': [],
  };
}