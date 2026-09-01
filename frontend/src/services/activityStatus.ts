export interface ActivityStatusInput {
  simulation: {
    active: boolean;
    fraction: number;
    completed: number;
    total: number;
    etaMs: number;
  };
  backend: {
    loading: boolean;
    fraction?: number;
    detail?: string | null;
    etaSeconds?: number | null;
  };
}

export interface ActivityStatus {
  label: string;
  detail: string;
  fraction: number;
  etaLabel: string;
  indeterminate: boolean;
}

function formatEta(etaMs: number): string {
  const seconds = Math.max(0, Math.ceil(etaMs / 1_000));
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return minutes > 0 ? `ETA ${minutes}m ${remainder.toString().padStart(2, '0')}s` : `ETA ${seconds}s`;
}

function formatSeconds(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return minutes > 0 ? `ETA ${minutes}m ${remainder.toString().padStart(2, '0')}s` : `ETA ${seconds}s`;
}

export function selectActivityStatus(input: ActivityStatusInput): ActivityStatus | null {
  if (input.simulation.active) {
    return {
      label: 'Running simulation',
      detail: `${input.simulation.completed} of ${input.simulation.total} frames`,
      fraction: Math.max(0, Math.min(1, input.simulation.fraction)),
      etaLabel: formatEta(input.simulation.etaMs),
      indeterminate: false,
    };
  }

  if (input.backend.loading) {
    const hasProgress = typeof input.backend.fraction === 'number';
    const etaSeconds = input.backend.etaSeconds;
    return {
      label: 'Preparing map data',
      detail: input.backend.detail ? `Loading ${input.backend.detail}` : 'Starting data service',
      fraction: hasProgress ? Math.max(0, Math.min(1, input.backend.fraction ?? 0)) : 0,
      etaLabel: typeof etaSeconds === 'number' ? formatSeconds(Math.max(0, etaSeconds)) : 'ETA calculating',
      indeterminate: !hasProgress,
    };
  }

  return {
    label: 'Data ready',
    detail: 'Map and simulation services available',
    fraction: 1,
    etaLabel: 'Ready',
    indeterminate: false,
  };
}
