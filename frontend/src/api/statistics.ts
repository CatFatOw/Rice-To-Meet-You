import type {
  StatCardInfo,
  CityStatisticsResponse,
  CitySeedData,
  DistributionBucket,
  TopDestination
} from '../types/statistics';
export type { CityStatisticsResponse };

import type { Polygon } from './map';

const CITY_STATISTICS_SEED: Record<string, CitySeedData> = {
    Nationally: {
    averageHeatRisk: 64,
    totalVisitors: '23.19M',
    atRiskPopulation: '10.12M',
    extremeCities: 31,
    topDestinations: [
      { name: 'Houston', score: 75 },
      { name: 'Miami', score: 74 },
      { name: 'Dallas', score: 72 },
      { name: 'Los Angeles', score: 70 },
      { name: 'Atlanta', score: 67 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 31, color: '#c43f52' },
      { label: 'High (60-80)', value: 139, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 123, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 55, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 19, color: '#4aa39c' },
    ],
    pois: [
      { name: 'NRG Stadium — Houston', type: 'Stadium (711310)', heatRisk: 95, visitors: '72,000' },
      { name: 'AT&T Stadium — Dallas', type: 'Stadium (711310)', heatRisk: 90, visitors: '79,500' },
      { name: 'SoFi Stadium — Los Angeles', type: 'Stadium (711310)', heatRisk: 87, visitors: '70,200' },
      { name: 'Mercedes-Benz Stadium — Atlanta', type: 'Stadium (711310)', heatRisk: 86, visitors: '71,000' },
      { name: 'LoanDepot Park — Miami', type: 'Stadium (711310)', heatRisk: 84, visitors: '36,400' },
    ],
  },
  Atlanta: {
    averageHeatRisk: 67,
    totalVisitors: '1.62M',
    atRiskPopulation: '780K',
    extremeCities: 3,
    topDestinations: [
      { name: 'Downtown', score: 82 },
      { name: 'Midtown', score: 78 },
      { name: 'Buckhead', score: 74 },
      { name: 'Georgia Tech', score: 71 },
      { name: 'East Atlanta', score: 69 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 3, color: '#c43f52' },
      { label: 'High (60-80)', value: 12, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 9, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 4, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 1, color: '#4aa39c' },
    ],
    pois: [
      { name: 'Mercedes-Benz Stadium', type: 'Stadium (711310)', heatRisk: 86, visitors: '71,000' },
      { name: 'Georgia Aquarium', type: 'Attraction (712130)', heatRisk: 79, visitors: '16,500' },
      { name: 'Piedmont Park', type: 'Park (712190)', heatRisk: 66, visitors: '12,200' },
      { name: 'Lenox Square', type: 'Shopping Center (531120)', heatRisk: 74, visitors: '24,800' },
      { name: 'Grady Hospital', type: 'Hospital (622110)', heatRisk: 70, visitors: '7,300' },
    ],
  },
  Boston: {
    averageHeatRisk: 56,
    totalVisitors: '1.48M',
    atRiskPopulation: '540K',
    extremeCities: 1,
    topDestinations: [
      { name: 'Back Bay', score: 71 },
      { name: 'Fenway', score: 68 },
      { name: 'Seaport', score: 64 },
      { name: 'Cambridge', score: 62 },
      { name: 'South End', score: 60 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 1, color: '#c43f52' },
      { label: 'High (60-80)', value: 9, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 13, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 6, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 2, color: '#4aa39c' },
    ],
    pois: [
      { name: 'Fenway Park', type: 'Stadium (711310)', heatRisk: 73, visitors: '38,000' },
      { name: 'Boston Common', type: 'Park (712190)', heatRisk: 58, visitors: '15,400' },
      { name: 'Prudential Center', type: 'Shopping Center (531120)', heatRisk: 63, visitors: '19,900' },
      { name: 'Mass General Hospital', type: 'Hospital (622110)', heatRisk: 55, visitors: '6,100' },
      { name: 'South Station', type: 'Transit Hub (488111)', heatRisk: 60, visitors: '20,600' },
    ],
  },
  Dallas: {
    averageHeatRisk: 72,
    totalVisitors: '1.79M',
    atRiskPopulation: '910K',
    extremeCities: 4,
    topDestinations: [
      { name: 'Downtown', score: 88 },
      { name: 'Deep Ellum', score: 81 },
      { name: 'Uptown', score: 78 },
      { name: 'Bishop Arts', score: 74 },
      { name: 'Fair Park', score: 72 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 4, color: '#c43f52' },
      { label: 'High (60-80)', value: 15, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 8, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 3, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 1, color: '#4aa39c' },
    ],
    pois: [
      { name: 'AT&T Stadium', type: 'Stadium (711310)', heatRisk: 90, visitors: '79,500' },
      { name: 'Klyde Warren Park', type: 'Park (712190)', heatRisk: 69, visitors: '13,000' },
      { name: 'Galleria Dallas', type: 'Shopping Center (531120)', heatRisk: 77, visitors: '29,600' },
      { name: 'Dallas Market Hall', type: 'Convention (561920)', heatRisk: 82, visitors: '14,200' },
      { name: 'Baylor Hospital', type: 'Hospital (622110)', heatRisk: 71, visitors: '6,900' },
    ],
  },
  Houston: {
    averageHeatRisk: 75,
    totalVisitors: '2.45M',
    atRiskPopulation: '1.20M',
    extremeCities: 5,
    topDestinations: [
      { name: 'NRG District', score: 95 },
      { name: 'Medical Center', score: 90 },
      { name: 'Museum District', score: 77 },
      { name: 'Rice Village', score: 70 },
      { name: 'Hermann Park', score: 60 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 5, color: '#c43f52' },
      { label: 'High (60-80)', value: 14, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 8, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 2, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 1, color: '#4aa39c' },
    ],
    pois: [
      { name: 'NRG Stadium', type: 'Stadium (711310)', heatRisk: 95, visitors: '72,000' },
      { name: 'George R. Brown Conv. Center', type: 'Convention (561920)', heatRisk: 83, visitors: '18,000' },
      { name: 'Discovery Green', type: 'Park (712190)', heatRisk: 62, visitors: '9,500' },
      { name: 'The Galleria', type: 'Shopping Center (531120)', heatRisk: 78, visitors: '35,000' },
      { name: 'Houston Methodist Hospital', type: 'Hospital (622110)', heatRisk: 70, visitors: '6,200' },
    ],
  },
  'Kansas City': {
    averageHeatRisk: 64,
    totalVisitors: '1.11M',
    atRiskPopulation: '460K',
    extremeCities: 2,
    topDestinations: [
      { name: 'Downtown KC', score: 76 },
      { name: 'Westport', score: 72 },
      { name: 'Plaza', score: 68 },
      { name: 'River Market', score: 65 },
      { name: 'Crossroads', score: 63 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 2, color: '#c43f52' },
      { label: 'High (60-80)', value: 11, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 10, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 5, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 2, color: '#4aa39c' },
    ],
    pois: [
      { name: 'Arrowhead Stadium', type: 'Stadium (711310)', heatRisk: 82, visitors: '76,500' },
      { name: 'Union Station', type: 'Transit Hub (488111)', heatRisk: 65, visitors: '11,000' },
      { name: 'Crown Center', type: 'Shopping Center (531120)', heatRisk: 69, visitors: '15,400' },
      { name: 'City Market', type: 'Marketplace (445110)', heatRisk: 61, visitors: '8,300' },
      { name: 'KU Medical Center', type: 'Hospital (622110)', heatRisk: 58, visitors: '5,100' },
    ],
  },
  'Los Angeles': {
    averageHeatRisk: 70,
    totalVisitors: '2.88M',
    atRiskPopulation: '1.35M',
    extremeCities: 4,
    topDestinations: [
      { name: 'Downtown LA', score: 84 },
      { name: 'Hollywood', score: 80 },
      { name: 'Koreatown', score: 76 },
      { name: 'Westwood', score: 72 },
      { name: 'Santa Monica', score: 68 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 4, color: '#c43f52' },
      { label: 'High (60-80)', value: 13, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 9, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 4, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 1, color: '#4aa39c' },
    ],
    pois: [
      { name: 'SoFi Stadium', type: 'Stadium (711310)', heatRisk: 87, visitors: '70,200' },
      { name: 'LACC', type: 'Convention (561920)', heatRisk: 81, visitors: '22,400' },
      { name: 'Griffith Park', type: 'Park (712190)', heatRisk: 60, visitors: '18,100' },
      { name: 'The Grove', type: 'Shopping Center (531120)', heatRisk: 74, visitors: '27,500' },
      { name: 'Cedars-Sinai', type: 'Hospital (622110)', heatRisk: 66, visitors: '7,000' },
    ],
  },
  Miami: {
    averageHeatRisk: 74,
    totalVisitors: '1.95M',
    atRiskPopulation: '890K',
    extremeCities: 4,
    topDestinations: [
      { name: 'Downtown Miami', score: 86 },
      { name: 'Little Havana', score: 79 },
      { name: 'Wynwood', score: 77 },
      { name: 'Brickell', score: 75 },
      { name: 'South Beach', score: 73 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 4, color: '#c43f52' },
      { label: 'High (60-80)', value: 14, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 7, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 3, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 1, color: '#4aa39c' },
    ],
    pois: [
      { name: 'LoanDepot Park', type: 'Stadium (711310)', heatRisk: 84, visitors: '36,400' },
      { name: 'Bayside Marketplace', type: 'Shopping Center (531120)', heatRisk: 76, visitors: '28,000' },
      { name: 'Miami Beach Convention Center', type: 'Convention (561920)', heatRisk: 80, visitors: '17,200' },
      { name: 'Bayfront Park', type: 'Park (712190)', heatRisk: 67, visitors: '12,600' },
      { name: 'Jackson Memorial Hospital', type: 'Hospital (622110)', heatRisk: 71, visitors: '6,800' },
    ],
  },
  'New York': {
    averageHeatRisk: 62,
    totalVisitors: '3.42M',
    atRiskPopulation: '1.42M',
    extremeCities: 2,
    topDestinations: [
      { name: 'Midtown', score: 78 },
      { name: 'Lower Manhattan', score: 73 },
      { name: 'Brooklyn Heights', score: 69 },
      { name: 'Long Island City', score: 66 },
      { name: 'Harlem', score: 64 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 2, color: '#c43f52' },
      { label: 'High (60-80)', value: 12, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 11, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 5, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 2, color: '#4aa39c' },
    ],
    pois: [
      { name: 'Madison Square Garden', type: 'Stadium (711310)', heatRisk: 79, visitors: '42,000' },
      { name: 'Javits Center', type: 'Convention (561920)', heatRisk: 74, visitors: '24,500' },
      { name: 'Bryant Park', type: 'Park (712190)', heatRisk: 58, visitors: '21,300' },
      { name: 'Times Square', type: 'Attraction (712130)', heatRisk: 76, visitors: '33,200' },
      { name: 'Bellevue Hospital', type: 'Hospital (622110)', heatRisk: 60, visitors: '7,600' },
    ],
  },
  'New Jersey': {
    averageHeatRisk: 59,
    totalVisitors: '1.32M',
    atRiskPopulation: '610K',
    extremeCities: 1,
    topDestinations: [
      { name: 'Newark', score: 72 },
      { name: 'Jersey City', score: 68 },
      { name: 'Hoboken', score: 63 },
      { name: 'Paterson', score: 61 },
      { name: 'Trenton', score: 59 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 1, color: '#c43f52' },
      { label: 'High (60-80)', value: 10, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 12, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 6, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 2, color: '#4aa39c' },
    ],
    pois: [
      { name: 'MetLife Stadium', type: 'Stadium (711310)', heatRisk: 75, visitors: '74,000' },
      { name: 'American Dream', type: 'Shopping Center (531120)', heatRisk: 70, visitors: '25,600' },
      { name: 'Prudential Center', type: 'Arena (711310)', heatRisk: 66, visitors: '17,800' },
      { name: 'Liberty State Park', type: 'Park (712190)', heatRisk: 54, visitors: '10,900' },
      { name: 'Newark Beth Israel', type: 'Hospital (622110)', heatRisk: 57, visitors: '5,500' },
    ],
  },
  Philadelphia: {
    averageHeatRisk: 61,
    totalVisitors: '1.57M',
    atRiskPopulation: '690K',
    extremeCities: 2,
    topDestinations: [
      { name: 'Center City', score: 76 },
      { name: 'University City', score: 70 },
      { name: 'Old City', score: 66 },
      { name: 'South Philly', score: 64 },
      { name: 'Fishtown', score: 62 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 2, color: '#c43f52' },
      { label: 'High (60-80)', value: 11, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 11, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 5, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 2, color: '#4aa39c' },
    ],
    pois: [
      { name: 'Lincoln Financial Field', type: 'Stadium (711310)', heatRisk: 80, visitors: '69,500' },
      { name: 'PA Convention Center', type: 'Convention (561920)', heatRisk: 72, visitors: '19,300' },
      { name: 'Reading Terminal Market', type: 'Marketplace (445110)', heatRisk: 65, visitors: '13,400' },
      { name: 'Rittenhouse Square', type: 'Park (712190)', heatRisk: 56, visitors: '9,800' },
      { name: 'Jefferson Hospital', type: 'Hospital (622110)', heatRisk: 59, visitors: '6,300' },
    ],
  },
  Seattle: {
    averageHeatRisk: 53,
    totalVisitors: '1.44M',
    atRiskPopulation: '500K',
    extremeCities: 1,
    topDestinations: [
      { name: 'Downtown', score: 66 },
      { name: 'Capitol Hill', score: 61 },
      { name: 'South Lake Union', score: 59 },
      { name: 'Ballard', score: 56 },
      { name: 'University District', score: 55 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 1, color: '#c43f52' },
      { label: 'High (60-80)', value: 8, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 13, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 7, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 2, color: '#4aa39c' },
    ],
    pois: [
      { name: 'Lumen Field', type: 'Stadium (711310)', heatRisk: 68, visitors: '68,400' },
      { name: 'Seattle Center', type: 'Attraction (712130)', heatRisk: 57, visitors: '14,900' },
      { name: 'Pike Place Market', type: 'Marketplace (445110)', heatRisk: 60, visitors: '20,100' },
      { name: 'Westlake Center', type: 'Shopping Center (531120)', heatRisk: 55, visitors: '11,200' },
      { name: 'Harborview Medical', type: 'Hospital (622110)', heatRisk: 50, visitors: '5,800' },
    ],
  },
  'San Francisco Bay Area': {
    averageHeatRisk: 57,
    totalVisitors: '2.16M',
    atRiskPopulation: '770K',
    extremeCities: 2,
    topDestinations: [
      { name: 'Downtown SF', score: 70 },
      { name: 'Oakland', score: 66 },
      { name: 'San Jose', score: 64 },
      { name: 'Berkeley', score: 60 },
      { name: 'Palo Alto', score: 58 },
    ],
    distribution: [
      { label: 'Extreme (80-100)', value: 2, color: '#c43f52' },
      { label: 'High (60-80)', value: 10, color: '#e45b3f' },
      { label: 'Moderate (40-60)', value: 12, color: '#e8aa35' },
      { label: 'Low (20-40)', value: 5, color: '#83bf4f' },
      { label: 'Minimal (0-20)', value: 2, color: '#4aa39c' },
    ],
    pois: [
      { name: 'Oracle Park', type: 'Stadium (711310)', heatRisk: 72, visitors: '41,900' },
      { name: 'Moscone Center', type: 'Convention (561920)', heatRisk: 68, visitors: '21,600' },
      { name: 'Golden Gate Park', type: 'Park (712190)', heatRisk: 52, visitors: '17,700' },
      { name: 'Westfield SF Centre', type: 'Shopping Center (531120)', heatRisk: 61, visitors: '16,800' },
      { name: 'UCSF Medical Center', type: 'Hospital (622110)', heatRisk: 55, visitors: '6,600' },
    ],
  },
};

