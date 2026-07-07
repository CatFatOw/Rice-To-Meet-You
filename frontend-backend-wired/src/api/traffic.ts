const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

export interface TrafficCamera {
  name?: string | null;
  icd_id?: string | null;
  netid?: string | null;
  lat: number;
  lon: number;
  roadway?: string | null;
  distance_miles?: number;
}

export interface TrafficBBox {
  label: string;
  confidence: number;
  bbox: [number, number, number, number];
}

export interface TrafficSegmentation {
  label?: string;
  polygon: [number, number][];
  normalized_polygon?: [number, number][] | null;
}

export interface TrafficDetection extends TrafficBBox {
  segmentation?: TrafficSegmentation | null;
}

export interface TrafficAnalysis {
  vehicle_types: Record<string, number>;
  total_vehicle_count: number;
  bboxes: TrafficBBox[];
  segmentations: TrafficSegmentation[];
  detections: TrafficDetection[];
  has_segmentation: boolean;
}

export interface TrafficSnapshot {
  captured_at?: string | null;
  fetched_at: string;
  metadata?: Record<string, unknown>;
}

export interface NearestTrafficPrediction {
  query: {
    lat: number;
    lon: number;
  };
  camera: TrafficCamera;
  snapshot: TrafficSnapshot;
  analysis: TrafficAnalysis;
}

async function fetchTrafficJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Traffic request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export async function callNearestTrafficPrediction(
  lat: number,
  lon: number,
): Promise<NearestTrafficPrediction> {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
  });

  return fetchTrafficJson<NearestTrafficPrediction>(
    `/traffic_predict/nearest_camera/predict?${params.toString()}`,
  );
}

export async function callNearestTrafficImage(lat: number, lon: number): Promise<string> {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
  });
  const response = await fetch(
    `${API_BASE_URL}/traffic_predict/nearest_camera/image?${params.toString()}`,
  );

  if (!response.ok) {
    throw new Error(`Traffic image request failed: ${response.status} ${response.statusText}`);
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
