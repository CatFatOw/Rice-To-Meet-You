import SelectDate from './SelectDate';
import SimulateButton from './SimulateButton';

export interface SimulatePanelProps {
  fromDate?: string | null;
  toDate?: string | null;
  availableDates?: string[];
  onFromDateChange?: (isoDate: string) => void;
  onToDateChange?: (isoDate: string) => void;
  onSimulate?: () => void;
  title?: string;
}

/**
 * Date range + run control for a scenario. Pulled out of POIStatistics so the
 * dashboard doesn't own simulation concerns; drop it anywhere a scenario needs
 * a window and a trigger.
 */
export default function SimulatePanel({
  fromDate,
  toDate,
  availableDates,
  onFromDateChange,
  onToDateChange,
  onSimulate,
  title = 'Simulate',
}: SimulatePanelProps) {
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

        <SimulateButton onClick={onSimulate} className="h-10 min-w-28" />
      </div>
    </div>
  );
}