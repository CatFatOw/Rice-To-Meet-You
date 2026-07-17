import React, { useMemo, useCallback, useRef, useEffect } from 'react';
import { Expand, Shrink } from 'lucide-react';
import DeckGL from '@deck.gl/react';
import {
  type CityPOIArea,
  type HeatmapMetricSnapshot,
  type HeatmapMetricValue,
} from '../api/map';
import { type City } from '../data/hostCities';
import { getColor } from '../services/colors';
import { useHeatmapLayers } from '../hooks/useHeatmapLayers';
import { sampleHeatmapMetricByCity } from '../services/interpolate';
import SearchBar from './SearchBar';
import Toolbox from './Toolbox';
import HeatRiskScale from './Heatriskscale';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { SurfaceType } from '../services/map';
import { classifySurface } from '../services/map';
import type { GeocodeResult } from '../types/search';
import type { HeatmapProps, TooltipState } from '../types/components';
import type { ViewState } from '../types/viewState';
import { fetchPlacedObjects } from '../api/tool';
import type { Geometry } from '../types/simulation';
import { isPointInPolygon } from '../services/toolbox';
import { isPolygonSimple } from '../services/polygon';



// Re-exported so existing imports (`import Heatmap, { type GeocodeResult }`)
// keep working now that the search UI lives in its own component.
export type { GeocodeResult, TooltipState };

// ======================================================
// Formatting helpers
// Pure functions: raw metric keys -> human-readable text.
// ======================================================

/**
 * Short display name for a raw sub-metric key, used in the tooltip's
 * `individual_metrics` breakdown (e.g. 'heatIndexF' -> 'Heat Index').
 * Unknown keys fall through unchanged so new metrics still render.
 */
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

/**
 * Unit suffix inferred from the metric key's naming convention:
 * a trailing 'F' means Fahrenheit, a trailing 'Pct' means percent.
 * Returns an empty string for unitless metrics.
 */
function metricUnit(metricKey: string): string {
  if (metricKey.endsWith('F')) return ' deg F';
  if (metricKey.endsWith('Pct')) return '%';
  return '';
}

// Convert a #rrggbb hex string to an [r, g, b] tuple for deck.gl color props.
// Malformed components degrade to 0 rather than NaN, which deck.gl would
// otherwise render as a transparent/black fill.
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

// ======================================================
// Colour helpers
// Map a metric onto the shared palette in utils/colors.
// ======================================================

/**
 * Maps a metric to the palette name `getColor` understands.
 * 'heat_risk_score' has no palette of its own and reuses the temperature ramp.
 */
function colorMetricKey(metric: string): string {
  if (metric === 'heat_risk_score') return 'temperature';
  return metric;
}

/** Format an [r, g, b] tuple plus an alpha as a CSS rgba() string. */
function rgbaCss(rgb: [number, number, number], alpha: number): string {
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
}

/**
 * Build the six-stop RGBA colour ramp deck.gl's heatmap layer expects.
 * The first stop is fully transparent (alpha 0) so low-intensity areas fade
 * into the basemap instead of tinting the whole city.
 */
function metricColorRange(metric: string): [number, number, number, number][] {
  const colorMetric = colorMetricKey(metric);
  const stops = [0, 20, 40, 60, 80, 100];

  return stops.map((value, index) => {
    const [r, g, b] = getColor(value, colorMetric);
    const alpha = index === 0 ? 0 : 230;
    return [r, g, b, alpha];
  });
}

/**
 * CSS linear-gradient for the HeatRiskScale legend, using the same stops as
 * `metricColorRange` so the legend always matches the rendered heatmap.
 * Alpha is near-opaque here (unlike the layer ramp) so the legend stays legible.
 */
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

