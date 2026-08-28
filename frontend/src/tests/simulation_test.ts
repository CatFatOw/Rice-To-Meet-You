/**
 * =============================================================================
 * Simulation test harness
 * =============================================================================
 *
 * Runs the intervention simulation against the Houston mock readings and prints
 * ONLY the points that actually moved, so you can verify the physics without
 * scrolling past ~48 unchanged readings per date.
 *
 * Run it:      npx tsx src/path/to/simulation_test.ts
 * Or import:   await runSimulationTest()
 *
 * Edit METRIC and PLACED_OBJECTS below — everything else is machinery.
 */

// ⚠️ Adjust these two paths to wherever the files live in your tree.
import { getSimulatedPointsByDate } from '../api/simulation';
import { getHeatmapPointsByCityDateMetric } from '../api/map';

import type { HeatmapPointsByDate, HeatmapMetricValue } from '../types/heatmap';
import type {
  BasePlacedObject,
  BasePlacedObjectCategorized,
} from '../hooks/usePlacedObjects';

// =============================================================================
// ── TESTER KNOBS ─────────────────────────────────────────────────────────────
// =============================================================================

/**
 * Which layer to simulate.
 *   'change_in_temperature' → point.value becomes the signed ΔT (baseline 0)
 *   'temperature'           → point.value becomes the new temperature in °C
 *
 * Anything that doesn't match /temp/i is a no-op: `metricIsTemperature` gates
 * the whole loop, so e.g. 'visitor_density' will always report zero changes.
 */
const METRIC = 'temperature';

/**
 * Geometry helper — the simulation only looks at `kind` and `ring`.
 * If your codebase already exports one, import that instead and delete this.
 */
const polygon = (ring: [number, number][]) => ({ kind: 'polygon' as const, ring });

/**
 * The planner's interventions, as a flat list (the shape the toolbox produces).
 *
 * Category strings MUST match the *_CATEGORY constants in the simulation:
 *   'Vegetation' | 'High-albedo surface' | 'Shade structure' | 'Evaporative / water'
 *
 * Geometry:
 *   - Vegetation / albedo / shade need a polygon — any other `kind` is skipped
 *     silently by getObjectPolygon.
 *   - Evaporative takes a point (a polygon/line works too; its centroid becomes
 *     the emitter).
 *
 * activeFrom / activeTo are ISO dates, both optional. The mock readings cover
 * 2026-07-05 … 2026-07-08.
 */
const HOUSTON_TOOLS: BasePlacedObject[] = [
  // --- Street trees (vegetation) — Rice University --------------------------
  {
    id: 'placed-hou-1',
    type: 'street_trees',
    category: 'Vegetation',
    name: 'Rice University street trees',
    color: '#22c55e',
    geometry: polygon([
      [-95.400412, 29.718285],
      [-95.400347, 29.718055],
      [-95.399941, 29.718152],
      [-95.400023, 29.718413],
    ]),
    params: {
      coverPct: 0.4,   // 0–1  fraction of cell under canopy (scale)
      lai: 4,          // ~0–6 Leaf Area Index — transpiring surface (intensity)
      irrigation: 0.6, // 0–1  irrigation level committed to (lever)
      // canopyFraction omitted → DEFAULT_CANOPY_FRACTION (1) is used
    },
    activeFrom: '2026-07-05',
    activeTo: '2026-07-07', // note: excludes 2026-07-08
  },

  // --- Cool roof coating (high-albedo surface) — TMC rooftop -----------------
  {
    id: 'placed-hou-2',
    type: 'cool_roof',
    category: 'High-albedo surface',
    name: 'TMC cool roof coating',
    color: '#e2e8f0',
    geometry: polygon([
      [-95.39960, 29.70700],
      [-95.39880, 29.70700],
      [-95.39880, 29.70640],
      [-95.39960, 29.70640],
    ]),
    params: {
      deltaAlbedo: 0.6, // 0–1  reflectance gain vs baseline (asphalt ~0.1 → cool coat ~0.7)
      coverPct: 0.85,   // 0–1  treated fraction of the cell (scale, linear)
    },
    activeFrom: '2026-07-05',
    activeTo: '2026-07-08',
  },

  // --- Shade sail (shade structure) — Hermann Park plaza ---------------------
  {
    id: 'placed-hou-3',
    type: 'shade_sail',
    category: 'Shade structure',
    name: 'Hermann Park shade sail',
    color: '#a78bfa',
    geometry: polygon([
      [-95.39120, 29.71910],
      [-95.39040, 29.71910],
      [-95.39040, 29.71850],
      [-95.39120, 29.71850],
    ]),
    params: {
      opacity: 0.7,           // 0–1  fraction of the direct beam blocked (sail ~0.7)
      footprintFraction: 0.6, // 0–1  shaded ground as a fraction of the cell (scale, linear)
    },
    activeFrom: '2026-07-05',
    activeTo: '2026-07-08',
  },

  // --- High-pressure misting (evaporative) — Hermann Park, point source ------
  {
    id: 'placed-hou-4',
    type: 'misting_station',
    category: 'Evaporative / water',
    name: 'Hermann Park misting station',
    color: '#38bdf8',
    geometry: { kind: 'point', longitude: -95.3889, latitude: 29.7168 },
    params: {
      evapRateLpm: 2.5,    // L/min  effective evaporation (high-pressure misting)
      coverageRadiusM: 25, // m      plume reach — distance-falloff scale
      activeFraction: 0.8, // 0–1    duty cycle (humidity/temperature gated)
    },
    activeFrom: '2026-07-05',
    activeTo: '2026-07-08',
  },
] as unknown as BasePlacedObject[];
// ^ cast because this literal is hand-written rather than produced by the
//   usePlacedObjects hook. If it stops compiling, that's a signal the toolbox
//   shape drifted — worth fixing rather than widening the cast.

