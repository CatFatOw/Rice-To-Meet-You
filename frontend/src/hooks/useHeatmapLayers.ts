import { useMemo, useRef } from 'react';
import {
  ScatterplotLayer,
  PolygonLayer,
  PathLayer,
  TextLayer,
  IconLayer,
} from '@deck.gl/layers';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import { type CityPOIArea, type HeatmapMetricValue } from '../api/map';
import { cities, type City } from '../data/hostCities';
import { TOOLBOX_BY_TYPE, toolboxMarkerDataUrl, type PlacedObject } from '../services/toolbox';
import type { UseHeatmapLayersArgs } from '../types/components';
import { polygonCenter } from '../services/toolbox';

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

function translatePolygon(
  points: [number, number][],
  deltaLng: number,
  deltaLat: number,
): [number, number][] {
  return points.map(([lng, lat]) => [lng + deltaLng, lat + deltaLat]);
}

// #rrggbb -> [r, g, b] for deck.gl color props. PlacedObject.color is a hex
// string, but PolygonLayer needs RGBA arrays. Malformed components degrade to
// 0 rather than NaN, which deck.gl would render as transparent/black.
function hexToRgb(hex: string): [number, number, number] {
  const n = hex.replace('#', '');
  const r = parseInt(n.substring(0, 2), 16);
  const g = parseInt(n.substring(2, 4), 16);
  const b = parseInt(n.substring(4, 6), 16);
  return [Number.isNaN(r) ? 0 : r, Number.isNaN(g) ? 0 : g, Number.isNaN(b) ? 0 : b];
}

function geometryAnchor(geometry: PlacedObject['geometry']): [number, number] {
  if (geometry.kind === 'point') {
    return [geometry.longitude, geometry.latitude];
  }

  const points = geometry.kind === 'line' ? geometry.coordinates : geometry.ring;
  if (points.length === 0) return [0, 0];

  const total = points.reduce(
    (acc, [lng, lat]) => ({ lng: acc.lng + lng, lat: acc.lat + lat }),
    { lng: 0, lat: 0 },
  );

  return [total.lng / points.length, total.lat / points.length];
}


// Transient state for a drag-in-progress on either the draft polygon or an
// existing (editing) POI area. Lives here because only the layers below read
// or write it.
type DragContext =
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
    };

/**
 * Builds the ordered deck.gl layer stack for the heatmap. All layer-local
 * interaction state (the drag context ref) is owned here; the caller only
 * passes in data + setters and receives the `layers` array to hand to DeckGL.
 */
export function useHeatmapLayers({
  isDrawing,
  selectedCity,
  displayedHeatmapPoints,
  activeMetricColorRange,
  activeMetricColorDomain,
  activeMetricWeightOffset,
  activeMetricKey,
  displayedPOIAreas,
  userPOIAreas,
  editingAreaId,
  placedObjects,
  pendingPlacedObjects,
  draftPoints,
  draftRgb,
  onCityClick,
  onRemovePlacedObject,
  setEditingAreaId,
  setIsDrawing,
  setIsAreaDragging,
  setUserPOIAreas,
  setDraftPoints,
}: UseHeatmapLayersArgs) {
  const dragContextRef = useRef<DragContext | null>(null);

  const isTemperatureChange =
    activeMetricKey === 'change_in_temperature'
    || activeMetricKey === 'change_in_average_temperature_c';

  const deltaThreshold = 0.05;

    const coolingPoints = useMemo(
      () =>
        isTemperatureChange
          ? displayedHeatmapPoints.filter(
              (point) => point.value < -deltaThreshold,
            )
          : [],
      [displayedHeatmapPoints, isTemperatureChange],
    );

    const warmingPoints = useMemo(
      () =>
        isTemperatureChange
          ? displayedHeatmapPoints.filter(
              (point) => point.value > deltaThreshold,
            )
          : [],
      [displayedHeatmapPoints, isTemperatureChange],
    );

  
  // Committed objects plus any pending (staged) ones, rendered identically.
  // pendingPlacedObjects is optional (pages without a toolbox omit it).
  const allPlacedObjects = useMemo(
    () => [...placedObjects, ...(pendingPlacedObjects ?? [])],
    [placedObjects, pendingPlacedObjects],
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
            onCityClick(info.object as City);
          }
        },
      }),
    [onCityClick, isDrawing],
  );

  // City name label under each football icon.
  const cityLabelLayer = useMemo(
    () =>
      new TextLayer({
        id: 'city-label-layer',
        data: cities,
        pickable: !isDrawing,
        characterSet: 'auto',
        fontFamily: 'Inter, sans-serif',
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
            onCityClick(info.object as City);
          }
        },
      }),
    [onCityClick, isDrawing, selectedCity],
  );

  // Continuous, interpolated density surface (GPU kernel-density estimation).
  // Larger radius + lower threshold = smoother blending between points. This is
  // the *visible* layer and stays non-pickable — pointPickLayer below handles
  // hover so the tooltip reports true point values, not the blended surface.
  
  const interpolatedHeatmapLayer = useMemo(
    () =>
      new HeatmapLayer<HeatmapMetricValue>({
        id: 'interpolated-heatmap-layer',
        data: displayedHeatmapPoints,

        getPosition: (d) => d.location_coordinates,
        getWeight: (d) => d.value + activeMetricWeightOffset,

        // Nearby observations contribute to a weighted average.
        aggregation: 'MEAN',

        radiusPixels: 60,   // smaller kernel → less spread → thinner halo
        intensity: 1,
        threshold: 0.08,    // higher cutoff → trims the faint blue fringe

        // Keep this fixed for the metric so colors do not rescale every day.
        colorDomain: activeMetricColorDomain,
        colorRange: activeMetricColorRange,

        pickable: false,
      }),
    [
      displayedHeatmapPoints,
      activeMetricColorDomain,
      activeMetricColorRange,
      activeMetricWeightOffset,
    ],
  );
  const coolingHeatmapLayer = useMemo(
  () =>
    new HeatmapLayer<HeatmapMetricValue>({
      id: 'cooling-heatmap-layer',
      data: coolingPoints,

      getPosition: (d) => d.location_coordinates,

      // Convert negative cooling to positive magnitude.
      getWeight: (d) => -d.value,

      aggregation: 'MEAN',
      radiusPixels: 60,
      intensity: 1,
      threshold: 0.08,

      colorDomain: [0, 5],
      colorRange: [
        [219, 234, 254, 0],   // 0: transparent
        [147, 197, 253, 100],
        [96, 165, 250, 160],
        [59, 130, 246, 210],
        [30, 64, 175, 240],   // -5°C: strong blue
      ],

      pickable: false,
    }),
  [coolingPoints],
);

