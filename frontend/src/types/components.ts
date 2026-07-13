import type React from 'react';
import type { ViewState } from './viewState';
import type { HeatmapMetricValue, HeatmapMetricSnapshot, CityPOIArea, CityPOIAreaMap, HeatmapMetricPointByCity } from './heatmap';
import type { PlacedObject as ToolboxPlacedObject } from './toolbox';
import type { SurfaceType } from './map';
import type { GeocodeResult } from './search';
import type { City } from './city';

// ---------------------------------------------------------------------------
// SelectDate props
// ---------------------------------------------------------------------------
export interface SelectDateProps {
  // Selected date as 'YYYY-MM-DD', or null when nothing is chosen yet.
  value: string | null;
  onChange: (isoDate: string) => void;
  // Heading shown above the trigger. Defaults to "Date".
  label?: string;
  // Optional bounds (inclusive), as 'YYYY-MM-DD'. Days outside are disabled.
  minDate?: string;
  maxDate?: string;
  // If provided, ONLY these dates ('YYYY-MM-DD') are selectable.
  availableDates?: string[];
  disabled?: boolean;
  // 0 = weeks start on Sunday (default), 1 = Monday.
  weekStartsOn?: 0 | 1;
  /**
   * 'panel' (default) renders self-contained chrome (border + translucent
   * background). 'bare' drops it for embedding in an existing panel/toolbar.
   */
  variant?: 'panel' | 'bare';
  className?: string;
  style?: React.CSSProperties;
}

// ---------------------------------------------------------------------------
// SearchBar props
// ---------------------------------------------------------------------------
export interface SearchBarProps {
  searchQuery: string;
  setSearchQuery: React.Dispatch<React.SetStateAction<string>>;
  geoResults: GeocodeResult[];
  setGeoResults: React.Dispatch<React.SetStateAction<GeocodeResult[]>>;
  isSearching: boolean;
  setIsSearching: React.Dispatch<React.SetStateAction<boolean>>;
  showSuggestions: boolean;
  setShowSuggestions: React.Dispatch<React.SetStateAction<boolean>>;
  flyTo: (lng: number, lat: number, zoom: number, cityName?: string) => void;
}

// ---------------------------------------------------------------------------
// Toolbox props
// ---------------------------------------------------------------------------
export interface ToolboxProps {
  /**
   * When true, the panel renders the full toolbox: the metric toggle, a palette
   * of placeable objects that can be dragged onto the map, followed by the
   * Create POI Area section. When false only the metric toggle and Create POI
   * Area section are shown.
   */
  displayToolbox: boolean;

  // --- Metric toggle ---
  selectedDate: string | null;
  setSelectedDate: React.Dispatch<React.SetStateAction<string | null>>;
  availableDates: string[];
  metricLabel: string;
  canToggleMetric: boolean;
  onToggleMetric: () => void;

  // --- Placeable objects palette ---
  placedCount: number;
  onClearObjects: () => void;

  // --- Create POI Area ---
  selectedCity: string | null;
  draftName: string;
  setDraftName: React.Dispatch<React.SetStateAction<string>>;
  draftColorHex: string;
  setDraftColorHex: React.Dispatch<React.SetStateAction<string>>;
  isDrawing: boolean;
  draftPointCount: number;
  onStartDrawing: () => void;
  onFinishArea: () => void;
  onUndoLastPoint: () => void;
  onCancelDrawing: () => void;
  hasUserAreasInCity: boolean;
  onClearMyAreas: () => void;
  editingAreaId: string | null;
  onFinishEdit: () => void;
}

// ---------------------------------------------------------------------------
// SimulateButton props
// ---------------------------------------------------------------------------
export interface SimulateButtonProps {
  onClick?: () => void;
  disabled?: boolean;
  label?: string;
  className?: string;
  style?: React.CSSProperties;
}

// ---------------------------------------------------------------------------
// HeatRiskScale props
// ---------------------------------------------------------------------------
export interface HeatRiskScaleProps {
  // Display name of the active metric, e.g. "Heat Risk".
  label: string;
  // CSS `linear-gradient(...)` string for the active metric's color ramp.
  gradient: string;
}

// ---------------------------------------------------------------------------
// TooltipState (used by Heatmap and pages)
// ---------------------------------------------------------------------------
export interface TooltipState {
  point: HeatmapMetricValue;
  metric: string;
  x: number;
  y: number;
  coordinates: {
    longitude: number;
    latitude: number;
  };
  surface?: { type: SurfaceType; detail?: string };
}

// ---------------------------------------------------------------------------
// Heatmap props
// ---------------------------------------------------------------------------
export interface HeatmapProps {
  viewState: ViewState;
  setViewState: React.Dispatch<React.SetStateAction<ViewState>>;
  selectedCity: string | null;
  setSelectedCity: React.Dispatch<React.SetStateAction<string | null>>;
  cityPOIAreas: CityPOIAreaMap;
  heatmapPointsByCity: Record<string, HeatmapMetricSnapshot[]>;
  heatmapAnchorsByCity: HeatmapMetricPointByCity;
  availableDates: string[];
  selectedDate: string | null;
  setSelectedDate: React.Dispatch<React.SetStateAction<string | null>>;
  mapContainerRef: React.RefObject<HTMLDivElement | null>;
  mapRef: React.MutableRefObject<import('maplibre-gl').Map | null>;
  mapSyncFrameRef: React.MutableRefObject<number | null>;
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
  onPlacedObjectsChange?: (objects: ToolboxPlacedObject[]) => void;
  /**
   * When true, the left panel renders as a full toolbox. When false (default)
   * only the metric toggle and Create POI Area are shown.
   */
  displayToolbox?: boolean;
}

// ---------------------------------------------------------------------------
// UseHeatmapLayers args
// ---------------------------------------------------------------------------
export interface UseHeatmapLayersArgs {
  isDrawing: boolean;
  selectedCity: string | null;

  displayedHeatmapPoints: HeatmapMetricValue[];
  activeMetricColorRange: [number, number, number, number][];

  displayedPOIAreas: CityPOIArea[];
  userPOIAreas: CityPOIArea[];
  editingAreaId: string | null;

  placedObjects: ToolboxPlacedObject[];

  draftPoints: [number, number][];
  draftRgb: [number, number, number];

  onCityClick: (city: City) => void;
  onRemovePlacedObject: (id: string) => void;
  setEditingAreaId: React.Dispatch<React.SetStateAction<string | null>>;
  setIsDrawing: React.Dispatch<React.SetStateAction<boolean>>;
  setIsAreaDragging: React.Dispatch<React.SetStateAction<boolean>>;
  setUserPOIAreas: React.Dispatch<React.SetStateAction<CityPOIArea[]>>;
  setDraftPoints: React.Dispatch<React.SetStateAction<[number, number][]>>;
}
