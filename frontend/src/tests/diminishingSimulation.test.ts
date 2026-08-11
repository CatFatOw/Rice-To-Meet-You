import { describe, expect, it } from 'vitest';
import { runDiminishingReturnSimulation } from '../api/diminishingSimulation';
import type { BasePlacedObject, BasePlacedObjectCategorized } from '../hooks/usePlacedObjects';
import type { HeatmapPointsByDate } from '../types/heatmap';

const date = '2026-07-05';
const points: HeatmapPointsByDate = {
  [date]: [{
    value: 36,
    location_name: 'Overlap test point',
    location_coordinates: [-95.4, 29.717],
    individual_metrics: { avg_temperature_c: '36°C', relative_humidity: '55%' },
  }],
};

const tree = {
  id: 'tree', type: 'street_trees', name: 'Tree', category: 'Vegetation',
  geometry: { kind: 'polygon' as const, ring: [[-95.401, 29.716], [-95.399, 29.716], [-95.399, 29.718], [-95.401, 29.718]] },
  params: { coverPct: 0.25, lai: 1, irrigation: 0.3 },
};
const water = {
  id: 'water', type: 'fountain', name: 'Water', category: 'Evaporative / water',
  geometry: { kind: 'point' as const, longitude: -95.4, latitude: 29.717 },
  params: { flowRate: 2, radius: 100, activeFraction: 0.5 },
};
const concrete = {
  id: 'concrete', type: 'cool_pavement', name: 'Concrete', category: 'High-albedo surface',
  geometry: { kind: 'polygon' as const, ring: [[-95.401, 29.716], [-95.399, 29.716], [-95.399, 29.718], [-95.401, 29.718]] },
  params: { deltaAlbedo: 0.3, coverPct: 0.4 },
};

function categorized(objects: BasePlacedObject[]): BasePlacedObjectCategorized {
  return {
    Vegetation: objects.filter((object) => object.category === 'Vegetation'),
    'High-albedo surface': objects.filter((object) => object.category === 'High-albedo surface'),
    'Shade structure': [],
    'Evaporative / water': objects.filter((object) => object.category === 'Evaporative / water'),
  };
}

describe('runDiminishingReturnSimulation interaction modes', () => {
  it('preserves the original standard calculation when no mode is supplied', async () => {
    const implicit = await runDiminishingReturnSimulation('temperature', points, categorized([tree, water]));
    const explicit = await runDiminishingReturnSimulation('temperature', points, categorized([tree, water]), 'standard');

    expect(implicit.pointsByDate[date][0].value).toBeCloseTo(explicit.pointsByDate[date][0].value, 8);
    expect(implicit.feedback.mode).toBe('standard');
  });

  it('boosts an overlapping tree + water intervention in contextual mode', async () => {
    const standard = await runDiminishingReturnSimulation('temperature', points, categorized([tree, water]), 'standard');
    const contextual = await runDiminishingReturnSimulation('temperature', points, categorized([tree, water]), 'contextual');

    expect(contextual.pointsByDate[date][0].value).toBeLessThan(standard.pointsByDate[date][0].value);
    expect(contextual.feedback.contextualInteractions.join(' ')).toContain('Vegetation + water');
    expect(contextual.pointsByDate[date][0].individual_metrics?.simulation_overlap_count).toBe('2');
  });

  it('reduces the overlapping tree + reflective concrete combination in contextual mode', async () => {
    const standard = await runDiminishingReturnSimulation('temperature', points, categorized([tree, concrete]), 'standard');
    const contextual = await runDiminishingReturnSimulation('temperature', points, categorized([tree, concrete]), 'contextual');

    expect(contextual.pointsByDate[date][0].value).toBeGreaterThan(standard.pointsByDate[date][0].value);
    expect(contextual.feedback.contextualInteractions.join(' ')).toContain('reflective concrete');
  });
});
