import { useRef } from "react";
import {
  ArrowRight,
  Building2,
  Expand,
  ExternalLink,
  MapPin,
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
  {
    name: "NRG Stadium",
    type: "Stadium (711310)",
    heatRisk: 95,
    visitors: "72,000",
  },
  {
    name: "George R. Brown Conv. Center",
    type: "Convention (561920)",
    heatRisk: 83,
    visitors: "18,000",
  },
  {
    name: "Discovery Green",
    type: "Park (811210)",
    heatRisk: 62,
    visitors: "9,500",
  },
  {
    name: "The Galleria",
    type: "Shopping Center (531120)",
    heatRisk: 78,
    visitors: "35,000",
  },
  {
    name: "Houston Methodist Hospital",
    type: "Hospital (622110)",
    heatRisk: 70,
    visitors: "6,200",
  },
];

const DEFAULT_COLUMNS: Column[] = [
  {
    header: "POI Name",
    cell: (poi) => poi.name,
    className: "font-medium text-slate-200",
  },
  {
    header: "Type (NAICS)",
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

function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Unknown";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  return String(value);
}

function humanizeKey(key: string): string {
  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
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
  selectedPOI = null,
}: POIStatisticsProps) {
  const panelRef = useRef<HTMLElement>(null);
  const { isFullscreen, toggleFullscreen } = useFullscreen(panelRef);
  const handleStartSimulation = onStartSimulation ?? onSimulate;

  // Detail rows for the POI the user clicked on the map. Anything the backend
  // did not send is dropped rather than rendered as an empty row.
  const selectedStats = selectedPOI?.properties?.statistics ?? {};
  const selectedDetails: [string, unknown][] = (
    [
      ["Category", selectedPOI?.category],
      ["Address", selectedStats.address],
      ["City", selectedStats.city ?? selectedPOI?.cityName],
      ["State", selectedStats.region ?? selectedPOI?.stateName],
      ["NAICS", selectedStats.naics_code],
      ["Area sq m", selectedStats.wkt_area_sq_meters],
      ["Parking lot", selectedStats.includes_parking_lot],
      ["Enclosed", selectedStats.enclosed],
      ["Website", selectedStats.website],
      ["Phone", selectedStats.phone_number],
    ] as [string, unknown][]
  ).filter(([, value]) => value !== undefined && value !== null && value !== "");

  return (
    <section
      ref={panelRef}
      className={`relative flex h-full w-full flex-col border-slate-800 bg-[#07111f] p-5 text-white shadow-lg ${
        isFullscreen ? 'rounded-none border-0' : 'rounded-xl border'
      }`}
    >
      {/* Floating corner control - sits above the content, never scrolls away */}
      <button
        type="button"
        onClick={toggleFullscreen}
        aria-label={isFullscreen ? 'Exit fullscreen' : 'View fullscreen'}
        title={isFullscreen ? 'Exit fullscreen' : 'View fullscreen'}
        className="absolute right-4 top-4 z-20 flex h-10 w-10 items-center justify-center rounded-lg border border-slate-600/60 bg-slate-950/85 text-slate-100 shadow-md transition hover:border-slate-500 hover:bg-slate-900"
      >
        {isFullscreen ? <Shrink size={18} /> : <Expand size={18} />}
      </button>

      {/* Fixed header - stays put while the body below it scrolls. pr-12 keeps
          the title clear of the corner button. */}
      <h2 className="mb-4 shrink-0 pr-12 text-lg font-semibold">{title}</h2>

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

        {selectedPOI && (
          <div className="shrink-0 rounded-lg border border-sky-500/25 bg-sky-950/15 p-3">
            <div className="flex items-start gap-2">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-sky-400/25 bg-sky-400/10">
                <Building2 size={16} className="text-sky-200" />
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-sky-100">{selectedPOI.name}</div>
                <div className="mt-0.5 flex items-center gap-1 text-xs text-slate-400">
                  <MapPin size={12} />
                  <span className="truncate">
                    {formatDetailValue(selectedStats.address ?? selectedPOI.cityName)}
                  </span>
                </div>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              {selectedDetails.map(([label, value]) => (
                <div key={label} className="min-w-0">
                  <div className="text-slate-500">{humanizeKey(label)}</div>
                  <div className="truncate font-medium text-slate-200">{formatDetailValue(value)}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex shrink-0 flex-col">
          <h3 className="mb-3 shrink-0 text-sm font-semibold uppercase tracking-wide text-slate-300">
            Key POIs in View
          </h3>

          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-slate-800 text-sm text-slate-400">
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
                    className="border-b border-slate-800 last:border-b-0"
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

        <button className="shrink-0 flex items-center gap-2 font-semibold text-blue-400 transition hover:text-blue-300">
          View all POIs in {cityName}
          <ArrowRight size={20} />
        </button>
      </div>
    </section>
  );
}