import { CircleCheck, LoaderCircle } from 'lucide-react';
import useBackendPreloadStatus from '../hooks/useBackendPreloadStatus';
import { selectActivityStatus } from '../services/activityStatus';
import type { SimulationProgressDisplay } from '../types/statistics';

interface ActivityStatusPillProps {
  isSimulationActive: boolean;
  simulationProgress: SimulationProgressDisplay;
  isMapLoading: boolean;
}

export default function ActivityStatusPill({
  isSimulationActive,
  simulationProgress,
  isMapLoading,
}: ActivityStatusPillProps) {
  const backendStatus = useBackendPreloadStatus();
  const status = selectActivityStatus({
    simulation: {
      active: isSimulationActive,
      fraction: simulationProgress.fraction,
      completed: simulationProgress.completedFrames,
      total: simulationProgress.totalFrames,
      etaMs: simulationProgress.etaMs,
    },
    backend: {
      loading: isMapLoading || backendStatus.loading,
      fraction: backendStatus.fraction,
      detail: backendStatus.detail,
      etaSeconds: backendStatus.etaSeconds,
    },
  });

  const isReady = status.etaLabel === 'Ready';

  return (
    <aside
      aria-live="polite"
      aria-label={`${status.label}. ${status.detail}. ${status.etaLabel}.`}
      className="fixed bottom-3 left-3 z-50 w-44 overflow-hidden rounded-full border border-slate-700/90 bg-slate-950/95 px-3 py-1.5 text-slate-100 shadow-lg shadow-black/25 backdrop-blur-md"
    >
      <div className="flex items-center gap-2">
        {isReady ? (
          <CircleCheck size={15} aria-hidden="true" className="shrink-0 text-emerald-300" />
        ) : (
          <LoaderCircle
            size={15}
            aria-hidden="true"
            className="shrink-0 animate-spin text-sky-300 motion-reduce:animate-none"
          />
        )}
        <span className="min-w-0 flex-1 truncate text-xs font-semibold">{status.label}</span>
        <span className="shrink-0 text-[11px] font-medium tabular-nums text-sky-200">{status.etaLabel}</span>
      </div>
      {!isReady && <p className="mt-0.5 truncate text-[10px] text-slate-400">{status.detail}</p>}
      <div className={`${isReady ? 'mt-1' : 'mt-1.5'} h-1 overflow-hidden rounded-full bg-white/10`} role="progressbar" aria-label={status.label}>
        <div
          className={`h-full rounded-full bg-sky-400 ${status.indeterminate ? 'activity-status-indeterminate' : 'transition-[width] duration-300 ease-out motion-reduce:transition-none'}`}
          style={status.indeterminate ? undefined : { width: `${status.fraction * 100}%` }}
        />
      </div>
    </aside>
  );
}
