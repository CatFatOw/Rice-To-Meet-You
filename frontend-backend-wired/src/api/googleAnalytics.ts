import { apiBaseUrl } from './base';

const API_BASE_URL = apiBaseUrl();

export interface GoogleTrafficRouteSample {
  label: string;
  duration_seconds: number;
  static_duration_seconds: number;
  delay_seconds: number;
  distance_meters: number | null;
  congestion_percent: number;
}

export interface GooglePoiAnalyticsResponse {
  venue_name: string;
  latitude: number;
  longitude: number;
  category: string | null;
  radius_m: number;
  traffic_score: number | null;
  traffic_status: 'unavailable' | 'light' | 'moderate' | 'heavy' | 'severe';
  average_delay_seconds: number | null;
  route_samples: GoogleTrafficRouteSample[];
  nearby_place_count: number | null;
  nearby_place_type: string | null;
  visitor_analytics_available: boolean;
  data_source: 'google_routes_places_aggregate';
  data_notes: string[];
}

export async function getGooglePoiAnalytics(
  venueName: string,
  latitude: number,
  longitude: number,
  category: string | null,
): Promise<GooglePoiAnalyticsResponse> {
  const params = new URLSearchParams({
    venue_name: venueName,
    lat: latitude.toString(),
    lon: longitude.toString(),
    radius_m: '500',
  });
  if (category) params.set('category', category);

  const response = await fetch(`${API_BASE_URL}/google/poi-analytics?${params.toString()}`, {
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

  return response.json() as Promise<GooglePoiAnalyticsResponse>;
}