const warmingHeatmapLayer = useMemo(
  () =>
    new HeatmapLayer<HeatmapMetricValue>({
      id: 'warming-heatmap-layer',
      data: warmingPoints,

      getPosition: (d) => d.location_coordinates,
      getWeight: (d) => d.value,

      aggregation: 'MEAN',
      radiusPixels: 60,
      intensity: 1,
      threshold: 0.08,

      colorDomain: [0, 5],
      colorRange: [
        [254, 226, 226, 0],   // 0: transparent
        [252, 165, 165, 100],
        [248, 113, 113, 160],
        [239, 68, 68, 210],
        [153, 27, 27, 240],   // +5°C: strong red
      ],

      pickable: false,
    }),
  [warmingPoints],
);

const visibleMetricLayers = useMemo(
  () =>
    isTemperatureChange
      ? [coolingHeatmapLayer, warmingHeatmapLayer]
      : [interpolatedHeatmapLayer],
  [
    isTemperatureChange,
    interpolatedHeatmapLayer,
    coolingHeatmapLayer,
    warmingHeatmapLayer,
  ],
);

  // Transparent, pickable dots sitting exactly on each reading. The heatmap
  // above is the visible surface; this layer exists only so hovering a point
  // returns its true value (via info.object) instead of the interpolated
  // surface value. Sits just above the heatmap and below every interactive
  // vector layer, so POI / placed-object / city clicks still win. Bump the
  // fill alpha if you'd like the raw readings to be visible.
  const pointPickLayer = useMemo(
    () =>
      new ScatterplotLayer<HeatmapMetricValue>({
        id: 'heatmap-point-pick-layer',
        data: displayedHeatmapPoints,
        pickable: !isDrawing,
        getPosition: (d) => d.location_coordinates,
        // Keep alpha > 0 so fragments are not discarded by alpha cutoffs in
        // the picking pass; fully transparent points can become unpickable.
        getFillColor: [0, 0, 0, 1],
        opacity: 0.01,
        radiusUnits: 'pixels',
        getRadius: 8,
        radiusMinPixels: 6,
        radiusMaxPixels: 14,
      }),
    [displayedHeatmapPoints, isDrawing],
  );

  // Placed objects with point/line geometry, rendered as toolbox marker icons
  // at the geometry's anchor. Polygon-geometry objects are handled separately
  // by placedObjectPolygonLayer below. Click a pin to remove it.
  const placedObjectPointLayer = useMemo(
    () =>
      new IconLayer({
        id: 'placed-object-point-layer',
        data: allPlacedObjects.filter((o) => o.geometry.kind !== 'polygon'),
        pickable: !isDrawing,
        getPosition: (d: PlacedObject) => geometryAnchor(d.geometry),
        getIcon: (d: PlacedObject) => {
          const toolKey = d.type ?? d.intervention ?? 'unknown';
          const def = TOOLBOX_BY_TYPE[toolKey];
          const color = d.color ?? def?.color ?? '#f8fafc';
          return {
            url: toolboxMarkerDataUrl(toolKey, color),
            width: 48,
            height: 60,
            anchorX: 24,
            anchorY: 58,
            id: toolKey,
          };
        },
        getSize: 46,
        sizeUnits: 'pixels',
        onClick: (info: any) => {
          if (info.object) onRemovePlacedObject((info.object as PlacedObject).id);
        },
      }),
    [allPlacedObjects, isDrawing, onRemovePlacedObject],
  );

  // Placed objects with polygon geometry, rendered as filled areas (POI-style)
  // instead of an icon. Fill/stroke come from the object's own color, falling
  // back to the toolbox definition. Click to remove.
  const placedObjectPolygonLayer = useMemo(
    () =>
      new PolygonLayer({
        id: 'placed-object-polygon-layer',
        data: allPlacedObjects.filter((o) => o.geometry.kind === 'polygon'),
        pickable: !isDrawing,
        stroked: true,
        filled: true,
        opacity: 0.55,
        getPolygon: (d: PlacedObject) =>
          d.geometry.kind === 'polygon' ? d.geometry.ring : [],
        getFillColor: (d: PlacedObject) => {
          const toolKey = d.type ?? d.intervention ?? 'unknown';
          const color = d.color ?? TOOLBOX_BY_TYPE[toolKey]?.color ?? '#f8fafc';
          return [...hexToRgb(color), 140];
        },
        getLineColor: (d: PlacedObject) => {
          const toolKey = d.type ?? d.intervention ?? 'unknown';
          const color = d.color ?? TOOLBOX_BY_TYPE[toolKey]?.color ?? '#f8fafc';
          return [...hexToRgb(color), 255];
        },
        getLineWidth: 2,
        lineWidthUnits: 'pixels',
        onClick: (info: any) => {
          if (info.object) onRemovePlacedObject((info.object as PlacedObject).id);
        },
      }),
    [allPlacedObjects, isDrawing, onRemovePlacedObject],
  );

  // Toolbox marker icon centered on each polygon placed object (in addition to
  // the filled area from placedObjectPolygonLayer). Anchored at the polygon's
  // area centroid via polygonCenter. Click to remove, same as the pins.
  const placedObjectPolygonIconLayer = useMemo(
    () =>
      new IconLayer({
        id: 'placed-object-polygon-icon-layer',
        data: allPlacedObjects.filter(
          (o) => o.geometry.kind === 'polygon' && o.geometry.ring.length >= 3,
        ),
        pickable: !isDrawing,
        getPosition: (d: PlacedObject) =>
          d.geometry.kind === 'polygon' ? polygonCenter(d.geometry.ring) : [0, 0],
        getIcon: (d: PlacedObject) => {
          const toolKey = d.type ?? d.intervention ?? 'unknown';
          const def = TOOLBOX_BY_TYPE[toolKey];
          const color = d.color ?? def?.color ?? '#f8fafc';
          return {
            url: toolboxMarkerDataUrl(toolKey, color),
            width: 48,
            height: 60,
            anchorX: 24,
            anchorY: 58,
            id: toolKey,
          };
        },
        getSize: 46,
        sizeUnits: 'pixels',
        onClick: (info: any) => {
          if (info.object) onRemovePlacedObject((info.object as PlacedObject).id);
        },
      }),
    [allPlacedObjects, isDrawing, onRemovePlacedObject],
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
        getLineWidth: 2,
        lineWidthUnits: 'pixels',
        onClick: (info: any) => {
          const area = info.object as CityPOIArea | undefined;
          if (!area) return;

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
    ],
  );

  // --- Draft (in-progress) drawing layers ---
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

  return useMemo(
    () => [
      ...visibleMetricLayers,
      pointPickLayer,
      poiAreaLayer,
      placedObjectPolygonLayer,
      placedObjectPolygonIconLayer,
      draftPolygonLayer,
      draftPathLayer,
      draftPointsLayer,
      placedObjectPointLayer,
      cityIconLayer,
      cityLabelLayer,
    ],
    [
      visibleMetricLayers,
      pointPickLayer,
      poiAreaLayer,
      placedObjectPolygonLayer,
      placedObjectPolygonIconLayer,
      draftPolygonLayer,
      draftPathLayer,
      draftPointsLayer,
      placedObjectPointLayer,
      cityIconLayer,
      cityLabelLayer,
    ],
  );
}