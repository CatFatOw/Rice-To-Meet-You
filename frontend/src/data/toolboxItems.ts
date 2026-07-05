import type { ComponentType } from 'react';
import { Snowflake, Umbrella, Droplets, Fan, Cross, TreePine } from 'lucide-react';

// ============================================================================
// Toolbox items inputs
// ============================================================================


// Definition of a draggable structure available in the toolbox palette.
export interface ToolboxItemDef {
  // Stable id. Also selects the map-pin glyph in utils/toolbox (toolboxGlyph);
  // a new type with no matching glyph falls back to a plain dot.
  type: string;
  label: string;
  color: string; // hex; drives both the palette chip and the map pin
  Icon: ComponentType<{ size?: number | string; color?: string }>;
}

export const TOOLBOX_ITEMS: ToolboxItemDef[] = [
  { type: 'cooling_station', label: 'Cooling Station', color: '#38bdf8', Icon: Snowflake },
  { type: 'shade_canopy', label: 'Shade Canopy', color: '#a3e635', Icon: Umbrella },
  { type: 'water_station', label: 'Water Station', color: '#22d3ee', Icon: Droplets },
  { type: 'misting_fan', label: 'Misting Fan', color: '#818cf8', Icon: Fan },
  { type: 'first_aid', label: 'First Aid', color: '#f87171', Icon: Cross },
  { type: 'tree_planting', label: 'Tree Planting', color: '#4ade80', Icon: TreePine },
];