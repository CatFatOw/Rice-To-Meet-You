import React, { useMemo, useCallback, useRef, useEffect, useState } from 'react';
import { Expand, Shrink } from 'lucide-react';
import DeckGL from '@deck.gl/react';
import {
  type CityPOIArea,
  type HeatmapMetricSnapshot,
  type HeatmapMetricValue,
} from '../api/map';
import { type City } from '../data/hostCities';
import { getColor } from '../utils/colors';
import { type PlacedObject, TOOLBOX_DRAG_MIME } from '../utils/toolbox';
import { useHeatmapLayers } from '../hooks/useHeatmapLayers';
import SearchBar from './SearchBar';
import Toolbox from './Toolbox';
import HeatRiskScale from './Heatriskscale';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

// Re-exported so existing imports (`import Heatmap, { type GeocodeResult }`)
// keep working now that the search UI lives in its own component.
export type { GeocodeResult } from './SearchBar';

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
  heatmapPointsByCity: Record<string, HeatmapMetricSnapshot[]>;
  mapContainerRef: React.RefObject<HTMLDivElement | null>;
  mapRef: React.MutableRefObject<maplibregl.Map | null>;
  mapSyncFrameRef: React.MutableRefObject<number | null>;
  // Element to request fullscreen on instead of the Heatmap's own root. Pass
  // the map panel/section so page-level overlays (e.g. the date picker) stay
  // visible in fullscreen. Falls back to the Heatmap root when omitted.
  fullscreenTargetRef?: React.RefObject<HTMLElement | null>;
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
  /**
   * When true, the left panel renders as a full toolbox: a palette of
   * placeable objects (cooling stations, shade canopy, ...) that can be
   * dragged onto the map, followed by the Create POI Area section. When
   * false (default) only the metric toggle and Create POI Area are shown.
   */
  displayToolbox?: boolean;
}

export interface TooltipState {
  point: HeatmapMetricValue;
  metric: string;
  x: number;
  y: number;
}

