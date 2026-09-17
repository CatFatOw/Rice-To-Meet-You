import { Users, Sun, Wind, PieChart, TrendingUp, type LucideIcon } from "lucide-react";
import type {
  DistributionBucket,
  OverallStatisticsProps,
  StatCardInfo,
  TopDestination,
  IconKey,
} from '../types/statistics';
export type {
  DistributionBucket,
  OverallStatisticsProps,
  StatCardInfo,
  TopDestination,
  IconKey,
};

/** Registry of icons usable by stat cards. Add new icons here as needed. */
const ICONS = {
  sun: Sun,
  users: Users,
  wind: Wind,
} as const;

/* ------------------------------------------------------------------ */
/* Monthly defaults                                                    */
/* ------------------------------------------------------------------ */

type MonthlyDefaults = {
  statCards: StatCardInfo[];
  topDestinations: TopDestination[];
  distribution: DistributionBucket[];
};

/** Risk band colors / labels, shared by the distribution and the heat-risk suffix. */
const RISK_BANDS = [
  { label: "Extreme (80-100)", short: "Extreme", min: 80, color: "#c43f52", textClass: "text-red-500" },
  { label: "High (60-80)", short: "High", min: 60, color: "#e45b3f", textClass: "text-orange-400" },
  { label: "Moderate (40-60)", short: "Moderate", min: 40, color: "#e8aa35", textClass: "text-yellow-400" },
  { label: "Low (20-40)", short: "Low", min: 20, color: "#83bf4f", textClass: "text-lime-400" },
  { label: "Minimal (0-20)", short: "Minimal", min: 0, color: "#4aa39c", textClass: "text-teal-400" },
] as const;

function riskBand(score: number) {
  return RISK_BANDS.find((band) => score >= band.min) ?? RISK_BANDS[RISK_BANDS.length - 1];
}

/** Build the 5 distribution buckets from counts ordered Extreme → Minimal. */
function buildDistribution(counts: [number, number, number, number, number]): DistributionBucket[] {
  return RISK_BANDS.map((band, i) => ({ label: band.label, value: counts[i], color: band.color }));
}

function buildStatCards(
  avgHeatRisk: number,
  totalVisitors: string,
  atRiskPopulation: string,
  extremeCities: number,
): StatCardInfo[] {
  const band = riskBand(avgHeatRisk);

  return [
    {
      icon: "sun",
      iconClassName: "text-red-400",
      label: "Average Heat Risk",
      value: String(avgHeatRisk),
      suffix: band.short,
      suffixClassName: band.textClass,
    },
    {
      icon: "users",
      iconClassName: "text-indigo-400",
      label: "Total Visitors (est.)",
      value: totalVisitors,
    },
    {
      icon: "users",
      iconClassName: "text-red-400",
      label: "At Risk Population",
      value: atRiskPopulation,
    },
    {
      icon: "wind",
      iconClassName: "text-yellow-400",
      label: "Cities in Extreme Risk",
      value: String(extremeCities),
    },
  ];
}

/**
 * Default dataset for each calendar month (1 = January … 12 = December).
 * Distribution counts are ordered [Extreme, High, Moderate, Low, Minimal] and sum to 34 states.
 */