function getRiskLevelLabel(score: number): string {
  if (score >= 80) return 'Extreme';
  if (score >= 60) return 'High';
  if (score >= 40) return 'Moderate';
  if (score >= 20) return 'Low';
  return 'Minimal';
}

function buildStatCards(seed: CitySeedData): StatCardInfo[] {
  return [
    {
      icon: 'sun',
      iconClassName: 'text-red-400',
      label: 'Average Heat Risk',
      value: seed.averageHeatRisk.toString(),
      suffix: getRiskLevelLabel(seed.averageHeatRisk),
      suffixClassName: 'text-orange-400',
    },
    {
      icon: 'users',
      iconClassName: 'text-indigo-400',
      label: 'Total Visitors (est.)',
      value: seed.totalVisitors,
    },
    {
      icon: 'users',
      iconClassName: 'text-red-400',
      label: 'At Risk Population',
      value: seed.atRiskPopulation,
    },
    {
      icon: 'wind',
      iconClassName: 'text-yellow-400',
      label: 'Cities in Extreme Risk',
      value: seed.extremeCities.toString(),
    },
  ];
}

export async function callMockStatistics(city: string): Promise<CityStatisticsResponse> {
  await new Promise((resolve) => setTimeout(resolve, 300));

  const fallbackCity = 'Nationally';
  const selectedCity = CITY_STATISTICS_SEED[city] ? city : fallbackCity;
  const seed = CITY_STATISTICS_SEED[selectedCity];
  const isNational = selectedCity === 'Nationally';

  return {
    overallStatistics: {
      title: isNational ? 'National Summary' : `${selectedCity} Summary`,
      donutLabel: isNational ? 'Cities' : 'Zones',
      topDestinations: seed.topDestinations,
      distribution: seed.distribution,
      statCardsInfo: buildStatCards(seed),
    },
    poiStatistics: {
      title: isNational ? 'Key POIs Nationally' : `Key POIs in ${selectedCity}`,
      cityName: selectedCity,
      pois: seed.pois,
    },
  };
}







