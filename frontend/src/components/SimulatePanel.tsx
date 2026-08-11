import SelectDate from './SelectDate';
import SimulateButton from './SimulateButton';
import type { SimulationMode } from '../api/diminishingSimulation';

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
  title?: string;
  simulationMode?: SimulationMode;
  onSimulationModeChange?: (mode: SimulationMode) => void;
  onLoadDemoScenario?: () => void;
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
  title = 'Simulate',
  simulationMode = 'standard',
  onSimulationModeChange,
  onLoadDemoScenario,
}: SimulatePanelProps) {
  const handleStart = onStartSimulation ?? onSimulate;

  return (
    <div className="shrink-0 rounded-lg border border-slate-800 bg-slate-950/55 p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">
        {title}
      </h3>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-52 flex-1">
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-400" htmlFor="simulation-mode">
            Interaction model
          </label>
          <select
            id="simulation-mode"
            value={simulationMode}
            onChange={(event) => onSimulationModeChange?.(event.target.value as SimulationMode)}
            className="h-10 w-full rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-100"
          >
            <option value="standard">Standard diminishing returns</option>
            <option value="contextual">Context-aware combinations</option>
          </select>
        </div>
        <div className="min-w-52 flex-1">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            From
          </p>
          <SelectDate
            label="From"
            value={fromDate ?? null}
            onChange={(isoDate) => onFromDateChange?.(isoDate)}
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
          <SimulateButton onClick={handleStart} className="h-10 min-w-28" />
        )}

        {onLoadDemoScenario && (
          <button
            type="button"
            onClick={onLoadDemoScenario}
            className="h-10 rounded-md border border-cyan-500/70 bg-cyan-500/10 px-3 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/20"
          >
            Load & run live demo
          </button>
        )}
      </div>
    </div>
  );
}
