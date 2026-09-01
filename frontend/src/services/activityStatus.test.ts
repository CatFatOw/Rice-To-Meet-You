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

  it('shows an indeterminate data-preparation state while the backend is unavailable', () => {
    expect(selectActivityStatus({
      simulation: { active: false, fraction: 0, completed: 0, total: 0, etaMs: 0 },
      backend: { loading: true },
    })).toEqual({
      label: 'Preparing map data',
      detail: 'Starting data service',
      fraction: 0,
      etaLabel: 'ETA calculating',
      indeterminate: true,
    });
  });

  it('uses the backend preload percent and ETA when that status is available', () => {
    expect(selectActivityStatus({
      simulation: { active: false, fraction: 0, completed: 0, total: 0, etaMs: 0 },
      backend: { loading: true, fraction: 0.5, detail: 'dallas', etaSeconds: 90 },
    })).toEqual({
      label: 'Preparing map data',
      detail: 'Loading dallas',
      fraction: 0.5,
      etaLabel: 'ETA 1m 30s',
      indeterminate: false,
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
