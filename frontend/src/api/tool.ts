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

// The Houston tool set. misting_station -> point (icon), shade_sail +
// cool_roof -> polygon (fill), so both layers have something to render.
// Same set is used for every date in the range below.
const HOUSTON_TOOLS: BasePlacedObject[] = [
  // --- Street trees (vegetation) — Rice University --------------------------
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
      coverPct: 0.4, //     0–1  fraction of ground carrying vegetation
      canopyFraction: 1, // 0–1  fraction of that vegetation under a crown
      lai: 4, //           ~0–6  Leaf Area Index — transpiring surface
      irrigation: 0.6, //   0–1  water availability committed to
    },
    activeFrom: '2020-07-12',
    activeTo: '2020-07-17',
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
      deltaAlbedo: 0.5, // 0–1  reflectance GAIN vs baseline, not the finished value
      coverPct: 0.85, //   0–1  treated fraction of the cell
    },
    activeFrom: '2020-07-12',
    activeTo: '2020-07-17',
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
      opacity: 0.7, //           0–1  fraction of the direct beam blocked
      footprintFraction: 0.6, // 0–1  shaded ground as a fraction of the cell
    },
    activeFrom: '2020-07-12',
    activeTo: '2020-07-17',
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
      evapRateLpm: 2.5, //   L/min  EFFECTIVE evaporation, not delivered flow
      coverageRadiusM: 25, // m     plume reach — distance-falloff scale
      activeFraction: 0.8, // 0–1   duty cycle
    },
    activeFrom: '2020-07-12',
    activeTo: '2020-07-17',
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

/**
 * The inverse, used on the way back in.
 *
 * The simulation branches on the category key by exact string match against its
 * *_CATEGORY constants ('Vegetation', 'High-albedo surface', ...). Assigning the
 * raw `archetype_code` to `category` would hand it 'vegetation', which matches
 * nothing — every fetched object would be skipped and reported in
 * `feedback.interventions_without_effect` with no error anywhere.
 */
