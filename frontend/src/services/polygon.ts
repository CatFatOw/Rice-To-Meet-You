// polygon-utils.ts
// Utilities for turning an arbitrary set of points into a *simple* polygon
// (one whose boundary never crosses itself). Works with deck.gl PolygonLayer,
// where points are [lng, lat] pairs.
import type { Ring } from "../hooks/usePolygonDraw";
export type Point = [number, number]; // [lng, lat]


// Signed area of triangle (p, q, r): sign tells you which side r is on.
function orient(p: Point, q: Point, r: Point): number {
  return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
}

// True only when the interiors of the two segments cross (shared endpoints
// and collinear touches don't count).
function segmentsCross(p1: Point, p2: Point, p3: Point, p4: Point): boolean {
  const d1 = orient(p3, p4, p1);
  const d2 = orient(p3, p4, p2);
  const d3 = orient(p1, p2, p3);
  const d4 = orient(p1, p2, p4);
  return (
    ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
    ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))
  );
}

/**
 * Returns false if the polygon self-intersects (any two edges cross),
 * true if it's a valid simple polygon. Ring may be open or closed.
 */
export function isPolygonSimple(ring: Ring): boolean {
  // Drop a duplicated closing vertex so the wrap-around edge isn't degenerate.
  let pts = ring as Point[];
  if (pts.length > 1) {
    const first = pts[0];
    const last = pts[pts.length - 1];
    if (first[0] === last[0] && first[1] === last[1]) pts = pts.slice(0, -1);
  }

  const n = pts.length;
  if (n < 4) return true; // 3 edges or fewer can't cross

  for (let i = 0; i < n; i++) {
    const a1 = pts[i];
    const a2 = pts[(i + 1) % n];
    for (let j = i + 1; j < n; j++) {
      // Skip edges that share a vertex — adjacent edges and the wrap-around pair.
      if (j === i + 1 || (i === 0 && j === n - 1)) continue;
      const b1 = pts[j];
      const b2 = pts[(j + 1) % n];
      if (segmentsCross(a1, a2, b1, b2)) return false;
    }
  }
  return true;
}