export interface City {
  name: string;
  latitude: number;
  longitude: number;
}

export const cities: City[] = [
  { name: 'Atlanta', latitude: 33.7490, longitude: -84.3880 },
  { name: 'Boston', latitude: 42.3601, longitude: -71.0589 },
  { name: 'Dallas', latitude: 32.7767, longitude: -96.7970 },
  { name: 'Houston', latitude: 29.7604, longitude: -95.3698 },
  { name: 'Kansas City', latitude: 39.0997, longitude: -94.5786 },
  { name: 'Los Angeles', latitude: 34.0522, longitude: -118.2437 },
  { name: 'Miami', latitude: 25.7617, longitude: -80.1918 },
  { name: 'New York', latitude: 40.7128, longitude: -74.0060 },
  { name: 'New Jersey', latitude: 40.0583, longitude: -74.4057 },
  { name: 'Philadelphia', latitude: 39.9526, longitude: -75.1652 },
  { name: 'Seattle', latitude: 47.6062, longitude: -122.3321 },
  { name: 'San Francisco Bay Area', latitude: 37.7749, longitude: -122.4194 },
];