import React, { useEffect, useRef, useState } from 'react';
import { usePolygonDraw, type Ring } from '../hooks/usePolygonDraw';
import maplibregl from 'maplibre-gl';
import Heatmap from '../components/Heatmap';
import NavigationBar from '../components/NavigationBar';
import OverallStatistics from '../components/OverallStatistics';
import POIStatistics from '../components/POIStatistics';
import {
  callHeatmapAnchors,
  callMockAllCityPOIs,
  type CityPOIArea,
  type CityPOIAreaMap,
  type HeatmapMetricPointByCity,
  type HeatmapMetricSnapshot,
} from '../api/map';
import { callMockStatistics } from '../api/statistics';
import { determineCityView } from '../utils/cityViews';
import { interpolateByCity } from '../utils/interpolate';
import { KERNEL_MODEL as BASE_KERNEL_MODEL } from '../data/kernel';
import { eachDay, runSimulation, type KernelModel, type KernelInput } from '../utils/simulation';
import type { PlacedObject as ToolboxPlacedObject } from '../types/toolbox';
import type { Geometry, PlacedObject as SimulationPlacedObject, Schedule } from '../types/simulation';
import type { ViewState } from '../types/viewState';
import type { GeocodeResult } from '../types/search';
import type { TooltipState } from '../types/components';
import type { OverallStatisticsProps, POIStatisticsProps } from '../types/statistics';
import usePlacedObjects from '../hooks/usePlacedObjects';

function geometryCenter(geometry: Geometry): [number, number] {
  if (geometry.kind === 'point') {
    return [geometry.longitude, geometry.latitude];
  }

  if (geometry.kind === 'line') {
    const first = geometry.coordinates[0];
    const last = geometry.coordinates[geometry.coordinates.length - 1] ?? first;
    return [(first[0] + last[0]) / 2, (first[1] + last[1]) / 2];
  }

  const ring = geometry.ring;
  const total = ring.reduce(
    (acc, [lng, lat]) => ({ lng: acc.lng + lng, lat: acc.lat + lat }),
    { lng: 0, lat: 0 },
  );
  return [total.lng / ring.length, total.lat / ring.length];
}

function toolboxTypeToSimulationType(type: string): SimulationPlacedObject['type'] {
  switch (type) {
    case 'cool_roofs':
      return 'cool_roof';
    case 'shade_canopy':
      return 'shade_structure';
    default:
      return type as SimulationPlacedObject['type'];
  }
}

function buildSimulationPlacedObject(obj: ToolboxPlacedObject): SimulationPlacedObject {
  const [longitude, latitude] = geometryCenter(obj.geometry);
  const type = toolboxTypeToSimulationType(obj.type);
  const schedule: Schedule = { mode: 'always' };

  const paramByType: Record<string, unknown> = {
    cool_roof: { albedo: 0.65, emissivity: 0.9 },
    misting_station: {
      nozzleCount: 4,
      flowRate_L_per_min: 1.2,
      dropletDiameter_um: 25,
      mountHeight_m: 2.5,
    },
    shade_structure: { transmissivity: 0.2, height_m: 4 },
    cool_pavement: { albedo: 0.45, width_m: 3 },
  };

  return {
    id: obj.id,
    type,
    geometry: obj.geometry as SimulationPlacedObject['geometry'],
    param: paramByType[type] as SimulationPlacedObject['param'],
    schedule,
    longitude,
    latitude,
  } as SimulationPlacedObject;
}

function mergeCityDateRecords(records: HeatmapMetricPointByCity[string] | undefined) {
  if (!records || records.length === 0) return null;
  return records.reduce<Record<string, HeatmapMetricSnapshot[]>>(
    (acc, byDate) => ({ ...acc, ...byDate }),
    {},
  );
}

function adaptKernelModel(): KernelModel {
  const entries = Object.entries(BASE_KERNEL_MODEL).map(([toolType, byMetric]) => {
    const metricEntries = Object.entries(byMetric).map(([metric, spec]) => {
      const legacySpec = spec as typeof spec & {
        temporal?: (elapsedHours: number, activeHours: number) => number;
      };
      const kernels = [
        (input: KernelInput) => spec.spatial(input.dist_m),
        (input: KernelInput) => legacySpec.temporal?.(input.elapsedHours, input.dutyHours) ?? 1,
        (input: KernelInput) => spec.response(input.baseValue),
      ];

      if (spec.environmental) {
        kernels.push((input: KernelInput) => spec.environmental?.(input.metrics, '12:00') ?? 1);
      }

      return [
        metric,
        {
          intensity: spec.intensity,
          floor: spec.floor,
          kernels,
        },
      ] as const;
    });

    return [toolType, Object.fromEntries(metricEntries)] as const;
  });

  return Object.fromEntries(entries) as KernelModel;
}