// Simulated network latency so callers can exercise their loading states.
const MOCK_LATENCY_MS = 150;

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * Mock "POST /poi-areas". Takes the drafted area's name, color, and polygon
 * coordinates. Returns empty for now — the body just resolves without
 * persisting anything. Swap in a real request (and a created-area return type)
 * when the endpoint lands; the parameter list is the contract callers rely on.
 */
export async function createPOIArea(
  name: string,
  color: string,
  coordinates: Polygon,
): Promise<void> {
  await delay(MOCK_LATENCY_MS);
  void name;
  void color;
  void coordinates;
  // returns empty for now
}

// ---------------------------------------------------------------------------
// GET /final_visitor/query-visitor-rows-with-geometry-by-city-date
// ---------------------------------------------------------------------------

const API_BASE_URL = 'http://localhost:8000';

export interface VisitorPOI {
  name: string;
  streetAddress: string;
  heatRisk: number | null;
  visitors: string;
}

/** Shape of a single row coming back from the endpoint. */
interface VisitorRow {
  city?: string | null;
  location_name?: string | null;
  street_address?: string | null;
  avg_daily_visits?: number | null;
  heat_risk_score?: number | null;
  core_poi_geometry_city?: string | null;
  core_poi_geometry_location_name?: string | null;
  core_poi_geometry_street_address?: string | null;
  core_poi_geometry_sub_category?: string | null;
  core_poi_geometry_top_category?: string | null;
  core_poi_geometry_naics_code?: number | null;
  core_poi_geometry_naics_code_2022?: number | null;
}

