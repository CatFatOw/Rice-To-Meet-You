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
//
// PARAM NAMING: these keys are the ones the simulation's `get_*_params` guards
// read, verbatim. A guard returns None if any required key is missing and the
// object is then skipped silently — no error, it just shows up in
// `feedback.interventions_without_effect`. Renaming anything here breaks the
// intervention quietly, so the names have to stay in step with the Python side:
//
//   Vegetation           coverPct, lai, irrigation  (+ optional canopyFraction)
//   High-albedo surface  deltaAlbedo, coverPct
//   Shade structure      opacity, footprintFraction
//   Evaporative / water  evapRateLpm, coverageRadiusM, activeFraction
//
// Every fraction is 0–1, not a percentage. Fractions of "the cell" are measured
// against the polygon the planner draws, not against a fixed grid square.
export const TOOLBOX_ITEMS: ToolboxItemsByArchetype = {
  Vegetation: [
    {
      intervention: 'street_trees',
      category: 'Vegetation',
      color: '#22c55e',
      kind: 'polygon',
      Icon: TreePine,
      params: {
        coverPct: 0.35, //      0–1  fraction of ground carrying vegetation (scale)
        canopyFraction: 1.0, // 0–1  of that vegetation, how much sits under a crown
        lai: 4, //             ~0–6  Leaf Area Index — transpiring surface (intensity)
        irrigation: 0.6, //     0–1  water availability committed to (lever)
      },
    },
    {
      intervention: 'urban_park',
      category: 'Vegetation',
      color: '#16a34a',
      kind: 'polygon',
      Icon: Trees,
      params: {
        // Mixed lawn and tree cover, actively irrigated.
        coverPct: 0.70,
        canopyFraction: 0.85,
        lai: 3.5,
        irrigation: 0.8,
      },
    },
    {
      intervention: 'green_roof',
      category: 'Vegetation',
      color: '#4ade80',
      kind: 'polygon',
      Icon: Sprout,
      params: {
        // Sedum mat: covers the roof, but casts no crown shade at all.
        coverPct: 0.90,
        canopyFraction: 0.05,
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
        // Vertical: dense foliage, but it shades a wall rather than the ground.
        coverPct: 0.85,
        canopyFraction: 0.05,
        lai: 2.5,
        irrigation: 0.7,
      },
    },
    {
      intervention: 'rain_garden',
      category: 'Vegetation',
      color: '#15803d',
      kind: 'polygon',
      Icon: Flower2,
      params: {
        // Stormwater-fed, so water is rarely the limiting factor.
        coverPct: 0.60,
        canopyFraction: 0.25,
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
        // Dense foliage, partial crown, usually unirrigated once established.
        coverPct: 0.50,
        canopyFraction: 0.60,
        lai: 4.5,
        irrigation: 0.5,
      },
    },
  ],

  // `deltaAlbedo` is the reflectance GAIN over the surface being replaced, not
  // the finished value — the model divides it by DELTA_ALBEDO_REF = 0.7.
  // Baselines assumed: dark roof ~0.15, asphalt ~0.10, aged concrete ~0.25.
  'High-albedo surface': [
    {
      intervention: 'cool_roof',
      category: 'High-albedo surface',
      color: '#f8fafc',
      kind: 'polygon',
      Icon: Home,
      params: {
        deltaAlbedo: 0.50, // white coating over dark membrane: ~0.15 -> ~0.65
        coverPct: 1.0, //    the drawn polygon is the treated roof
      },
    },
    {
      intervention: 'cool_pavement',
      category: 'High-albedo surface',
      color: '#e2e8f0',
      kind: 'polygon',
      Icon: Route,
      params: {
        deltaAlbedo: 0.25, // cool coating over asphalt: ~0.12 -> ~0.37
        coverPct: 1.0,
      },
    },
    {
      intervention: 'reflective_parking',
      category: 'High-albedo surface',
      color: '#cbd5e1',
      kind: 'polygon',
      Icon: SquareParking,
      params: {
        deltaAlbedo: 0.30,
        coverPct: 0.85, // lots keep islands and markings untreated
      },
    },
    {
      intervention: 'light_sidewalk',
      category: 'High-albedo surface',
      color: '#f1f5f9',
      kind: 'polygon',
      Icon: Footprints,
      params: {
        deltaAlbedo: 0.20, // light concrete over aged concrete is a small gain
        coverPct: 0.60,
      },
    },
    {
      intervention: 'reflective_facade',
      category: 'High-albedo surface',
      color: '#e0f2fe',
      kind: 'polygon',
      Icon: Building2,
      params: {
        deltaAlbedo: 0.25, // reflective cladding: ~0.25 -> ~0.50
        coverPct: 0.80, //   vertical, so it never covers the whole footprint
      },
    },
  ],

  // `footprintFraction` is shaded ground as a fraction of the DRAWN polygon, so
  // a structure the planner outlines directly sits high here. `opacity` goes to
  // the model as-is: it reads the value as the blocked fraction of the direct
  // beam, so sending transmissivity would invert every one of these.
  'Shade structure': [
    {
      intervention: 'solar_canopy',
      category: 'Shade structure',
      color: '#6366f1',
      kind: 'polygon',
      Icon: PanelTop,
      params: {
        opacity: 0.95, //           0–1  fraction of direct beam blocked (intensity)
        footprintFraction: 0.90, // 0–1  shaded ground within the polygon (scale)
      },
    },
    {
      intervention: 'awning',
      category: 'Shade structure',
      color: '#818cf8',
      kind: 'polygon',
      Icon: Tent,
      params: {
        opacity: 0.90, //           opaque fabric
        footprintFraction: 0.50, // narrow strip against the building
      },
    },
    {
      intervention: 'shade_sail',
      category: 'Shade structure',
      color: '#a78bfa',
      kind: 'polygon',
      Icon: Triangle,
      params: {
        opacity: 0.70, //           woven mesh passes some light
        footprintFraction: 0.80,
      },
    },
    {
      intervention: 'pergola',
      category: 'Shade structure',
      color: '#8b5cf6',
      kind: 'polygon',
      Icon: Grid2x2,
      params: {
        opacity: 0.40, //           slatted: a lot of beam gets through
        footprintFraction: 0.85,
      },
    },
    {
      intervention: 'bus_shelter',
      category: 'Shade structure',
      color: '#7c3aed',
      kind: 'polygon',
      Icon: BusFront,
      params: {
        opacity: 0.85, //           solid roof
        footprintFraction: 0.40, // small structure, loose polygon around it
      },
    },
  ],

  // `evapRateLpm` is EFFECTIVE evaporation — the share of water that reaches the
  // air — not pumped throughput. A 20 L/min fountain evaporates a few percent of
  // that; the rest falls back as liquid.
  //
  // i_source saturates at EVAP_POWER_REF_W / (L_v / 60) ≈ 1.22 L/min, so
  // anything at or above that is identical to the model. Splash pads, misting
  // and evaporative pavement are separated below only by radius and duty cycle.
  'Evaporative / water': [
    {
      intervention: 'fountain',
      category: 'Evaporative / water',
      color: '#0ea5e9',
      kind: 'polygon',
      Icon: Droplets,
      params: {
        evapRateLpm: 1.0, //     L/min  coarse spray, ~5% of 20 L/min throughput
        coverageRadiusM: 8, //   m      cooled-plume reach (scale)
        activeFraction: 1.0, //  0–1    runs continuously through the day
      },
    },
    {
      intervention: 'splash_pad',
      category: 'Evaporative / water',
      color: '#06b6d4',
      kind: 'polygon',
      Icon: Waves,
      params: {
        evapRateLpm: 3.0, //    high throughput over a wide pad
        coverageRadiusM: 10,
        activeFraction: 0.6, // seasonal, daytime only
      },
    },
    {
      intervention: 'misting',
      category: 'Evaporative / water',
      color: '#22d3ee',
      kind: 'polygon',
      Icon: SprayCan,
      params: {
        evapRateLpm: 2.5, //    fine droplets flash off almost entirely
        coverageRadiusM: 10,
        activeFraction: 0.5, // cycles on a thermostat
      },
    },
    {
      intervention: 'reflecting_pool',
      category: 'Evaporative / water',
      color: '#0284c7',
      kind: 'polygon',
      Icon: Droplet,
      params: {
        evapRateLpm: 0.5, //   passive surface evaporation from still water
        coverageRadiusM: 6,
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
        evapRateLpm: 1.8, //   wetted porous paving, most of it evaporates
        coverageRadiusM: 5, // tight plume, close to the ground
        activeFraction: 0.8,
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

// The editable fields per archetype, in the order they should be shown. These
// are the same keys the simulation reads — `canopyFraction` is the only
// optional one (the model falls back to DEFAULT_CANOPY_FRACTION = 1.0).
export const ARCHETYPE_PARAMS = {
  Vegetation: [
    'coverPct',
    'canopyFraction',
    'lai',
    'irrigation',
  ],

  'High-albedo surface': [
    'deltaAlbedo',
    'coverPct',
  ],

  'Shade structure': [
    'opacity',
    'footprintFraction',
  ],

  'Evaporative / water': [
    'evapRateLpm',
    'coverageRadiusM',
    'activeFraction',
  ],
} as const;