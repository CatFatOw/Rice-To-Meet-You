import { Droplets, Sun, Trees, Umbrella } from 'lucide-react';
import type { ToolboxItemDef } from '../types/toolbox';
export type { ToolboxItemDef };

export const TOOLBOX_ITEMS: ToolboxItemDef[] = [
  {
    id: 'vegetation',
    type: 'vegetation',
    label: 'Vegetation',
    color: '#22c55e',
    kind: 'polygon',
    Icon: Trees,
    params: {
      coverPct: 0.6,      // 0–1  fraction of cell under vegetation (scale)
      lai: 3,             // ~0–6 Leaf Area Index — transpiring surface (intensity)
      irrigation: 0.7,    // 0–1  irrigation level the planner commits to (lever)
    },
  },
  {
    id: 'cool_surface',
    type: 'cool_surface',
    label: 'Cool Surfaces',
    color: '#fbbf24',
    kind: 'polygon',
    Icon: Sun,
    params: {
      albedo: 0.65,       // 0–1  solar reflectance of the coating (intensity)
      coverage: 1,        // 0–1  treated fraction of the cell (scale)
    },
  },
  {
    id: 'shade_canopy',
    type: 'shade_canopy',
    label: 'Shade Structure',
    color: '#64748b',
    kind: 'polygon',
    Icon: Umbrella,
    params: {
      opacity: 0.8,       // 0–1  fraction of direct beam blocked (intensity)
      coverage: 1,        // 0–1  footprint fraction actually shaded (scale)
    },
  },
  {
    id: 'water_misting',
    type: 'water_misting',
    label: 'Water & Misting',
    color: '#818cf8',
    kind: 'point',
    Icon: Droplets,
    params: {
      flowRate: 20,       // L/min  evaporation budget (intensity)
      radius: 8,          // m      plume reach → distance falloff (scale)
      activeFraction: 0.5,// 0–1    duty cycle: ~1 fountain, <1 switched misting
    },
  },
];