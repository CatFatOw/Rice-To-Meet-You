import React, { useEffect, useRef, useState, useMemo } from 'react';
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
import { determineCityView } from '../services/cityViews';
import { eachDay } from '../services/simulation';
import type { ViewState } from '../types/viewState';
import type { GeocodeResult } from '../types/search';
import type { TooltipState } from '../types/components';
import type { OverallStatisticsProps, POIStatisticsProps } from '../types/statistics';
import useSimulationRunner from '../hooks/useSimulationRunner';
import {
  runDiminishingReturnSimulation,
  type SimulationMode,
  type SimulationFeedback,
} from '../api/diminishingSimulation';
import type { HeatmapPointsByDate } from '../types/heatmap';

import usePlacedObjects, {
  PLACED_OBJECT_CATEGORIES,
  type BasePlacedObject,
  type BasePlacedObjectCategorized,
  type PlacedObjectCategory,
} from '../hooks/usePlacedObjects';

function mergeCityDateRecords(records: HeatmapMetricPointByCity[string] | undefined) {
  if (!records || records.length === 0) return null;
  return records.reduce<Record<string, HeatmapMetricSnapshot[]>>(
    (acc, byDate) => ({ ...acc, ...byDate }),
    {},
  );
}

// Flatten merged snapshots down to one metric's points per date — the shape
// getSimulatedPointsByDate consumes.
function toHeatmapPointsByDate(
  records: Record<string, HeatmapMetricSnapshot[]> | null,
  metric: string | null,
): HeatmapPointsByDate {
  if (!records || !metric) return {};

  const result: HeatmapPointsByDate = {};
  for (const [date, snapshots] of Object.entries(records)) {
    const snapshot = snapshots.find((s) => s.metric === metric);
    if (snapshot) {
      result[date] = snapshot.points;
    }
  }
  return result;
}

function isPlacedObjectCategory(value: string): value is PlacedObjectCategory {
  return (PLACED_OBJECT_CATEGORIES as readonly string[]).includes(value);
}

function toCategorizedPlacedObjects(
  placedObjects: BasePlacedObject[],
): BasePlacedObjectCategorized {
  const categorized = Object.fromEntries(
    PLACED_OBJECT_CATEGORIES.map((category) => [category, [] as BasePlacedObject[]]),
  ) as BasePlacedObjectCategorized;

  for (const object of placedObjects) {
    const category = object.category;
    if (!category || !isPlacedObjectCategory(category)) continue;
    categorized[category].push(object);
  }

  return categorized;
}

// A fixed Houston scenario for quick visual and regression testing. The three
// footprints intentionally share the Rice Quad sample points: tree + fountain
// is the beneficial pairing, while the cool pavement demonstrates the less
// complementary reflective-surface pairing in context-aware mode.
const OVERLAP_DEMO_OBJECTS: BasePlacedObject[] = [
  {
    id: 'demo-rice-trees',
    type: 'street_trees',
    name: 'Demo: Street Trees',
    category: 'Vegetation',
    color: '#22c55e',
    activeFrom: '2026-07-05',
    activeTo: '2026-07-08',
    geometry: { kind: 'polygon', ring: [[-95.403, 29.7158], [-95.3985, 29.7158], [-95.3985, 29.719], [-95.403, 29.719]] },
    params: { coverPct: 0.75, lai: 4.5, irrigation: 0.8 },
  },
  {
    id: 'demo-rice-fountain',
    type: 'fountain',
    name: 'Demo: Fountain',
    category: 'Evaporative / water',
    color: '#0ea5e9',
    activeFrom: '2026-07-05',
    activeTo: '2026-07-08',
    geometry: { kind: 'point', longitude: -95.4008, latitude: 29.7173 },
    params: { flowRate: 45, radius: 65, activeFraction: 1 },
  },
  {
    id: 'demo-rice-cool-pavement',
    type: 'cool_pavement',
    name: 'Demo: Cool Pavement',
    category: 'High-albedo surface',
    color: '#e2e8f0',
    activeFrom: '2026-07-05',
    activeTo: '2026-07-08',
    geometry: { kind: 'polygon', ring: [[-95.4024, 29.7172], [-95.4012, 29.7172], [-95.4012, 29.7184], [-95.4024, 29.7184]] },
    params: { deltaAlbedo: 0.3, coverPct: 0.35 },
  },
];

