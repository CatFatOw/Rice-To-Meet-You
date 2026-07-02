import { ArrowRight, ExternalLink, SlidersHorizontal } from "lucide-react";
import type { ReactNode } from "react";

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

export default function POIStatistics({
  pois = DEFAULT_POIS,
  columns = DEFAULT_COLUMNS,
  title = "Key POIs in View",
  cityName = "Houston",
}: POIStatisticsProps) {
  return (
    <section className="flex h-full w-full flex-col rounded-xl border border-slate-800 bg-[#07111f] p-5 text-white shadow-lg">
      <h2 className="mb-4 shrink-0 text-lg font-semibold">{title}</h2>

      <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-slate-800">
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

      <button className="mt-4 shrink-0 flex items-center gap-2 font-semibold text-blue-400 transition hover:text-blue-300">
        View all POIs in {cityName}
        <ArrowRight size={20} />
      </button>
    </section>
  );
}