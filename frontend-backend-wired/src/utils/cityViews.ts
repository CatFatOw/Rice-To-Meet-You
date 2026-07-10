import { cities, type City } from '../data/hostCities';

interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

const CITY_ZOOM_THRESHOLD = 7;  // below this, you're at a regional/national view
const CITY_RADIUS_DEG = 0.5;    // how close the view center must sit to a city to count

/**
 * Resolves which city the map is currently centered on.
 * Returns the city name, or null when the view is zoomed out
 * or not centered on any known city.
 */
export function determineCityView(viewState: ViewState): string | null {
  // 1. Zoom gate: if you're zoomed out, you're not "in" any city.
  if (viewState.zoom < CITY_ZOOM_THRESHOLD) return null;

  // 2. Find the nearest city to the view center.
  let nearest: City | null = null;
  let nearestDist = Infinity;

  for (const city of cities) {
    const dLon = city.longitude - viewState.longitude;
    const dLat = city.latitude - viewState.latitude;
    const dist = Math.sqrt(dLon * dLon + dLat * dLat);
    if (dist < nearestDist) {
      nearestDist = dist;
      nearest = city;
    }
  }

  // 3. Only count it if the center is actually within that city's radius.
  return nearest && nearestDist <= CITY_RADIUS_DEG ? nearest.name : null;
}