function toVisitorPOI(row: VisitorRow): VisitorPOI {
  const name = row.location_name ?? row.core_poi_geometry_location_name ?? 'Unknown';
  const city = row.city ?? row.core_poi_geometry_city ?? null;

  const category = row.core_poi_geometry_sub_category ?? row.core_poi_geometry_top_category ?? null;
  const naics = row.core_poi_geometry_naics_code_2022 ?? row.core_poi_geometry_naics_code ?? null;

  let streetAddress: string;
  if (category && naics != null) {
    streetAddress = `${category} (${naics})`;
  } else if (category) {
    streetAddress = category;
  } else {
    streetAddress = row.street_address ?? row.core_poi_geometry_street_address ?? '';
  }

  const visits = row.avg_daily_visits;

  return {
    name: city ? `${name} — ${city}` : name,
    streetAddress,
    heatRisk: row.heat_risk_score != null ? Math.round(row.heat_risk_score) : null,
    visitors: visits != null ? Math.round(visits).toLocaleString('en-US') : '',
  };
}

/**
 * Maps a row into the ranked-list shape. Returns null for rows this list can't
 * represent, which the caller filters out.
 */
function toTopDestination(row: VisitorRow): TopDestination | null {
  const name = row.location_name ?? row.core_poi_geometry_location_name ?? null;
  const score = row.heat_risk_score;

  // score is non-nullable on TopDestination, so unscored rows are dropped
  // rather than coerced to 0 — an unscored POI isn't a zero-risk one.
  if (name == null || score == null || !Number.isFinite(score)) return null;

  return { name, score: Math.round(score) };
}

