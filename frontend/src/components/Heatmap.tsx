import React, { useMemo, useCallback, useRef, useEffect, useState } from 'react';
import {
  Expand,
  Shrink,
  Pencil,
  Check,
  Undo2,
  X,
  Trash2,
  Search,
  MapPin,
  Crosshair,
  Loader2,
  Snowflake,
  Umbrella,
  Droplets,
  Fan,
  Cross,
  TreePine,
} from 'lucide-react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, PolygonLayer, PathLayer, TextLayer, IconLayer } from '@deck.gl/layers';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import {
  applySimulation,
  createSimulationPolygon,
  type CityPOIArea,
  type HeatmapMetricPoint,
  type HeatmapMetricValue,
  type HeatmapMetricsPointResponse,
  type SimulationPlacedObject,
} from '../api/map';
import { cities, type City } from '../data/hostCities';
import { getColor } from '../utils/colors';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

interface HeatmapProps {
  viewState: ViewState;
  setViewState: React.Dispatch<React.SetStateAction<ViewState>>;
  selectedCity: string | null;
  setSelectedCity: React.Dispatch<React.SetStateAction<string | null>>;
  cityPOIAreas: CityPOIArea[];
  heatmapPointsByCity: HeatmapMetricsPointResponse;
  showAllCityHeatmaps?: boolean;
  mapContainerRef: React.RefObject<HTMLDivElement | null>;
  mapRef: React.MutableRefObject<maplibregl.Map | null>;
  mapSyncFrameRef: React.MutableRefObject<number | null>;
  tooltip: TooltipState | null;
  setTooltip: React.Dispatch<React.SetStateAction<TooltipState | null>>;
  isFullscreen: boolean;
  setIsFullscreen: React.Dispatch<React.SetStateAction<boolean>>;
  isDrawing: boolean;
  setIsDrawing: React.Dispatch<React.SetStateAction<boolean>>;
  draftPoints: [number, number][];
  setDraftPoints: React.Dispatch<React.SetStateAction<[number, number][]>>;
  draftColorHex: string;
  setDraftColorHex: React.Dispatch<React.SetStateAction<string>>;
  draftName: string;
  setDraftName: React.Dispatch<React.SetStateAction<string>>;
  userPOIAreas: CityPOIArea[];
  setUserPOIAreas: React.Dispatch<React.SetStateAction<CityPOIArea[]>>;
  hoveringHeatmap: boolean;
  setHoveringHeatmap: React.Dispatch<React.SetStateAction<boolean>>;
  searchQuery: string;
  setSearchQuery: React.Dispatch<React.SetStateAction<string>>;
  geoResults: GeocodeResult[];
  setGeoResults: React.Dispatch<React.SetStateAction<GeocodeResult[]>>;
  isSearching: boolean;
  setIsSearching: React.Dispatch<React.SetStateAction<boolean>>;
  showSuggestions: boolean;
  setShowSuggestions: React.Dispatch<React.SetStateAction<boolean>>;
  selectedMetric: string | null;
  setSelectedMetric: React.Dispatch<React.SetStateAction<string | null>>;
  editingAreaId: string | null;
  setEditingAreaId: React.Dispatch<React.SetStateAction<string | null>>;
  isAreaDragging: boolean;
  setIsAreaDragging: React.Dispatch<React.SetStateAction<boolean>>;
  onPOIAreaSelect?: (area: CityPOIArea) => void;
  onMetricPointSelect?: (point: HeatmapMetricValue, metric: string) => void;
  /**
   * When true, the left panel renders as a full toolbox: a palette of
   * placeable objects (cooling stations, shade canopy, ...) that can be
   * dragged onto the map, followed by the Create POI Area section. When
   * false (default) only the Create POI Area section is shown.
   */
  displayToolbox?: boolean;
}

export interface TooltipState {
  point: HeatmapMetricValue;
  metric: string;
  x: number;
  y: number;
}

// A single resolved place from the geocoder (or a coordinate/city match).
export interface GeocodeResult {
  label: string;
  lng: number;
  lat: number;
}

function metricLabel(metricKey: string): string {
  switch (metricKey) {
    case 'temperatureF':
      return 'Air Temp';
    case 'heatIndexF':
      return 'Heat Index';
    case 'relativeHumidityPct':
      return 'Humidity';
    case 'landSurfaceTempF':
      return 'Surface Temp';
    case 'nighttimeTempF':
      return 'Night Temp';
    case 'treeCanopyPct':
      return 'Tree Canopy';
    case 'imperviousSurfacePct':
      return 'Impervious';
    default:
      return metricKey;
  }
}

function metricUnit(metricKey: string): string {
  if (metricKey.endsWith('F')) return ' deg F';
  if (metricKey.endsWith('Pct')) return '%';
  return '';
}

// Convert a #rrggbb hex string to an [r, g, b] tuple for deck.gl color props.
function hexToRgb(hex: string): [number, number, number] {
  const normalized = hex.replace('#', '');
  const r = parseInt(normalized.substring(0, 2), 16);
  const g = parseInt(normalized.substring(2, 4), 16);
  const b = parseInt(normalized.substring(4, 6), 16);
  return [
    Number.isNaN(r) ? 0 : r,
    Number.isNaN(g) ? 0 : g,
    Number.isNaN(b) ? 0 : b,
  ];
}

// Parse a "lat, lng" string into [lng, lat] deck.gl order, or null if it isn't
// a valid coordinate pair. Tolerates degree symbols and optional hemisphere
// letters, e.g. "29.717154, -95.404182°", "29.71° N, 95.40° W".
function parseCoordinates(query: string): [number, number] | null {
  const match = query
    .trim()
    .match(
      /^\s*(-?\d+(?:\.\d+)?)\s*°?\s*([NSns])?\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*°?\s*([EWew])?\s*$/,
    );
  if (!match) return null;

  let lat = parseFloat(match[1]);
  let lng = parseFloat(match[3]);
  const latHem = match[2]?.toUpperCase();
  const lngHem = match[4]?.toUpperCase();

  if (latHem === 'S') lat = -Math.abs(lat);
  if (latHem === 'N') lat = Math.abs(lat);
  if (lngHem === 'W') lng = -Math.abs(lng);
  if (lngHem === 'E') lng = Math.abs(lng);

  if (Math.abs(lat) <= 90 && Math.abs(lng) <= 180) {
    return [lng, lat];
  }
  return null;
}

// Free-form place lookup via OpenStreetMap Nominatim. Swap this out for
// MapTiler / Mapbox / Google Geocoding in production (rate limits + API key).
async function geocode(query: string, signal?: AbortSignal): Promise<GeocodeResult[]> {
  const url = `https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(
    query,
  )}`;
  const res = await fetch(url, { signal, headers: { Accept: 'application/json' } });
  if (!res.ok) return [];
  const data = (await res.json()) as Array<{ display_name: string; lon: string; lat: string }>;
  return data.map((d) => ({
    label: d.display_name,
    lng: parseFloat(d.lon),
    lat: parseFloat(d.lat),
  }));
}

// Subtle host-city football badge. It borrows the visual language of a global
// tournament marker without using official tournament branding.
const FOOTBALL_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 64" width="56" height="64">
  <defs>
    <radialGradient id="badgeGlow" cx="50%" cy="35%" r="70%">
      <stop offset="0%" stop-color="#fef3c7"/>
      <stop offset="55%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#92400e"/>
    </radialGradient>
  </defs>
  <path d="M28 3 C16.5 3 7 12.2 7 23.7 C7 40.3 28 61 28 61 C28 61 49 40.3 49 23.7 C49 12.2 39.5 3 28 3 Z" fill="url(#badgeGlow)" stroke="#f8fafc" stroke-width="1.4" opacity="0.94"/>
  <circle cx="28" cy="24" r="14.5" fill="#07111f" stroke="#fef3c7" stroke-width="1.4"/>
  <path d="M18 27.5 C22 21 34 21 38 27.5" fill="none" stroke="#38bdf8" stroke-width="1.6" stroke-linecap="round"/>
  <path d="M19.5 31.5 H36.5" stroke="#94a3b8" stroke-width="1" stroke-linecap="round" opacity="0.8"/>
  <circle cx="28" cy="24" r="5.3" fill="#f8fafc" stroke="#0f172a" stroke-width="1"/>
  <polygon points="28,20.2 31.8,23 30.4,27.3 25.6,27.3 24.2,23" fill="#0f172a"/>
  <path d="M28 18.7 V12.5 M32.8 21.2 L38.3 18.5 M31.3 28.1 L35.2 33 M24.7 28.1 L20.8 33 M23.2 21.2 L17.7 18.5" stroke="#f8fafc" stroke-width="1" stroke-linecap="round" opacity="0.75"/>
  <path d="M20.5 43 H35.5" stroke="#fff7ed" stroke-width="2" stroke-linecap="round" opacity="0.85"/>