const MONTHLY_DEFAULTS: Record<number, MonthlyDefaults> = {
  1: {
    statCards: buildStatCards(0, "1.60M", "0", 0),
    topDestinations: [
      { name: "Miami", score: 6 },
      { name: "Phoenix", score: 3 },
      { name: "Houston", score: 2 },
      { name: "Los Angeles", score: 1 },
    ],
    distribution: buildDistribution([0, 0, 0, 0, 34]),
  },
  2: {
    statCards: buildStatCards(2, "1.75M", "20K", 0),
    topDestinations: [
      { name: "Miami", score: 9 },
      { name: "Phoenix", score: 6 },
      { name: "Houston", score: 5 },
      { name: "Los Angeles", score: 3 },
    ],
    distribution: buildDistribution([0, 0, 0, 2, 32]),
  },
  3: {
    statCards: buildStatCards(8, "2.10M", "80K", 0),
    topDestinations: [
      { name: "Miami", score: 18 },
      { name: "Phoenix", score: 16 },
      { name: "Houston", score: 14 },
      { name: "Dallas", score: 10 },
    ],
    distribution: buildDistribution([0, 0, 1, 4, 29]),
  },
  4: {
    statCards: buildStatCards(15, "2.05M", "180K", 0),
    topDestinations: [
      { name: "Phoenix", score: 30 },
      { name: "Miami", score: 28 },
      { name: "Houston", score: 26 },
      { name: "Dallas", score: 22 },
    ],
    distribution: buildDistribution([0, 0, 2, 8, 24]),
  },
  5: {
    statCards: buildStatCards(22, "2.20M", "350K", 0),
    topDestinations: [
      { name: "Phoenix", score: 48 },
      { name: "Houston", score: 42 },
      { name: "Miami", score: 40 },
      { name: "Dallas", score: 38 },
    ],
    distribution: buildDistribution([0, 1, 4, 12, 17]),
  },
  6: {
    statCards: buildStatCards(30, "2.60M", "750K", 0),
    topDestinations: [
      { name: "Phoenix", score: 72 },
      { name: "Las Vegas", score: 66 },
      { name: "Houston", score: 60 },
      { name: "Dallas", score: 55 },
    ],
    distribution: buildDistribution([0, 3, 8, 13, 10]),
  },
  7: {
    statCards: buildStatCards(42, "2.85M", "1.3M", 2),
    topDestinations: [
      { name: "Phoenix", score: 88 },
      { name: "Las Vegas", score: 84 },
      { name: "Houston", score: 76 },
      { name: "Dallas", score: 72 },
    ],
    distribution: buildDistribution([2, 7, 11, 10, 4]),
  },
  8: {
    statCards: buildStatCards(45, "2.70M", "1.4M", 3),
    topDestinations: [
      { name: "Phoenix", score: 90 },
      { name: "Houston", score: 85 },
      { name: "Las Vegas", score: 83 },
      { name: "Dallas", score: 78 },
    ],
    distribution: buildDistribution([3, 8, 11, 9, 3]),
  },
  9: {
    statCards: buildStatCards(32, "2.25M", "800K", 0),
    topDestinations: [
      { name: "Phoenix", score: 70 },
      { name: "Houston", score: 64 },
      { name: "Dallas", score: 58 },
      { name: "Miami", score: 55 },
    ],
    distribution: buildDistribution([0, 4, 9, 13, 8]),
  },
  10: {
    statCards: buildStatCards(18, "2.15M", "250K", 0),
    topDestinations: [
      { name: "Phoenix", score: 38 },
      { name: "Miami", score: 34 },
      { name: "Houston", score: 32 },
      { name: "Dallas", score: 26 },
    ],
    distribution: buildDistribution([0, 0, 3, 10, 21]),
  },
  11: {
    statCards: buildStatCards(6, "1.90M", "50K", 0),
    topDestinations: [
      { name: "Miami", score: 16 },
      { name: "Phoenix", score: 12 },
      { name: "Houston", score: 10 },
      { name: "Los Angeles", score: 8 },
    ],
    distribution: buildDistribution([0, 0, 0, 4, 30]),
  },
  12: {
    statCards: buildStatCards(0, "2.00M", "0", 0),
    topDestinations: [
      { name: "Miami", score: 7 },
      { name: "Phoenix", score: 4 },
      { name: "Houston", score: 3 },
      { name: "Los Angeles", score: 2 },
    ],
    distribution: buildDistribution([0, 0, 0, 0, 34]),
  },
};

/** Defaults for a month; falls back to the current calendar month when none is selected. */
export function getMonthlyDefaults(month: number | null): MonthlyDefaults {
  const resolved = month ?? new Date().getMonth() + 1;
  return MONTHLY_DEFAULTS[resolved] ?? MONTHLY_DEFAULTS[1];
}

