import type {
  StatCardInfo,
  CityStatisticsResponse,
  CitySeedData,
} from '../types/statistics';
export type { CityStatisticsResponse };

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
