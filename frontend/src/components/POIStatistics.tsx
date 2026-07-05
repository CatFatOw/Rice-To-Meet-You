import { ArrowRight, Building2, ExternalLink, MapPin, SlidersHorizontal } from "lucide-react";
import type { ReactNode } from "react";
import type { CityPOIArea } from "../api/map";

export interface POI {
  name: string;
  type: string;
  heatRisk: number;
  visitors: string;
}

export interface Column {
  /** Text shown in the table header for this column. */
  header: string;
  /** Renders the cell contents for a given row. */
  cell: (poi: POI) => ReactNode;
  /** Extra classes for the cell — static, or derived from the row. */
  className?: string | ((poi: POI) => string);
}

export interface POIStatisticsProps {
  pois?: POI[];
  columns?: Column[];
  title?: string;
  /** Used in the footer link, e.g. "View all POIs in Houston". */
  cityName?: string;
  selectedPOI?: CityPOIArea | null;
}

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
  title = "Key POIs in View",
  cityName = "Houston",
  selectedPOI = null,
}: POIStatisticsProps) {
  const selectedStats = selectedPOI?.properties?.statistics ?? {};
  const selectedDetails = [
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
  ].filter(([, value]) => value !== undefined && value !== null && value !== "");

  return (
    <section className="flex h-full w-full flex-col rounded-lg border border-slate-800 bg-[#07111f]/90 p-3 text-white shadow-md">
      <div className="mb-2 shrink-0">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Inspection</div>
        <h2 className="mt-0.5 truncate text-sm font-semibold text-slate-100">
          {selectedPOI ? 'Selected Core POI' : title}
        </h2>
      </div>

      {selectedPOI && (
        <div className="mb-2 max-h-28 shrink-0 overflow-auto rounded-md border border-sky-500/25 bg-sky-950/15 p-2.5">
          <div className="flex items-start gap-2">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-sky-400/25 bg-sky-400/10">
              <Building2 size={15} className="text-sky-200" />
            </div>
            <div className="min-w-0">
              <div className="truncate text-xs font-semibold text-sky-100">{selectedPOI.name}</div>
              <div className="mt-0.5 flex items-center gap-1 text-[11px] text-slate-400">
                <MapPin size={11} />
                <span className="truncate">
                  {formatDetailValue(selectedStats.address ?? selectedPOI.cityName)}
                </span>
              </div>
            </div>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px]">
            {selectedDetails.map(([label, value]) => (
              <div key={String(label)} className="min-w-0">
                <div className="text-slate-500">{humanizeKey(String(label))}</div>
                <div className="truncate font-medium text-slate-200">{formatDetailValue(value)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto rounded-md border border-slate-800/90">
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-[11px] text-slate-500">
              {columns.map((column) => (
                <th key={column.header} className="px-3 py-2 font-semibold">
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
                    className={`px-3 py-2 ${resolveClassName(
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

      <button className="mt-2 shrink-0 flex items-center gap-1.5 text-xs font-semibold text-sky-400 transition hover:text-sky-300">
        View all POIs in {cityName}
        <ArrowRight size={14} />
      </button>
    </section>
  );
}
