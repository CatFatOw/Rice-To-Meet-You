import { useRef } from "react";
import {
  ArrowRight,
  Expand,
  ExternalLink,
  Shrink,
  SlidersHorizontal,
} from "lucide-react";
import SimulatePanel from './SimulatePanel';
import ToolboxTable from './ToolboxTable';
import { useFullscreen } from '../hooks/useFullScreen';
import type { Column, POI, POIStatisticsProps } from '../types/statistics';
export type { Column, POI, POIStatisticsProps };

export function riskColor(score: number) {
  if (score >= 80) return "text-red-500";
  if (score >= 70) return "text-orange-500";
  if (score >= 60) return "text-yellow-400";
  return "text-green-400";
}

const DEFAULT_POIS: POI[] = [

];

const DEFAULT_COLUMNS: Column[] = [
  {
    header: "POI Name",
    cell: (poi) => poi.name,
    className: "font-medium text-slate-200",
  },
  {
    header: "Street Address",
    cell: (poi) => poi.type,
    className: "text-slate-400",
  },
  {
    header: "Heat Risk",
    cell: (poi) => poi.heatRisk,
    className: (poi) => `text-xl font-bold ${riskColor(poi.heatRisk)}`,
  },
  {
    header: "Visitors (est.)",
    cell: (poi) => poi.visitors,
    className: "text-slate-300",
  },
  {
    header: "Actions",
    cell: () => (
      <div className="flex items-center gap-5 text-slate-400">
        <button className="transition hover:text-blue-400">
          <ExternalLink size={18} />
        </button>

        <button className="transition hover:text-blue-400">
          <SlidersHorizontal size={18} />
        </button>
      </div>
    ),
  },
];

function resolveClassName(className: Column["className"], poi: POI): string {
  if (!className) return "";
  return typeof className === "function" ? className(poi) : className;
}

export default function POIStatistics({
  pois = DEFAULT_POIS,
  columns = DEFAULT_COLUMNS,
  title = "Planner's workspace",
  cityName = "Houston",
  containSimulation = false,
  fromDate,
  toDate,
  availableDates,
  placedObjects,
  onPlacedObjectsChange,
  onFromDateChange,
  onToDateChange,
  onStartSimulation,
  onSimulate,
  onStopSimulation,
  isRunning,
  loadingSimulation,
}: POIStatisticsProps) {
  const panelRef = useRef<HTMLElement>(null);
  const { isFullscreen, toggleFullscreen } = useFullscreen(panelRef);
  const handleStartSimulation = onStartSimulation ?? onSimulate;

  return (
    <section
      ref={panelRef}
      className={`app-panel relative flex h-full w-full flex-col p-5 text-[var(--text-primary)] ${
        isFullscreen ? 'rounded-none border-0' : 'rounded-xl border'
      }`}
    >
      {/* Floating corner control - sits above the content, never scrolls away */}
      <button
        type="button"
        onClick={toggleFullscreen}
        aria-label={isFullscreen ? 'Exit fullscreen' : 'View fullscreen'}
        title={isFullscreen ? 'Exit fullscreen' : 'View fullscreen'}
        className="absolute right-4 top-4 z-20 flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border-strong)] bg-[var(--surface-raised)] text-[var(--text-secondary)] shadow-sm transition-colors hover:border-sky-400/70 hover:text-[var(--text-primary)]"
      >
        {isFullscreen ? <Shrink size={18} /> : <Expand size={18} />}
      </button>

      {/* Fixed header - stays put while the body below it scrolls. pr-12 keeps
          the title clear of the corner button. */}
      <h2 className="mb-4 shrink-0 pr-12 text-lg font-semibold tracking-tight">{title}</h2>

      {/* Scroll container: everything else lives in here */}
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto pr-1">
        {containSimulation && (
          <>
            <SimulatePanel
              fromDate={fromDate}
              toDate={toDate}
              availableDates={availableDates}
              onFromDateChange={onFromDateChange}
              onToDateChange={onToDateChange}
              onStartSimulation={handleStartSimulation}
              onStopSimulation={onStopSimulation}
              isRunning={isRunning}
              loadingSimulation={loadingSimulation}
            />

            <ToolboxTable
              placedObjects={placedObjects}
              onPlacedObjectsChange={onPlacedObjectsChange}
              availableDates={availableDates}
            />
          </>
        )}

        <div className="flex shrink-0 flex-col">
          <h3 className="mb-3 shrink-0 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
            Key POIs in View
          </h3>

          <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-raised)]">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] text-xs uppercase tracking-wide text-[var(--text-muted)]">
                  {columns.map((column) => (
                    <th key={column.header} className="px-5 py-4 font-semibold">
                      {column.header}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {pois.map((poi) => (
                  <tr
                    key={poi.name}
                    className="border-b border-[var(--border-subtle)] transition-colors last:border-b-0 hover:bg-white/4"
                  >
                    {columns.map((column) => (
                      <td
                        key={column.header}
                        className={`px-5 py-4 ${resolveClassName(
                          column.className,
                          poi,
                        )}`}
                      >
                        {column.cell(poi)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <button className="shrink-0 flex items-center gap-2 text-sm font-semibold text-sky-300 transition-colors hover:text-sky-200">
          View all POIs in {cityName}
          <ArrowRight size={20} />
        </button>
      </div>
    </section>
  );
}
