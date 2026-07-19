import {
  Sprout,
  TreePine,
  Trees,
  Leaf,
  Flower2,
  Fence,
  Sun,
  Building2,
  Umbrella,
  Tent,
  Sailboat,
  CloudRain,
  Waves,
  Droplets,
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
  'High-albedo surface': [],
  'Shade structure': [],
  'Evaporative / water': [],
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