/** Extract the 1-based calendar month from the selected ISO date. */
export function filterMonth(selectedDate?: string | null): number | null {
  if (!selectedDate) return null;

  const month = Number(selectedDate.slice(5, 7));
  return month >= 1 && month <= 12 ? month : null;
}

export default function OverallStatistics({
  title = "National Summary",
  selectedDate,
  donutLabel = "States",
  topDestinations: topDestinationsProp,
  distribution: distributionProp,
  statCardsInfo: statCardsInfoProp,
}: OverallStatisticsProps) {
  const selectedMonth = filterMonth(selectedDate);
  const monthDefaults = getMonthlyDefaults(selectedMonth);

  // Explicit props win; otherwise use the selected month's defaults.
  const topDestinations = topDestinationsProp ?? monthDefaults.topDestinations;
  const distribution = distributionProp ?? monthDefaults.distribution;
  const statCardsInfo = statCardsInfoProp ?? monthDefaults.statCards;

  const total = distribution.reduce((sum, item) => sum + item.value, 0);
  const topRiskHeading = title === "National Summary" ? "Top Risk Cities" : "Top Risk POIs";

  const donut =
    total > 0
      ? `conic-gradient(${distribution
          .map((item, index) => {
            const start =
              distribution
                .slice(0, index)
                .reduce((sum, cur) => sum + cur.value, 0) / total;
            const end = start + item.value / total;

            return `${item.color} ${start * 100}% ${end * 100}%`;
          })
          .join(", ")})`
      : "var(--surface-muted)";

  return (
    <div
      className="app-panel w-full rounded-2xl p-5 text-[var(--text-primary)]"
      data-selected-date={selectedDate ?? undefined}
      data-selected-month={selectedMonth ?? undefined}
    >
      <h2 className="mb-5 text-base font-semibold tracking-tight">{title}</h2>

      <div className="grid grid-cols-1 gap-4 border-b border-[var(--border-subtle)] pb-5 md:grid-cols-4">
        {statCardsInfo.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="app-subpanel rounded-xl p-4">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold">
            <TrendingUp size={15} className="text-sky-300" />
            {topRiskHeading}
          </h3>
          <div className="space-y-1">
            {topDestinations.map((city, index) => (
              <div
                key={`${city.name}-${index}`}
                className="grid grid-cols-[24px_100px_1fr_36px] items-center gap-4 rounded-lg px-2 py-1.5 -mx-2 transition-colors hover:bg-white/5"
              >
                <span className="text-[var(--text-muted)]">{index + 1}</span>
                <span>{city.name}</span>

                <div className="h-2.5 rounded-full bg-[var(--surface-muted)]">
                  <div
                    className="h-2.5 rounded-full bg-linear-to-r from-sky-400 to-blue-600"
                    style={{ width: `${city.score}%` }}
                  />
                </div>

                <span className="text-right font-medium">{city.score}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="app-subpanel rounded-xl p-4">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold">
            <PieChart size={15} className="text-sky-300" />
            Risk Distribution
          </h3>

          <div className="flex flex-col items-center gap-4 md:flex-row">
            <div
              className="relative h-36 w-36 rounded-full"
              style={{ background: donut }}
            >
              <div className="absolute inset-8 flex flex-col items-center justify-center rounded-full bg-[var(--surface-panel)]">
                <span className="text-xs text-[var(--text-muted)]">{donutLabel}</span>
                <span className="text-xl font-semibold">{total}</span>
              </div>
            </div>

            <div className="w-full space-y-2">
              {distribution.map((item) => (
                <div
                  key={item.label}
                  className="flex items-center justify-between gap-6 rounded-lg px-2 py-1 -mx-2 transition-colors hover:bg-white/5"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="h-4 w-4 rounded"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="text-sm text-[var(--text-secondary)]">{item.label}</span>
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
    <div className="flex items-center gap-4 rounded-lg px-2 py-1 -mx-2 transition-colors hover:bg-white/5">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/5">
        <Icon className={`h-5 w-5 ${iconClassName}`} />
      </span>

      <div>
        <p className="text-xs font-medium text-[var(--text-muted)]">{label}</p>
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