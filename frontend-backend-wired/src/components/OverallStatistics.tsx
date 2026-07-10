import { Users, Sun, Wind, type LucideIcon } from "lucide-react";

/** Registry of icons usable by stat cards. Add new icons here as needed. */
const ICONS = {
  sun: Sun,
  users: Users,
  wind: Wind,
} as const;

export type IconKey = keyof typeof ICONS;

export interface TopDestination {
  name: string;
  score: number;
}

export interface DistributionBucket {
  label: string;
  value: number;
  color: string;
}

export interface StatCardInfo {
  icon: IconKey;
  iconClassName?: string;
  label: string;
  value: string;
  suffix?: string;
  suffixClassName?: string;
}

export interface OverallStatisticsProps {
  title?: string;
  donutLabel?: string;
  topDestinations?: TopDestination[];
  distribution?: DistributionBucket[];
  statCardsInfo?: StatCardInfo[];
}

const DEFAULT_TOP_DESTINATIONS: TopDestination[] = [
  { name: "Houston", score: 84 },
  { name: "Dallas", score: 78 },
  { name: "Miami", score: 72 },
  { name: "Las Vegas", score: 71 },
  { name: "Los Angeles", score: 68 },
];

const DEFAULT_DISTRIBUTION: DistributionBucket[] = [
  { label: "Extreme (80-100)", value: 4, color: "#c43f52" },
  { label: "High (60-80)", value: 14, color: "#e45b3f" },
  { label: "Moderate (40-60)", value: 10, color: "#e8aa35" },
  { label: "Low (20-40)", value: 5, color: "#83bf4f" },
  { label: "Minimal (0-20)", value: 1, color: "#4aa39c" },
];

const DEFAULT_STAT_CARDS: StatCardInfo[] = [
  {
    icon: "sun",
    iconClassName: "text-red-400",
    label: "Average Heat Risk",
    value: "61",
    suffix: "High",
    suffixClassName: "text-orange-400",
  },
  {
    icon: "users",
    iconClassName: "text-indigo-400",
    label: "Total Visitors (est.)",
    value: "2.45M",
  },
  {
    icon: "users",
    iconClassName: "text-red-400",
    label: "At Risk Population",
    value: "1.2M",
  },
  {
    icon: "wind",
    iconClassName: "text-yellow-400",
    label: "Cities in Extreme Risk",
    value: "4",
  },
];

export default function OverallStatistics({
  title = "National Summary",
  donutLabel = "States",
  topDestinations = DEFAULT_TOP_DESTINATIONS,
  distribution = DEFAULT_DISTRIBUTION,
  statCardsInfo = DEFAULT_STAT_CARDS,
}: OverallStatisticsProps) {
  const total = distribution.reduce((sum, item) => sum + item.value, 0);

  const donut = `conic-gradient(${distribution
    .map((item, index) => {
      const start =
        distribution
          .slice(0, index)
          .reduce((sum, cur) => sum + cur.value, 0) / total;
      const end = start + item.value / total;

      return `${item.color} ${start * 100}% ${end * 100}%`;
    })
    .join(", ")})`;

  return (
    <div className="w-full rounded-xl border border-slate-800 bg-slate-950 p-4 text-slate-100">
      <h2 className="mb-4 text-base font-semibold">{title}</h2>

      <div className="grid grid-cols-1 gap-4 border-b border-slate-800 pb-4 md:grid-cols-4">
        {statCardsInfo.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <h3 className="mb-3 text-sm font-semibold">Top Risk Cities</h3>
          <div className="space-y-3">
            {topDestinations.map((city, index) => (
              <div
                key={city.name}
                className="grid grid-cols-[24px_100px_1fr_36px] items-center gap-4"
              >
                <span className="text-slate-400">{index + 1}</span>
                <span>{city.name}</span>

                <div className="h-3 rounded-full bg-slate-800">
                  <div
                    className="h-3 rounded-full bg-linear-to-r from-orange-400 to-red-500"
                    style={{ width: `${city.score}%` }}
                  />
                </div>

                <span className="text-right font-medium">{city.score}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <h3 className="mb-3 text-sm font-semibold">Risk Distribution</h3>

          <div className="flex flex-col items-center gap-4 md:flex-row">
            <div
              className="relative h-36 w-36 rounded-full"
              style={{ background: donut }}
            >
              <div className="absolute inset-8 flex flex-col items-center justify-center rounded-full bg-slate-950">
                <span className="text-xs text-slate-400">{donutLabel}</span>
                <span className="text-xl font-semibold">{total}</span>
              </div>
            </div>

            <div className="w-full space-y-2">
              {distribution.map((item) => (
                <div
                  key={item.label}
                  className="flex items-center justify-between gap-6"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="h-4 w-4 rounded"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="text-sm text-slate-300">{item.label}</span>
                  </div>

                  <span className="text-sm font-medium">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  iconClassName = "text-slate-300",
  label,
  value,
  suffix,
  suffixClassName = "text-slate-300",
}: StatCardInfo) {
  const Icon: LucideIcon = ICONS[icon];

  return (
    <div className="flex items-center gap-4">
      <Icon className={`h-9 w-9 ${iconClassName}`} />

      <div>
        <p className="text-xs text-slate-400">{label}</p>
        <div className="flex items-end gap-1.5">
          <span className="text-2xl font-semibold">{value}</span>
          {suffix && (
            <span className={`pb-0.5 text-sm font-medium ${suffixClassName}`}>
              {suffix}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}