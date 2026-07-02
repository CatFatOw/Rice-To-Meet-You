import React, { useMemo, useCallback, useRef, useEffect } from 'react';
import { Expand, Shrink, Pencil, Check, Undo2, X, Trash2, Search, MapPin, Crosshair, Loader2 } from 'lucide-react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, PolygonLayer, PathLayer, TextLayer, IconLayer } from '@deck.gl/layers';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import {
  type CityPOIArea,
  type HeatmapMetricPoint,
  type HeatmapMetricValue,
  type HeatmapMetricsPointResponse,
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

// Colored soccer-ball SVG for city markers. Rendered via IconLayer (not
// TextLayer) so it keeps its colors — TextLayer's grayscale glyph atlas turns
// color emoji into a flat white ball.
const FOOTBALL_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <circle cx="24" cy="24" r="22" fill="#ffffff" stroke="#0f172a" stroke-width="2.5"/>
  <line x1="24" y1="16" x2="24" y2="2" stroke="#0f172a" stroke-width="2"/>
  <line x1="31.6" y1="21.5" x2="44.9" y2="17.2" stroke="#0f172a" stroke-width="2"/>
  <line x1="28.7" y1="30.5" x2="36.9" y2="41.8" stroke="#0f172a" stroke-width="2"/>
  <line x1="19.3" y1="30.5" x2="11.1" y2="41.8" stroke="#0f172a" stroke-width="2"/>
  <line x1="16.4" y1="21.5" x2="3.1" y2="17.2" stroke="#0f172a" stroke-width="2"/>
  <polygon points="24,16 31.6,21.5 28.7,30.5 19.3,30.5 16.4,21.5" fill="#0f172a"/>
</svg>`;

const FOOTBALL_ICON = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(FOOTBALL_SVG)}`;