const DEMO_DATES = ['2026-07-05', '2026-07-06', '2026-07-07', '2026-07-08'];
const DEMO_TEMPERATURE_POINTS: HeatmapPointsByDate = Object.fromEntries(
  DEMO_DATES.map((date, dayOffset) => [date, [
    {
      value: 36.4 + dayOffset * 0.2,
      location_name: 'Demo A: tree + water synergy',
      location_coordinates: [-95.4008, 29.7173] as [number, number],
      individual_metrics: { avg_temperature_c: `${(36.4 + dayOffset * 0.2).toFixed(1)}°C`, relative_humidity: '55%' },
    },
    {
      value: 35.9 + dayOffset * 0.2,
      location_name: 'Demo B: tree + reflective pavement',
      location_coordinates: [-95.4017, 29.7178] as [number, number],
      individual_metrics: { avg_temperature_c: `${(35.9 + dayOffset * 0.2).toFixed(1)}°C`, relative_humidity: '55%' },
    },
    {
      value: 37.1 + dayOffset * 0.2,
      location_name: 'Demo control point',
      location_coordinates: [-95.3968, 29.7155] as [number, number],
      individual_metrics: { avg_temperature_c: `${(37.1 + dayOffset * 0.2).toFixed(1)}°C`, relative_humidity: '55%' },
    },
  ]]),
);

