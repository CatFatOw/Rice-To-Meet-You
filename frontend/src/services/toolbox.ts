import { getToolboxItems, type ToolboxItemDef } from '../data/toolboxItems';
import type { PlacedObject } from '../types/toolbox';
import type { Ring } from '../hooks/usePolygonDraw';
export type { PlacedObject };



export const TOOLBOX_BY_TYPE: Record<string, ToolboxItemDef> = {};

void getToolboxItems()
  .then((itemsByArchetype) => {
    const entries = Object.values(itemsByArchetype)
      .flat()
      .map((item) => [item.type, item] as const);
    Object.assign(TOOLBOX_BY_TYPE, Object.fromEntries(entries));
  })
  .catch((error) => {
    console.error('Failed to initialize toolbox items by type', error);
  });

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


/**
 * Returns the area centroid (center of mass) of a polygon ring as [lng, lat].
 * Works for any simple polygon; ring may be open or closed (first point
 * repeated at the end is fine). Falls back to the vertex average for
 * degenerate rings (zero area, e.g. all points collinear or identical).
 */
export function polygonCenter(ring: Ring): [number, number] {
  const n = ring.length;
  if (n === 0) throw new Error('polygonCenter: ring has no points');
  if (n === 1) return [ring[0][0], ring[0][1]];
  if (n === 2) {
    return [(ring[0][0] + ring[1][0]) / 2, (ring[0][1] + ring[1][1]) / 2];
  }

  let twiceArea = 0;
  let cx = 0;
  let cy = 0;

  // Shoelace-weighted centroid. Sum over each edge (i -> i+1), wrapping the
  // last vertex back to the first so an open ring is treated as closed.
  for (let i = 0; i < n; i++) {
    const [x0, y0] = ring[i];
    const [x1, y1] = ring[(i + 1) % n];
    const cross = x0 * y1 - x1 * y0;
    twiceArea += cross;
    cx += (x0 + x1) * cross;
    cy += (y0 + y1) * cross;
  }

  // Degenerate polygon (no area): fall back to the mean of the vertices.
  if (twiceArea === 0) {
    const sum = ring.reduce<[number, number]>(
      (acc, [x, y]) => [acc[0] + x, acc[1] + y],
      [0, 0],
    );
    return [sum[0] / n, sum[1] / n];
  }

  const factor = 1 / (3 * twiceArea);
  return [cx * factor, cy * factor];
}



/**
 * Returns true if [longitude, latitude] lies inside the polygon ring.
 * Ray-casting (even–odd rule): counts edge crossings of a ray going right
 * from the point; odd = inside. Ring may be open or closed (repeating the
 * first point at the end is fine). Points exactly on an edge/vertex are
 * boundary cases and may return either result — see note below.
 */
export function isPointInPolygon(
  ring: Ring,
  longitude: number,
  latitude: number,
): boolean {
  const n = ring.length;
  if (n < 3) return false; // not a polygon — no interior

  const x = longitude;
  const y = latitude;
  let inside = false;

  // Walk each edge (j -> i), wrapping the last vertex back to the first so an
  // open ring is treated as closed.
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];

    // Does the horizontal ray at y cross this edge, and is the crossing to the
    // right of x? Each qualifying crossing flips the inside/outside state.
    const intersects =
      yi > y !== yj > y &&
      x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;

    if (intersects) inside = !inside;
  }

  return inside;
}