import { describe, expect, it } from 'vitest';
import { selectActivityStatus } from './activityStatus';

describe('selectActivityStatus', () => {
  it('prioritizes an active simulation and exposes its real progress and ETA', () => {
    expect(selectActivityStatus({
      simulation: { active: true, fraction: 0.4, completed: 2, total: 5, etaMs: 9_000 },
      backend: { loading: true },
    })).toEqual({
      label: 'Running simulation',
      detail: '2 of 5 frames',
      fraction: 0.4,
      etaLabel: 'ETA 9s',
      indeterminate: false,
    });
  });

  it('shows an indeterminate map-loading state without requiring backend progress data', () => {
    expect(selectActivityStatus({
      simulation: { active: false, fraction: 0, completed: 0, total: 0, etaMs: 0 },
      backend: { loading: true },
    })).toEqual({
      label: 'Loading map',
      detail: 'Fetching map data',
      fraction: 0,
      etaLabel: 'Loading',
      indeterminate: true,
    });
  });

  it('does not expose backend preload progress in the frontend-only loading state', () => {
    expect(selectActivityStatus({
      simulation: { active: false, fraction: 0, completed: 0, total: 0, etaMs: 0 },
      backend: { loading: true, fraction: 0.5, detail: 'dallas', etaSeconds: 90 },
    })).toEqual({
      label: 'Loading map',
      detail: 'Fetching map data',
      fraction: 0,
      etaLabel: 'Loading',
      indeterminate: true,
    });
  });

  it('keeps a quiet ready state visible when no work is active', () => {
    expect(selectActivityStatus({
      simulation: { active: false, fraction: 0, completed: 0, total: 0, etaMs: 0 },
      backend: { loading: false },
    })).toEqual({
      label: 'Data ready',
      detail: 'Map and simulation services available',
      fraction: 1,
      etaLabel: 'Ready',
      indeterminate: false,
    });
  });
});
