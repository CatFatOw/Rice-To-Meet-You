import { apiBaseUrl } from './base';

const API_BASE_URL = apiBaseUrl();

export interface FoursquarePlace {
  fsq_place_id: string;
  name: string;
  latitude: number;
  longitude: number;
  category: string | null;
  address: string | null;
  distance_m: number;
  visitor_count: number | null;
  visitor_count_status: 'unavailable_free_places';
}

export interface FoursquareLookupResponse {
  requested_time: string | null;
  latitude: number;
  longitude: number;
  radius_m: number;
  fetched_at: string;
  historical_visitor_counts_available: boolean;
  places: FoursquarePlace[];
}

export async function lookupFoursquarePlaces(
  latitude: number,
  longitude: number,
  time: string,
): Promise<FoursquareLookupResponse> {
  const params = new URLSearchParams({
    lat: latitude.toString(),
    lon: longitude.toString(),
    radius: '1000',
    limit: '20',
  });

  if (time) {
    params.set('time', new Date(time).toISOString());
  }

  const response = await fetch(`${API_BASE_URL}/foursquare/lookup?${params.toString()}`, {
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      // Keep the HTTP status when the backend does not return JSON.
    }
    throw new Error(detail);
  }

  return response.json() as Promise<FoursquareLookupResponse>;
}
