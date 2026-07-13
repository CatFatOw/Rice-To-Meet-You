import type { ReactNode } from 'react';

export type IconKey = 'sun' | 'users' | 'wind';

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
  containSimulation?: boolean;
  fromDate?: string | null;
  toDate?: string | null;
  availableDates?: string[];
  onFromDateChange?: (isoDate: string) => void;
  onToDateChange?: (isoDate: string) => void;
  onSimulate?: () => void;
}

export interface CityStatisticsResponse {
  overallStatistics: OverallStatisticsProps;
  poiStatistics: POIStatisticsProps;
}

export interface CitySeedData {
  averageHeatRisk: number;
  totalVisitors: string;
  atRiskPopulation: string;
  extremeCities: number;
  topDestinations: TopDestination[];
  distribution: DistributionBucket[];
  pois: POI[];
}
