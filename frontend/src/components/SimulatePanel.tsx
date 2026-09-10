import SelectDate from './SelectDate';
import SimulateButton from './SimulateButton';
import { LoaderCircle } from 'lucide-react';
import { createContext, useContext, type ReactNode } from 'react';
import type { SimulationProgressDisplay } from '../types/statistics';

export interface SimulatePanelProps {
  fromDate?: string | null;
  toDate?: string | null;
  availableDates?: string[];
  onFromDateChange?: (isoDate: string) => void;
  onToDateChange?: (isoDate: string) => void;
  onStartSimulation?: () => void;
  onSimulate?: () => void;
  onStopSimulation?: () => void;
  isRunning?: boolean;
  loadingSimulation?: boolean;
  progress?: SimulationProgressDisplay;
  title?: string;
}

const SimulationProgressContext = createContext<SimulationProgressDisplay | undefined>(undefined);

export function SimulationProgressProvider({
  children,
  value,
}: {
  children: ReactNode;
  value: SimulationProgressDisplay;
}) {
  return (
    <SimulationProgressContext.Provider value={value}>
      {children}
    </SimulationProgressContext.Provider>
  );
}

function formatEta(etaMs: number): string {
  const seconds = Math.max(0, Math.ceil(etaMs / 1000));
  if (seconds === 0) return '< 1s';
  if (seconds < 60) return `${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return remainingSeconds === 0 ? `${minutes}m` : `${minutes}m ${remainingSeconds}s`;
}

/**
 * Date range + run control for a scenario. Pulled out of POIStatistics so the
 * dashboard doesn't own simulation concerns; drop it anywhere a scenario needs
 * a window and a trigger. Swaps the run control for a stop control while a
 * simulation is running.
 */
export default function SimulatePanel({
  fromDate,
  toDate,
  availableDates,
  onFromDateChange,
  onToDateChange,
  onStartSimulation,
  onSimulate,
  onStopSimulation,
  isRunning,
  loadingSimulation,
  progress,
  title = 'Simulate',
}: SimulatePanelProps) {
  const contextualProgress = useContext(SimulationProgressContext);
  const displayProgress = progress ?? contextualProgress;
  const handleStart = onStartSimulation ?? onSimulate;
  const handleFromDateChange = (isoDate: string) => {
    onFromDateChange?.(isoDate);
    if (toDate && isoDate > toDate) {
      onToDateChange?.(isoDate);
    }
  };
  const showProgress = Boolean(isRunning || loadingSimulation);
  const progressFraction = Math.max(0, Math.min(1, displayProgress?.fraction ?? 0));
  const completedFrames = displayProgress?.completedFrames ?? 0;
  const totalFrames = displayProgress?.totalFrames ?? 0;
  const eta = formatEta(displayProgress?.etaMs ?? 0);
  const progressLabel = loadingSimulation
    ? `Preparing ${totalFrames} frame${totalFrames === 1 ? '' : 's'}`
    : `Frame ${completedFrames} of ${totalFrames}`;
  const progressDescription = loadingSimulation
    ? `Preparing simulation. Estimated ${eta} remaining.`
    : `${completedFrames} of ${totalFrames} frames complete. Estimated ${eta} remaining.`;

  return (
    <div className="app-subpanel shrink-0 rounded-xl p-4">
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
        {title}
      </h3>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-52 flex-1">
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            From
          </p>
          <SelectDate
            label="From"
            value={fromDate ?? null}
            onChange={handleFromDateChange}
            availableDates={availableDates}
            variant="bare"
            className="w-full"
          />
        </div>

        <div className="min-w-52 flex-1">
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            To
          </p>
          <SelectDate
            label="To"
            value={toDate ?? null}
            onChange={(isoDate) => onToDateChange?.(isoDate)}
            availableDates={availableDates}
            variant="bare"
            className="w-full"
          />
        </div>

        {isRunning ? (
          <button
            type="button"
            onClick={() => onStopSimulation?.()}
            className="inline-flex h-10 min-w-28 items-center justify-center rounded-lg bg-red-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-red-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
          >
            Stop
          </button>
        ) : (
          <SimulateButton
            onClick={handleStart}
            disabled={loadingSimulation}
            label={
              loadingSimulation ? (
                <span className="inline-flex items-center gap-2">
                  <LoaderCircle size={16} aria-hidden="true" className="animate-spin motion-reduce:animate-none" />
                  Loading
                </span>
              ) : (
                'Simulate'
              )
            }
            className="h-10 min-w-28"
          />
        )}
      </div>

      {showProgress && (
        <div
          className="mt-3 border-t border-[var(--border-subtle)] pt-3 text-xs text-[var(--text-muted)] transition-opacity duration-200 motion-reduce:transition-none"
          aria-live="polite"
        >
          <div className="mb-2 flex items-center justify-between gap-3">
            <span>{progressLabel}</span>
            <span className="tabular-nums">ETA {eta}</span>
          </div>
          <div
            role="progressbar"
            aria-label="Simulation progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progressFraction * 100)}
            aria-valuetext={progressDescription}
            className="h-1.5 overflow-hidden rounded-full bg-white/10"
          >
            <div
              className="h-full rounded-full bg-sky-400 transition-[width] duration-300 ease-out motion-reduce:transition-none"
              style={{ width: `${progressFraction * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
