import type { ComponentType } from 'react';

// Definition of a draggable structure available in the toolbox palette.
export interface ToolboxItemDef {
  // Stable id. Also selects the map-pin glyph in utils/toolbox (toolboxGlyph);
  // a new type with no matching glyph falls back to a plain dot.
  type: string;
  label: string;
  color: string; // hex; drives both the palette chip and the map pin
  Icon: ComponentType<{ size?: number | string; color?: string }>;
}

// A placed instance of a toolbox item, positioned in map (lng/lat) space.
export interface PlacedObject {
  id: string;
  type: string;
  longitude: number;
  latitude: number;
}
