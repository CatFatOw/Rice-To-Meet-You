import maplibregl from 'maplibre-gl';
import type { SurfaceType } from '../types/map';
export type { SurfaceType };

export function classifySurface(
  map: maplibregl.Map,
  x: number,
  y: number,
): { type: SurfaceType; detail?: string } {
  // A few px of padding so thin features (roads) reliably register a hit.
  const features = map.queryRenderedFeatures([
    [x - 4, y - 4],
    [x + 4, y + 4],
  ]);

  // queryRenderedFeatures returns topmost-first, so the first match by
  // priority is usually what's visually "on top" at that point.
  for (const f of features) {
    switch (f.sourceLayer) {
      case 'building':
        return { type: 'building' };
      case 'transportation':
      case 'transportation_name':
        return { type: 'road', detail: f.properties?.class as string };
      case 'water':
      case 'waterway':
        return { type: 'water', detail: f.properties?.class as string };
      case 'park':
      case 'landcover':
        return { type: 'green', detail: f.properties?.class as string };
      case 'landuse':
        return { type: 'land', detail: f.properties?.class as string };
    }
  }
  return { type: 'unknown' };
}

export function formatMetricName(metricKey: string): string {
  if (metricKey === 'heat_risk_score') return 'Heat Risk';
  if (metricKey === 'visitor_activity') return 'Visitor Activity';
  return metricKey
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

