import { TOOLBOX_ITEMS, type ToolboxItemDef } from '../data/toolboxItems';
import type { PlacedObject } from '../types/toolbox';
export type { PlacedObject };

// --- Toolbox plumbing + rendering -------------------------------------------
//
// The editable list of tools lives in ../data/toolboxItems. This file derives
// the lookup, the drag identifier, and the map-pin marker SVGs from it.
//
// Re-exported so existing imports from '../utils/toolbox' keep working; you can
// import TOOLBOX_ITEMS / ToolboxItemDef from either path.
export { TOOLBOX_ITEMS };
export type { ToolboxItemDef };

export const TOOLBOX_BY_TYPE: Record<string, ToolboxItemDef> = Object.fromEntries(
  TOOLBOX_ITEMS.map((item) => [item.type, item]),
);

// Custom MIME type used to carry the toolbox item type through an HTML5 drag.
export const TOOLBOX_DRAG_MIME = 'application/x-heatmap-toolbox-item';

// White-on-color glyph fragments, drawn centered on the origin, inside the pin.
// Keyed by item `type`; add a case here if you want a custom pin for a new
// tool, otherwise it falls back to a plain dot.
function toolboxGlyph(type: string, color: string): string {
  switch (type) {
    case 'misting_station':
      return `<g fill="${color}">
        <circle r="2.2"/>
        <path d="M0 -2.4 C-6 -9 -9 -4 -2.2 -1 Z"/>
        <path d="M2.4 0 C9 -6 4 -9 1 -2.2 Z"/>
        <path d="M0 2.4 C6 9 9 4 2.2 1 Z"/>
        <path d="M-2.4 0 C-9 6 -4 9 -1 2.2 Z"/>
      </g>`;
    case 'shade_canopy':
      return `<g fill="${color}">
        <path d="M-9 1 A9 9 0 0 1 9 1 Z"/>
        <rect x="-0.9" y="1" width="1.8" height="8" rx="0.9"/>
      </g>`;
    case 'cool_roofs':
      return `<g fill="${color}" stroke="${color}" stroke-width="1.6" stroke-linecap="round">
        <path d="M-9 2.5 L0 -4 L9 2.5 L9 5 L-9 5 Z" stroke="none"/>
        <line x1="0" y1="-9" x2="0" y2="-6.5"/>
        <line x1="-6" y1="-7" x2="-4.6" y2="-5.4"/>
        <line x1="6" y1="-7" x2="4.6" y2="-5.4"/>
      </g>`;
    default:
      return `<circle r="5" fill="${color}"/>`;
  }
}

// Teardrop map pin (tip at the bottom) with a white disc and a colored glyph.
export function toolboxMarkerSvg(type: string, color: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 60" width="48" height="60">
    <path d="M24 2 C13 2 4 11 4 22 C4 36 24 57 24 57 C24 57 44 36 44 22 C44 11 35 2 24 2 Z" fill="${color}" stroke="#0f172a" stroke-width="2.5"/>
    <circle cx="24" cy="22" r="13" fill="#ffffff" stroke="#0f172a" stroke-width="1.5"/>
    <g transform="translate(24,22)">${toolboxGlyph(type, color)}</g>
  </svg>`;
}

export function toolboxMarkerDataUrl(type: string, color: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(toolboxMarkerSvg(type, color))}`;
}