import React, { useMemo, useCallback, useRef, useEffect, useState } from 'react';
import { Expand, Shrink } from 'lucide-react';
import DeckGL from '@deck.gl/react';
import { type CityPOIArea } from '../api/map';
import { type City } from '../data/hostCities';
import { getColor, getSmoothColor, hasSmoothRamp } from '../services/colors';
import {
  buildCityMetricRaster,
  isInsideRaster,
  metricScore,
  sampleMetricGrid,
} from '../services/metricRaster';
import { useHeatmapLayers } from '../hooks/useHeatmapLayers';
import SearchBar from './SearchBar';
import Toolbox from './Toolbox';
import HeatRiskScale from './Heatriskscale';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { SurfaceType } from '../services/map';
import { classifySurface } from '../services/map';
import type { GeocodeResult } from '../types/search';
import type {
  CityMetricRasterEntry,
  HeatmapProps,
  TooltipState,
} from '../types/components';
import type { CityMetricGrid, HeatmapMetricValue as MetricValue } from '../types/heatmap';
import type { ViewState } from '../types/viewState';
import { fetchPlacedObjects } from '../api/tool';
import type { Geometry } from '../types/simulation';
import { isPolygonSimple } from '../services/polygon';
import { availableMetrics, availableDates } from '../api/map';




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

/**
 * Colour lookup for the legend. Metrics that come from the interpolated grid
 * (heat_risk, crowd_density, ...) have their own continuous ramp, so the
 * legend samples the *same* function the raster renderer uses and therefore
 * always matches what is drawn. Everything else keeps the banded getColor.
 */
function legendColor(value: number, metric: string): [number, number, number] {
  return hasSmoothRamp(metric) ? getSmoothColor(value, metric) : getColor(value, metric);
}

/** Format an [r, g, b] tuple plus an alpha as a CSS rgba() string. */
function rgbaCss(rgb: [number, number, number], alpha: number): string {
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
}


/**
 * Stops (in each metric's own units) used to sample getColor for both the
 * heatmap colour range and the legend gradient. Temperature is in °C and
 * spans ~10–44; visitor density is a 0–100 index.
 */
