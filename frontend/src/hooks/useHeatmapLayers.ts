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
import { TOOLBOX_BY_TYPE, toolboxMarkerDataUrl, type PlacedObject } from '../utils/toolbox';
import type { UseHeatmapLayersArgs } from '../types/components';

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
  displayedPOIAreas,
  userPOIAreas,
  editingAreaId,
  placedObjects,
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
            onCityClick(info.object as City);
          }
        },
      }),
    [onCityClick, isDrawing, selectedCity],
  );

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
          if (info.object) onRemovePlacedObject((info.object as PlacedObject).id);
        },
      }),
    [placedObjects, isDrawing, onRemovePlacedObject],
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

  return useMemo(
    () => [
      interpolatedHeatmapLayer,
      poiAreaLayer,
      draftPolygonLayer,
      draftPathLayer,
      draftPointsLayer,
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
      placedObjectLayer,
      cityIconLayer,
      cityLabelLayer,
    ],
  );
}