// GeocodeResult is defined in ./SearchBar and re-exported above; import the
// type here so it can be referenced in HeatmapProps.
import type { GeocodeResult } from './SearchBar';

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
  fullscreenTargetRef,
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
  displayToolbox = false,
}) => {
  const heatmapRootRef = useRef<HTMLDivElement>(null);

  // Objects placed onto the map from the toolbox. Kept local to the component
  // since they're a self-contained overlay; lift into props if you need them
  // shared with the parent (e.g. for persistence).
  const [placedObjects, setPlacedObjects] = useState<PlacedObject[]>([]);

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
  }, [selectedCity, setDraftPoints, setIsDrawing]);

  const cancelDrawing = useCallback(() => {
    setDraftPoints([]);
    setDraftName('');
    setIsDrawing(false);
  }, [setDraftPoints, setDraftName, setIsDrawing]);

  const undoLastPoint = useCallback(() => {
    setDraftPoints((prev) => prev.slice(0, -1));
  }, [setDraftPoints]);

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
    setDraftPoints([]);
    setDraftName('');
    setIsDrawing(false);
  }, [
    selectedCity,
    draftPoints,
    draftColorHex,
    draftName,
    userPOIAreas.length,
    setUserPOIAreas,
    setDraftPoints,
    setDraftName,
    setIsDrawing,
  ]);

  const clearMyAreas = useCallback(() => {
    setUserPOIAreas((prev) => prev.filter((a) => a.cityName !== selectedCity));
  }, [selectedCity, setUserPOIAreas]);

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

  const availableMetricLayers: HeatmapMetricSnapshot[] = useMemo(
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

  // Cycle to the next available metric (drives the Toolbox metric toggle).
  const cycleMetric = useCallback(() => {
    if (availableMetricLayers.length <= 1) return;
    const idx = availableMetricLayers.findIndex((m) => m.metric === selectedMetric);
    const next =
      availableMetricLayers[(idx + 1 + availableMetricLayers.length) % availableMetricLayers.length];
    setSelectedMetric(next.metric);
  }, [availableMetricLayers, selectedMetric, setSelectedMetric]);

  const displayedPOIAreas: CityPOIArea[] = useMemo(() => {
    if (!selectedCity) return [];
    return [
      ...cityPOIAreas.filter((poi) => poi.cityName === selectedCity),
      ...userPOIAreas.filter((poi) => poi.cityName === selectedCity),
    ];
  }, [selectedCity, cityPOIAreas, userPOIAreas]);

  const draftRgb = useMemo(() => hexToRgb(draftColorHex), [draftColorHex]);

  // All deck.gl layers (city markers, heatmap surface, POI areas, placed
  // objects, and the in-progress draft) are built in this hook.
  const layers = useHeatmapLayers({
    isDrawing,
    selectedCity,
    displayedHeatmapPoints,
    activeMetricColorRange,
    activeMetricKey,
    displayedPOIAreas,
    userPOIAreas,
    editingAreaId,
    placedObjects,
    draftPoints,
    draftRgb,
    onCityClick: handleCityClick,
    onRemovePlacedObject: removePlacedObject,
    setTooltip,
    setHoveringHeatmap,
    setEditingAreaId,
    setIsDrawing,
    setIsAreaDragging,
    setUserPOIAreas,
    setDraftPoints,
  });

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
      const target = fullscreenTargetRef?.current ?? heatmapRootRef.current;
      setIsFullscreen(document.fullscreenElement === target);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [setIsFullscreen, fullscreenTargetRef]);

  const toggleFullscreen = useCallback(async () => {
    const target = fullscreenTargetRef?.current ?? heatmapRootRef.current;
    if (!target) return;

    try {
      if (document.fullscreenElement === target) {
        await document.exitFullscreen();
      } else {
        await target.requestFullscreen();
      }
    } catch (error) {
      console.error('Failed to toggle fullscreen heatmap', error);
    }
  }, [fullscreenTargetRef]);

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

      <SearchBar
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        geoResults={geoResults}
        setGeoResults={setGeoResults}
        isSearching={isSearching}
        setIsSearching={setIsSearching}
        showSuggestions={showSuggestions}
        setShowSuggestions={setShowSuggestions}
        flyTo={flyTo}
      />

      <Toolbox
        displayToolbox={displayToolbox}
        metricLabel={metricLabelText}
        canToggleMetric={availableMetricLayers.length > 1}
        onToggleMetric={cycleMetric}
        placedCount={placedObjects.length}
        onClearObjects={clearPlacedObjects}
        selectedCity={selectedCity}
        draftName={draftName}
        setDraftName={setDraftName}
        draftColorHex={draftColorHex}
        setDraftColorHex={setDraftColorHex}
        isDrawing={isDrawing}
        draftPointCount={draftPoints.length}
        onStartDrawing={startDrawing}
        onFinishArea={finishArea}
        onUndoLastPoint={undoLastPoint}
        onCancelDrawing={cancelDrawing}
        hasUserAreasInCity={userPOIAreas.some((a) => a.cityName === selectedCity)}
        onClearMyAreas={clearMyAreas}
        editingAreaId={editingAreaId}
        onFinishEdit={() => {
          setEditingAreaId(null);
          setIsAreaDragging(false);
        }}
      />

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

      <HeatRiskScale label={metricLabelText} gradient={activeMetricLegendGradient} />

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
            <span
              style={{
                fontWeight: 600,
                color:
                  tooltip.point.value >= 85
                    ? '#ef4444'
                    : tooltip.point.value >= 70
                      ? '#f97316'
                      : '#facc15',
              }}
            >
              {tooltip.point.value}
            </span>
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 16,
              color: '#cbd5e1',
              marginTop: 4,
            }}
          >
            <span>Metric</span>
            <span style={{ fontWeight: 600, color: '#94a3b8' }}>
              {formatMetricName(tooltip.metric)}
            </span>
          </div>

          {tooltip.point.individual_metrics && (
            <div
              style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(148, 163, 184, 0.35)' }}
            >
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