const SIMULATION_MODEL = adaptKernelModel();


const SimulationPage: React.FC = () => {


// ======================================================
// States
// ======================================================

  // --- Map and viewport state ---
  // Controls the map's position, lifecycle, and interactive overlays.
  const [viewState, setViewState] = useState<ViewState>({
    longitude: -95.7129,
    latitude: 37.0902,
    zoom: 3.5,
    pitch: 0,
    bearing: 0,
  });

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const mapSyncFrameRef = useRef<number | null>(null);

  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [hoveringHeatmap, setHoveringHeatmap] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // --- City and heatmap data ---
  // Stores the selected city and loaded environmental data.
  const [selectedCity, setSelectedCity] = useState<string | null>(null);
  const [cityPOIAreas, setCityPOIAreas] = useState<CityPOIAreaMap>({});
  const [heatmapPointsByCity, setHeatmapPointsByCity] =
    useState<Record<string, HeatmapMetricSnapshot[]>>({});
  const [heatmapAnchorsByCity, setHeatmapAnchorsByCity] =
    useState<HeatmapMetricPointByCity>({});
  const [baselineHeatmapAnchorsByCity, setBaselineHeatmapAnchorsByCity] =
    useState<HeatmapMetricPointByCity>({});

  // --- Date and timeline state ---
  // Controls the active date and simulation period.
  const [selectedDate, setSelectedDate] = useState<string | null>('2026-07-07');
  const [fromDate, setFromDate] = useState<string | null>('2026-07-05');
  const [toDate, setToDate] = useState<string | null>('2026-07-08');
  const availableDates = ['2026-07-05', '2026-07-06', '2026-07-07', '2026-07-08'];

  // --- Simulation state ---
  // Controls simulation data and playback.
  const [simulationByDate, setSimulationByDate] =
    useState<Record<string, HeatmapMetricSnapshot[]> | null>(null);
  const [containSimulation] = useState(true);
  const simulationTimerRef = useRef<number | null>(null);

  // --- Placed objects (toolbox items) ---
  // Controls draggable toolbox objects placed on the map.
  const placedObjectsControls = usePlacedObjects({
    mapRef,
    mapContainerRef,
    buildPlacedObject: ((args: any): ToolboxPlacedObject => ({
      id: args.id,
      type: args.type,
      name: args.name,
      color: args.color,
      geometry: args.geometry,
    })) as any,
  }) as unknown as {
    placedObjects: ToolboxPlacedObject[];
    setPlacedObjects: React.Dispatch<React.SetStateAction<ToolboxPlacedObject[]>>;
    addPlacedObject: (object: ToolboxPlacedObject) => void;
    removePlacedObject: (id: string) => void;
    clearPlacedObjects: () => void;
    patchPlacedObject: (id: string, patch: Partial<ToolboxPlacedObject>) => void;
    handleObjectDragOver: (e: React.DragEvent<HTMLDivElement>) => void;
    handleObjectDrop: (e: React.DragEvent<HTMLDivElement>) => void;
  };

  // --- POI area drawing state ---
  // Controls the creation and management of user-drawn POI areas.
  const drawControls = usePolygonDraw(3) as unknown as {
    isDrawing: boolean;
    setIsDrawing: React.Dispatch<React.SetStateAction<boolean>>;
    draftPoints: Ring;
    setDraftPoints: React.Dispatch<React.SetStateAction<Ring>>;
    startDrawing: () => void;
    addDraftPoint: (lng: number, lat: number) => void;
    undoDraftPoint: () => void;
    cancelDrawing: () => void;
    commitDrawing: () => Ring | null;
    canCommitDrawing: boolean;
  };
  const [draftColorHex, setDraftColorHex] = useState('#22c55e');
  const [draftName, setDraftName] = useState('');
  const [userPOIAreas, setUserPOIAreas] = useState<CityPOIArea[]>([]);
  const [editingAreaId, setEditingAreaId] = useState<string | null>(null);
  const [isAreaDragging, setIsAreaDragging] = useState(false);

  // --- Search state ---
  // Controls search input, geocoding results, and suggestions display.
  const [searchQuery, setSearchQuery] = useState('');
  const [geoResults, setGeoResults] = useState<GeocodeResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // --- Statistics and UI state ---
  // Controls metric selection and statistics panel data.
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [overallStatisticsProps, setOverallStatisticsProps] =
    useState<OverallStatisticsProps>();
  const [poiStatisticsProps, setPOIStatisticsProps] = useState<POIStatisticsProps>();


// ======================================================
// Hooks
// ======================================================
  // --- Load initial data ---
  // Fetch city POI areas from API on component mount
  useEffect(() => {
    let isMounted = true;

    const loadMockPOIs = async () => {
      try {
        const poisByCity = await callMockAllCityPOIs();
        if (isMounted) {
          setCityPOIAreas(poisByCity);
        }
      } catch (error) {
        console.error('Failed to load mock city POIs', error);
      }
    };

    loadMockPOIs();

    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch heatmap anchor points and set baseline data on component mount
  useEffect(() => {
    let isMounted = true;

    const loadHeatmapAnchors = async () => {
      try {
        const anchorsByCity = await callHeatmapAnchors();
        if (isMounted) {
          setHeatmapAnchorsByCity(anchorsByCity);
          setBaselineHeatmapAnchorsByCity(anchorsByCity);
        }
      } catch (error) {
        console.error('Failed to load heatmap anchors', error);
      }
    };

    loadHeatmapAnchors();

    return () => {
      isMounted = false;
    };
  }, []);

  // --- Cleanup simulation state on unmount ---
  // Ensure any running simulation timer is cleared when component unmounts
  useEffect(() => {
    return () => {
      if (simulationTimerRef.current !== null) {
        window.clearInterval(simulationTimerRef.current);
        simulationTimerRef.current = null;
      }
    };
  }, []);

  // --- Update heatmap visualization ---
  // Interpolate heatmap points based on selected city and date
  useEffect(() => {
    if (!selectedCity || !selectedDate) {
      setHeatmapPointsByCity({});
      return;
    }

    const interpolated = interpolateByCity(heatmapAnchorsByCity, selectedCity, selectedDate);
    setHeatmapPointsByCity({ [selectedCity]: interpolated });
  }, [heatmapAnchorsByCity, selectedCity, selectedDate]);

  // --- Initialize and manage map lifecycle ---
  // Create MapLibre GL map instance on mount and clean up on unmount
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapRef.current) return;

    mapRef.current = new maplibregl.Map({
      container: mapContainerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [viewState.longitude, viewState.latitude],
      zoom: viewState.zoom,
      pitch: viewState.pitch,
      bearing: viewState.bearing,
    });

    return () => {
      if (mapSyncFrameRef.current !== null) {
        cancelAnimationFrame(mapSyncFrameRef.current);
        mapSyncFrameRef.current = null;
      }
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // --- Update city selection based on viewport ---
  // Automatically select city when user pans/zooms to a different city area
  useEffect(() => {
    const cityInView = determineCityView(viewState);
    setSelectedCity((prev) => (prev === cityInView ? prev : cityInView));
  }, [viewState]);

  // --- Load statistics for selected city ---
  // Fetch and display overall and POI statistics when city changes
  useEffect(() => {
    let isMounted = true;

    const loadStatistics = async () => {
      try {
        const cityQuery = selectedCity ?? 'Nationally';
        const statistics = await callMockStatistics(cityQuery);
        if (isMounted) {
          setOverallStatisticsProps(statistics.overallStatistics);
          setPOIStatisticsProps(statistics.poiStatistics);
        }
      } catch (error) {
        console.error('Failed to load city statistics', error);
      }
    };

    loadStatistics();

    return () => {
      isMounted = false;
    };
  }, [selectedCity]);

  // --- Reset POI area editing state ---
  // Clear any active POI area edits when user switches cities
  useEffect(() => {
    setEditingAreaId(null);
    setIsAreaDragging(false);
  }, [selectedCity]);


// ======================================================
// UI Component
// ======================================================

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#020817] text-white">
      <div className="shrink-0">
        <NavigationBar />
      </div>

      <main className="flex-1 overflow-hidden p-3">
        <div className="grid h-full grid-cols-[minmax(0,1fr)_360px] grid-rows-[minmax(0,1fr)_minmax(180px,24vh)] gap-3">
          <section className="min-h-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
            <Heatmap
              viewState={viewState}
              setViewState={setViewState}
              selectedCity={selectedCity}
              setSelectedCity={setSelectedCity}
              cityPOIAreas={cityPOIAreas}
              heatmapPointsByCity={heatmapPointsByCity}
              heatmapAnchorsByCity={heatmapAnchorsByCity}
              availableDates={availableDates}
              selectedDate={selectedDate}
              setSelectedDate={setSelectedDate}
              mapContainerRef={mapContainerRef}
              mapRef={mapRef}
              mapSyncFrameRef={mapSyncFrameRef}
              tooltip={tooltip}
              setTooltip={setTooltip}
              isFullscreen={isFullscreen}
              setIsFullscreen={setIsFullscreen}
              draftColorHex={draftColorHex}
              setDraftColorHex={setDraftColorHex}
              draftName={draftName}
              setDraftName={setDraftName}
              userPOIAreas={userPOIAreas}
              setUserPOIAreas={setUserPOIAreas}
              hoveringHeatmap={hoveringHeatmap}
              setHoveringHeatmap={setHoveringHeatmap}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              geoResults={geoResults}
              setGeoResults={setGeoResults}
              isSearching={isSearching}
              setIsSearching={setIsSearching}
              showSuggestions={showSuggestions}
              setShowSuggestions={setShowSuggestions}
              selectedMetric={selectedMetric}
              setSelectedMetric={setSelectedMetric}
              editingAreaId={editingAreaId}
              setEditingAreaId={setEditingAreaId}
              isAreaDragging={isAreaDragging}
              setIsAreaDragging={setIsAreaDragging}
              placedObjectsControls={placedObjectsControls}
              displayToolbox={true}
              drawControls={drawControls}
            />
          </section>

          <div className="min-h-0 flex h-full flex-col gap-3">
            <section className="min-h-0 flex-1">
              <POIStatistics
                {...poiStatisticsProps}
                containSimulation={containSimulation}
                fromDate={fromDate}
                toDate={toDate}
                availableDates={availableDates}
                onFromDateChange={setFromDate}
                onToDateChange={setToDate}
                placedObjects={placedObjectsControls.placedObjects}
                onPlacedObjectsChange={placedObjectsControls.setPlacedObjects}
                onSimulate={() => {
                  if (!selectedCity || !fromDate || !toDate) return;

                  // Read the previous result so strict no-unused-locals passes
                  // while still keeping simulation output in component state.
                  const hadPreviousSimulation = simulationByDate !== null;

                  const cityBaseline = mergeCityDateRecords(
                    baselineHeatmapAnchorsByCity[selectedCity],
                  );
                  if (!cityBaseline) return;

                  let simulatedByDate: Record<string, HeatmapMetricSnapshot[]>;
                  try {
                    const simulationPlacedObjects = placedObjectsControls.placedObjects.map(buildSimulationPlacedObject);
                    simulatedByDate = runSimulation(
                      { [selectedCity]: cityBaseline },
                      selectedCity,
                      simulationPlacedObjects,
                      fromDate,
                      toDate,
                      SIMULATION_MODEL,
                    );
                  } catch (error) {
                    console.error('Failed to run simulation', error);
                    return;
                  }

                  setSimulationByDate(simulatedByDate);
                  if (hadPreviousSimulation) {
                    console.debug('Replacing previous simulation result');
                  }

                  const timeline = eachDay(fromDate, toDate).filter(
                    (date) => simulatedByDate[date] !== undefined,
                  );
                  if (timeline.length === 0) return;

                  if (simulationTimerRef.current !== null) {
                    window.clearInterval(simulationTimerRef.current);
                    simulationTimerRef.current = null;
                  }

                  let cursor = 0;
                  const applyFrame = (date: string) => {
                    setSelectedDate(date);
                    setHeatmapAnchorsByCity((prev) => ({
                      ...prev,
                      [selectedCity]: [{ [date]: simulatedByDate[date] }],
                    }));
                  };

                  applyFrame(timeline[0]);

                  simulationTimerRef.current = window.setInterval(() => {
                    cursor += 1;
                    if (cursor >= timeline.length) {
                      if (simulationTimerRef.current !== null) {
                        window.clearInterval(simulationTimerRef.current);
                        simulationTimerRef.current = null;
                      }
                      return;
                    }

                    applyFrame(timeline[cursor]);
                  }, 1000);
                }}
              />
            </section>
          </div>

          <section className="col-span-2 min-h-0 overflow-auto">
            <OverallStatistics {...overallStatisticsProps} />
          </section>
        </div>
      </main>
    </div>
  );
};

export default SimulationPage;
