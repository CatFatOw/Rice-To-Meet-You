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
  const simulated = await getSimulatedPointsByDate(
    METRIC,
    '2026-07-05',
    '2026-07-08',
    'Houston',
  );
  const changed = changedPointsByDate(baseline, simulated);

  printChanged(baseline, changed);
  return { baseline, simulated, changed };
}

runSimulationTest().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});