function formatSimulationFeedback(feedback: SimulationFeedback): string {
  if (feedback.affectedPoints === 0) {
    return [
      'No heatmap sample points were changed.',
      'An intervention must be active and cover at least one sampled map point; evaporative interventions also need a point inside their configured radius.',
      `Not contributing: ${feedback.interventionsWithoutEffect.join(', ') || 'none'}.`,
    ].join('\n');
  }

  const overlapLine = feedback.overlapPoints > 0
    ? `${feedback.overlapPoints} sample points receive cooling from multiple interventions (${feedback.maxObjectsAtPoint} at the busiest point): ${feedback.overlapLocations.slice(0, 4).join(', ')}${feedback.overlapLocations.length > 4 ? ', …' : ''}.`
    : 'No sampled map point is inside more than one intervention influence area. Visual shapes can overlap without containing the same sampled map point.';

  return [
    `Model: ${feedback.mode === 'contextual' ? 'context-aware combinations' : 'standard diminishing returns'}.`,
    `Diminishing-return simulation applied to ${feedback.affectedPoints} heatmap sample-point records at: ${feedback.affectedLocations.slice(0, 4).join(', ')}${feedback.affectedLocations.length > 4 ? ', …' : ''}.`,
    overlapLine,
    `Contributing interventions: ${feedback.contributingInterventions.join(', ') || 'none'}.`,
    feedback.interventionsWithoutEffect.length
      ? `No sampled-point effect from: ${feedback.interventionsWithoutEffect.join(', ')}. Check its active dates, parameters, and footprint/radius.`
      : 'Every placed intervention affected at least one sampled map point.',
    `Average cooling: ${feedback.averageCoolingC.toFixed(2)}°C. Peak carrying-capacity use: ${feedback.maxCapacityUsed.toFixed(0)}% (the ceiling prevented cooling from exceeding the local weather limit).`,
    'Where interventions share a point, their cooling is combined with the diminishing-return formula, not added linearly.',
    feedback.contextualInteractions.length
      ? `Context effects applied: ${feedback.contextualInteractions.join(' ')}`
      : feedback.mode === 'contextual'
        ? 'No configured context pair shared a sampled point in this run.'
        : 'Switch to context-aware combinations to apply tree/water and tree/reflective-surface interaction rules.',
    'Map key: cyan rings mark the affected union of sample points; magenta rings mark overlap points.',
  ].join('\n');
}


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
  const [baselineSelectedDate] = useState<string | null>('2026-07-07');
  const [fromDate, setFromDate] = useState<string | null>('2026-07-05');
  const [toDate, setToDate] = useState<string | null>('2026-07-08');
  const availableDates = ['2026-07-05', '2026-07-06', '2026-07-07', '2026-07-08'];

  // --- Simulation state ---
  // Controls simulation data and playback.
  const [, setSimulationByDate] =
    useState<Record<string, HeatmapMetricSnapshot[]> | null>(null);
  const [containSimulation] = useState(true);
  const simulationTimerRef = useRef<number | null>(null);

  // --- Placed objects (toolbox items) ---
  // Controls draggable toolbox objects placed on the map.
  const placedObjectsControls = usePlacedObjects({
    mapRef,
    mapContainerRef,
  });

  // --- POI area drawing state ---
  // Controls the creation and management of user-drawn POI areas.
  const drawControls = usePolygonDraw(3) as unknown as {
    isDrawing: boolean;
    setIsDrawing: React.Dispatch<React.SetStateAction<boolean>>;
    draftPoints: Ring;
    setDraftPoints: React.Dispatch<React.SetStateAction<Ring>>;
    draftColor: string;
    setDraftColor: React.Dispatch<React.SetStateAction<string>>;
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
  const [simulationFeedback, setSimulationFeedback] = useState<string | null>(null);
  const [simulationMode, setSimulationMode] = useState<SimulationMode>('standard');
  const [isHardcodedDemoActive, setIsHardcodedDemoActive] = useState(false);
  const [runDemoWhenReady, setRunDemoWhenReady] = useState(false);

  const { runTimeline, stop, isRunning } = useSimulationRunner();


  const heatmapPointsByDate = useMemo<HeatmapPointsByDate>(() => {
    if (isHardcodedDemoActive) return DEMO_TEMPERATURE_POINTS;
    if (!selectedCity) return {};
    const records = mergeCityDateRecords(baselineHeatmapAnchorsByCity[selectedCity]);
    return toHeatmapPointsByDate(records, selectedMetric ?? 'temperature');
  }, [baselineHeatmapAnchorsByCity, isHardcodedDemoActive, selectedCity, selectedMetric]);

  

  
  useEffect(() => {
    console.log(heatmapPointsByDate)

  }, [heatmapPointsByDate]) 

  const onStopSimulation = () => {
    stop();
    if (isHardcodedDemoActive) {
      setHeatmapPointsByCity({ Houston: [{ metric: 'temperature', points: DEMO_TEMPERATURE_POINTS['2026-07-05'] }] });
      setSelectedDate('2026-07-05');
    } else {
      setHeatmapAnchorsByCity(baselineHeatmapAnchorsByCity);
      setSelectedDate(baselineSelectedDate);
    }
    setSimulationFeedback(null);
  };

  const onLoadDemoScenario = () => {
    placedObjectsControls.setPlacedObjects(OVERLAP_DEMO_OBJECTS);
    setIsHardcodedDemoActive(true);
    setRunDemoWhenReady(true);
    setSimulationMode('contextual');
    setSelectedCity('Houston');
    setSelectedMetric('temperature');
    setSelectedDate('2026-07-05');
    setViewState({ longitude: -95.4008, latitude: 29.7173, zoom: 15.2, pitch: 0, bearing: 0 });
    setHeatmapPointsByCity({ Houston: [{ metric: 'temperature', points: DEMO_TEMPERATURE_POINTS['2026-07-05'] }] });
    setSimulationFeedback('Loading live hardcoded demo: green = tree + water synergy, amber = tree + reflective pavement restraint, grey = unchanged control.');
  };

  const onStartSimulation = async () => {
    if (!selectedCity || !fromDate || !toDate) return;

    const metric = selectedMetric ?? 'temperature';

    // 1. Simulate over the baseline points-by-date, then re-wrap each date's
    //    points into the { metric, points } snapshot shape used as a frame.
    let framesByDate: Record<string, HeatmapMetricSnapshot[]>;
    // console.log(`Metric: ${metric}`)
    // console.log(`placedObjets initial: ${JSON.stringify(placedObjectsControls.placedObjects)}`)
    // console.log(`placedObjets: ${JSON.stringify(toCategorizedPlacedObjects(placedObjectsControls.placedObjects))}`)
    try {
      const simulation = await runDiminishingReturnSimulation(
        metric,
        heatmapPointsByDate,
        toCategorizedPlacedObjects(placedObjectsControls.placedObjects),
        simulationMode,
      );
      const { feedback, pointsByDate: simulatedPointsByDate } = simulation;
      setSimulationFeedback(formatSimulationFeedback(feedback));

      framesByDate = Object.fromEntries(
        Object.entries(simulatedPointsByDate).map(([date, points]) => [
          date,
          [{ metric, points }] as HeatmapMetricSnapshot[],
        ]),
      );
    } catch (error) {
      console.error('Failed to simulate points by date', error);
      return;
    }


    // 2. Play the timeline. runTimeline calls stop() first (resets timer +
    //    isRunning), stores the result via onStart, then updates
    //    heatmapAnchorsByCity per frame off the previous value.
    runTimeline<HeatmapMetricSnapshot[]>({
      fromDate,
      toDate,
      framesByDate,
      eachDay,
      onStart: (frames) => setSimulationByDate(frames),
      onFrame: (date, frame) => {
        setSelectedDate(date);
        setHeatmapAnchorsByCity((prev) => ({
          ...prev,
          [selectedCity]: [{ [date]: frame }],
        }));
      },
      onComplete: () => {
        // Keep the final simulated frame visible so the changed interpolation
        // points and overlap markers can be inspected. Stop restores baseline.
        setSimulationFeedback((current) => `${current ?? ''}\nSimulation complete. Final changed points remain on the map; click Stop to restore the baseline.`);
      }
    });

  };

  // The hardcoded demo is intentionally hands-off: loading it immediately
  // starts playback so users can see the before/after interpolation change.
  useEffect(() => {
    if (!runDemoWhenReady || !isHardcodedDemoActive || !selectedCity) return;
    setRunDemoWhenReady(false);
    void onStartSimulation();
  }, [isHardcodedDemoActive, runDemoWhenReady, selectedCity]);





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
    if (isHardcodedDemoActive && selectedCity === 'Houston' && selectedDate) {
      setHeatmapPointsByCity({
        Houston: [{ metric: 'temperature', points: DEMO_TEMPERATURE_POINTS[selectedDate] ?? DEMO_TEMPERATURE_POINTS['2026-07-05'] }],
      });
      return;
    }
    if (!selectedCity || !selectedDate) {
      setHeatmapPointsByCity({});
      return;
    }

    // Raw anchors for the selected city/date — no interpolation.
    const snapshots =
      mergeCityDateRecords(heatmapAnchorsByCity[selectedCity])?.[selectedDate] ?? [];
    setHeatmapPointsByCity({ [selectedCity]: snapshots });
  }, [heatmapAnchorsByCity, isHardcodedDemoActive, selectedCity, selectedDate]);

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
              preservePlacedObjects={isHardcodedDemoActive}
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
                onPlacedObjectsChange={(placedObjects) => placedObjectsControls.setPlacedObjects(placedObjects)}
                onStartSimulation={onStartSimulation}
                onStopSimulation={onStopSimulation}
                isRunning={isRunning}
                simulationFeedback={simulationFeedback}
                simulationMode={simulationMode}
                onSimulationModeChange={setSimulationMode}
                onLoadDemoScenario={onLoadDemoScenario}
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
