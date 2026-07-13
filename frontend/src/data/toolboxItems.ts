import { Snowflake, Umbrella, Droplets, Fan, Cross, TreePine } from 'lucide-react';
import type { ToolboxItemDef } from '../types/toolbox';
export type { ToolboxItemDef };

export const TOOLBOX_ITEMS: ToolboxItemDef[] = [
  { type: 'cooling_station', label: 'Cooling Station', color: '#38bdf8', Icon: Snowflake },
  { type: 'shade_canopy', label: 'Shade Canopy', color: '#a3e635', Icon: Umbrella },
  { type: 'water_station', label: 'Water Station', color: '#22d3ee', Icon: Droplets },
  { type: 'misting_station', label: 'Misting Station', color: '#818cf8', Icon: Fan },
  { type: 'first_aid', label: 'First Aid', color: '#f87171', Icon: Cross },
  { type: 'tree_planting', label: 'Tree Planting', color: '#4ade80', Icon: TreePine },
];