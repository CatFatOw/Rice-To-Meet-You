import {

  // Vegetation

  Sprout,

  TreePine,

  Trees,

  Leaf,

  Flower2,

  Fence,

  // High-albedo surface

  Home,

  Route,

  SquareParking,

  Footprints,

  Building2,

  // Shade structure

  PanelTop,

  Tent,

  Triangle,

  Grid2x2,

  BusFront,

  // Evaporative / water

  Droplets,

  Waves,

  SprayCan,

  Droplet,

  Blocks,

  // Misc / existing

  Sun,

  Umbrella,

  Sailboat,

  CloudRain,

  ShowerHead,

  CircleDot,

} from 'lucide-react';
import type { ToolboxItemDef } from '../types/toolbox';
export type { ToolboxItemDef };

// The four intervention archetypes. These keys are the single source of truth
// for the "choose archetype" dropdown — it lists Object.keys of the collection.
export type ArchetypeType =
  | 'Vegetation'
  | 'High-albedo surface'
  | 'Shade structure'
  | 'Evaporative / water';

// Shape of the whole categorized collection returned by getToolboxItems().
export type ToolboxItemsByArchetype = Record<ArchetypeType, ToolboxItemDef[]>;

// In-memory store standing in for a backend table. getToolboxItems reads from
// it; addToolboxItems will eventually write to it (no-op for now). Not exported
// as the public surface — callers should go through the API functions below so
// swapping in a real fetch later is a one-file change.
const TOOLBOX_ITEMS: ToolboxItemsByArchetype = {
  Vegetation: [
    {
      id: 'street_trees',
      type: 'street_trees',
      label: 'Street Trees',
      color: '#22c55e',
      kind: 'polygon',
      Icon: TreePine,
      params: {
        coverPct: 0.4, // 0–1  fraction of cell under canopy (scale)
        lai: 4, //         ~0–6 Leaf Area Index — transpiring surface (intensity)
        irrigation: 0.6, // 0–1  irrigation level committed to (lever)
      },
    },
    {
      id: 'urban_park',
      type: 'urban_park',
      label: 'Urban Park',
      color: '#16a34a',
      kind: 'polygon',
      Icon: Trees,
      params: {
        coverPct: 0.8,
        lai: 3.5,
        irrigation: 0.7,
      },
    },
    {
      id: 'green_roof',
      type: 'green_roof',
      label: 'Green Roof',
      color: '#4ade80',
      kind: 'polygon',
      Icon: Sprout,
      params: {
        coverPct: 0.9,
        lai: 2,
        irrigation: 0.5,
      },
    },
    {
      id: 'green_wall',
      type: 'green_wall',
      label: 'Green Wall',
      color: '#65a30d',
      kind: 'polygon',
      Icon: Leaf,
      params: {
        coverPct: 0.7,
        lai: 2.5,
        irrigation: 0.6,
      },
    },
    {
      id: 'rain_garden',
      type: 'rain_garden',
      label: 'Rain Garden',
      color: '#15803d',
      kind: 'polygon',
      Icon: Flower2,
      params: {
        coverPct: 0.6,
        lai: 3,
        irrigation: 0.9,
      },
    },
    {
      id: 'hedgerow',
      type: 'hedgerow',
      label: 'Hedgerow',
      color: '#166534',
      kind: 'polygon',
      Icon: Fence,
      params: {
        coverPct: 0.5,
        lai: 4.5,
        irrigation: 0.4,
      },
    },
  ],

  // Populated later — declared now so the archetype dropdown lists all four.
'High-albedo surface': [
    {
      id: 'cool_roof',
      type: 'cool_roof',
      label: 'Cool Roof Coating',
      color: '#f8fafc',
      kind: 'polygon',
      Icon: Home,
      params: {
        deltaAlbedo: 0.65, // 0–1  albedo increase vs baseline (intensity)
        coverPct: 0.35, //    0–1  treated fraction of cell (scale)
      },
    },
    {
      id: 'cool_pavement',
      type: 'cool_pavement',
      label: 'Cool Pavement Coating',
      color: '#e2e8f0',
      kind: 'polygon',
      Icon: Route,
      params: {
        deltaAlbedo: 0.25,
        coverPct: 0.25,
      },
    },
    {
      id: 'reflective_parking',
      type: 'reflective_parking',
      label: 'Reflective Parking Lot',
      color: '#cbd5e1',
      kind: 'polygon',
      Icon: SquareParking,
      params: {
        deltaAlbedo: 0.35,
        coverPct: 0.15,
      },
    },
    {
      id: 'light_sidewalk',
      type: 'light_sidewalk',
      label: 'Light Concrete Sidewalk',
      color: '#f1f5f9',
      kind: 'polygon',
      Icon: Footprints,
      params: {
        deltaAlbedo: 0.30,
        coverPct: 0.10,
      },
    },
    {
      id: 'reflective_facade',
      type: 'reflective_facade',
      label: 'Reflective Facade Paint',
      color: '#e0f2fe',
      kind: 'polygon',
      Icon: Building2,
      params: {
        deltaAlbedo: 0.30,
        coverPct: 0.20,
      },
    },
  ],

  'Shade structure': [
    {
      id: 'solar_canopy',
      type: 'solar_canopy',
      label: 'Solar PV Canopy',
      color: '#6366f1',
      kind: 'polygon',
      Icon: PanelTop,
      params: {
        opacity: 0.95, //  0–1  fraction of direct beam blocked (intensity)
        coverPct: 0.15, // 0–1  shaded footprint as cell fraction (scale)
      },
    },
    {
      id: 'awning',
      type: 'awning',
      label: 'Solid Awning / Canopy',
      color: '#818cf8',
      kind: 'polygon',
      Icon: Tent,
      params: {
        opacity: 0.90,
        coverPct: 0.05,
      },
    },
    {
      id: 'shade_sail',
      type: 'shade_sail',
      label: 'Shade Sail',
      color: '#a78bfa',
      kind: 'polygon',
      Icon: Triangle,
      params: {
        opacity: 0.70,
        coverPct: 0.10,
      },
    },
    {
      id: 'pergola',
      type: 'pergola',
      label: 'Pergola / Trellis',
      color: '#8b5cf6',
      kind: 'polygon',
      Icon: Grid2x2,
      params: {
        opacity: 0.40,
        coverPct: 0.08,
      },
    },
    {
      id: 'bus_shelter',
      type: 'bus_shelter',
      label: 'Bus Shelter Canopy',
      color: '#7c3aed',
      kind: 'polygon',
      Icon: BusFront,
      params: {
        opacity: 0.85,
        coverPct: 0.04,
      },
    },
  ],

  'Evaporative / water': [
    {
      id: 'fountain',
      type: 'fountain',
      label: 'Spray / Jet Fountain',
      color: '#0ea5e9',
      kind: 'polygon',
      Icon: Droplets,
      params: {
        flowRate: 20, //        L/min  effective evaporation budget (intensity)
        radius: 20, //          m      cooled-plume reach (scale)
        activeFraction: 1.0, // 0–1    duty cycle (scale)
      },
    },
    {
      id: 'splash_pad',
      type: 'splash_pad',
      label: 'Splash Pad',
      color: '#06b6d4',
      kind: 'polygon',
      Icon: Waves,
      params: {
        flowRate: 40,
        radius: 15,
        activeFraction: 0.7,
      },
    },
    {
      id: 'misting',
      type: 'misting',
      label: 'High-Pressure Misting',
      color: '#22d3ee',
      kind: 'polygon',
      Icon: SprayCan,
      params: {
        flowRate: 5,
        radius: 8,
        activeFraction: 0.5,
      },
    },
    {
      id: 'reflecting_pool',
      type: 'reflecting_pool',
      label: 'Reflecting Pool / Pond',
      color: '#0284c7',
      kind: 'polygon',
      Icon: Droplet,
      params: {
        flowRate: 8, // effective evaporation, not pumped throughput
        radius: 25,
        activeFraction: 1.0,
      },
    },
    {
      id: 'evaporative_pavement',
      type: 'evaporative_pavement',
      label: 'Water-Retentive Pavement',
      color: '#38bdf8',
      kind: 'polygon',
      Icon: Blocks,
      params: {
        flowRate: 3,
        radius: 10,
        activeFraction: 0.6,
      },
    },
  ],
};

