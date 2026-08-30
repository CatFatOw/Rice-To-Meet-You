import SelectDate from './SelectDate';
import SimulateButton from './SimulateButton';
import { LoaderCircle } from 'lucide-react';

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
  title?: string;
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
  title = 'Simulate',
}: SimulatePanelProps) {
  const handleStart = onStartSimulation ?? onSimulate;
  const handleFromDateChange = (isoDate: string) => {
    onFromDateChange?.(isoDate);
    if (toDate && isoDate > toDate) {
      onToDateChange?.(isoDate);
    }
  };

  return (
    <div className="shrink-0 rounded-lg border border-slate-800 bg-slate-950/55 p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">
        {title}
      </h3>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-52 flex-1">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
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
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
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
            className="inline-flex h-10 min-w-28 items-center justify-center rounded-md bg-red-600 px-4 text-sm font-semibold text-white transition hover:bg-red-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
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
                  <LoaderCircle size={16} aria-hidden="true" className="animate-spin" />
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
    </div>
  );
}