function colorMetricKey(metric: string): string {
  if (metric === 'heat_risk_score') return 'temperature';
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

const Heatmap: React.FC<HeatmapProps> = ({
  viewState,
  setViewState,
  selectedCity,
  setSelectedCity,
  cityPOIAreas,
  heatmapPointsByCity,
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
}) => {
  const heatmapRootRef = useRef<HTMLDivElement>(null);
  const blurTimeoutRef = useRef<number | null>(null);

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
      cityName: selectedCity,
      name: draftName.trim() || `Custom Area ${userPOIAreas.length + 1}`,
      polygon: draftPoints,
      color: [...rgb, 140],
    } as CityPOIArea;

    setUserPOIAreas((prev) => [...prev, newArea]);
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
      if (!isDrawing || !info?.coordinate) return;
      const [lng, lat] = info.coordinate;
      setDraftPoints((prev) => [...prev, [lng, lat]]);
    },
    [isDrawing],
  );

  // Football icon marking each city (replaces the old red dots). Uses an
  // IconLayer with a colored SVG so it renders in full color.
  const cityIconLayer = useMemo(
    () =>
      new IconLayer({
        id: 'city-icon-layer',
        data: cities,
        pickable: !isDrawing,
        getPosition: (d: City) => [d.longitude, d.latitude],
        getIcon: () => ({
          url: FOOTBALL_ICON,
          width: 48,
          height: 48,
          anchorX: 24,
          anchorY: 24,
          id: 'football',
        }),
        getSize: 30,
        sizeUnits: 'pixels',
        getPixelOffset: [0, -14],
        onClick: (info: any) => {
          if (info.object) {
            handleCityClick(info.object as City);
          }
        },
      }),
    [handleCityClick, isDrawing],
  );

  // City name label under each football icon.
  const cityLabelLayer = useMemo(
    () =>
      new TextLayer({
        id: 'city-label-layer',
        data: cities,
        pickable: !isDrawing,
        characterSet: 'auto',
        fontFamily: '"Inter", system-ui, sans-serif',
        fontWeight: 700,
        getPosition: (d: City) => [d.longitude, d.latitude],
        getText: (d: City) => d.name,
        getSize: 14,
        sizeUnits: 'pixels',
        getPixelOffset: [0, 6],
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'top',
        getColor: (d: City) =>
          selectedCity === d.name ? [56, 189, 248, 255] : [248, 250, 252, 255],
        background: true,
        getBackgroundColor: [2, 8, 23, 200],
        backgroundPadding: [6, 3, 6, 3],
        fontSettings: { sdf: true },
        outlineWidth: 2,
        outlineColor: [2, 8, 23, 255],
        updateTriggers: {
          getColor: [selectedCity],
        },
        onClick: (info: any) => {
          if (info.object) {
            handleCityClick(info.object as City);
          }
        },
      }),
    [handleCityClick, isDrawing, selectedCity],
  );

  const availableMetricLayers: HeatmapMetricPoint[] = useMemo(
    () => (selectedCity ? (heatmapPointsByCity[selectedCity] ?? []) : []),
    [selectedCity, heatmapPointsByCity],
  );

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
  const metricLabelText = formatMetricName(activeMetricKey);
  const activeMetricColorRange = useMemo(
    () => metricColorRange(activeMetricKey),
    [activeMetricKey],
  );
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
        data: displayedHeatmapPoints,
        pickable: false,
        getPosition: (d: HeatmapMetricValue) => d.location_coordinates,
        getWeight: (d: HeatmapMetricValue) => d.value,
        aggregation: 'SUM',
        radiusPixels: 60,
        intensity: 1.2,
        threshold: 0.03,
        weightsTextureSize: 1024,
        colorRange: activeMetricColorRange as any,
      }),
    [displayedHeatmapPoints, activeMetricColorRange],
  );

  const heatmapPickLayer = useMemo(
    () =>
      new ScatterplotLayer({
        id: 'heatmap-pick-layer',
        data: displayedHeatmapPoints,
        pickable: !isDrawing,
        opacity: 0,
        radiusMinPixels: 14,
        radiusMaxPixels: 14,
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
      }),
    [displayedHeatmapPoints, isDrawing, setHoveringHeatmap, setTooltip, activeMetricKey],
  );

  const poiAreaLayer = useMemo(
    () =>
      new PolygonLayer({
        id: 'poi-area-layer',
        data: displayedPOIAreas,
        pickable: !isDrawing,
        stroked: true,
        filled: true,
        opacity: 0.55,
        getPolygon: (d: CityPOIArea) => d.polygon,
        getFillColor: (d: CityPOIArea) => d.color,
        getLineColor: [255, 255, 255, 255],
        getLineWidth: 2,
        lineWidthUnits: 'pixels',
      }),
    [displayedPOIAreas, isDrawing],
  );

  // --- Draft (in-progress) drawing layers ---
  const draftRgb = useMemo(() => hexToRgb(draftColorHex), [draftColorHex]);

  const draftPolygonLayer = useMemo(
    () =>
      new PolygonLayer({
        id: 'draft-polygon-layer',
        data: draftPoints.length >= 3 ? [{ polygon: draftPoints }] : [],
        pickable: false,
        stroked: true,
        filled: true,
        opacity: 0.5,
        getPolygon: (d: { polygon: [number, number][] }) => d.polygon,
        getFillColor: [...draftRgb, 120],
        getLineColor: [...draftRgb, 255],
        getLineWidth: 2,
        lineWidthUnits: 'pixels',
      }),
    [draftPoints, draftRgb],
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
      cityIconLayer,
      cityLabelLayer,
    ],
  );

  // Crosshair while drawing or hovering the heatmap; grab/grabbing otherwise
  // so normal map panning still reads correctly.
  const getCursor = useCallback(
    ({ isDragging }: { isDragging: boolean }) =>
      isDragging ? 'grabbing' : isDrawing || hoveringHeatmap ? 'crosshair' : 'grab',
    [isDrawing, hoveringHeatmap],
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

  return (
    <div ref={heatmapRootRef} style={{ width: '100%', height: '100%', minHeight: '480px', position: 'relative' }}>
      <div
        ref={mapContainerRef}
        style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}
      />
      <DeckGL
        viewState={viewState}
        onViewStateChange={handleViewStateChange}
        onClick={handleDeckClick}
        controller={true}
        layers={layers}
        getCursor={getCursor}
        style={{ position: 'absolute', width: '100%', height: '100%' }}
      />

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

      {/* --- POI area drawing toolbar (left) --- */}
      <div
        style={{
          position: 'absolute',
          top: 20,
          left: 20,
          zIndex: 30,
          width: 240,
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
          right: 20,
          bottom: 20,
          zIndex: 25,
          width: 240,
          border: '1px solid rgba(148, 163, 184, 0.45)',
          backgroundColor: 'rgba(2, 8, 23, 0.88)',
          borderRadius: 10,
          padding: '10px 12px',
          color: '#f1f5f9',
          boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35)',
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8 }}>{metricLabelText} Scale</div>
        <div
          style={{
            height: 12,
            width: '100%',
            borderRadius: 999,
            background: activeMetricLegendGradient,
            border: '1px solid rgba(148, 163, 184, 0.35)',
          }}
        />
        <div
          style={{
            marginTop: 6,
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 11,
            color: '#cbd5e1',
          }}
        >
          <span>0</span>
          <span>25</span>
          <span>50</span>
          <span>75</span>
          <span>100</span>
        </div>
        <div
          style={{
            marginTop: 6,
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 11,
            color: '#94a3b8',
          }}
        >
          <span>Low</span>
          <span>High</span>
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