/**
 * Shared request for the visitor-rows endpoint. Both fetchVisitorPOIs and
 * fetchTopDestinations hit this and differ only in how they map the rows.
 */
async function fetchVisitorRows(
  city: string,
  date: string,
  limit: number,
  signal?: AbortSignal,
): Promise<VisitorRow[]> {
  const params = new URLSearchParams({
    city,
    date,
    sorted: 'true',
    limit: String(limit),
  });

  const url = `${API_BASE_URL}/final_visitor/query-visitor-rows-with-geometry-by-city-date?${params}`;
  const response = await fetch(url, { signal });

  if (!response.ok) {
    throw new Error(`Visitor rows request failed: ${response.status} ${response.statusText}`);
  }

  const payload: unknown = await response.json();
  return Array.isArray(payload)
    ? (payload as VisitorRow[])
    : ((payload as { data?: VisitorRow[]; results?: VisitorRow[]; rows?: VisitorRow[] })?.data ??
       (payload as { results?: VisitorRow[] })?.results ??
       (payload as { rows?: VisitorRow[] })?.rows ??
       []);
}

/**
 * Fetches the top visitor rows for a city/date, sorted, and maps them into the
 * POI card shape the statistics panel renders.
 */
export async function fetchVisitorPOIs(
  city: string,
  date: string,
  limit = 10,
  signal?: AbortSignal,
): Promise<VisitorPOI[]> {
  const rows = await fetchVisitorRows(city, date, limit, signal);
  return rows.map(toVisitorPOI);
}

