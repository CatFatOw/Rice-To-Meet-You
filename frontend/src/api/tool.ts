// api/placedObjects.ts
import type { Geometry } from '../types/simulation';
import type { BasePlacedObject } from '../hooks/usePlacedObjects';
import type {
  AddToolboxItemInput,
  ArchetypeType,
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
    market_code: 'houston',
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
    market_code: 'houston',
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
    market_code: 'houston',
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
    market_code: 'houston',
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

const API_BASE_URL = 'http://localhost:8000';


/** Full map: every date -> every city -> tools. */
export async function fetchPlacedObjects(): Promise<PlacedObjectsByDateCity> {
  await new Promise((resolve) => setTimeout(resolve, LATENCY_MS));
  return clone(MOCK_PLACED_OBJECTS);
}

type UrbanInterventionRecord = {
  id: string;
  market_code: string;
  name: string;
  color: string;
  archetype_code: string;
  intervention_type: string;
  geometry_kind: 'point' | 'line' | 'polygon';
  geometry: {
    type: 'Point' | 'LineString' | 'Polygon';
    coordinates: number[] | number[][] | number[][][];
  };
  parameters: Record<string, number | boolean>;
  active_from: string | null;
  active_to: string | null;
  status: string;
};

function toPlacedObject(record: UrbanInterventionRecord): BasePlacedObject {
  const { geometry } = record;

  let mapGeometry: Geometry;
  if (geometry.type === 'Point') {
    const [longitude, latitude] = geometry.coordinates as [number, number];
    mapGeometry = { kind: 'point', longitude, latitude };
  } else if (geometry.type === 'LineString') {
    mapGeometry = { kind: 'line', coordinates: geometry.coordinates as [number, number][] };
  } else {
    const [ring] = geometry.coordinates as [number, number][][];
    mapGeometry = { kind: 'polygon', ring };
  }

  return {
    id: String(record.id),
    type: record.intervention_type,
    name: record.name,
    color: record.color,
    market_code: record.market_code,
    geometry: mapGeometry,
    params: record.parameters,
    activeFrom: record.active_from ?? undefined,
    activeTo: record.active_to ?? undefined,
  };
}

/** Tools for one city on one date, loaded from the urban-intervention API. */
export async function fetchPlacedObjectsByCityDate(
  date: string,
  city: string,
): Promise<BasePlacedObject[]> {
  const params = new URLSearchParams({ city, as_of: date });
  const response = await fetch(
    `${API_BASE_URL}/urban_intervention/get-urban-interventions-by-city-date?${params.toString()}`,
  );
  console.log(JSON.stringify(response))

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Fetch urban interventions failed: ${response.status} ${response.statusText}${
        detail ? ` — ${detail}` : ''
      }`,
    );
  }

  const records = (await response.json()) as UrbanInterventionRecord[];
  return records.map(toPlacedObject);
}

/** Tools for one city across an inclusive ISO-date range. */
export async function fetchPlacedObjectsForCity(
  fromDate: string,
  toDate: string,
  city: string,
): Promise<BasePlacedObject[]> {
  await new Promise((resolve) => setTimeout(resolve, LATENCY_MS));

  const objectsById = new Map<string, BasePlacedObject>();
  for (const [date, byCity] of Object.entries(MOCK_PLACED_OBJECTS)) {
    if (date < fromDate || date > toDate) continue;

    for (const object of byCity[city] ?? []) {
      objectsById.set(object.id, object);
    }
  }

  return clone([...objectsById.values()]);
}

// ---------------------------------------------------------------------------
// POST /urban_intervention/create-urban-intervention
// ---------------------------------------------------------------------------

/** The `intervention_type` discriminants the backend accepts. */
export type InterventionType =
  | 'cool_roof'
  | 'misting_station'
  | 'street_tree'
  | 'shade_structure'
  | 'cool_pavement';

export type InterventionStatus = 'draft' | 'active' | 'archived';

interface UrbanInterventionCreateBody {
  market_code: string;
  name: string;
  color: string;
  archetype_code: string;
  geometry: Geometry;
  intervention_type: InterventionType;
  parameters: Record<string, unknown>;
  status?: InterventionStatus;
  active_from?: string | null;
  active_to?: string | null;
}

/**
 * Tool identifier -> the backend discriminant.
 *
 * The two vocabularies don't line up on their own: the seed data uses
 * `street_trees` (plural) and `shade_sail`, neither of which is a literal the
 * API accepts. Anything not listed here is rejected before the request goes
 * out, rather than sent and 422'd.
 */
const INTERVENTION_TYPE_BY_TOOL: Record<string, InterventionType> = {
  street_tree: 'street_tree',
  street_trees: 'street_tree',
  urban_park: 'street_tree',
  green_roof: 'street_tree',
  green_wall: 'street_tree',
  rain_garden: 'street_tree',
  hedgerow: 'street_tree',
  cool_roof: 'cool_roof',
  cool_pavement: 'cool_pavement',
  reflective_parking: 'cool_pavement',
  light_sidewalk: 'cool_pavement',
  reflective_facade: 'cool_roof',
  shade_structure: 'shade_structure',
  solar_canopy: 'shade_structure',
  awning: 'shade_structure',
  shade_sail: 'shade_structure',
  shade_canopy: 'shade_structure',
  pergola: 'shade_structure',
  bus_shelter: 'shade_structure',
  misting_station: 'misting_station',
  fountain: 'misting_station',
  splash_pad: 'misting_station',
  misting: 'misting_station',
  reflecting_pool: 'misting_station',
  evaporative_pavement: 'misting_station',
};

/**
 * Archetype -> `archetype_code`.
 *
 * These are guesses — the codes weren't in the schema you shared. Confirm them
 * against the archetype table before relying on this.
 */
const ARCHETYPE_CODE_BY_CATEGORY: Record<ArchetypeType, string> = {
  Vegetation: 'vegetation',
  'High-albedo surface': 'high_albedo_surface',
  'Shade structure': 'shade_structure',
  'Evaporative / water': 'evaporative_water',
};

/** "Street Trees" and "street_trees" both need to land on "street_tree". */
const normalize = (value: string) => value.trim().toLowerCase().replace(/[\s-]+/g, '_');

function toBackendParameters(
  interventionType: InterventionType,
  params: ToolboxItemDef['params'],
): Record<string, unknown> {
  switch (interventionType) {
    case 'cool_roof':
      return {
        albedo: params.albedo ?? 0,
        emissivity: params.emissivity ?? 0,
      };
    case 'cool_pavement':
      return {
        albedo: params.albedo ?? 0,
        width_m: params.coverage ?? 1,
      };
    case 'street_tree':
      return {
        canopyRadius_m: 5,
        canopyHeight_m: 8,
        lai: params.lai ?? 0,
        deciduous: true,
      };
    case 'shade_structure':
      return {
        transmissivity: 1 - (params.opacity ?? 0),
        height_m: 3,
      };
    case 'misting_station':
      return {
        nozzleCount: 1,
        flowRate_L_per_min: params.flowRate ?? 0,
        dropletDiameter_um: 100,
        mountHeight_m: 3,
      };
  }
}

function toCreateBody(input: AddToolboxItemInput): UrbanInterventionCreateBody {
  const interventionType = INTERVENTION_TYPE_BY_TOOL[normalize(input.intervention)];
  if (!interventionType) {
    throw new Error(`No intervention_type mapped for "${input.intervention}"`);
  }

  const archetypeCode = ARCHETYPE_CODE_BY_CATEGORY[input.category];
  if (!archetypeCode) {
    throw new Error(`No archetype_code mapped for category "${input.category}"`);
  }
  if (!input.market_code?.trim()) {
    throw new Error('Cannot create an intervention without market_code');
  }
  if (!input.geometry) {
    throw new Error('Cannot create an intervention without geometry');
  }

  return {
    market_code: input.market_code,
    name: input.intervention,
    color: input.color,
    archetype_code: archetypeCode,
    geometry: input.geometry,
    intervention_type: interventionType,
    parameters: toBackendParameters(interventionType, input.params),
    active_from: input.activeFrom ?? null,
    active_to: input.activeTo ?? null,
  };
}

/**
 * POST /urban_intervention/create-urban-intervention
 *
 * Throws before the request if the input can't be expressed as a valid create
 * body (unmapped intervention or archetype, empty polygon ring).
 */
export async function addPlacedObjects(input: AddToolboxItemInput): Promise<void> {
  const body = toCreateBody(input);

  const response = await fetch(
    `${API_BASE_URL}/urban_intervention/create-urban-intervention`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );

  if (!response.ok) {
    // FastAPI puts validation failures in the body; surface them rather than
    // just the status, since a 422 here is almost always a field mismatch.
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Create urban intervention failed: ${response.status} ${response.statusText}${
        detail ? ` — ${detail}` : ''
      }`,
    );
  }
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