</svg>`;

const FOOTBALL_ICON = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(FOOTBALL_SVG)}`;

// --- Toolbox: placeable objects that can be dragged onto the map ---

// Definition of a draggable structure available in the toolbox palette.
interface ToolboxItemDef {
  type: string;
  label: string;
  color: string; // hex; drives both the palette chip and the map pin
  Icon: React.ComponentType<{ size?: number | string; color?: string }>;
}

// A placed instance of a toolbox item, positioned in map (lng/lat) space.
interface PlacedObject {
  id: string;
  type: string;
  longitude: number;
  latitude: number;
}

const TOOLBOX_ITEMS: ToolboxItemDef[] = [
  { type: 'cooling_station', label: 'Cooling Station', color: '#38bdf8', Icon: Snowflake },
  { type: 'shade_canopy', label: 'Shade Canopy', color: '#a3e635', Icon: Umbrella },
  { type: 'water_station', label: 'Water Station', color: '#22d3ee', Icon: Droplets },
  { type: 'misting_fan', label: 'Misting Fan', color: '#818cf8', Icon: Fan },
  { type: 'first_aid', label: 'First Aid', color: '#f87171', Icon: Cross },
  { type: 'tree_planting', label: 'Tree Planting', color: '#4ade80', Icon: TreePine },
];

const TOOLBOX_BY_TYPE: Record<string, ToolboxItemDef> = Object.fromEntries(
  TOOLBOX_ITEMS.map((item) => [item.type, item]),
);

// Custom MIME type used to carry the toolbox item type through an HTML5 drag.
const TOOLBOX_DRAG_MIME = 'application/x-heatmap-toolbox-item';

// White-on-color glyph fragments, drawn centered on the origin, inside the pin.
function toolboxGlyph(type: string, color: string): string {
  switch (type) {
    case 'cooling_station':
      return `<g stroke="${color}" stroke-width="1.8" stroke-linecap="round">
        <line x1="0" y1="-8.5" x2="0" y2="8.5"/>
        <line x1="-7.4" y1="-4.25" x2="7.4" y2="4.25"/>
        <line x1="-7.4" y1="4.25" x2="7.4" y2="-4.25"/>
      </g>`;
    case 'shade_canopy':
      return `<g fill="${color}">
        <path d="M-9 1 A9 9 0 0 1 9 1 Z"/>
        <rect x="-0.9" y="1" width="1.8" height="8" rx="0.9"/>
      </g>`;
    case 'water_station':
      return `<path d="M0 -9 C5 -2.5 7.5 1 7.5 4.2 A7.5 7.5 0 1 1 -7.5 4.2 C-7.5 1 -5 -2.5 0 -9 Z" fill="${color}"/>`;
    case 'misting_fan':
      return `<g fill="${color}">
        <circle r="2.2"/>
        <path d="M0 -2.4 C-6 -9 -9 -4 -2.2 -1 Z"/>
        <path d="M2.4 0 C9 -6 4 -9 1 -2.2 Z"/>
        <path d="M0 2.4 C6 9 9 4 2.2 1 Z"/>
        <path d="M-2.4 0 C-9 6 -4 9 -1 2.2 Z"/>
      </g>`;
    case 'first_aid':
      return `<g fill="${color}">
        <rect x="-2.6" y="-8" width="5.2" height="16" rx="1.6"/>
        <rect x="-8" y="-2.6" width="16" height="5.2" rx="1.6"/>
      </g>`;
    case 'tree_planting':
      return `<g fill="${color}">
        <polygon points="0,-9 6.5,3.5 -6.5,3.5"/>
        <rect x="-1.5" y="3.5" width="3" height="5" rx="0.6"/>
      </g>`;
    default:
      return `<circle r="5" fill="${color}"/>`;
  }
}

// Teardrop map pin (tip at the bottom) with a white disc and a colored glyph.
function toolboxMarkerSvg(type: string, color: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 60" width="48" height="60">
    <path d="M24 2 C13 2 4 11 4 22 C4 36 24 57 24 57 C24 57 44 36 44 22 C44 11 35 2 24 2 Z" fill="${color}" stroke="#0f172a" stroke-width="2.5"/>
    <circle cx="24" cy="22" r="13" fill="#ffffff" stroke="#0f172a" stroke-width="1.5"/>
    <g transform="translate(24,22)">${toolboxGlyph(type, color)}</g>
  </svg>`;
}

function toolboxMarkerDataUrl(type: string, color: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(toolboxMarkerSvg(type, color))}`;
}

function colorMetricKey(metric: string): string {
  if (metric === 'heat_risk_score') return 'heat_risk';
  if (metric === 'heat_index') return 'heat_risk';
  return metric;
}

function rgbaCss(rgb: [number, number, number], alpha: number): string {
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
}

function metricColorRange(metric: string): [number, number, number, number][] {
  const colorMetric = colorMetricKey(metric);
  const stops = [0, 20, 40, 60, 80, 100];

  return stops.map((value, index) => {
    const [r, g, b] = getColor(value, colorMetric);
    const alpha = index === 0 ? 0 : 230;
    return [r, g, b, alpha];
  });
}

function metricLegendGradient(metric: string): string {
  const colorMetric = colorMetricKey(metric);
  const stops = [0, 20, 40, 60, 80, 100];
  const pctStep = 100 / (stops.length - 1);

  const segments = stops.map((value, index) => {
    const color = getColor(value, colorMetric);
    const pct = Math.round(index * pctStep);
    return `${rgbaCss(color, 0.95)} ${pct}%`;
  });

  return `linear-gradient(to right, ${segments.join(', ')})`;
}