/**
 * Same endpoint as fetchVisitorPOIs, mapped into the ranked-list shape the
 * "Top Destinations" panel renders. Rows arrive sorted, so the returned order
 * is the ranking.
 *
 * Rows without a heat_risk_score are omitted, so the result can be shorter
 * than `limit` — over-fetch and slice if you need exactly that many.
 */
export async function fetchTopDestinations(
  city: string,
  date: string,
  limit = 5,
  signal?: AbortSignal,
): Promise<TopDestination[]> {
  const rows = await fetchVisitorRows(city, date, limit, signal);
  return rows
    .map(toTopDestination)
    .filter((destination): destination is TopDestination => destination !== null);
}


/** Bands in severity order, with the colors the donut renders. */
const HEAT_RISK_BANDS: readonly { label: string; color: string }[] = [
  { label: 'Extreme Danger', color: '#c43f52' },
  { label: 'Danger', color: '#e45b3f' },
  { label: 'Extreme Caution', color: '#e8aa35' },
  { label: 'Caution', color: '#83bf4f' },
  { label: 'Low', color: '#4aa39c' },
];

/**
 * GET /final_visitor/get-visitor-percentage-by-heat-risk, mapped into the
 * donut's bucket shape.
 *
 * Always returns all five bands in severity order, zeros included — the chart
 * legend then stays put across dates instead of reflowing as bands come and
 * go. Values are percentages summing to 100, not counts like the seed data.
 *
 * Returns [] when the backend has nothing to classify for that city/date,
 * which callers should treat as "no data" rather than "all zero".
 */