const CATEGORY_BY_ARCHETYPE_CODE: Record<string, ArchetypeType> = Object.fromEntries(
  Object.entries(ARCHETYPE_CODE_BY_CATEGORY).map(([category, code]) => [
    code,
    category as ArchetypeType,
  ]),
);

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

  const numericParams: Record<string, number> = {};
  for (const [key, val] of Object.entries(record.parameters)) {
    if (typeof val === 'number') {
      numericParams[key] = val;
    }
  }

  const category = CATEGORY_BY_ARCHETYPE_CODE[record.archetype_code];
  if (!category) {
    // Better to fail loudly here than to have the simulation quietly ignore it.
    throw new Error(
      `Unknown archetype_code "${record.archetype_code}" on intervention ${record.id}`,
    );
  }

  return {
    id: String(record.id),
    type: record.intervention_type,
    name: record.name,
    color: record.color,
    category,
    market_code: record.market_code,
    geometry: mapGeometry,
    params: numericParams,
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
  const params = new URLSearchParams({
    city,
    from_date: fromDate,
    to_date: toDate,
  });

  const response = await fetch(
    `${API_BASE_URL}/urban_intervention/get-urban-interventions-by-city-between-dates?${params.toString()}`,
  );

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Fetch urban interventions between dates failed: ${response.status} ${response.statusText}${
        detail ? ` — ${detail}` : ''
      }`,
    );
  }

  const records = (await response.json()) as UrbanInterventionRecord[];
  return records.map(toPlacedObject);
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

/** "Street Trees" and "street_trees" both need to land on "street_tree". */
const normalize = (value: string) => value.trim().toLowerCase().replace(/[\s-]+/g, '_');

// ---------------------------------------------------------------------------
// Parameter defaults
//
// Each table below holds exactly the keys its `get_*_params` guard reads, and
// nothing else. A guard returns None if any required key is missing or null,
// and the object is then skipped silently — it lands in
// `feedback.interventions_without_effect` with no error raised.
//
//   Vegetation           coverPct, lai, irrigation  (+ optional canopyFraction)
//   High-albedo surface  deltaAlbedo, coverPct
//   Shade structure      opacity, footprintFraction
//   Evaporative / water  evapRateLpm, coverageRadiusM, activeFraction
//
// Every fraction is 0–1, not a percentage — `coverPct` is named "Pct" but feeds
// a 0–1 intensity term directly. Values are stated as the model consumes them,
// so nothing has to be derived at request time.
// ---------------------------------------------------------------------------

const clamp01 = (v: number): number => Math.max(0, Math.min(1, v));

/** Exactly the keys `get_cooling_params` reads. */
interface VegetationParams {
  coverPct: number; //       -> vegetated_coverage
  canopyFraction: number; // -> canopy_fraction (optional; backend defaults to 1.0)
  lai: number; //            -> lai
  irrigation: number; //     -> water_factor
}

/**
 * `canopyFraction` gates the shade channel, which carries 60% of the intensity
 * weight (WEIGHT_SHADE = 0.6). Ground-level and vertical plantings cast no
 * pedestrian shade, so they sit near zero and cool almost entirely through
 * transpiration — which makes their `irrigation` value the thing that decides
 * whether they do anything at all.
 */
const VEGETATION_DEFAULTS: Record<string, VegetationParams> = {
  // Mature crowns over a street: full canopy, moderate ground coverage.
  street_trees: { coverPct: 0.35, canopyFraction: 1.0, lai: 4.0, irrigation: 0.6 },
  street_tree: { coverPct: 0.35, canopyFraction: 1.0, lai: 4.0, irrigation: 0.6 },
  // Mixed lawn and tree cover, actively irrigated.
  urban_park: { coverPct: 0.70, canopyFraction: 0.85, lai: 3.5, irrigation: 0.8 },
  // Sedum mat: covers nearly the whole roof, casts no crown shade, thin foliage.
  green_roof: { coverPct: 0.90, canopyFraction: 0.05, lai: 2.0, irrigation: 0.5 },
  // Vertical surface — dense, but shades a wall rather than the ground.
  green_wall: { coverPct: 0.85, canopyFraction: 0.05, lai: 2.5, irrigation: 0.7 },
  // Stormwater-fed, so water is rarely the limiting factor.
  rain_garden: { coverPct: 0.60, canopyFraction: 0.25, lai: 3.0, irrigation: 0.9 },
  // Dense foliage, partial crown, usually unirrigated once established.
  hedgerow: { coverPct: 0.50, canopyFraction: 0.60, lai: 4.5, irrigation: 0.5 },
};

const VEGETATION_FALLBACK: VegetationParams = VEGETATION_DEFAULTS.street_trees;

/** Exactly the keys `get_albedo_params` reads. */
interface AlbedoParams {
  deltaAlbedo: number; // -> delta_albedo (the GAIN, not the finished value)
  coverPct: number; //    -> area_coverage
}

/**
 * `deltaAlbedo` is normalized against DELTA_ALBEDO_REF = 0.7, which no real
 * treatment reaches — the strongest case here (a cool coating on a dark roof)
 * lands at f_albedo ≈ 0.71. Gains are stated against the surface being
 * replaced: dark roof ≈ 0.15, asphalt ≈ 0.10, aged concrete ≈ 0.25.
 */
const ALBEDO_DEFAULTS: Record<string, AlbedoParams> = {
  // White coating over dark membrane: ~0.15 -> ~0.65.
  cool_roof: { deltaAlbedo: 0.50, coverPct: 1.0 },
  // Reflective cladding over a typical facade: ~0.25 -> ~0.50. Vertical, so it
  // never covers the whole cell.
  reflective_facade: { deltaAlbedo: 0.25, coverPct: 0.80 },
  // Cool coating over asphalt: ~0.12 -> ~0.37.
  cool_pavement: { deltaAlbedo: 0.25, coverPct: 1.0 },
  // Same treatment, but lots keep islands and markings untreated.
  reflective_parking: { deltaAlbedo: 0.30, coverPct: 0.85 },
  // Light concrete over aged concrete: a small gain over a partial footprint.
  light_sidewalk: { deltaAlbedo: 0.20, coverPct: 0.60 },
};

/** Exactly the keys `get_shade_params` reads. */
interface ShadeParams {
  opacity: number; //           -> opacity (blocked fraction of the direct beam)
  footprintFraction: number; // -> shaded_footprint
}

/**
 * `opacity` goes across as-is. The model reads it as the blocked fraction, so
 * sending transmissivity instead would report a 0.95 solar canopy as 0.05 —
 * near-total shade as near-total clarity.
 */
const SHADE_DEFAULTS: Record<string, ShadeParams> = {
  shade_structure: { opacity: 0.85, footprintFraction: 0.80 },
  // Solid PV panels: near-total blockage over a wide footprint.
  solar_canopy: { opacity: 0.95, footprintFraction: 0.90 },
  // Opaque fabric, but only a narrow strip against the building.
  awning: { opacity: 0.90, footprintFraction: 0.50 },
  // Woven mesh passes some light; spans a broad area.
  shade_sail: { opacity: 0.70, footprintFraction: 0.80 },
  shade_canopy: { opacity: 0.70, footprintFraction: 0.80 },
  // Slatted: wide coverage, but a lot of beam gets through.
  pergola: { opacity: 0.40, footprintFraction: 0.85 },
  // Solid roof over a small footprint.
  bus_shelter: { opacity: 0.85, footprintFraction: 0.40 },
};

const SHADE_FALLBACK: ShadeParams = SHADE_DEFAULTS.shade_structure;

/** Exactly the keys `get_evaporative_params` reads. */
interface EvaporativeParams {
  evapRateLpm: number; //     -> evap_rate_lpm (EFFECTIVE evaporation, not flow)
  coverageRadiusM: number; // -> coverage_radius_m
  activeFraction: number; //  -> active_fraction
}

/**
 * `evapRateLpm` is the share of delivered water that actually reaches the air,
 * not the pump's flow rate — a 20 L/min fountain evaporates only a few percent
 * of that, the rest falls back as liquid.
 *
 * Worth knowing before tuning these: i_source saturates at
 * EVAP_POWER_REF_W / (L_v / 60) ≈ 1.22 L/min. Anything at or above that value
 * is identical to the model, so misting, splash pads and evaporative pavement
 * are separated here only by radius and duty cycle.
 */
const EVAPORATIVE_DEFAULTS: Record<string, EvaporativeParams> = {
  // Fine droplets flash off almost entirely; cycles on a thermostat.
  misting_station: { evapRateLpm: 2.5, coverageRadiusM: 10, activeFraction: 0.5 },
  misting: { evapRateLpm: 2.5, coverageRadiusM: 10, activeFraction: 0.5 },
  // Coarse spray, ~5% evaporates, but runs continuously through the day.
  fountain: { evapRateLpm: 1.0, coverageRadiusM: 8, activeFraction: 1.0 },
  // High throughput over a wide pad; seasonal and daytime-only.
  splash_pad: { evapRateLpm: 3.0, coverageRadiusM: 10, activeFraction: 0.6 },
  // Passive surface evaporation only — still water, small exchange area.
  reflecting_pool: { evapRateLpm: 0.5, coverageRadiusM: 6, activeFraction: 1.0 },
  // Wetted porous paving: most of it evaporates, tight plume near the ground.
  evaporative_pavement: { evapRateLpm: 1.8, coverageRadiusM: 5, activeFraction: 0.8 },
};

const EVAPORATIVE_FALLBACK: EvaporativeParams = EVAPORATIVE_DEFAULTS.misting_station;

function toBackendParameters(
  interventionType: InterventionType,
  params: ToolboxItemDef['params'],
  interventionName?: string,
): Record<string, unknown> {
  const p = params as unknown as Record<string, number | undefined>;
  const name = interventionName ? normalize(interventionName) : '';

  switch (interventionType) {
    // Vegetation: street_trees, urban_park, green_roof, green_wall,
    // rain_garden, hedgerow
    case 'street_tree': {
      const d = VEGETATION_DEFAULTS[name] ?? VEGETATION_FALLBACK;

      return {
        coverPct: clamp01(p.coverPct ?? d.coverPct),
        canopyFraction: clamp01(p.canopyFraction ?? d.canopyFraction),
        lai: Math.max(0, p.lai ?? d.lai),
        irrigation: clamp01(p.irrigation ?? d.irrigation),
      };
    }

    // High-albedo: cool_roof, reflective_facade, cool_pavement,
    // reflective_parking, light_sidewalk
    case 'cool_roof':
    case 'cool_pavement': {
      const d =
        ALBEDO_DEFAULTS[name] ??
        (interventionType === 'cool_roof'
          ? ALBEDO_DEFAULTS.cool_roof
          : ALBEDO_DEFAULTS.cool_pavement);

      return {
        deltaAlbedo: clamp01(p.deltaAlbedo ?? d.deltaAlbedo),
        coverPct: clamp01(p.coverPct ?? d.coverPct),
      };
    }

    // Shade: solar_canopy, awning, shade_sail, shade_canopy, pergola,
    // bus_shelter
    case 'shade_structure': {
      const d = SHADE_DEFAULTS[name] ?? SHADE_FALLBACK;

      return {
        opacity: clamp01(p.opacity ?? d.opacity),
        footprintFraction: clamp01(p.footprintFraction ?? d.footprintFraction),
      };
    }

    // Evaporative: fountain, splash_pad, misting, reflecting_pool,
    // evaporative_pavement
    case 'misting_station': {
      const d = EVAPORATIVE_DEFAULTS[name] ?? EVAPORATIVE_FALLBACK;

      return {
        evapRateLpm: Math.max(0, p.evapRateLpm ?? d.evapRateLpm),
        coverageRadiusM: Math.max(0, p.coverageRadiusM ?? d.coverageRadiusM),
        activeFraction: clamp01(p.activeFraction ?? d.activeFraction),
      };
    }

    default: {
      const exhaustive: never = interventionType;
      throw new Error(`Unmapped intervention type: ${String(exhaustive)}`);
    }
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

  // Evaporative sources anchor on a point, a line centroid or a polygon
  // centroid, so any kind works — but a missing geometry silently anchors at
  // (0, 0) and cools a spot in the Atlantic, so it is required all the same.
  if (!input.geometry) {
    throw new Error('Cannot create an intervention without geometry');
  }

  // Vegetation, albedo and shade objects only reach a reading through
  // `get_object_polygon`, which requires kind === 'polygon' with a ring. A tree
  // dropped as a point or a pavement drawn as a line cools nothing, whatever
  // its params say.
  if (interventionType !== 'misting_station') {
    if (input.geometry.kind !== 'polygon') {
      throw new Error(
        `"${input.intervention}" must be drawn as a polygon — ${input.geometry.kind} ` +
          'geometry is ignored by the simulation for this archetype',
      );
    }
    if (!input.geometry.ring?.length) {
      throw new Error(`"${input.intervention}" was drawn as a polygon with an empty ring`);
    }
  }

  return {
    market_code: input.market_code,
    name: input.intervention,
    color: input.color,
    archetype_code: archetypeCode,
    geometry: input.geometry,
    intervention_type: interventionType,
    parameters: toBackendParameters(interventionType, input.params, input.intervention),
    active_from: input.activeFrom ?? null,
    active_to: input.activeTo ?? null,
  };
}

/**
 * POST /urban_intervention/create-urban-intervention
 *
 * Throws before the request if the input can't be expressed as a valid create
 * body (unmapped intervention or archetype, wrong geometry kind, empty ring).
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