export const TOOLBOX_ICONS = {
  // Vegetation
  streetTrees: TreePine,
  urbanPark: Trees,
  greenRoof: Sprout,
  greenWall: Leaf,
  rainGarden: Flower2,
  hedgerow: Fence,

  // High-albedo surface
  coolPavement: Sun,
  coolRoof: Building2,
  reflectiveCoating: CircleDot,

  // Shade structure
  shadeCanopy: Umbrella,
  pergola: Tent,
  shadeSail: Sailboat,

  // Evaporative / water
  mistingSystem: CloudRain,
  fountain: Droplets,
  waterFeature: Waves,
  coolingSpray: ShowerHead,
} as const;

export const ARCHETYPE_PARAMS = {
  Vegetation: [
    "coverPct",
    "lai",
    "irrigation",
  ],

  "High-albedo surface": [
    "albedo",
  ],

  "Shade structure": [
    "shadePct",
    "transmittance",
  ],

  "Evaporative / water": [
    "waterCoverage",
    "evaporationRate",
    "flowRate",
  ],
} as const;

// --- Mock API ---------------------------------------------------------------

// Simulated network latency so callers exercise their loading states. Set to 0
// to make the mock resolve synchronously-ish.
const MOCK_LATENCY_MS = 150;

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

// Shallow-clone the collection (record + its arrays) so callers can't mutate
// the in-memory store by holding onto the returned reference. Item objects
// themselves are shared — fine for read-only rendering, and a real fetch would
// hand back fresh objects anyway.
function snapshot(): ToolboxItemsByArchetype {
  return (Object.keys(TOOLBOX_ITEMS) as ArchetypeType[]).reduce((acc, key) => {
    acc[key] = [...TOOLBOX_ITEMS[key]];
    return acc;
  }, {} as ToolboxItemsByArchetype);
}

/**
 * Mock "GET /toolbox-items". Resolves with the categorized collection after a
 * short simulated delay. Swap the body for a real fetch when the endpoint lands
 * — the signature (no args in, Promise<ToolboxItemsByArchetype> out) is the
 * contract callers rely on.
 */
export async function getToolboxItems(): Promise<ToolboxItemsByArchetype> {
  await delay(MOCK_LATENCY_MS);
  return snapshot();
}

// Payload for adding a new intervention: a full item plus the archetype bucket
// it belongs in.
export type AddToolboxItemInput = ToolboxItemDef & { category: ArchetypeType };

/**
 * Mock "POST /toolbox-items". Accepts a new item but intentionally does nothing
 * for now (no persistence, no store mutation) — it just resolves so callers can
 * await it. Wire the body to push into TOOLBOX_ITEMS[input.category] (or a real
 * request) when the feature is ready.
 */
export async function addToolboxItems(input: AddToolboxItemInput): Promise<void> {
  await delay(MOCK_LATENCY_MS);
  void input; // no-op for now
}