export async function getRiskDistributionByCityDate(
  city: string,
  date: string,
  signal?: AbortSignal,
): Promise<DistributionBucket[]> {
  const params = new URLSearchParams({ city, date });
  const url = `${API_BASE_URL}/final_visitor/get-visitor-percentage-by-heat-risk?${params}`;

  const response = await fetch(url, { signal });

  if (!response.ok) {
    throw new Error(
      `Heat risk distribution request failed: ${response.status} ${response.statusText}`,
    );
  }

  const payload: unknown = await response.json();

  // The endpoint returns {} when nothing for that city/date could be
  // classified -- distinct from every band genuinely sitting at zero.
  if (payload == null || typeof payload !== 'object' || Array.isArray(payload)) {
    return [];
  }

  const percentages = payload as Record<string, unknown>;
  if (Object.keys(percentages).length === 0) {
    return [];
  }

  return HEAT_RISK_BANDS.map(({ label, color }) => {
    const value = percentages[label];
    return {
      label,
      color,
      value: typeof value === 'number' && Number.isFinite(value) ? value : 0,
    };
  });
}


/**
 * GET /final_visitor/get-average-heat-risk-score-by-city-date
 *
 * Mean heat_risk_score across rows that have one. Null when the city/date
 * isn't cached or nothing in it is scored — distinct from an average that
 * genuinely came out at 0, so don't collapse the two at the call site.
 */
export async function getAverageHeatRiskScoreByCityDate(
  city: string,
  date: string,
  signal?: AbortSignal,
): Promise<number | null> {
  const params = new URLSearchParams({ city, date });
  const url = `${API_BASE_URL}/final_visitor/get-average-heat-risk-score-by-city-date?${params}`;

  const response = await fetch(url, { signal });

  if (!response.ok) {
    throw new Error(
      `Average heat risk request failed: ${response.status} ${response.statusText}`,
    );
  }

  const payload: unknown = await response.json();

  // The endpoint returns a bare number (or null). Unwrap a single-key object
  // too, in case the response later gets wrapped in a model.
  const value =
    typeof payload === 'object' && payload !== null && !Array.isArray(payload)
      ? (payload as { average_heat_risk_score?: unknown; value?: unknown })
          .average_heat_risk_score ?? (payload as { value?: unknown }).value
      : payload;

  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}


/**
 * GET /final_visitor/get-visitor-in-unsafe-condition
 *
 * Total avg_daily_visits for the city/date, counted only when the heat index
 * was at or above the unsafe threshold (90°F).
 *
 * The backend returns 0 in three different situations: it wasn't hot, there's
 * no weather row for that market/date, and nothing is cached for that
 * city/date. A 0 here does not mean "no visitors" — pair it with the total
 * visits endpoint if you need to tell those apart.
 */
