import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  callNearestTrafficImage,
  callNearestTrafficPrediction,
  type NearestTrafficPrediction,
  type TrafficDetection,
} from '../api/traffic';

interface LiveTrafficPanelProps {
  defaultLatitude?: number;
  defaultLongitude?: number;
  latitude?: string;
  longitude?: string;
  sourceLabel?: string | null;
  onCoordinateChange?: (coordinate: { latitude: string; longitude: string; sourceLabel: string }) => void;
}

interface ImageSize {
  width: number;
  height: number;
}

type OverlayMode = 'both' | 'bbox' | 'segmentation';

const MIN_IMAGE_ZOOM = 1;
const MAX_IMAGE_ZOOM = 8;
const IMAGE_ZOOM_STEP = 0.5;

interface GoogleMapInstance {
  setCenter(center: { lat: number; lng: number }): void;
  setZoom(zoom: number): void;
}

interface GoogleTrafficLayerInstance {
  setMap(map: GoogleMapInstance | null): void;
}

interface GoogleMapsNamespace {
  Map: new (
    element: HTMLElement,
    options: {
      center: { lat: number; lng: number };
      zoom: number;
      disableDefaultUI: boolean;
      clickableIcons: boolean;
      gestureHandling: string;
      styles: { featureType?: string; elementType?: string; stylers: Record<string, unknown>[] }[];
    },
  ) => GoogleMapInstance;
  TrafficLayer: new () => GoogleTrafficLayerInstance;
}

declare global {
  interface Window {
    google?: {
      maps: GoogleMapsNamespace;
    };
  }
}

let googleMapsLoadPromise: Promise<void> | null = null;

interface CachedTrafficResult {
  imageUrl: string;
  prediction: NearestTrafficPrediction;
}

const trafficResultCache = new Map<string, CachedTrafficResult>();

function trafficCacheKey(lat: number, lon: number): string {
  return `${lat.toFixed(5)},${lon.toFixed(5)}`;
}

