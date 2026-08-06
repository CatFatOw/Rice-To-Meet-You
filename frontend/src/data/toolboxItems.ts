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
import type { ToolboxItemsByArchetype } from '../types/toolbox';

// In-memory store standing in for a backend table. getToolboxItems reads from
// it; addToolboxItems will eventually write to it (no-op for now). Not exported
// as the public surface — callers should go through the API functions below so
// swapping in a real fetch later is a one-file change.
export const TOOLBOX_ITEMS: ToolboxItemsByArchetype = {
  Vegetation: [
    {
      intervention: 'street_trees',
      category: 'Vegetation',
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
      intervention: 'urban_park',
      category: 'Vegetation',
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
      intervention: 'green_roof',
      category: 'Vegetation',
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
      intervention: 'green_wall',
      category: 'Vegetation',
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
      intervention: 'rain_garden',
      category: 'Vegetation',
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
      intervention: 'hedgerow',
      category: 'Vegetation',
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
      intervention: 'cool_roof',
      category: 'High-albedo surface',
      color: '#f8fafc',
      kind: 'polygon',
      Icon: Home,
      params: {
        albedo: 0.65,
        coverage: 0.35,
        emissivity: 0.9,
      },
    },
    {
      intervention: 'cool_pavement',
      category: 'High-albedo surface',
      color: '#e2e8f0',
      kind: 'polygon',
      Icon: Route,
      params: {
        albedo: 0.25,
        coverage: 0.25,
        emissivity: 0.9,
      },
    },
    {
      intervention: 'reflective_parking',
      category: 'High-albedo surface',
      color: '#cbd5e1',
      kind: 'polygon',
      Icon: SquareParking,
      params: {
        albedo: 0.35,
        coverage: 0.15,
        emissivity: 0.9,
      },
    },
    {
      intervention: 'light_sidewalk',
      category: 'High-albedo surface',
      color: '#f1f5f9',
      kind: 'polygon',
      Icon: Footprints,
      params: {
        albedo: 0.30,
        coverage: 0.10,
        emissivity: 0.9,
      },
    },
    {
      intervention: 'reflective_facade',
      category: 'High-albedo surface',
      color: '#e0f2fe',
      kind: 'polygon',
      Icon: Building2,
      params: {
        albedo: 0.30,
        coverage: 0.20,
        emissivity: 0.9,
      },
    },
  ],

  'Shade structure': [
    {
      intervention: 'solar_canopy',
      category: 'Shade structure',
      color: '#6366f1',
      kind: 'polygon',
      Icon: PanelTop,
      params: {
        opacity: 0.95, //  0–1  fraction of direct beam blocked (intensity)
        coverage: 0.15, // 0–1  shaded footprint as cell fraction (scale)
      },
    },
    {
      intervention: 'awning',
      category: 'Shade structure',
      color: '#818cf8',
      kind: 'polygon',
      Icon: Tent,
      params: {
        opacity: 0.90,
        coverage: 0.05,
      },
    },
    {
      intervention: 'shade_sail',
      category: 'Shade structure',
      color: '#a78bfa',
      kind: 'polygon',
      Icon: Triangle,
      params: {
        opacity: 0.70,
        coverage: 0.10,
      },
    },
    {
      intervention: 'pergola',
      category: 'Shade structure',
      color: '#8b5cf6',
      kind: 'polygon',
      Icon: Grid2x2,
      params: {
        opacity: 0.40,
        coverage: 0.08,
      },
    },
    {
      intervention: 'bus_shelter',
      category: 'Shade structure',
      color: '#7c3aed',
      kind: 'polygon',
      Icon: BusFront,
      params: {
        opacity: 0.85,
        coverage: 0.04,
      },
    },
  ],

  'Evaporative / water': [
    {
      intervention: 'fountain',
      category: 'Evaporative / water',
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
      intervention: 'splash_pad',
      category: 'Evaporative / water',
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
      intervention: 'misting',
      category: 'Evaporative / water',
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
      intervention: 'reflecting_pool',
      category: 'Evaporative / water',
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
      intervention: 'evaporative_pavement',
      category: 'Evaporative / water',
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
    "coverage",
    "emissivity",
  ],

  "Shade structure": [
    "opacity",
    "coverage",
  ],

  "Evaporative / water": [
    "flowRate",
    "radius",
    "activeFraction",
  ],
} as const;
