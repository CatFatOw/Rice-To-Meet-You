import { Fan, Umbrella, Home } from 'lucide-react';
import type { ToolboxItemDef } from '../types/toolbox';
export type { ToolboxItemDef };

export const TOOLBOX_ITEMS: ToolboxItemDef[] = [
  { type: 'misting_station', label: 'Misting Station', color: '#818cf8', kind: 'point', Icon: Fan },
  { type: 'shade_canopy', label: 'Shade Canopy', color: '#a3e635', kind: 'polygon', Icon: Umbrella },
  { type: 'cool_roofs', label: 'Cool Roofs', color: '#fbbf24', kind: 'polygon', Icon: Home },
];