/**
 * getSimulatedPointsByDate iterates Object.entries(placedObjects), so it needs
 * the category-keyed shape rather than the flat list. Group on the way in, and
 * keep HOUSTON_TOOLS above as the thing you edit.
 */
function groupByCategory(tools: BasePlacedObject[]): BasePlacedObjectCategorized {
  const grouped: Record<string, BasePlacedObject[]> = {};
  for (const tool of tools) {
    if (!tool.category) continue;
    (grouped[tool.category] ??= []).push(tool);
  }
  return grouped as unknown as BasePlacedObjectCategorized;
}

const PLACED_OBJECTS = groupByCategory(HOUSTON_TOOLS);

async function callHeatmapPointByDateHouston(
  metric: string,
): Promise<HeatmapPointsByDate> {
  const dates = ['2026-07-05', '2026-07-06', '2026-07-07', '2026-07-08'];
  const byDate: HeatmapPointsByDate = {};

  for (const date of dates) {
    const { points } = await getHeatmapPointsByCityDateMetric('Houston', date, metric);
    byDate[date] = points;
  }

  return byDate;
}

// =============================================================================
// ── DIFFING ──────────────────────────────────────────────────────────────────
// =============================================================================

/** Below this, treat a value as unchanged (float noise, not cooling). */
const EPSILON = 1e-6;

const coordKey = (c: [number, number]): string => `${c[0]},${c[1]}`;

/** True if `after` differs from `before` in value or in any sub-metric string. */
function pointChanged(
  before: HeatmapMetricValue,
  after: HeatmapMetricValue,
): boolean {
  if (Math.abs(after.value - before.value) > EPSILON) return true;

  // Catch metadata-only edits (RH bumped, avg_temperature_c rewritten) even
  // when the headline value happens to land in the same place.
  const b = before.individual_metrics ?? {};
  const a = after.individual_metrics ?? {};
  for (const key of new Set([...Object.keys(b), ...Object.keys(a)])) {
    if (b[key] !== a[key]) return true;
  }
  return false;
}

/**
 * Reduce a simulated set down to just the readings the interventions touched,
 * keeping the by-date grouping. Dates with no changes are dropped entirely.
 *
 * Matches points by coordinate rather than array index, so it stays correct if
 * the simulation ever reorders or filters.
 */