/**
 * Title-cased display name for a top-level metric key, used in the legend,
 * the Toolbox toggle and the tooltip header. Two keys are special-cased;
 * anything else is snake_case -> Title Case.
 */
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
  heatmapAnchorsByCity,
  availableDates,
  selectedDate,
  setSelectedDate,
  mapContainerRef,
  mapRef,
  mapSyncFrameRef,
  fullscreenTargetRef,
  tooltip,
  setTooltip,
  isFullscreen,
  setIsFullscreen,
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
  placedObjectsControls,
  displayToolbox = false,
  drawControls,
}) => {
  // Fallback fullscreen target when the parent doesn't supply one: the root
  // element of this component.
  const heatmapRootRef = useRef<HTMLDivElement>(null);

  // Drawing state lives in the usePolygonDraw hook; aliased here for brevity.
  const isDrawing = drawControls.isDrawing;
  const draftPoints = drawControls.draftPoints;

  // placedObjectsControls is optional (ExplorePage renders without a toolbox),
  // so default to an empty list rather than guarding at every use site.
const currentPlacedObjects = placedObjectsControls?.placedObjects ?? [];
const pendingPlacedObjects = useMemo(
  () =>
    placedObjectsControls?.pendingPlacedObject
      ? [placedObjectsControls.pendingPlacedObject]
      : [],
  [placedObjectsControls?.pendingPlacedObject],
);

// Polygon things the hover test should check: committed + pending placed
// objects whose geometry is a polygon, plus the user-drawn POI areas. Each
// entry is normalized to a { ring } with a tagged source so the tooltip can
// render the right details. Server POI areas (cityPOIAreas) are NOT included.
const hoverablePolygons = useMemo(() => {
  const placed = [...currentPlacedObjects, ...pendingPlacedObjects]
    .filter((o) => o.geometry.kind === 'polygon')
    .map((o) => ({
      source: 'placed' as const,
      ring: o.geometry.kind === 'polygon' ? o.geometry.ring : [],
      object: o,
    }));

  const poi = userPOIAreas.map((area) => ({
    source: 'poi' as const,
    ring: area.polygon,
    area,
  }));

  return [...placed, ...poi];
}, [currentPlacedObjects, pendingPlacedObjects, userPOIAreas]);

  // ======================================================
  // Placed-object handlers
  // ======================================================

  /** Remove a single placed intervention by id (wired to the layer's X icon). */
  const removePlacedObject = useCallback((id: string) => {
    if (placedObjectsControls?.setPlacedObjects) {
      placedObjectsControls.setPlacedObjects((prev) => prev.filter((o) => o.id !== id));
    }
  }, [placedObjectsControls]);

  // ======================================================
  // Map interaction handlers
  // ======================================================

  /**
   * Deck click. Only meaningful in draw mode, where each click appends a
   * vertex to the in-progress polygon. Ignored otherwise so normal map
   * clicks (e.g. city markers) are handled by their own layers.
   */
  const handleDeckClick = useCallback(
    (info: any) => {
      // Add vertices while drawing
      if (!isDrawing || !info?.coordinate) return;
      const [lng, lat] = info.coordinate;
      drawControls.addDraftPoint(lng, lat);
    },
    [isDrawing, drawControls],
  );

  // Fly the map + shared view state to a location. Pass cityName to also mark a
  // city as selected (so its heatmap points load); omit for generic places.
  // Both the deck.gl view state and the underlying MapLibre instance are moved
  // so the basemap and the overlays stay in sync.
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

  /**
   * Click on a city marker: zoom to city level and select it, which triggers
   * the parent to load that city's heatmap points.
   */
  const handleCityClick = useCallback(
    (city: City) => {
      // While drawing, map clicks add vertices instead of switching cities.
      if (isDrawing) return;

      setViewState({
        longitude: city.longitude,
        latitude: city.latitude,
        zoom: 10,
        pitch: 0,
        bearing: 0,
      });
      setSelectedCity(city.name);

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

  // ======================================================
  // Metric selection and derived display data
  // ======================================================

  /** Metric layers available for the selected city on the selected date. */
  const availableMetricLayers: HeatmapMetricSnapshot[] = useMemo(
    () => (selectedCity ? (heatmapPointsByCity[selectedCity] ?? []) : []),
    [selectedCity, heatmapPointsByCity],
  );

  // Keep selectedMetric valid as the available layers change (city switch, date
  // change, simulation run): preserve the current metric if it still exists,
  // otherwise fall back to the first layer, or null when there's no data.
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

  /** The metric layer actually being rendered; falls back to the first layer. */
  const activeMetricLayer = useMemo(
    () =>
      availableMetricLayers.find((m) => m.metric === selectedMetric) ??
      availableMetricLayers[0],
    [availableMetricLayers, selectedMetric],
  );

  /** Point set fed to the deck.gl heatmap layer. */
  const displayedHeatmapPoints: HeatmapMetricValue[] = useMemo(
    () => activeMetricLayer?.points ?? [],
    [activeMetricLayer],
  );

  // Presentation derived from the active metric: key, display name, layer
  // colour ramp and matching legend gradient.
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

  // Load mock placed-object tools for the selected city + date and push them
  // into placedObjectsControls. Re-runs on city/date change; clears when either
  // is missing. The ignore flag drops a stale response if the selection changes
  // mid-fetch.
  useEffect(() => {
    if (!placedObjectsControls?.setPlacedObjects) return;

    if (!selectedCity || !selectedDate) {
      placedObjectsControls.setPlacedObjects([]);
      return;
    }

    let ignore = false;

    fetchPlacedObjects()
      .then((byDateCity) => {
        if (ignore) return;
        const tools = byDateCity[selectedDate]?.[selectedCity] ?? [];
        placedObjectsControls.setPlacedObjects(tools);
      })
      .catch((error) => {
        if (ignore) return;
        console.error('Failed to load placed objects', error);
        placedObjectsControls.setPlacedObjects([]);
      });

    return () => {
      ignore = true;
    };
  }, [selectedCity, selectedDate, placedObjectsControls]);


  // Mirror the in-progress polygon draft into a pending placed object so it
  // renders through the same placed-object path and can be named/colored before
  // commit. While drawing, keep pending metadata alive even with <3 points so
  // selecting a polygon tool doesn't get immediately wiped on draw start.
  useEffect(() => {
    const setPending = placedObjectsControls?.setPendingPlacedObject;
    if (!setPending) return;

    setPending((prev) => {
      if (!isDrawing) {
        // Only clear polygon drafts when drawing ends; keep non-polygon pending
        // objects (e.g. dragged point tools) untouched.
        return prev?.geometry?.kind === 'polygon' ? null : prev;
      }

      return {
        type: prev?.type ?? 'polygon',
        name: prev?.name ?? 'polygon',
        color: prev?.color,
        params: prev?.params,
        activeFrom: prev?.activeFrom,
        activeTo: prev?.activeTo,
        geometry: { kind: 'polygon', ring: draftPoints } as Geometry,
      };
    });
  }, [draftPoints, isDrawing, placedObjectsControls?.setPendingPlacedObject]);

  // Cycle to the next available metric (drives the Toolbox metric toggle).
  // Wraps around at the end of the list; no-op when there's nothing to cycle to.
  const cycleMetric = useCallback(() => {
    if (availableMetricLayers.length <= 1) return;
    const idx = availableMetricLayers.findIndex((m) => m.metric === selectedMetric);
    const next =
      availableMetricLayers[(idx + 1 + availableMetricLayers.length) % availableMetricLayers.length];
    setSelectedMetric(next.metric);
  }, [availableMetricLayers, selectedMetric, setSelectedMetric]);

  /** Server-provided POI areas for the city, plus any the user drew themselves. */
  const displayedPOIAreas: CityPOIArea[] = useMemo(() => {
    if (!selectedCity) return [];
    return [...(cityPOIAreas[selectedCity] ?? []), ...userPOIAreas];
  }, [selectedCity, cityPOIAreas, userPOIAreas]);

  /** Draft polygon colour as an RGB tuple for the deck.gl draft layer. */
  const draftRgb = useMemo(() => hexToRgb(drawControls.draftColor), [drawControls.draftColor]);

  // All deck.gl layers (city markers, heatmap surface, POI areas, placed
  // objects, and the in-progress draft) are built in this hook.

  const draftIsSimple = useMemo(() => isPolygonSimple(draftPoints), [draftPoints]);

  
 
  const layers = useHeatmapLayers({
    isDrawing,
    selectedCity,
    displayedHeatmapPoints,
    activeMetricColorRange,
    displayedPOIAreas,
    userPOIAreas,
    editingAreaId,
    placedObjects: currentPlacedObjects,
    pendingPlacedObjects,
    draftPoints,
    draftRgb,
    onCityClick: handleCityClick,
    onRemovePlacedObject: removePlacedObject,
    setEditingAreaId,
    setIsDrawing: drawControls.cancelDrawing,
    setIsAreaDragging,
    setUserPOIAreas,
    setDraftPoints: drawControls.setDraftPoints,
  });

  // ======================================================
  // Hover, cursor and fullscreen
  // ======================================================

  /**
   * Hover on the heatmap: sample the metric at the cursor from the *anchor*
   * data (not the rendered points, which are interpolated and coarser),
   * classify the basemap surface under the pointer, and publish a tooltip.
   * Clears the tooltip while drawing or when there's nothing under the cursor.
   */
  const handleDeckHover = useCallback(
    (info: { coordinate?: number[]; x: number; y: number }) => {
      if (
        isDrawing ||
        !selectedCity ||
        !selectedDate ||
        displayedHeatmapPoints.length === 0 ||
        !info.coordinate ||
        info.coordinate.length < 2
      ) {
        setHoveringHeatmap(false);
        setTooltip(null);
        return;
      }

      const [longitude, latitude] = info.coordinate;
      const sampledPoint = sampleHeatmapMetricByCity(
        heatmapAnchorsByCity,
        selectedCity,
        selectedDate,
        activeMetricKey,
        longitude,
        latitude,
      );

      // Cursor is inside the city view but outside the sampled grid.
      if (!sampledPoint) {
        setHoveringHeatmap(false);
        setTooltip(null);
        return;
      }

      // Prefer polygon context over raw coordinate label when the hovered
      // point is inside a user/placed polygon.
      const hoveredPolygon = hoverablePolygons.find(({ ring }) =>
        isPointInPolygon(ring, longitude, latitude),
      );

      const prioritizedPoint = hoveredPolygon
        ? {
            ...sampledPoint,
            location_name:
              hoveredPolygon.source === 'placed'
                ? (hoveredPolygon.object.name?.trim() || hoveredPolygon.object.type)
                : hoveredPolygon.area.name,
          }
        : sampledPoint;

      setHoveringHeatmap(true);
      // Surface classification needs the MapLibre instance to query rendered
      // basemap features at the pixel; degrade to 'unknown' if it isn't ready.
      const surface = mapRef.current
        ? classifySurface(mapRef.current, info.x, info.y)
        : { type: 'unknown' as SurfaceType };

      setTooltip({
        point: prioritizedPoint,
        metric: activeMetricKey,
        x: info.x,
        y: info.y,
        coordinates: { longitude, latitude },
        surface,
      });
    },
    [
      activeMetricKey,
      displayedHeatmapPoints.length,
      heatmapAnchorsByCity,
      isDrawing,
      mapRef,
      hoverablePolygons,
      selectedCity,
      selectedDate,
      setHoveringHeatmap,
      setTooltip,
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

  // Mirror the browser's fullscreen state into React. Needed because the user
  // can leave fullscreen via Esc or the browser chrome, which never goes
  // through toggleFullscreen below.
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

  /**
   * Enter/exit fullscreen on the parent-supplied target (so the page can
   * fullscreen the map *and* the stats panel together), falling back to this
   * component's root. Note isFullscreen is not set here — the
   * 'fullscreenchange' listener above is the single source of truth.
   */
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

  /**
   * Keep the MapLibre basemap locked to deck.gl's camera as the user pans/zooms.
   *
   * Two guards matter here:
   *  - The epsilon comparison returns the previous state object when the camera
   *    hasn't meaningfully moved, so React can bail out of a re-render.
   *  - The basemap sync is throttled to one rAF frame (cancelling any pending
   *    one) because deck.gl fires this far more often than the browser paints.
   * jumpTo (not flyTo) is used so the basemap tracks the drag with no easing lag.
   */
  const handleViewStateChange = useCallback(
    (e: any) => {
      const nextState = e.viewState as ViewState;
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

  // ======================================================
  // UI Component
  // Layered bottom-to-top: MapLibre basemap -> deck.gl overlays ->
  // SearchBar / Toolbox / fullscreen button / legend -> tooltip.
  // ======================================================

  return (
    <div
      ref={heatmapRootRef}
      style={{ width: '100%', height: '100%', minHeight: '480px', position: 'relative' }}
      onDragOver={(e) => placedObjectsControls?.handleObjectDragOver?.(e)}
      onDrop={(e) => placedObjectsControls?.handleObjectDrop?.(e)}
    >
      {/* MapLibre basemap. Positioned absolutely beneath the deck.gl canvas and
          kept in sync by handleViewStateChange. */}
      <div
        ref={mapContainerRef}
        style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}
      />

      {/* deck.gl overlay canvas. dragPan is disabled while an area is being
          dragged so the map doesn't pan out from under the vertex handle. */}
      <DeckGL
        viewState={viewState}
        onViewStateChange={handleViewStateChange}
        onClick={handleDeckClick}
        onHover={handleDeckHover}
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
        selectedDate={selectedDate}
        setSelectedDate={setSelectedDate}
        availableDates={availableDates}
        metricLabel={metricLabelText}
        canToggleMetric={availableMetricLayers.length > 1}
        onToggleMetric={cycleMetric}
        placedCount={currentPlacedObjects.length}
        onClearObjects={() => placedObjectsControls?.setPlacedObjects([])}
        placedObjectsControls={placedObjectsControls}
        onSelectPolygonTool={() => {}}
        selectedCity={selectedCity}
        draftName={draftName}
        setDraftName={setDraftName}
        draftColorHex={draftColorHex}
        setDraftColorHex={setDraftColorHex}
        isDrawing={isDrawing}
        draftPointCount={draftPoints.length}
        onStartDrawing={() => drawControls.startDrawing()}
        onCommitDrawing={() => drawControls.commitDrawing()}
        draftPoints={draftPoints}
        draftIsSimple={draftIsSimple}
        // Commit the draft polygon into a saved user POI area. commitDrawing()
        // returns null when the ring is invalid (fewer than the minimum
        // vertices), in which case the draft is left untouched. Name defaults
        // to a numbered "Custom Area" when the input is blank; the stored
        // colour is the draft RGB plus a fixed 140 alpha for the fill.
        onSetDraftColor={(color) => drawControls.setDraftColor(color)}
        onFinishArea={() => {
          const ring = drawControls.commitDrawing();
          if (ring && selectedCity) {
            setUserPOIAreas((prev) => [
              ...prev,
              {
                id: `custom-${Date.now()}-${prev.length + 1}`,
                name: draftName.trim() || `Custom Area ${prev.length + 1}`,
                polygon: ring,
                color: [...hexToRgb(drawControls.draftColor), 140],
              } as CityPOIArea,
            ]);
            setDraftName('');
          }
        }}
        onUndoLastPoint={() => drawControls.undoDraftPoint()}
        onCancelDrawing={() => drawControls.cancelDrawing()}
        hasUserAreasInCity={userPOIAreas.length > 0}
        onClearMyAreas={() => setUserPOIAreas([])}
        editingAreaId={editingAreaId}
        // Leave edit mode and drop any in-flight vertex drag.
        onFinishEdit={() => {
          setEditingAreaId(null);
          setIsAreaDragging(false);
        }}
      />

      {/* Fullscreen toggle, floating top-right over the map. */}
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

      {/* Legend. Shares its gradient with the active layer's colour ramp. */}
      <HeatRiskScale label={metricLabelText} gradient={activeMetricLegendGradient} />

      {/* Hover tooltip, positioned in screen space from the deck.gl pixel
          coordinates. pointerEvents: none so it never swallows map hovers. */}
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

          {/* Primary metric value, colour-coded by severity band:
              >= 85 red, >= 70 orange, otherwise yellow. */}
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
            <span>Coordinates</span>
            <span style={{ fontWeight: 600, color: '#e2e8f0' }}>
              {tooltip.coordinates.latitude.toFixed(6)}, {tooltip.coordinates.longitude.toFixed(6)}
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

          {/* Basemap surface under the cursor (e.g. park, building, road),
              with the classifier's extra detail in parentheses when present. */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 16,
              color: '#cbd5e1',
              marginTop: 4,
            }}
          >
            <span>Surface</span>
            <span style={{ fontWeight: 600, color: '#94a3b8' }}>
              {tooltip.surface?.detail
                ? `${tooltip.surface.type} (${tooltip.surface.detail})`
                : (tooltip.surface?.type ?? 'unknown')}
            </span>
          </div>

          {/* Optional breakdown of the sub-metrics behind the headline score. */}
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
                    {value}
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