function metricStops(colorMetric: string): number[] {
  // Grid metrics are normalized to a 0-100 score, so a uniform ramp is right.
  if (hasSmoothRamp(colorMetric) && colorMetric !== 'temperature') {
    return [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
  }
  if (colorMetric === 'temperature') {
    return [12, 16, 20, 23, 25, 27, 29, 31, 33, 35, 37, 39, 44];
  }
  if (colorMetric === 'change_in_temperature') {
    return [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5];
  }
  return [0, 20, 40, 60, 80, 100];
}

/**
 * CSS linear-gradient for the HeatRiskScale legend, using the same stops as
 * `metricColorRange` so the legend always matches the rendered heatmap.
 * Alpha is near-opaque here (unlike the layer ramp) so the legend stays legible.
 */
function metricLegendGradient(metric: string): string {
  const colorMetric = colorMetricKey(metric);
  const stops = metricStops(colorMetric);
  const pctStep = 100 / (stops.length - 1);

  const segments = stops.map((value, index) => {
    const color = legendColor(value, colorMetric);
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
  if (metricKey === 'heat_risk_score' || metricKey === 'heat_risk') return 'Heat Risk';
  if (metricKey === 'visitor_activity' || metricKey === 'crowd_density') return 'Visitor Activity';
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
  displayedHeatmapPoints,
  metricGridsByCity,
  selectedDate,
  setSelectedDate,
  setBaselineSelectedDate,
  isLoading = false,
  isRunning = false,
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
  drawControls
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
  const [isPlacedObjectsLoading, setIsPlacedObjectsLoading] = useState(false);
  const pendingPlacedObjects = useMemo(
    () =>
      placedObjectsControls?.pendingPlacedObject
        ? [placedObjectsControls.pendingPlacedObject]
        : [],
    [placedObjectsControls?.pendingPlacedObject],
  );



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
      if (!info?.coordinate) return;
      const [lng, lat] = info.coordinate;

      // Add vertices while drawing
      if (isDrawing) {
        drawControls.addDraftPoint(lng, lat);
      }
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

  // Interpolated grids in view. Only the selected city's grid is drawn, so
  // cities the backend has no grid data for simply render no surface.
  const visibleCityGrids = useMemo(() => {
    const entries: [string, CityMetricGrid][] = [];
    for (const [cityName, grid] of Object.entries(metricGridsByCity)) {
      if (cityName === selectedCity) entries.push([cityName, grid]);
    }
    return entries;
  }, [metricGridsByCity, selectedCity]);

  /**
   * Metric layers available for the selected city on the selected date. The
   * interpolated grid is the source of truth when the backend has one; the
   * static `availableMetrics` list is the fallback for cities without grids.
   */
  const gridMetricLayers = useMemo(() => {
    const keys = new Set<string>();
    for (const [, grid] of visibleCityGrids) {
      for (const metricKey of Object.keys(grid.metrics)) keys.add(metricKey);
    }
    return Array.from(keys)
      .sort()
      .map((key) => ({ [key]: [] as string[] }));
  }, [visibleCityGrids]);

  const availableMetricLayers = useMemo(
    () =>
      gridMetricLayers.length > 0
        ? gridMetricLayers
        : (availableMetrics as unknown as Record<string, string[]>[]),
    [gridMetricLayers],
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
      if (!prev) return availableMetricLayers[0];
      const prevKey = Object.keys(prev)[0];
      if (availableMetricLayers.some((metric) => Object.keys(metric)[0] === prevKey)) {
        return prev;
      }
      
      return availableMetricLayers[0];
    });
  }, [availableMetricLayers, setSelectedMetric]);

  // Presentation derived from the active metric: key, display name, layer
  // colour ramp and matching legend gradient.
  const activeMetricKey = selectedMetric
    ? Object.keys(selectedMetric)[0]
    : availableMetricLayers[0]
      ? Object.keys(availableMetricLayers[0])[0]
      : 'heat_risk_score';
  const metricLabelText = formatMetricName(activeMetricKey);
  const activeMetricLegendGradient = useMemo(
    () => metricLegendGradient(activeMetricKey),
    [activeMetricKey],
  );

  // One geographically-anchored raster per visible city for the active metric.
  // The image is fixed-resolution and pinned to its lon/lat bounds, so the
  // rendered surface never changes with zoom.
  const metricRasters: CityMetricRasterEntry[] = useMemo(
    () =>
      visibleCityGrids
        .filter(([, grid]) => grid.metrics[activeMetricKey])
        .map(([cityName, grid]) => ({
          cityName,
          grid,
          raster: buildCityMetricRaster(cityName, grid, activeMetricKey),
        })),
    [visibleCityGrids, activeMetricKey],
  );

  /**
   * Sample every metric of the grid at a coordinate. Returns a synthesized
   * reading when the coordinate lands inside a city raster, or null outside all
   * of them, so places without data never show values.
   */
  const sampleRasterPoint = useCallback(
    (lon: number, lat: number): MetricValue | null => {
      for (const { cityName, grid, raster } of metricRasters) {
        if (!isInsideRaster(raster, lon, lat)) continue;
        const raw = sampleMetricGrid(grid, activeMetricKey, lon, lat);
        if (raw === null) continue;

        const individualMetrics: Record<string, string> = {};
        for (const metricKey of Object.keys(grid.metrics)) {
          const value = sampleMetricGrid(grid, metricKey, lon, lat);
          if (value !== null) individualMetrics[metricKey] = value.toFixed(1);
        }

        const { min, max } = grid.metrics[activeMetricKey];
        return {
          value: Math.round(metricScore(raw, min, max)),
          location_name: `${cityName} · ${lat.toFixed(4)}, ${lon.toFixed(4)}`,
          location_coordinates: [lon, lat],
          individual_metrics: individualMetrics,
          is_interpolated: true,
        };
      }
      return null;
    },
    [metricRasters, activeMetricKey],
  );

  // Load mock placed-object tools for the selected city + date and push them
  // into placedObjectsControls. Re-runs on city/date change; clears when either
  // is missing. The ignore flag drops a stale response if the selection changes
  // mid-fetch.
  const setPlacedObjects = placedObjectsControls?.setPlacedObjects;

  useEffect(() => {
    if (!setPlacedObjects) return;

    if (isRunning) {
      setIsPlacedObjectsLoading(false);
      return;
    }

    if (!selectedCity || !selectedDate) {
      setIsPlacedObjectsLoading(false);
      setPlacedObjects([]);
      return;
    }

    let ignore = false;
    setIsPlacedObjectsLoading(true);

    fetchPlacedObjects()
      .then((byDateCity) => {
        if (ignore) return;
        const tools = byDateCity[selectedDate]?.[selectedCity] ?? [];
        setPlacedObjects(tools);
        setIsPlacedObjectsLoading(false);
      })
      .catch((error) => {
        if (ignore) return;
        console.error('Failed to load placed objects', error);
        setPlacedObjects([]);
        setIsPlacedObjectsLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [isRunning, selectedCity, selectedDate, setPlacedObjects]);


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
    const selectedMetricKey = selectedMetric ? Object.keys(selectedMetric)[0] : null;
    const idx = availableMetricLayers.findIndex(
      (metric) => Object.keys(metric)[0] === selectedMetricKey,
    );
    const next =
      availableMetricLayers[(idx + 1 + availableMetricLayers.length) % availableMetricLayers.length];
    setSelectedMetric(next);
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
    metricRasters,
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
    (info: {
      coordinate?: number[];
      object?: MetricValue | null;
      x: number;
      y: number;
      layer?: { id?: string } | null;
    }) => {
      if (isDrawing || !info.coordinate || info.coordinate.length < 2) {
        setHoveringHeatmap(false);
        setTooltip(null);
        return;
      }

      const [lon, lat] = info.coordinate as [number, number];

      const publish = (point: MetricValue) => {
        setHoveringHeatmap(true);
        setTooltip({
          point,
          metric: activeMetricKey,
          x: info.x,
          y: info.y,
          coordinates: {
            longitude: point.location_coordinates[0],
            latitude: point.location_coordinates[1],
          },
          surface: mapRef.current
            ? classifySurface(mapRef.current, info.x, info.y)
            : { type: 'unknown' as SurfaceType },
        });
      };

      // The interpolated surface answers at any coordinate, so the tooltip
      // reports the value under the exact cursor instead of snapping to the
      // nearest discrete reading.
      const sampled = sampleRasterPoint(lon, lat);
      if (sampled) {
        publish(sampled);
        return;
      }

      // Outside every raster: fall back to a picked measured reading, which is
      // all there is for cities the backend has no grid for.
      if (info.layer?.id === 'heatmap-point-pick-layer' && info.object) {
        publish(info.object as MetricValue);
        return;
      }

      setHoveringHeatmap(false);
      setTooltip(null);
    },
    [
      activeMetricKey,
      isDrawing,
      mapRef,
      sampleRasterPoint,
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
        style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0, filter: !isRunning && (isLoading || isPlacedObjectsLoading) ? 'blur(4px)' : undefined, transition: 'filter 180ms ease' }}
      />

      {/* deck.gl overlay canvas. dragPan is disabled while an area is being
          dragged so the map doesn't pan out from under the vertex handle. */}
      <DeckGL
        viewState={viewState}
        onViewStateChange={handleViewStateChange}
        onClick={handleDeckClick}
        onHover={handleDeckHover}
        pickingRadius={10}
        controller={{ dragPan: !isAreaDragging, scrollZoom: true, touchZoom: true }}
        layers={layers}
        getCursor={getCursor}
        style={{ position: 'absolute', width: '100%', height: '100%', filter: !isRunning && (isLoading || isPlacedObjectsLoading) ? 'blur(4px)' : undefined, transition: 'filter 180ms ease' }}
      />

      {!isRunning && (isLoading || isPlacedObjectsLoading) && (
        <div
          role="status"
          aria-live="polite"
          aria-label="Loading heatmap data"
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 25,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(2, 8, 23, 0.28)',
            pointerEvents: 'none',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '12px 16px',
              border: '1px solid rgba(148, 163, 184, 0.45)',
              borderRadius: 10,
              background: 'rgba(2, 8, 23, 0.88)',
              color: '#f8fafc',
              fontSize: 14,
              fontWeight: 600,
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.28)',
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 18,
                height: 18,
                border: '2px solid rgba(148, 163, 184, 0.45)',
                borderTopColor: '#38bdf8',
                borderRadius: '50%',
                animation: 'heatmap-loading-spin 0.8s linear infinite',
              }}
            />
            Loading heatmap
          </div>
        </div>
      )}

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
        setBaselineSelectedDate={setBaselineSelectedDate}
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
            Point at {tooltip.coordinates.latitude.toFixed(4)}, {tooltip.coordinates.longitude.toFixed(4)}
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