export async function getVisitorInUnsafeCondition(
  city: string,
  date: string,
  signal?: AbortSignal,
): Promise<number> {
  const params = new URLSearchParams({ city, date });
  const url = `${API_BASE_URL}/final_visitor/get-visitor-in-unsafe-condition?${params}`;

  const response = await fetch(url, { signal });

  if (!response.ok) {
    throw new Error(
      `Unsafe condition visits request failed: ${response.status} ${response.statusText}`,
    );
  }

  const payload: unknown = await response.json();

  // Bare number today; unwrap a single-key object in case it gets wrapped later.
  const value =
    typeof payload === 'object' && payload !== null && !Array.isArray(payload)
      ? (payload as { total?: unknown; value?: unknown }).total ??
        (payload as { value?: unknown }).value
      : payload;

  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

/**
 * GET /final_visitor/get-total-visits-by-city-date
 *
 * Total avg_daily_visits for the city/date. The endpoint keys the number by
 * ISO date ({"2026-08-16": 48213.0}) and returns {} when the total is zero or
 * nothing is cached, so both cases arrive here as null.
 *
 * Passing an empty city totals every cached city for that date into one
 * number, matching the backend's null-city branch.
 */
export async function getTotalVisitsByCityDate(
  city: string,
  date: string,
  signal?: AbortSignal,
): Promise<number | null> {
  const params = new URLSearchParams({ city, date });
  const url = `${API_BASE_URL}/final_visitor/get-total-visits-by-city-date?${params}`;

  const response = await fetch(url, { signal });

  if (!response.ok) {
    throw new Error(
      `Total visits request failed: ${response.status} ${response.statusText}`,
    );
  }

  const payload: unknown = await response.json();

  if (payload == null || typeof payload !== 'object' || Array.isArray(payload)) {
    return typeof payload === 'number' && Number.isFinite(payload) ? payload : null;
  }

  // Read the requested date's key, but fall back to the only value present in
  // case the backend normalizes the date differently than it was sent.
  const byDate = payload as Record<string, unknown>;
  const values = Object.values(byDate);
  const value = date in byDate ? byDate[date] : values.length === 1 ? values[0] : undefined;

  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/**
 * GET /final_visitor/get-poi-count-in-unsafe-condition
 *
 * Number of POI-linked visitor rows for the city/date, counted only when the
 * heat index was at or above the unsafe threshold (90°F).
 *
 * Returns 0 both when it wasn't hot and when there's no weather row for that
 * market/date, so a 0 here doesn't mean "no POIs" — it means "no POIs counted
 * as unsafe".
 */
export async function getPoiCountInUnsafeCondition(
  city: string,
  date: string,
  signal?: AbortSignal,
): Promise<number> {
  const params = new URLSearchParams({ city, date });
  const url = `${API_BASE_URL}/final_visitor/get-poi-count-in-unsafe-condition?${params}`;

  const response = await fetch(url, { signal });

  if (!response.ok) {
    throw new Error(
      `Unsafe POI count request failed: ${response.status} ${response.statusText}`,
    );
  }

  const payload: unknown = await response.json();

  // Bare integer today; unwrap a single-key object in case it gets wrapped later.
  const value =
    typeof payload === 'object' && payload !== null && !Array.isArray(payload)
      ? (payload as { count?: unknown; total?: unknown; value?: unknown }).count ??
        (payload as { total?: unknown }).total ??
        (payload as { value?: unknown }).value
      : payload;

  return typeof value === 'number' && Number.isFinite(value) ? Math.trunc(value) : 0;
}

/** Compact counts for the stat cards: 12480 -> "12.5K", 1950000 -> "1.95M". */
const compact = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 2,
});

/**
 * Live replacement for buildStatCards(seed) — same four cards, in the same
 * order, but sourced from the API instead of CITY_STATISTICS_SEED.
 *
 * The four requests go out together, so one slow endpoint doesn't serialize
 * the rest. Any one of them rejecting rejects the whole call; catch at the
 * call site and fall back to the seed if you'd rather show stale cards than
 * an error state.
 *
 * Missing values render as an em dash rather than 0, since the backend
 * returns 0/null for "no weather row" as well as for a genuine zero.
 */
export async function getStatsInfo(
  city: string,
  date: string,
  signal?: AbortSignal,
): Promise<StatCardInfo[]> {
  const results = await Promise.allSettled([
    getAverageHeatRiskScoreByCityDate(city, date, signal),
    getTotalVisitsByCityDate(city, date, signal),
    getVisitorInUnsafeCondition(city, date, signal),
    getPoiCountInUnsafeCondition(city, date, signal),
  ]);

  const averageHeatRisk = results[0].status === 'fulfilled' ? results[0].value : null;
  const totalVisitors = results[1].status === 'fulfilled' ? results[1].value : null;
  const atRiskPopulation = results[2].status === 'fulfilled' ? results[2].value : 0;
  const unsafePOIs = results[3].status === 'fulfilled' ? results[3].value : 0;

  return [
    {
      icon: 'sun',
      iconClassName: 'text-red-400',
      label: 'Average Heat Risk',
      value: averageHeatRisk != null ? Math.round(averageHeatRisk).toString() : '—',
      suffix: averageHeatRisk != null ? getRiskLevelLabel(averageHeatRisk) : undefined,
      suffixClassName: 'text-orange-400',
    },
    {
      icon: 'users',
      iconClassName: 'text-indigo-400',
      label: 'Total Visitors (est.)',
      value: totalVisitors != null ? compact.format(totalVisitors) : '—',
    },
    {
      icon: 'users',
      iconClassName: 'text-red-400',
      label: 'At Risk Population',
      value: compact.format(atRiskPopulation),
    },
    {
      icon: 'wind',
      iconClassName: 'text-yellow-400',
      label: 'Unsafe POIs',
      value: unsafePOIs.toLocaleString('en-US'),
    },
  ];
}