function loadGoogleMaps(apiKey: string): Promise<void> {
  if (window.google?.maps) return Promise.resolve();
  if (googleMapsLoadPromise) return googleMapsLoadPromise;

  googleMapsLoadPromise = new Promise((resolve, reject) => {
    const existingScript = document.getElementById('google-maps-js');
    if (existingScript) {
      existingScript.addEventListener('load', () => resolve(), { once: true });
      existingScript.addEventListener('error', () => reject(new Error('Google Maps failed to load.')), {
        once: true,
      });
      return;
    }

    const script = document.createElement('script');
    script.id = 'google-maps-js';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}`;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Google Maps failed to load.'));
    document.head.appendChild(script);
  });

  return googleMapsLoadPromise;
}

function confidencePercent(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

function polygonPoints(points: [number, number][]): string {
  return points.map(([x, y]) => `${x},${y}`).join(' ');
}

function formatSnapshotTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  }).format(date);
}

const LiveTrafficPanel: React.FC<LiveTrafficPanelProps> = ({
  defaultLatitude = 29.7604,
  defaultLongitude = -95.3698,
  latitude,
  longitude,
  sourceLabel,
  onCoordinateChange,
}) => {
  const googleTrafficContainerRef = useRef<HTMLDivElement>(null);
  const googleMapRef = useRef<GoogleMapInstance | null>(null);
  const googleTrafficLayerRef = useRef<GoogleTrafficLayerInstance | null>(null);
  const didAutoLoadRef = useRef(false);
  const [latitudeInput, setLatitudeInput] = useState(String(defaultLatitude));
  const [longitudeInput, setLongitudeInput] = useState(String(defaultLongitude));
  const [prediction, setPrediction] = useState<NearestTrafficPrediction | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageSize, setImageSize] = useState<ImageSize | null>(null);
  const [imageZoom, setImageZoom] = useState(1);
  const [isImageFullscreen, setIsImageFullscreen] = useState(false);
  const [overlayMode, setOverlayMode] = useState<OverlayMode>('both');
  const [isLoading, setIsLoading] = useState(false);
  const [googleTrafficStatus, setGoogleTrafficStatus] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const googleMapsApiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined;

  useEffect(() => {
    if (latitude) setLatitudeInput(latitude);
    if (longitude) setLongitudeInput(longitude);
  }, [latitude, longitude]);

  const parsedLatitude = Number.parseFloat(latitudeInput);
  const parsedLongitude = Number.parseFloat(longitudeInput);
  const canLoad =
    Number.isFinite(parsedLatitude) &&
    Number.isFinite(parsedLongitude) &&
    Math.abs(parsedLatitude) <= 90 &&
    Math.abs(parsedLongitude) <= 180;

  const sortedDetections = useMemo<TrafficDetection[]>(() => {
    const detections = prediction?.analysis.detections ?? [];
    return [...detections].sort((a, b) => b.confidence - a.confidence);
  }, [prediction]);

  const topDetections = sortedDetections.slice(0, 5);
  const shouldShowBoxes = overlayMode === 'both' || overlayMode === 'bbox';
  const shouldShowSegmentation = overlayMode === 'both' || overlayMode === 'segmentation';
  const snapshotTimeLabel =
    formatSnapshotTime(prediction?.snapshot.captured_at) ??
    formatSnapshotTime(prediction?.snapshot.fetched_at);
  const snapshotTimeSource = prediction?.snapshot.captured_at ? 'Image time' : 'Fetched';
  const vehicleSummary = prediction
    ? Object.entries(prediction.analysis.vehicle_types)
        .map(([label, count]) => `${count} ${label}`)
        .join(', ')
    : 'No prediction loaded';

  const loadTraffic = useCallback(async () => {
    if (!canLoad) {
      setErrorMessage('Enter a valid latitude and longitude.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const cacheKey = trafficCacheKey(parsedLatitude, parsedLongitude);
      const cachedResult = trafficResultCache.get(cacheKey);
      if (cachedResult) {
        setImageUrl(cachedResult.imageUrl);
        setImageSize(null);
        setImageZoom(1);
        setPrediction(cachedResult.prediction);
        return;
      }

      const [nextImageUrl, nextPrediction] = await Promise.all([
        callNearestTrafficImage(parsedLatitude, parsedLongitude),
        callNearestTrafficPrediction(parsedLatitude, parsedLongitude),
      ]);

      trafficResultCache.set(cacheKey, { imageUrl: nextImageUrl, prediction: nextPrediction });
      setImageUrl(nextImageUrl);
      setImageSize(null);
      setImageZoom(1);
      setPrediction(nextPrediction);
    } catch (error) {
      console.error('Failed to load live traffic prediction', error);
      setErrorMessage('Could not load live traffic. Check the backend and TxDOT feed.');
    } finally {
      setIsLoading(false);
    }
  }, [canLoad, parsedLatitude, parsedLongitude]);

  useEffect(() => {
    if (didAutoLoadRef.current) return;
    didAutoLoadRef.current = true;

    const timeoutId = window.setTimeout(() => {
      void loadTraffic();
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadTraffic]);

  useEffect(() => {
    if (!sourceLabel) return;
    if (!canLoad) return;
    void loadTraffic();
  }, [canLoad, loadTraffic, sourceLabel]);

  useEffect(() => {
    if (!googleTrafficContainerRef.current) return;
    if (!canLoad) return;
    if (!googleMapsApiKey) return;

    let isMounted = true;

    const setupGoogleTraffic = async () => {
      try {
        setGoogleTrafficStatus('Loading Google live traffic...');
        await loadGoogleMaps(googleMapsApiKey);
        if (!isMounted || !googleTrafficContainerRef.current || !window.google?.maps) return;

        const center = { lat: parsedLatitude, lng: parsedLongitude };

        if (!googleMapRef.current) {
          googleMapRef.current = new window.google.maps.Map(googleTrafficContainerRef.current, {
            center,
            zoom: 14,
            disableDefaultUI: true,
            clickableIcons: false,
            gestureHandling: 'cooperative',
            styles: [],
          });
          googleTrafficLayerRef.current = new window.google.maps.TrafficLayer();
          googleTrafficLayerRef.current.setMap(googleMapRef.current);
        } else {
          googleMapRef.current.setCenter(center);
          googleMapRef.current.setZoom(14);
        }

        setGoogleTrafficStatus(null);
      } catch (error) {
        console.error('Failed to load Google traffic layer', error);
        setGoogleTrafficStatus(
          'Google traffic could not load. Check that Maps JavaScript API is enabled and this localhost URL is allowed for the key.',
        );
      }
    };

    void setupGoogleTraffic();

    return () => {
      isMounted = false;
    };
  }, [canLoad, googleMapsApiKey, parsedLatitude, parsedLongitude]);

  const trafficStatusMessage =
    googleTrafficStatus ??
    (!googleMapsApiKey
      ? 'Set VITE_GOOGLE_MAPS_API_KEY to enable Google live traffic. The TxDOT camera + YOLO panel still works without it.'
      : null);

  const zoomOut = () => setImageZoom((zoom) => Math.max(MIN_IMAGE_ZOOM, zoom - IMAGE_ZOOM_STEP));
  const zoomIn = () => setImageZoom((zoom) => Math.min(MAX_IMAGE_ZOOM, zoom + IMAGE_ZOOM_STEP));
  const resetZoom = () => setImageZoom(1);
  const renderTrafficImage = (isFullscreen = false) => (
    <div
      className={`relative overflow-auto rounded-md border border-slate-800 bg-slate-950 ${
        isFullscreen ? 'h-[calc(100vh-150px)]' : 'max-h-[420px]'
      }`}
    >
      {imageUrl ? (
        <div
          className="relative"
          style={{
            width: `${imageZoom * 100}%`,
            minWidth: '100%',
            aspectRatio: imageSize ? `${imageSize.width} / ${imageSize.height}` : undefined,
          }}
        >
          <img
            src={imageUrl}
            alt="Nearest live traffic camera"
            className="block h-auto w-full"
            onLoad={(event) => {
              setImageSize({
                width: event.currentTarget.naturalWidth,
                height: event.currentTarget.naturalHeight,
              });
            }}
          />
          {imageSize && (
            <svg
              className="pointer-events-none absolute inset-0 h-full w-full"
              viewBox={`0 0 ${imageSize.width} ${imageSize.height}`}
              preserveAspectRatio="none"
            >
              {sortedDetections.map((detection, index) => {
                const [x1, y1, x2, y2] = detection.bbox;
                const polygon = detection.segmentation?.polygon;
                return (
                  <g key={`${detection.label}-${index}`}>
                    {shouldShowSegmentation && polygon && polygon.length > 2 && (
                      <polygon
                        points={polygonPoints(polygon)}
                        fill="rgba(34, 211, 238, 0.22)"
                        stroke="rgba(34, 211, 238, 0.75)"
                        strokeWidth="2"
                      />
                    )}
                    {shouldShowBoxes && (
                      <rect
                        x={x1}
                        y={y1}
                        width={x2 - x1}
                        height={y2 - y1}
                        fill="none"
                        stroke="rgba(250, 204, 21, 0.95)"
                        strokeWidth="2"
                      />
                    )}
                  </g>
                );
              })}
            </svg>
          )}
        </div>
      ) : (
        <div className="flex aspect-video items-center justify-center text-xs text-slate-500">
          No camera image loaded
        </div>
      )}
    </div>
  );

  return (
    <div className="rounded-lg border border-slate-800 bg-[#07111f] p-4 shadow-lg">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Live Traffic
          </div>
          <div className="mt-1 text-sm font-semibold text-slate-100">
            {prediction?.camera.name ?? 'Nearest TxDOT camera'}
          </div>
          {snapshotTimeLabel && (
            <div className="mt-1 text-xs text-slate-500">
              {snapshotTimeSource}: {snapshotTimeLabel}
            </div>
          )}
        </div>
        <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-xs font-semibold text-cyan-100">
          YOLO
        </span>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2">
        <label className="text-xs text-slate-400">
          Latitude
          <input
            value={latitudeInput}
            onChange={(event) => {
              const nextLatitude = event.target.value;
              setLatitudeInput(nextLatitude);
              onCoordinateChange?.({
                latitude: nextLatitude,
                longitude: longitudeInput,
                sourceLabel: 'coordinate',
              });
            }}
            className="mt-1 w-full rounded-md border border-slate-800 bg-slate-950/80 px-2 py-1.5 text-xs text-slate-100 outline-none transition focus:border-cyan-500"
          />
        </label>
        <label className="text-xs text-slate-400">
          Longitude
          <input
            value={longitudeInput}
            onChange={(event) => {
              const nextLongitude = event.target.value;
              setLongitudeInput(nextLongitude);
              onCoordinateChange?.({
                latitude: latitudeInput,
                longitude: nextLongitude,
                sourceLabel: 'coordinate',
              });
            }}
            className="mt-1 w-full rounded-md border border-slate-800 bg-slate-950/80 px-2 py-1.5 text-xs text-slate-100 outline-none transition focus:border-cyan-500"
          />
        </label>
      </div>

      <button
        type="button"
        disabled={isLoading || !canLoad}
        onClick={() => void loadTraffic()}
        className="mb-3 w-full rounded-md border border-cyan-500/40 bg-cyan-500/15 px-3 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/25 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isLoading ? 'Loading traffic...' : 'Analyze Nearest Camera'}
      </button>

      <div className="mb-3 grid grid-cols-3 gap-2">
        {(['both', 'bbox', 'segmentation'] as OverlayMode[]).map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => setOverlayMode(mode)}
            className={`rounded-md border px-2 py-1.5 text-[11px] font-semibold capitalize transition ${
              overlayMode === mode
                ? 'border-cyan-500/50 bg-cyan-500/15 text-cyan-100'
                : 'border-slate-800 bg-slate-950/70 text-slate-400 hover:text-slate-200'
            }`}
          >
            {mode === 'bbox' ? 'Boxes' : mode}
          </button>
        ))}
      </div>

      {errorMessage && (
        <div className="mb-3 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-100">
          {errorMessage}
        </div>
      )}

      {imageUrl && (
        <div className="mb-2 flex items-center justify-between gap-2 rounded-md border border-slate-800 bg-slate-950/70 px-2 py-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Image Zoom {Math.round(imageZoom * 100)}%
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={zoomOut}
              disabled={imageZoom <= MIN_IMAGE_ZOOM}
              className="rounded border border-slate-700 px-2 py-1 text-xs font-semibold text-slate-200 transition hover:border-cyan-500/50 hover:text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              -
            </button>
            <button
              type="button"
              onClick={resetZoom}
              className="rounded border border-slate-700 px-2 py-1 text-xs font-semibold text-slate-200 transition hover:border-cyan-500/50 hover:text-cyan-100"
            >
              Reset
            </button>
            <button
              type="button"
              onClick={() => setIsImageFullscreen(true)}
              className="rounded border border-slate-700 px-2 py-1 text-xs font-semibold text-slate-200 transition hover:border-cyan-500/50 hover:text-cyan-100"
            >
              Full
            </button>
            <button
              type="button"
              onClick={zoomIn}
              disabled={imageZoom >= MAX_IMAGE_ZOOM}
              className="rounded border border-slate-700 px-2 py-1 text-xs font-semibold text-slate-200 transition hover:border-cyan-500/50 hover:text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              +
            </button>
          </div>
        </div>
      )}

      {renderTrafficImage()}

      <div className="mt-3 overflow-hidden rounded-md border border-slate-800 bg-slate-950">
        <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
          <span className="text-xs font-semibold text-slate-200">Google traffic layer</span>
          <span className="text-[10px] uppercase tracking-wide text-slate-500">Real time</span>
        </div>
        <div className="relative">
          <div ref={googleTrafficContainerRef} className="h-56 w-full" />
          {canLoad && (
            <div className="pointer-events-none absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-full flex-col items-center">
              <div className="rounded-full border border-white bg-cyan-400 px-1.5 py-0.5 text-[10px] font-bold text-slate-950 shadow-lg shadow-black/40">
                Camera
              </div>
              <div className="h-3 w-3 rotate-45 border-b border-r border-white bg-cyan-400 shadow-lg shadow-black/40" />
            </div>
          )}
        </div>
        {trafficStatusMessage && (
          <div className="border-t border-slate-800 px-3 py-2 text-xs text-slate-400">
            {trafficStatusMessage}
          </div>
        )}
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="rounded-md border border-slate-800 bg-slate-950/70 p-2">
          <div className="text-[10px] uppercase text-slate-500">Vehicles</div>
          <div className="mt-1 text-base font-bold text-cyan-100">
            {prediction?.analysis.total_vehicle_count ?? '-'}
          </div>
        </div>
        <div className="rounded-md border border-slate-800 bg-slate-950/70 p-2">
          <div className="text-[10px] uppercase text-slate-500">Boxes</div>
          <div className="mt-1 text-base font-bold text-yellow-100">
            {prediction?.analysis.bboxes.length ?? '-'}
          </div>
        </div>
        <div className="rounded-md border border-slate-800 bg-slate-950/70 p-2">
          <div className="text-[10px] uppercase text-slate-500">Masks</div>
          <div className="mt-1 text-base font-bold text-emerald-100">
            {prediction?.analysis.segmentations.length ?? '-'}
          </div>
        </div>
      </div>

      <div className="mt-3 rounded-md border border-slate-800 bg-slate-950/70 px-3 py-2 text-xs text-slate-300">
        <div className="truncate">{vehicleSummary}</div>
        {snapshotTimeLabel && (
          <div className="mt-1 text-slate-500">
            {snapshotTimeSource}: {snapshotTimeLabel}
          </div>
        )}
        {prediction?.camera.distance_miles !== undefined && (
          <div className="mt-1 text-slate-500">
            {prediction.camera.distance_miles.toFixed(2)} miles from query
          </div>
        )}
      </div>

      {topDetections.length > 0 && (
        <div className="mt-2 max-h-24 overflow-y-auto rounded-md border border-slate-800">
          {topDetections.map((detection, index) => (
            <div
              key={`${detection.label}-summary-${index}`}
              className="flex items-center justify-between border-b border-slate-800 px-3 py-1.5 text-xs last:border-b-0"
            >
              <span className="text-slate-300">{detection.label}</span>
              <span className="text-slate-500">{confidencePercent(detection.confidence)}</span>
            </div>
          ))}
        </div>
      )}

      {isImageFullscreen && (
        <div className="fixed inset-0 z-[100] bg-slate-950/95 p-4 backdrop-blur">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Camera Analysis
              </div>
              <div className="mt-1 text-sm font-semibold text-slate-100">
                {prediction?.camera.name ?? 'Nearest TxDOT camera'}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={zoomOut}
                disabled={imageZoom <= MIN_IMAGE_ZOOM}
                className="rounded border border-slate-700 px-3 py-1.5 text-sm font-semibold text-slate-200 transition hover:border-cyan-500/50 hover:text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
              >
                -
              </button>
              <button
                type="button"
                onClick={resetZoom}
                className="rounded border border-slate-700 px-3 py-1.5 text-sm font-semibold text-slate-200 transition hover:border-cyan-500/50 hover:text-cyan-100"
              >
                Reset {Math.round(imageZoom * 100)}%
              </button>
              <button
                type="button"
                onClick={zoomIn}
                disabled={imageZoom >= MAX_IMAGE_ZOOM}
                className="rounded border border-slate-700 px-3 py-1.5 text-sm font-semibold text-slate-200 transition hover:border-cyan-500/50 hover:text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
              >
                +
              </button>
              <button
                type="button"
                onClick={() => setIsImageFullscreen(false)}
                className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm font-semibold text-slate-100 transition hover:border-cyan-500/50"
              >
                Close
              </button>
            </div>
          </div>
          {renderTrafficImage(true)}
        </div>
      )}
    </div>
  );
};

export default LiveTrafficPanel;