export function changedPointsByDate(
  baseline: HeatmapPointsByDate,
  simulated: HeatmapPointsByDate,
): HeatmapPointsByDate {
  const result: HeatmapPointsByDate = {};

  for (const [date, afterPoints] of Object.entries(simulated)) {
    const beforeByCoord = new Map(
      (baseline[date] ?? []).map((p) => [coordKey(p.location_coordinates), p]),
    );

    const changed = afterPoints.filter((after) => {
      const before = beforeByCoord.get(coordKey(after.location_coordinates));
      if (!before) return true; // no baseline counterpart → treat as changed
      return pointChanged(before, after);
    });

    if (changed.length > 0) result[date] = changed;
  }

  return result;
}

// =============================================================================
// ── REPORTING ────────────────────────────────────────────────────────────────
// =============================================================================

/**
 * Print the changed points, one table per date, plus a summary line.
 * Takes the baseline too so it can show before → after rather than just after.
 */
export function printChanged(
  baseline: HeatmapPointsByDate,
  changed: HeatmapPointsByDate,
): void {
  const totalPoints = Object.values(baseline).reduce((n, p) => n + p.length, 0);
  const totalChanged = Object.values(changed).reduce((n, p) => n + p.length, 0);

  console.log(`\nmetric: ${METRIC}`);
  console.log(
    `changed ${totalChanged} / ${totalPoints} points across ` +
      `${Object.keys(changed).length} / ${Object.keys(baseline).length} dates`,
  );

  if (totalChanged === 0) {
    console.log(
      '\nNothing moved. Usual causes: metric is not a temperature layer, ' +
        'the polygon misses every reading, geometry.kind is not "polygon", ' +
        'a required param is missing (the object is skipped silently), or the ' +
        'active window excludes all dates.\n',
    );
    return;
  }

  const deltas: number[] = [];

  for (const [date, points] of Object.entries(changed)) {
    const beforeByCoord = new Map(
      (baseline[date] ?? []).map((p) => [coordKey(p.location_coordinates), p]),
    );

    const rows = points.map((after) => {
      const before = beforeByCoord.get(coordKey(after.location_coordinates));
      const beforeValue = before?.value ?? NaN;
      const delta = after.value - beforeValue;
      deltas.push(delta);

      return {
        location: `${after.location_coordinates[1].toFixed(4)}, ${after.location_coordinates[0].toFixed(4)}`,
        lon: after.location_coordinates[0],
        lat: after.location_coordinates[1],
        before: Number(beforeValue.toFixed(2)),
        after: Number(after.value.toFixed(2)),
        delta: Number(delta.toFixed(3)),
        temp: after.individual_metrics?.avg_temperature_c ?? '—',
        rh: after.individual_metrics?.relative_humidity ?? '—',
      };
    });

    console.log(`\n── ${date} — ${rows.length} changed ─────────────────────`);
    console.table(rows);
  }

  const min = Math.min(...deltas);
  const max = Math.max(...deltas);
  const mean = deltas.reduce((a, b) => a + b, 0) / deltas.length;
  const nonFinite = deltas.filter((d) => !Number.isFinite(d)).length;

  console.log(
    `\ndelta — min ${min.toFixed(3)}  max ${max.toFixed(3)}  ` +
      `mean ${mean.toFixed(3)}${nonFinite ? `  ⚠️ ${nonFinite} non-finite` : ''}`,
  );

  // On a temperature layer every delta should be ≤ 0; on the ΔT layer the value
  // IS the signed change, so a positive delta means the model warmed a point.
  const warmed = deltas.filter((d) => d > EPSILON).length;
  if (warmed > 0) {
    console.log(`⚠️ ${warmed} point(s) got WARMER — check the sign convention.`);
  }
  console.log('');
}

// =============================================================================
// ── ENTRY POINT ──────────────────────────────────────────────────────────────
// =============================================================================

export async function runSimulationTest(): Promise<{
  baseline: HeatmapPointsByDate;
  simulated: HeatmapPointsByDate;
  changed: HeatmapPointsByDate;
}> {
  // callHeatmapPointByDateHouston clones per date, and getSimulatedPointsByDate
  // deep-clones its input, so `baseline` stays pristine and is safe to diff against.
  const baseline = await callHeatmapPointByDateHouston(METRIC);
  const simulated = await getSimulatedPointsByDate(METRIC, baseline, PLACED_OBJECTS);
  const changed = changedPointsByDate(baseline, simulated);

  printChanged(baseline, changed);
  return { baseline, simulated, changed };
}

runSimulationTest().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});