function formatMetricName(metricKey: string): string {
  if (metricKey === 'heat_risk_score') return 'Heat Risk';
  if (metricKey === 'visitor_activity') return 'Visitor Activity';
  return metricKey
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

const SPARSE_SURFACE_METRICS = new Set(['cooling_centers']);
const METRIC_SURFACE_CACHE = new Map<string, HeatmapMetricValue[]>();
const MAX_METRIC_SURFACE_CACHE_ENTRIES = 48;

function metricSurfaceCacheKey(points: HeatmapMetricValue[], metricKey: string): string {
  const first = points[0];
  const last = points[points.length - 1];
  return [
    metricKey,
    points.length,
    first?.location_coordinates.join(',') ?? 'none',
    first?.value ?? 0,
    last?.location_coordinates.join(',') ?? 'none',
    last?.value ?? 0,
  ].join('|');
}

function buildWeightedIndividualMetrics(
  metricSums: Record<string, number>,
  metricWeightTotals: Record<string, number>,
): HeatmapMetricValue['individual_metrics'] | undefined {
  const entries = Object.entries(metricSums)
    .filter(([key]) => metricWeightTotals[key] > 0)
    .map(([key, sum]) => [key, Number((sum / metricWeightTotals[key]).toFixed(1))]);

  return entries.length > 0 ? Object.fromEntries(entries) : undefined;
}

function addMetricWeights(
  point: HeatmapMetricValue,
  weight: number,
  metricSums: Record<string, number>,
  metricWeightTotals: Record<string, number>,
) {
  if (!point.individual_metrics || weight <= 0) return;

  for (const [key, value] of Object.entries(point.individual_metrics)) {
    if (typeof value !== 'number' || !Number.isFinite(value)) continue;
    metricSums[key] = (metricSums[key] ?? 0) + value * weight;
    metricWeightTotals[key] = (metricWeightTotals[key] ?? 0) + weight;
  }
}

function shouldInterpolateSparseMetric(metricKey: string, points: HeatmapMetricValue[]): boolean {
  if (!SPARSE_SURFACE_METRICS.has(metricKey)) return false;
  if (points.length < 3) return false;

  const nonZeroCount = points.filter((point) => point.value > 0).length;
  return nonZeroCount > 0 && nonZeroCount < points.length * 0.45;
}

function buildSparseInfluenceSurface(
  points: HeatmapMetricValue[],
  metricKey: string,
): HeatmapMetricValue[] {
  const anchors = points.filter((point) => point.value > 0);
  if (anchors.length === 0) return points;

  const lons = points.map((point) => point.location_coordinates[0]);
  const lats = points.map((point) => point.location_coordinates[1]);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const lonSpan = Math.max(maxLon - minLon, 0.01);
  const latSpan = Math.max(maxLat - minLat, 0.01);
  const lonStep = lonSpan / 68;
  const latStep = latSpan / 68;
  const influenceRadiusSq = Math.pow(Math.max(lonSpan, latSpan) * 0.12, 2);
  const maxAnchorValue = Math.max(...anchors.map((anchor) => anchor.value), 1);
  const syntheticPoints: HeatmapMetricValue[] = [];

  for (let lat = minLat; lat <= maxLat + latStep / 2; lat += latStep) {
    for (let lon = minLon; lon <= maxLon + lonStep / 2; lon += lonStep) {
      let strongestInfluence = 0;
      const metricSums: Record<string, number> = {};
      const metricWeightTotals: Record<string, number> = {};

      for (const anchor of anchors) {
        const [anchorLon, anchorLat] = anchor.location_coordinates;
        const dLon = lon - anchorLon;
        const dLat = lat - anchorLat;
        const distanceSq = dLon * dLon + dLat * dLat;
        const normalizedAnchorValue = (anchor.value / maxAnchorValue) * 100;
        const influence = normalizedAnchorValue * Math.exp(-distanceSq / influenceRadiusSq);
        strongestInfluence = Math.max(strongestInfluence, influence);
        addMetricWeights(anchor, influence, metricSums, metricWeightTotals);
      }

      if (strongestInfluence < 0.5) continue;

      syntheticPoints.push({
        value: strongestInfluence,
        location_name: `${formatMetricName(metricKey)} surface`,
        location_coordinates: [Number(lon.toFixed(5)), Number(lat.toFixed(5))],
        individual_metrics: buildWeightedIndividualMetrics(metricSums, metricWeightTotals),
        is_interpolated: true,
      });
    }
  }

  return [
    ...syntheticPoints,
    ...anchors.map((anchor) => ({
      ...anchor,
      value: (anchor.value / maxAnchorValue) * 100,
    })),
  ];
}

function buildContinuousMetricSurface(points: HeatmapMetricValue[]): HeatmapMetricValue[] {
  if (points.length < 3) return points;

  const lons = points.map((point) => point.location_coordinates[0]);
  const lats = points.map((point) => point.location_coordinates[1]);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const lonSpan = Math.max(maxLon - minLon, 0.01);
  const latSpan = Math.max(maxLat - minLat, 0.01);
  const lonStep = lonSpan / 80;
  const latStep = latSpan / 80;
  const power = 2;
  const maxInfluenceDistanceSq = Math.pow(Math.max(lonSpan, latSpan) * 0.22, 2);
  const syntheticPoints: HeatmapMetricValue[] = [];

  for (let lat = minLat; lat <= maxLat + latStep / 2; lat += latStep) {
    for (let lon = minLon; lon <= maxLon + lonStep / 2; lon += lonStep) {
      let weightedSum = 0;
      let weightTotal = 0;
      let nearestDistanceSq = Number.POSITIVE_INFINITY;
      let exactMetrics: HeatmapMetricValue['individual_metrics'] | undefined;
      const metricSums: Record<string, number> = {};
      const metricWeightTotals: Record<string, number> = {};

      for (const point of points) {
        const [pointLon, pointLat] = point.location_coordinates;
        const dLon = lon - pointLon;
        const dLat = lat - pointLat;
        const distanceSq = dLon * dLon + dLat * dLat;
        nearestDistanceSq = Math.min(nearestDistanceSq, distanceSq);

        if (distanceSq < 1e-10) {
          weightedSum = point.value;
          weightTotal = 1;
          nearestDistanceSq = 0;
          exactMetrics = point.individual_metrics;
          break;
        }

        if (distanceSq > maxInfluenceDistanceSq) continue;

        const weight = 1 / Math.pow(distanceSq, power / 2);
        weightedSum += point.value * weight;
        weightTotal += weight;
        addMetricWeights(point, weight, metricSums, metricWeightTotals);
      }

      if (weightTotal === 0) continue;

      const value = weightedSum / weightTotal;
      if (value < 0.5 && nearestDistanceSq > maxInfluenceDistanceSq * 0.2) continue;

      syntheticPoints.push({
        value,
        location_name: 'Surface estimate',
        location_coordinates: [Number(lon.toFixed(5)), Number(lat.toFixed(5))],
        individual_metrics:
          exactMetrics ?? buildWeightedIndividualMetrics(metricSums, metricWeightTotals),
        is_interpolated: true,
      });
    }
  }

  return [...syntheticPoints, ...points];
}

function buildMetricRenderSurface(
  points: HeatmapMetricValue[],
  metricKey: string,
): HeatmapMetricValue[] {
  const cacheKey = metricSurfaceCacheKey(points, metricKey);
  const cachedSurface = METRIC_SURFACE_CACHE.get(cacheKey);
  if (cachedSurface) return cachedSurface;

  const surface = shouldInterpolateSparseMetric(metricKey, points)
    ? buildSparseInfluenceSurface(points, metricKey)
    : buildContinuousMetricSurface(points);

  METRIC_SURFACE_CACHE.set(cacheKey, surface);
  if (METRIC_SURFACE_CACHE.size > MAX_METRIC_SURFACE_CACHE_ENTRIES) {
    const oldestKey = METRIC_SURFACE_CACHE.keys().next().value;
    if (oldestKey) METRIC_SURFACE_CACHE.delete(oldestKey);
  }

  return surface;
}

function translatePolygon(
  points: [number, number][],
  deltaLng: number,
  deltaLat: number,
): [number, number][] {
  return points.map(([lng, lat]) => [lng + deltaLng, lat + deltaLat]);
}

const Heatmap: React.FC<HeatmapProps> = ({
  viewState,
  setViewState,
  selectedCity,
  setSelectedCity,
  cityPOIAreas,
  heatmapPointsByCity,
  showAllCityHeatmaps = false,
  mapContainerRef,
  mapRef,
  mapSyncFrameRef,
  tooltip,
  setTooltip,
  isFullscreen,
  setIsFullscreen,
  isDrawing,
  setIsDrawing,
  draftPoints,
  setDraftPoints,
  draftColorHex,
  setDraftColorHex,
  draftName,
  setDraftName,
  userPOIAreas,
  setUserPOIAreas,
  hoveringHeatmap,
  setHoveringHeatmap,
  searchQuery,
  setSearchQuery,
  geoResults,
  setGeoResults,
  isSearching,
  setIsSearching,
  showSuggestions,
  setShowSuggestions,
  selectedMetric,
  setSelectedMetric,
  editingAreaId,
  setEditingAreaId,
  isAreaDragging,
  setIsAreaDragging,
  onPOIAreaSelect,
  onMetricPointSelect,
  displayToolbox = false,
}) => {
  const heatmapRootRef = useRef<HTMLDivElement>(null);
  const blurTimeoutRef = useRef<number | null>(null);

  // Objects placed onto the map from the toolbox. Kept local to the component
  // since they're a self-contained overlay; lift into props if you need them
  // shared with the parent (e.g. for persistence).
  const [placedObjects, setPlacedObjects] = useState<PlacedObject[]>([]);
  const [hoveredPOIArea, setHoveredPOIArea] = useState<{
    area: CityPOIArea;
    x: number;
    y: number;
  } | null>(null);

  const dragContextRef = useRef<
    | {
        mode: 'draft';
        start: [number, number];
        originalDraft: [number, number][];
      }
    | {
        mode: 'existing';
        areaId: string;
        start: [number, number];
        originalPolygon: [number, number][];
      }
    | null
  >(null);

  // Fly the map + shared view state to a location. Pass cityName to also mark a
  // city as selected (so its heatmap points load); omit for generic places.
  const flyTo = useCallback(
    (lng: number, lat: number, zoom: number, cityName?: string) => {
      const newState: ViewState = { longitude: lng, latitude: lat, zoom, pitch: 0, bearing: 0 };
      setViewState(newState);
      if (cityName !== undefined) setSelectedCity(cityName);

      if (mapRef.current) {
        mapRef.current.flyTo({ center: [lng, lat], zoom, duration: 1200 });
      }
    },
    [setViewState, setSelectedCity, mapRef],
  );

  // Local matches against the known host cities (instant, no network).
  const cityMatches = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];
    return cities.filter((c) => c.name.toLowerCase().includes(q)).slice(0, 5);
  }, [searchQuery]);

  const parsedCoords = useMemo(() => parseCoordinates(searchQuery), [searchQuery]);

  // Debounced geocoding for free-form destinations (skipped for coords / short
  // queries). Aborts stale requests so only the latest query resolves.
  useEffect(() => {
    const q = searchQuery.trim();
    if (q.length < 3 || parseCoordinates(q)) {
      setGeoResults([]);
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        setIsSearching(true);
        const results = await geocode(q, controller.signal);
        setGeoResults(results);
      } catch {
        /* aborted or failed — ignore */
      } finally {
        setIsSearching(false);
      }
    }, 350);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [searchQuery]);

  const selectCity = useCallback(
    (city: City) => {
      flyTo(city.longitude, city.latitude, 10, city.name);
      setSearchQuery(city.name);
      setShowSuggestions(false);
    },
    [flyTo],
  );

  const selectPlace = useCallback(
    (place: GeocodeResult) => {
      flyTo(place.lng, place.lat, 12);
      setSearchQuery(place.label);
      setShowSuggestions(false);
    },
    [flyTo],
  );

  // Enter / search-button: resolve in priority order coords -> city -> geocode.
  const handleSearchSubmit = useCallback(async () => {
    const q = searchQuery.trim();
    if (!q) return;

    if (parsedCoords) {
      flyTo(parsedCoords[0], parsedCoords[1], 12);
      setShowSuggestions(false);
      return;
    }
    if (cityMatches.length > 0) {
      selectCity(cityMatches[0]);
      return;
    }
    if (geoResults.length > 0) {
      selectPlace(geoResults[0]);
      return;
    }

    // Nothing cached yet — geocode synchronously on submit.
    try {
      setIsSearching(true);
      const results = await geocode(q);
      if (results.length > 0) selectPlace(results[0]);
    } catch {
      /* ignore */
    } finally {
      setIsSearching(false);
      setShowSuggestions(false);
    }
  }, [searchQuery, parsedCoords, cityMatches, geoResults, flyTo, selectCity, selectPlace]);

  const clearSearch = useCallback(() => {
    setSearchQuery('');
    setGeoResults([]);
    setShowSuggestions(false);
  }, []);

  const handleCityClick = useCallback(
    (city: City) => {
      // While drawing, map clicks add vertices instead of switching cities.
      if (isDrawing) return;

      const newState = {
        longitude: city.longitude,
        latitude: city.latitude,
        zoom: 10,
        pitch: 0,
        bearing: 0,
      };
      setViewState(newState);
      setSelectedCity(city.name);

      // Update map camera
      if (mapRef.current) {
        mapRef.current.flyTo({
          center: [city.longitude, city.latitude],
          zoom: 10,
          duration: 1000,
        });
      }
    },
    [isDrawing, setViewState, setSelectedCity, mapRef],
  );

  // --- Drawing controls ---
  const startDrawing = useCallback(() => {
    if (!selectedCity) return;
    setDraftPoints([]);
    setIsDrawing(true);
  }, [selectedCity]);

  const cancelDrawing = useCallback(() => {
    setDraftPoints([]);
    setDraftName('');
    setIsDrawing(false);
  }, []);

  const undoLastPoint = useCallback(() => {
    setDraftPoints((prev) => prev.slice(0, -1));
  }, []);

  const finishArea = useCallback(() => {
    if (!selectedCity || draftPoints.length < 3) return;

    const rgb = hexToRgb(draftColorHex);
    const newArea: CityPOIArea = {
      id: `custom-${Date.now()}-${userPOIAreas.length + 1}`,
      cityName: selectedCity,
      name: draftName.trim() || `Custom Area ${userPOIAreas.length + 1}`,
      polygon: draftPoints,
      color: [...rgb, 140],
    } as CityPOIArea;

    setUserPOIAreas((prev) => [...prev, newArea]);
    // Persist the newly drawn area in the backend copy. We optimistically show
    // the local polygon immediately, then replace it with the saved backend
    // version once impacted grid ids come back.
    void createSimulationPolygon({
      name: newArea.name,
      cityName: selectedCity,
      color: newArea.color,
      polygon: draftPoints,
    })
      .then((savedArea) => {
        setUserPOIAreas((prev) =>
          prev.map((area) => (area.id === newArea.id ? { ...area, ...savedArea } : area)),
        );
      })
      .catch((error) => {
        console.error('Failed to save simulation polygon', error);
      });
    setDraftPoints([]);
    setDraftName('');
    setIsDrawing(false);
  }, [selectedCity, draftPoints, draftColorHex, draftName, userPOIAreas.length]);

  const clearMyAreas = useCallback(() => {
    setUserPOIAreas((prev) => prev.filter((a) => a.cityName !== selectedCity));
  }, [selectedCity]);

  // Add a vertex on any map click while drawing.
  const handleDeckClick = useCallback(
    (info: any) => {
      if (!isDrawing || isAreaDragging || editingAreaId || !info?.coordinate) return;
      const [lng, lat] = info.coordinate;
      setDraftPoints((prev) => [...prev, [lng, lat]]);
    },
    [isDrawing, isAreaDragging, editingAreaId, setDraftPoints],
  );

  // --- Toolbox object placement (HTML5 drag from palette -> drop on map) ---

  // Only accept our custom drag payload; lets normal map interaction through.
  const handleObjectDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    if (e.dataTransfer.types.includes(TOOLBOX_DRAG_MIME)) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
    }
  }, []);

  // Convert the drop point (viewport px) into map lng/lat via maplibre and
  // append a placed object there.
  const handleObjectDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      const type = e.dataTransfer.getData(TOOLBOX_DRAG_MIME);
      if (!type) return;
      e.preventDefault();

      const map = mapRef.current;
      const container = mapContainerRef.current;
      if (!map || !container) return;

      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const { lng, lat } = map.unproject([x, y]);

      setPlacedObjects((prev) => [
        ...prev,
        {
          id: `placed-${Date.now()}-${prev.length + 1}`,
          type,
          longitude: lng,
          latitude: lat,
        },
      ]);
    },
    [mapRef, mapContainerRef],
  );

  const removePlacedObject = useCallback((id: string) => {
    setPlacedObjects((prev) => prev.filter((o) => o.id !== id));
  }, []);

  const clearPlacedObjects = useCallback(() => setPlacedObjects([]), []);

  const applyPlacedObjects = useCallback(() => {
    if (placedObjects.length === 0) return;

    // If the user has drawn/saved POI areas in this city, scope the simulation
    // to those impacted grid ids. Otherwise the backend applies the objects to
    // the current city/state metric set.
    const impactedGridCellIds = userPOIAreas
      .filter((area) => !selectedCity || area.cityName === selectedCity)
      .flatMap((area) => area.impacted_grid_cell_ids ?? []);

    void applySimulation({
      cityName: selectedCity ?? undefined,
      impactedGridCellIds: impactedGridCellIds.length > 0 ? impactedGridCellIds : undefined,
      placedObjects: placedObjects.map((object): SimulationPlacedObject => ({
        id: object.id,
        type: object.type,
        longitude: object.longitude,
        latitude: object.latitude,
      })),
    })
      .then((result) => {
        console.info('Simulation applied', result);
      })
      .catch((error) => {
        console.error('Failed to apply simulation', error);
      });
  }, [placedObjects, selectedCity, userPOIAreas]);

  // Tournament-style host marker. Kept intentionally quiet at national zoom so
  // the planning surfaces remain the primary map signal.
  const cityIconLayer = useMemo(
    () =>
      new IconLayer({
        id: 'city-icon-layer',
        data: cities,
        pickable: !isDrawing,
        getPosition: (d: City) => [d.longitude, d.latitude],
        getIcon: () => ({
          url: FOOTBALL_ICON,
          width: 56,
          height: 64,
          anchorX: 28,
          anchorY: 58,
          id: 'football',
        }),
        getSize: (d: City) => {
          if (selectedCity === d.name) return 34;
          if (viewState.zoom < 4.5) return 24;
          return 28;
        },
        sizeUnits: 'pixels',
        getPixelOffset: [0, -11],
        onClick: (info: any) => {
          if (info.object) {
            handleCityClick(info.object as City);
          }
        },
      }),
    [handleCityClick, isDrawing, selectedCity, viewState.zoom],
  );

  // City labels stay attached to markers, but become quieter at national zoom.
  const cityLabelLayer = useMemo(
    () =>
      new TextLayer({
        id: 'city-label-layer',
        data: cities,
        pickable: !isDrawing,
        characterSet: 'auto',
        fontFamily: '"Inter", system-ui, sans-serif',
        fontWeight: 650,
        getPosition: (d: City) => [d.longitude, d.latitude],
        getText: (d: City) => d.name,
        getSize: (d: City) => {
          if (selectedCity === d.name) return 11;
          if (viewState.zoom < 4.5) return 8;
          return 9;
        },
        sizeUnits: 'pixels',
        getPixelOffset: [0, -2],
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'top',
        getColor: (d: City) =>
          selectedCity === d.name ? [254, 243, 199, 235] : [226, 232, 240, viewState.zoom < 4.5 ? 95 : 130],
        background: true,
        getBackgroundColor: (d: City) =>
          selectedCity === d.name ? [15, 23, 42, 185] : [2, 8, 23, viewState.zoom < 4.5 ? 45 : 75],
        backgroundPadding: [3, 1, 3, 1],
        fontSettings: { sdf: true },
        outlineWidth: 1,
        outlineColor: [2, 8, 23, 180],
        updateTriggers: {
          getSize: [selectedCity, viewState.zoom],
          getColor: [selectedCity, viewState.zoom],
          getBackgroundColor: [selectedCity, viewState.zoom],
        },
        onClick: (info: any) => {
          if (info.object) {
            handleCityClick(info.object as City);
          }
        },
      }),
    [handleCityClick, isDrawing, selectedCity, viewState.zoom],
  );

  const availableMetricLayers: HeatmapMetricPoint[] = useMemo(() => {
    if (!showAllCityHeatmaps) {
      return selectedCity ? (heatmapPointsByCity[selectedCity] ?? []) : [];
    }

    const layersByMetric = new Map<string, HeatmapMetricPoint>();
    for (const cityLayers of Object.values(heatmapPointsByCity)) {
      for (const layer of cityLayers) {
        const mergedLayer = layersByMetric.get(layer.metric);
        if (mergedLayer) {
          mergedLayer.points.push(...layer.points);
        } else {
          layersByMetric.set(layer.metric, {
            metric: layer.metric,
            points: [...layer.points],
          });
        }
      }
    }

    return Array.from(layersByMetric.values());
  }, [heatmapPointsByCity, selectedCity, showAllCityHeatmaps]);

  useEffect(() => {
    if (availableMetricLayers.length === 0) {
      setSelectedMetric(null);
      return;
    }

    setSelectedMetric((prev) => {
      if (prev && availableMetricLayers.some((m) => m.metric === prev)) return prev;
      return availableMetricLayers[0].metric;
    });
  }, [availableMetricLayers, setSelectedMetric]);

  const activeMetricLayer = useMemo(
    () =>
      availableMetricLayers.find((m) => m.metric === selectedMetric) ??
      availableMetricLayers[0],
    [availableMetricLayers, selectedMetric],
  );

  const displayedHeatmapPoints: HeatmapMetricValue[] = useMemo(
    () => activeMetricLayer?.points ?? [],
    [activeMetricLayer],
  );

  const activeMetricKey = activeMetricLayer?.metric ?? 'heat_risk_score';
  const isSparseInterpolatedMetric = useMemo(
    () => shouldInterpolateSparseMetric(activeMetricKey, displayedHeatmapPoints),
    [activeMetricKey, displayedHeatmapPoints],
  );
  const renderedHeatmapPoints: HeatmapMetricValue[] = useMemo(
    () => {
      if (!showAllCityHeatmaps) {
        return buildMetricRenderSurface(displayedHeatmapPoints, activeMetricKey);
      }

      return Object.values(heatmapPointsByCity).flatMap((cityLayers) => {
        const cityMetricLayer = cityLayers.find((layer) => layer.metric === activeMetricKey);
        return cityMetricLayer ? buildMetricRenderSurface(cityMetricLayer.points, activeMetricKey) : [];
      });
    },
    [activeMetricKey, displayedHeatmapPoints, heatmapPointsByCity, showAllCityHeatmaps],
  );
  const heatmapCellCounts = useMemo(() => {
    const actual = displayedHeatmapPoints.length;
    const interpolated = renderedHeatmapPoints.filter((point) => point.is_interpolated).length;

    return {
      actual,
      interpolated,
      total: actual + interpolated,
    };
  }, [displayedHeatmapPoints, renderedHeatmapPoints]);
  const heatmapCountScopeLabel = showAllCityHeatmaps ? 'All cities' : selectedCity ?? 'Current city';
  const metricLabelText = formatMetricName(activeMetricKey);
  const activeMetricColorRange = useMemo(
    () => metricColorRange(activeMetricKey),
    [activeMetricKey],
  );
  const heatmapOpacity = useMemo(() => {
    const fadeStartZoom = 10;
    const fadeEndZoom = 15;
    const t = Math.min(
      1,
      Math.max(0, (viewState.zoom - fadeStartZoom) / (fadeEndZoom - fadeStartZoom)),
    );
    return 0.9 - t * 0.45;
  }, [viewState.zoom]);
  const heatmapRadiusPixels = useMemo(() => {
    const baseRadius = isSparseInterpolatedMetric ? 78 : 52;
    const regionalBoost = Math.max(0, Math.min(5, 10 - viewState.zoom)) * 15;
    const localReduction = Math.max(0, Math.min(4, viewState.zoom - 11)) * 5;
    const allCityBoost = showAllCityHeatmaps ? 12 : 0;

    return Math.round(
      Math.max(30, Math.min(136, baseRadius + regionalBoost + allCityBoost - localReduction)),
    );
  }, [isSparseInterpolatedMetric, showAllCityHeatmaps, viewState.zoom]);
  const heatmapIntensity = useMemo(() => {
    const baseIntensity = isSparseInterpolatedMetric ? 1.55 : 1.28;
    const zoomSoftening = Math.max(0, Math.min(4, 9.5 - viewState.zoom)) * 0.08;
    const closeFocus = Math.max(0, Math.min(4, viewState.zoom - 12)) * 0.04;

    return Math.max(0.95, baseIntensity - zoomSoftening + closeFocus);
  }, [isSparseInterpolatedMetric, viewState.zoom]);
  const activeMetricLegendGradient = useMemo(
    () => metricLegendGradient(activeMetricKey),
    [activeMetricKey],
  );

  const displayedPOIAreas: CityPOIArea[] = useMemo(() => {
    if (!selectedCity) return [];
    return [
      ...cityPOIAreas.filter((poi) => poi.cityName === selectedCity),
      ...userPOIAreas.filter((poi) => poi.cityName === selectedCity),
    ];
  }, [selectedCity, cityPOIAreas, userPOIAreas]);

  // Continuous, interpolated density surface (GPU kernel-density estimation).
  // Larger radius + lower threshold = smoother blending between points.
  const interpolatedHeatmapLayer = useMemo(
    () =>
      new HeatmapLayer({
        id: 'interpolated-heatmap-layer',
        data: renderedHeatmapPoints,
        pickable: false,
        opacity: heatmapOpacity,
        getPosition: (d: HeatmapMetricValue) => d.location_coordinates,
        getWeight: (d: HeatmapMetricValue) => d.value,
        aggregation: 'SUM',
        radiusPixels: heatmapRadiusPixels,
        intensity: heatmapIntensity,
        threshold: isSparseInterpolatedMetric ? 0.015 : 0.025,
        weightsTextureSize: 1024,
        colorRange: activeMetricColorRange as any,
      }),
    [
      renderedHeatmapPoints,
      activeMetricColorRange,
      heatmapIntensity,
      heatmapOpacity,
      heatmapRadiusPixels,
      isSparseInterpolatedMetric,
    ],
  );

  const heatmapPickLayer = useMemo(
    () =>
      new ScatterplotLayer({
        id: 'heatmap-pick-layer',
        data: renderedHeatmapPoints,
        pickable: !isDrawing,
        opacity: 0,
        radiusMinPixels: 10,
        radiusMaxPixels: 16,
        getPosition: (d: HeatmapMetricValue) => d.location_coordinates,
        getFillColor: [0, 0, 0, 0],
        onHover: (info: any) => {
          if (info.object) {
            setHoveringHeatmap(true);
            setTooltip({
              point: info.object as HeatmapMetricValue,
              metric: activeMetricKey,
              x: info.x,
              y: info.y,
            });
          } else {
            setHoveringHeatmap(false);
            setTooltip(null);
          }
        },
        onClick: (info: any) => {
          if (info.object && !(info.object as HeatmapMetricValue).is_interpolated) {
            onMetricPointSelect?.(info.object as HeatmapMetricValue, activeMetricKey);
          }
        },
      }),
    [
      renderedHeatmapPoints,
      isDrawing,
      setHoveringHeatmap,
      setTooltip,
      activeMetricKey,
      onMetricPointSelect,
    ],
  );

  // Toolbox objects dropped onto the map. Click a pin to remove it.
  const placedObjectLayer = useMemo(
    () =>
      new IconLayer({
        id: 'placed-object-layer',
        data: placedObjects,
        pickable: !isDrawing,
        getPosition: (d: PlacedObject) => [d.longitude, d.latitude],
        getIcon: (d: PlacedObject) => {
          const def = TOOLBOX_BY_TYPE[d.type];
          const color = def?.color ?? '#f8fafc';
          return {
            url: toolboxMarkerDataUrl(d.type, color),
            width: 48,
            height: 60,
            anchorX: 24,
            anchorY: 58,
            id: d.type,
          };
        },
        getSize: 46,
        sizeUnits: 'pixels',
        onClick: (info: any) => {
          if (info.object) removePlacedObject((info.object as PlacedObject).id);
        },
      }),
    [placedObjects, isDrawing, removePlacedObject],
  );

  const poiAreaLayer = useMemo(
    () =>
      new PolygonLayer({
        id: 'poi-area-layer',
        data: displayedPOIAreas,
        pickable: true,
        stroked: true,
        filled: true,
        opacity: 0.55,
        getPolygon: (d: CityPOIArea) => d.polygon,
        getFillColor: (d: CityPOIArea) => d.color,
        getLineColor: (d: CityPOIArea) =>
          d.id === editingAreaId ? [56, 189, 248, 255] : [255, 255, 255, 255],
        getLineWidth: (d: CityPOIArea) => (d.id === editingAreaId ? 3 : 1),
        lineWidthUnits: 'pixels',
        onHover: (info: any) => {
          const area = info.object as CityPOIArea | undefined;
          if (!area) {
            setHoveredPOIArea(null);
            return;
          }
          setHoveredPOIArea({ area, x: info.x, y: info.y });
        },
        onClick: (info: any) => {
          const area = info.object as CityPOIArea | undefined;
          if (!area) return;
          onPOIAreaSelect?.(area);

          if (info.tapCount >= 2) {
            const isUserArea = userPOIAreas.some((a) => a.id === area.id);
            if (isUserArea) {
              setEditingAreaId(area.id);
              setIsDrawing(false);
            }
          }
        },
        onDragStart: (info: any) => {
          const area = info.object as CityPOIArea | undefined;
          if (!area || !info.coordinate) return;
          if (editingAreaId !== area.id) return;

          dragContextRef.current = {
            mode: 'existing',
            areaId: area.id,
            start: [info.coordinate[0], info.coordinate[1]],
            originalPolygon: area.polygon,
          };
          setIsAreaDragging(true);
        },
        onDrag: (info: any) => {
          const ctx = dragContextRef.current;
          if (!ctx || ctx.mode !== 'existing' || !info.coordinate) return;

          const deltaLng = info.coordinate[0] - ctx.start[0];
          const deltaLat = info.coordinate[1] - ctx.start[1];
          const translated = translatePolygon(ctx.originalPolygon, deltaLng, deltaLat);

          setUserPOIAreas((prev) =>
            prev.map((area) =>
              area.id === ctx.areaId ? { ...area, polygon: translated } : area,
            ),
          );
        },
        onDragEnd: () => {
          dragContextRef.current = null;
          setIsAreaDragging(false);
        },
      }),
    [
      displayedPOIAreas,
      editingAreaId,
      userPOIAreas,
      setEditingAreaId,
      setIsDrawing,
      setIsAreaDragging,
      setUserPOIAreas,
      onPOIAreaSelect,
    ],
  );

  const hoveredPOIStats = hoveredPOIArea?.area.properties?.statistics;

  // --- Draft (in-progress) drawing layers ---
  const draftRgb = useMemo(() => hexToRgb(draftColorHex), [draftColorHex]);

  const draftPolygonLayer = useMemo(
    () =>
      new PolygonLayer({
        id: 'draft-polygon-layer',
        data: draftPoints.length >= 3 ? [{ polygon: draftPoints }] : [],
        pickable: isDrawing,
        stroked: true,
        filled: true,
        opacity: 0.5,
        getPolygon: (d: { polygon: [number, number][] }) => d.polygon,
        getFillColor: [...draftRgb, 120],
        getLineColor: [...draftRgb, 255],
        getLineWidth: 2,
        lineWidthUnits: 'pixels',
        onDragStart: (info: any) => {
          if (!isDrawing || draftPoints.length < 3 || !info.coordinate) return;
          dragContextRef.current = {
            mode: 'draft',
            start: [info.coordinate[0], info.coordinate[1]],
            originalDraft: draftPoints,
          };
          setIsAreaDragging(true);
        },
        onDrag: (info: any) => {
          const ctx = dragContextRef.current;
          if (!ctx || ctx.mode !== 'draft' || !info.coordinate) return;

          const deltaLng = info.coordinate[0] - ctx.start[0];
          const deltaLat = info.coordinate[1] - ctx.start[1];
          setDraftPoints(translatePolygon(ctx.originalDraft, deltaLng, deltaLat));
        },
        onDragEnd: () => {
          dragContextRef.current = null;
          setIsAreaDragging(false);
        },
      }),
    [draftPoints, draftRgb, isDrawing, setDraftPoints, setIsAreaDragging],
  );

  const draftPathLayer = useMemo(
    () =>
      new PathLayer({
        id: 'draft-path-layer',
        data: draftPoints.length >= 2 ? [{ path: draftPoints }] : [],
        pickable: false,
        getPath: (d: { path: [number, number][] }) => d.path,
        getColor: [...draftRgb, 255],
        getWidth: 2,
        widthUnits: 'pixels',
      }),
    [draftPoints, draftRgb],
  );

  const draftPointsLayer = useMemo(
    () =>
      new ScatterplotLayer({
        id: 'draft-points-layer',
        data: draftPoints,
        pickable: false,
        radiusMinPixels: 5,
        radiusMaxPixels: 5,
        getPosition: (d: [number, number]) => d,
        getFillColor: [...draftRgb, 255],
        getLineColor: [255, 255, 255, 255],
        lineWidthMinPixels: 1,
        stroked: true,
      }),
    [draftPoints, draftRgb],
  );

  const layers = useMemo(
    () => [
      interpolatedHeatmapLayer,
      poiAreaLayer,
      draftPolygonLayer,
      draftPathLayer,
      draftPointsLayer,
      heatmapPickLayer,
      placedObjectLayer,
      cityIconLayer,
      cityLabelLayer,
    ],
    [
      interpolatedHeatmapLayer,
      poiAreaLayer,
      draftPolygonLayer,
      draftPathLayer,
      draftPointsLayer,
      heatmapPickLayer,
      placedObjectLayer,
      cityIconLayer,
      cityLabelLayer,
    ],
  );

  // Crosshair while drawing or hovering the heatmap; grab/grabbing otherwise
  // so normal map panning still reads correctly.
  const getCursor = useCallback(
    ({ isDragging }: { isDragging: boolean }) =>
      isDragging || isAreaDragging
        ? 'grabbing'
        : isDrawing || hoveringHeatmap || !!editingAreaId
          ? 'crosshair'
          : 'grab',
    [isDrawing, hoveringHeatmap, editingAreaId, isAreaDragging],
  );

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === heatmapRootRef.current);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  const toggleFullscreen = useCallback(async () => {
    const root = heatmapRootRef.current;
    if (!root) return;

    try {
      if (document.fullscreenElement === root) {
        await document.exitFullscreen();
      } else {
        await root.requestFullscreen();
      }
    } catch (error) {
      console.error('Failed to toggle fullscreen heatmap', error);
    }
  }, []);

  const handleViewStateChange = useCallback(
    (e: any) => {
      const nextState = e.viewState as {
        longitude: number;
        latitude: number;
        zoom: number;
        pitch: number;
        bearing: number;
      };
      const newState: ViewState = {
        longitude: nextState.longitude,
        latitude: nextState.latitude,
        zoom: nextState.zoom,
        pitch: nextState.pitch,
        bearing: nextState.bearing,
      };

      setViewState((prev) => {
        if (
          Math.abs(prev.longitude - newState.longitude) < 1e-6 &&
          Math.abs(prev.latitude - newState.latitude) < 1e-6 &&
          Math.abs(prev.zoom - newState.zoom) < 1e-4 &&
          Math.abs(prev.pitch - newState.pitch) < 1e-4 &&
          Math.abs(prev.bearing - newState.bearing) < 1e-4
        ) {
          return prev;
        }
        return newState;
      });

      if (!mapRef.current) return;

      if (mapSyncFrameRef.current !== null) {
        cancelAnimationFrame(mapSyncFrameRef.current);
      }

      mapSyncFrameRef.current = requestAnimationFrame(() => {
        if (!mapRef.current) return;
        mapRef.current.jumpTo({
          center: [newState.longitude, newState.latitude],
          zoom: newState.zoom,
          pitch: newState.pitch,
          bearing: newState.bearing,
        });
      });
    },
    [setViewState, mapRef, mapSyncFrameRef],
  );

  const toolbarButtonStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    padding: '8px 10px',
    borderRadius: 8,
    border: '1px solid rgba(148, 163, 184, 0.45)',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    width: '100%',
  };

  const hasSuggestions =
    parsedCoords !== null || cityMatches.length > 0 || geoResults.length > 0;

  // The Create POI Area controls — shared between the standalone panel and the
  // full toolbox layout.
  const createPOISection = (
    <>
      <div style={{ fontSize: 13, fontWeight: 700 }}>Create POI Area</div>

      {!selectedCity && (
        <div style={{ fontSize: 12, color: '#fca5a5' }}>
          Click a city marker first to pick a city.
        </div>
      )}

      {selectedCity && (
        <div style={{ fontSize: 12, color: '#94a3b8' }}>
          City: <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{selectedCity}</span>
        </div>
      )}

      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#cbd5e1' }}>
        Area name
        <input
          type="text"
          value={draftName}
          onChange={(e) => setDraftName(e.target.value)}
          placeholder="e.g. Downtown Core"
          style={{
            padding: '6px 8px',
            borderRadius: 6,
            border: '1px solid rgba(148, 163, 184, 0.45)',
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            color: '#f1f5f9',
            fontSize: 13,
          }}
        />
      </label>

      <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12, color: '#cbd5e1' }}>
        Area color
        <input
          type="color"
          value={draftColorHex}
          onChange={(e) => setDraftColorHex(e.target.value)}
          style={{
            width: 44,
            height: 28,
            border: '1px solid rgba(148, 163, 184, 0.45)',
            borderRadius: 6,
            background: 'transparent',
            cursor: 'pointer',
          }}
        />
      </label>

      {!isDrawing ? (
        <button
          type="button"
          onClick={startDrawing}
          disabled={!selectedCity}
          style={{
            ...toolbarButtonStyle,
            backgroundColor: selectedCity ? '#2563eb' : 'rgba(71, 85, 105, 0.6)',
            color: '#f8fafc',
            cursor: selectedCity ? 'pointer' : 'not-allowed',
          }}
        >
          <Pencil size={15} /> Draw new area
        </button>
      ) : (
        <>
          <div style={{ fontSize: 12, color: '#cbd5e1' }}>
            Click the map to add points ({draftPoints.length} placed, need 3+).
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={finishArea}
              disabled={draftPoints.length < 3}
              style={{
                ...toolbarButtonStyle,
                backgroundColor: draftPoints.length >= 3 ? '#16a34a' : 'rgba(71, 85, 105, 0.6)',
                color: '#f8fafc',
                cursor: draftPoints.length >= 3 ? 'pointer' : 'not-allowed',
              }}
            >
              <Check size={15} /> Finish
            </button>
            <button
              type="button"
              onClick={undoLastPoint}
              disabled={draftPoints.length === 0}
              style={{
                ...toolbarButtonStyle,
                backgroundColor: 'rgba(30, 41, 59, 0.9)',
                color: '#e2e8f0',
                cursor: draftPoints.length === 0 ? 'not-allowed' : 'pointer',
              }}
            >
              <Undo2 size={15} /> Undo
            </button>
          </div>
          <button
            type="button"
            onClick={cancelDrawing}
            style={{
              ...toolbarButtonStyle,
              backgroundColor: 'rgba(30, 41, 59, 0.9)',
              color: '#fca5a5',
            }}
          >
            <X size={15} /> Cancel
          </button>
        </>
      )}

      {userPOIAreas.some((a) => a.cityName === selectedCity) && (
        <button
          type="button"
          onClick={clearMyAreas}
          style={{
            ...toolbarButtonStyle,
            backgroundColor: 'rgba(30, 41, 59, 0.9)',
            color: '#fca5a5',
          }}
        >
          <Trash2 size={15} /> Clear my areas
        </button>
      )}

      {editingAreaId && (
        <button
          type="button"
          onClick={() => {
            setEditingAreaId(null);
            setIsAreaDragging(false);
          }}
          style={{
            ...toolbarButtonStyle,
            backgroundColor: 'rgba(14, 116, 144, 0.85)',
            color: '#e0f2fe',
          }}
        >
          <Check size={15} /> Finish Edit
        </button>
      )}
    </>
  );

  // The draggable object palette — only rendered in the full toolbox layout.
  const toolboxObjectsSection = (
    <>
      <div style={{ fontSize: 13, fontWeight: 700 }}>Toolbox</div>
      <div style={{ fontSize: 12, color: '#94a3b8', marginTop: -4 }}>
        Drag an item onto the map to place it. Click a placed pin to remove it.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {TOOLBOX_ITEMS.map((item) => {
          const Icon = item.Icon;
          return (
            <div
              key={item.type}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData(TOOLBOX_DRAG_MIME, item.type);
                e.dataTransfer.effectAllowed = 'copy';
              }}
              title={`Drag to place ${item.label}`}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 6,
                padding: '10px 6px',
                borderRadius: 8,
                border: '1px solid rgba(148, 163, 184, 0.35)',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                cursor: 'grab',
                userSelect: 'none',
                textAlign: 'center',
              }}
            >
              <span
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 30,
                  height: 30,
                  borderRadius: 999,
                  backgroundColor: `${item.color}22`,
                  border: `1px solid ${item.color}`,
                }}
              >
                <Icon size={17} color={item.color} />
              </span>
              <span style={{ fontSize: 11, lineHeight: 1.2, color: '#e2e8f0' }}>
                {item.label}
              </span>
            </div>
          );
        })}
      </div>

      {placedObjects.length > 0 && (
        <>
          <button
            type="button"
            onClick={applyPlacedObjects}
            style={{
              ...toolbarButtonStyle,
              backgroundColor: '#16a34a',
              color: '#f8fafc',
            }}
          >
            <Check size={15} /> Apply simulation
          </button>

          <button
            type="button"
            onClick={clearPlacedObjects}
            style={{
              ...toolbarButtonStyle,
              backgroundColor: 'rgba(30, 41, 59, 0.9)',
              color: '#fca5a5',
            }}
          >
            <Trash2 size={15} /> Clear objects ({placedObjects.length})
          </button>
        </>
      )}

      <div
        style={{
          height: 1,
          backgroundColor: 'rgba(148, 163, 184, 0.3)',
          margin: '2px 0',
        }}
      />
    </>
  );

  return (
    <div
      ref={heatmapRootRef}
      style={{ width: '100%', height: '100%', minHeight: '480px', position: 'relative' }}
      onDragOver={handleObjectDragOver}
      onDrop={handleObjectDrop}
    >
      <div
        ref={mapContainerRef}
        style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}
      />
      <DeckGL
        viewState={viewState}
        onViewStateChange={handleViewStateChange}
        onClick={handleDeckClick}
        controller={{ dragPan: !isAreaDragging, scrollZoom: true, touchZoom: true }}
        layers={layers}
        getCursor={getCursor}
        style={{ position: 'absolute', width: '100%', height: '100%' }}
      />

      {hoveredPOIArea && (
        <div
          style={{
            position: 'absolute',
            left: hoveredPOIArea.x + 14,
            top: hoveredPOIArea.y + 14,
            zIndex: 45,
            maxWidth: 260,
            pointerEvents: 'none',
            border: '1px solid rgba(125, 211, 252, 0.45)',
            backgroundColor: 'rgba(2, 8, 23, 0.94)',
            borderRadius: 10,
            padding: '10px 12px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.45)',
            color: '#f8fafc',
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 800, lineHeight: 1.25 }}>
            {hoveredPOIArea.area.name}
          </div>
          <div style={{ marginTop: 4, fontSize: 12, color: '#bae6fd' }}>
            {hoveredPOIArea.area.category ?? 'Unknown category'}
          </div>
          <div style={{ marginTop: 8, display: 'grid', gap: 3, fontSize: 11, color: '#cbd5e1' }}>
            <span>{hoveredPOIStats?.address ?? hoveredPOIArea.area.cityName}</span>
            <span>
              {hoveredPOIStats?.city ?? hoveredPOIArea.area.cityName}
              {hoveredPOIStats?.region || hoveredPOIArea.area.stateName
                ? `, ${hoveredPOIStats?.region ?? hoveredPOIArea.area.stateName}`
                : ''}
            </span>
          </div>
        </div>
      )}

      {/* --- Search bar (top center) --- */}
      <div
        style={{
          position: 'absolute',
          top: 20,
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 35,
          width: 360,
          maxWidth: 'calc(100% - 320px)',
        }}
        onBlur={() => {
          // Delay so a click on a suggestion still registers before closing.
          blurTimeoutRef.current = window.setTimeout(() => setShowSuggestions(false), 120);
        }}
        onFocus={() => {
          if (blurTimeoutRef.current) window.clearTimeout(blurTimeoutRef.current);
          setShowSuggestions(true);
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 12px',
            borderRadius: 10,
            border: '1px solid rgba(148, 163, 184, 0.45)',
            backgroundColor: 'rgba(2, 8, 23, 0.92)',
            boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35)',
          }}
        >
          {isSearching ? (
            <Loader2 size={16} color="#94a3b8" style={{ animation: 'spin 1s linear infinite' }} />
          ) : (
            <Search size={16} color="#94a3b8" />
          )}
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setShowSuggestions(true);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSearchSubmit();
              if (e.key === 'Escape') setShowSuggestions(false);
            }}
            placeholder="Search city, place, or lat, lng"
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              background: 'transparent',
              color: '#f1f5f9',
              fontSize: 14,
            }}
          />
          {searchQuery && (
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={clearSearch}
              aria-label="Clear search"
              style={{
                display: 'flex',
                alignItems: 'center',
                background: 'transparent',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer',
                padding: 2,
              }}
            >
              <X size={15} />
            </button>
          )}
        </div>

        {/* Suggestions dropdown */}
        {showSuggestions && searchQuery.trim() && hasSuggestions && (
          <div
            style={{
              marginTop: 6,
              borderRadius: 10,
              border: '1px solid rgba(148, 163, 184, 0.45)',
              backgroundColor: 'rgba(2, 8, 23, 0.96)',
              boxShadow: '0 6px 18px rgba(0, 0, 0, 0.4)',
              overflow: 'hidden',
            }}
          >
            {parsedCoords && (
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  flyTo(parsedCoords[0], parsedCoords[1], 12);
                  setShowSuggestions(false);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  padding: '10px 12px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
                  color: '#f1f5f9',
                  cursor: 'pointer',
                  fontSize: 13,
                  textAlign: 'left',
                }}
              >
                <Crosshair size={15} color="#38bdf8" />
                Go to {parsedCoords[1].toFixed(4)}, {parsedCoords[0].toFixed(4)}
              </button>
            )}

            {cityMatches.map((city) => (
              <button
                key={`city-${city.name}`}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => selectCity(city)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  padding: '10px 12px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
                  color: '#f1f5f9',
                  cursor: 'pointer',
                  fontSize: 13,
                  textAlign: 'left',
                }}
              >
                <MapPin size={15} color="#f87171" />
                <span>{city.name}</span>
                <span style={{ marginLeft: 'auto', fontSize: 11, color: '#64748b' }}>City</span>
              </button>
            ))}

            {geoResults.map((place, i) => (
              <button
                key={`geo-${i}`}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => selectPlace(place)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  padding: '10px 12px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: i === geoResults.length - 1 ? 'none' : '1px solid rgba(148, 163, 184, 0.2)',
                  color: '#cbd5e1',
                  cursor: 'pointer',
                  fontSize: 13,
                  textAlign: 'left',
                }}
              >
                <Search size={14} color="#94a3b8" style={{ flexShrink: 0 }} />
                <span
                  style={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {place.label}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* --- Left panel: toolbox (objects + Create POI Area) or POI-only --- */}
      <div
        style={{
          position: 'absolute',
          top: 20,
          left: 20,
          zIndex: 30,
          width: 240,
          maxHeight: 'calc(100% - 40px)',
          overflowY: 'auto',
          border: '1px solid rgba(148, 163, 184, 0.45)',
          backgroundColor: 'rgba(2, 8, 23, 0.9)',
          borderRadius: 10,
          padding: '12px 14px',
          color: '#f1f5f9',
          boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35)',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
      >
        {displayToolbox && toolboxObjectsSection}
        {createPOISection}
      </div>

      <button
        type="button"
        onClick={toggleFullscreen}
        style={{
          position: 'absolute',
          top: 20,
          right: 20,
          zIndex: 30,
          border: '1px solid rgba(148, 163, 184, 0.55)',
          backgroundColor: 'rgba(2, 8, 23, 0.88)',
          color: '#f8fafc',
          borderRadius: '8px',
          width: '40px',
          height: '40px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
        }}
        aria-label={isFullscreen ? 'Exit fullscreen heatmap' : 'Enter fullscreen heatmap'}
        title={isFullscreen ? 'Exit fullscreen' : 'View fullscreen'}
      >
        {isFullscreen ? <Shrink size={20} /> : <Expand size={20} />}
      </button>

      {availableMetricLayers.length > 0 && (
        <button
          type="button"
          onClick={() => {
            if (availableMetricLayers.length <= 1) return;
            const idx = availableMetricLayers.findIndex((m) => m.metric === selectedMetric);
            const next = availableMetricLayers[(idx + 1 + availableMetricLayers.length) % availableMetricLayers.length];
            setSelectedMetric(next.metric);
          }}
          style={{
            position: 'absolute',
            top: 68,
            right: 20,
            zIndex: 30,
            border: '1px solid rgba(148, 163, 184, 0.55)',
            backgroundColor: 'rgba(2, 8, 23, 0.88)',
            color: '#f8fafc',
            borderRadius: '8px',
            padding: '8px 10px',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            cursor: availableMetricLayers.length > 1 ? 'pointer' : 'default',
            fontSize: 12,
            fontWeight: 600,
          }}
          title="Toggle metric"
        >
          <Crosshair size={14} />
          <span>{metricLabelText}</span>
        </button>
      )}

      <div
        style={{
          position: 'absolute',
          right: 16,
          bottom: 30,
          zIndex: 25,
          width: 186,
          border: '1px solid rgba(148, 163, 184, 0.3)',
          backgroundColor: 'rgba(2, 8, 23, 0.72)',
          borderRadius: 8,
          padding: '7px 8px',
          color: '#f1f5f9',
          boxShadow: '0 3px 10px rgba(0, 0, 0, 0.22)',
          backdropFilter: 'blur(6px)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 5 }}>
          <div style={{ fontSize: 11, fontWeight: 700 }}>{metricLabelText}</div>
          <div style={{ color: '#94a3b8', fontSize: 9, fontWeight: 700, textTransform: 'uppercase' }}>
            Scale
          </div>
        </div>
        <div
          style={{
            height: 8,
            width: '100%',
            borderRadius: 999,
            background: activeMetricLegendGradient,
            border: '1px solid rgba(148, 163, 184, 0.25)',
          }}
        />
        <div
          style={{
            marginTop: 4,
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 9,
            color: '#94a3b8',
          }}
        >
          <span>0</span>
          <span>100</span>
        </div>
        <div
          style={{
            marginTop: 6,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 8,
            border: '1px solid rgba(148, 163, 184, 0.22)',
            borderRadius: 999,
            background: 'rgba(15, 23, 42, 0.58)',
            padding: '4px 7px',
            fontSize: 10,
            color: '#94a3b8',
          }}
          title={`${heatmapCountScopeLabel}: ${heatmapCellCounts.total.toLocaleString()} total cells | Actual: ${heatmapCellCounts.actual.toLocaleString()} | Interpolated: ${heatmapCellCounts.interpolated.toLocaleString()}`}
        >
          <span style={{ color: '#e0f2fe', fontWeight: 800 }}>
            {heatmapCountScopeLabel}: {heatmapCellCounts.total.toLocaleString()}
          </span>
          <span>{heatmapCellCounts.actual.toLocaleString()} actual</span>
          <span>{heatmapCellCounts.interpolated.toLocaleString()} interp.</span>
        </div>
      </div>

      {tooltip && (
        <div
          style={{
            position: 'absolute',
            left: tooltip.x + 14,
            top: tooltip.y - 14,
            backgroundColor: 'rgba(2, 8, 23, 0.92)',
            border: '1px solid rgba(100, 116, 139, 0.6)',
            borderRadius: '8px',
            padding: '10px 14px',
            pointerEvents: 'none',
            zIndex: 20,
            minWidth: '180px',
            boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
            color: 'white',
            fontSize: '13px',
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 6, fontSize: '14px', color: '#f1f5f9' }}>
            {tooltip.point.location_name}
          </div>
          {tooltip.point.is_interpolated && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                marginBottom: 8,
                border: '1px solid rgba(56, 189, 248, 0.35)',
                borderRadius: 999,
                padding: '2px 7px',
                background: 'rgba(8, 47, 73, 0.55)',
                color: '#bae6fd',
                fontSize: 11,
                fontWeight: 700,
                textTransform: 'uppercase',
              }}
            >
              Interpolated
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: '#cbd5e1' }}>
            <span>{metricLabelText} Score</span>
            <span style={{ fontWeight: 600, color: tooltip.point.value >= 85 ? '#ef4444' : tooltip.point.value >= 70 ? '#f97316' : '#facc15' }}>
              {tooltip.point.value}
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: '#cbd5e1', marginTop: 4 }}>
            <span>Metric</span>
            <span style={{ fontWeight: 600, color: '#94a3b8' }}>{formatMetricName(tooltip.metric)}</span>
          </div>

          {tooltip.point.individual_metrics && (
            <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(148, 163, 184, 0.35)' }}>
              {Object.entries(tooltip.point.individual_metrics).map(([key, value]) => (
                <div
                  key={key}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 16,
                    color: '#cbd5e1',
                    marginTop: 4,
                  }}
                >
                  <span>{metricLabel(key)}</span>
                  <span style={{ fontWeight: 600, color: '#e2e8f0' }}>
                    {value as number}
                    {metricUnit(key)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Heatmap;
