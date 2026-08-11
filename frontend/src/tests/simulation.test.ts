import { describe, it, expect } from 'vitest';
import type { HeatmapPointsByDate, HeatmapMetricValue, Polygon } from '../types/heatmap';
import type { BasePlacedObjectCategorized } from '../hooks/usePlacedObjects';
import { getSimulatedPointsByDate } from '../api/simulation';

// ---------------------------------------------------------------------------
// One heatmap point, one date. This is the Rice University Main Quad
// temperature anchor from the mock backend (value = 91°F at [-95.4015, 29.717]).
// ---------------------------------------------------------------------------
const DATE = '2026-07-05';


// reading("Rice Fondren Library", -95.4002, 29.7182, 92, 70, 32, 57)
const ricePoint: HeatmapMetricValue = {
  value: 91,
  location_name: 'Rice University Main Quad',
  location_coordinates: [-95.4002, 29.7182],
  individual_metrics: {
    temperatureF: '91°F',
    treeCanopyPct: '36%',
    imperviousSurfacePct: '52%',
  },
};

const baseline: HeatmapPointsByDate = {
  [DATE]: [ricePoint],
};

// ---------------------------------------------------------------------------
// One urban intervention: Street Trees (Vegetation archetype), placed as a
// small polygon drawn around the Rice quad so it covers the point above.
// Params mirror the toolbox 'street_trees' item: coverPct 0.4, lai 4,
// irrigation 0.6.
// ---------------------------------------------------------------------------
const streetTreesPolygon: Polygon = [
     [-95.400412, 29.718285],
      [-95.400347, 29.718055],
      [-95.399941, 29.718152],
      [-95.400023, 29.718413], // closing vertex
];

const streetTrees = {
  id: 'street_trees',
  type: 'street_trees',
  label: 'Street Trees',
  geometry: { kind: 'polygon' as const, ring: streetTreesPolygon },
  params: { coverPct: 0.4, lai: 4, irrigation: 0.6 },
};

// Categorized placed objects: only Vegetation is populated for this test.
const placedObjects = {
  Vegetation: [streetTrees],
  'High-albedo surface': [],
  'Shade structure': [],
  'Evaporative / water': [],
} as unknown as BasePlacedObjectCategorized;

describe('getSimulatedPointsByDate', () => {
  it('cools the covered point and leaves the baseline untouched', async () => {
    const simulated = await getSimulatedPointsByDate(
      'temperature',
      baseline,
      placedObjects,
    );

    const cooled = simulated[DATE][0].value;

    // Hand-computed: fLAI = 1 - e^-2 = 0.86466, intensity = 0.273926,
    // ΔT = 5 * intensity = 1.36963, so 91 - 1.36963 = 89.6304.
    expect(cooled).toBeCloseTo(89.6304, 3);
    expect(cooled).toBeLessThan(91);

    // Input must not be mutated — the model works on a clone.
    expect(baseline[DATE][0].value).toBe(91);
  });

  it('leaves points outside the polygon unchanged', async () => {
    const outside: HeatmapPointsByDate = {
      [DATE]: [
        {
          ...ricePoint,
          location_name: 'TMC Core (far away)',
          location_coordinates: [-95.3992, 29.7067],
          value: 98,
        },
      ],
    };

    const simulated = await getSimulatedPointsByDate('temperature', outside, placedObjects);

    expect(simulated[DATE][0].value).toBe(98);
  });

  it('does not cool for a non-temperature metric', async () => {
    const simulated = await getSimulatedPointsByDate('heat_risk_score', baseline, placedObjects);

    expect(simulated[DATE][0].value).toBe(91);
  });
});
