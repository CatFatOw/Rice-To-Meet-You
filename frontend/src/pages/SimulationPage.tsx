import React, { useEffect, useRef, useState } from 'react';
import { usePolygonDraw, type Ring } from '../hooks/usePolygonDraw';
import maplibregl from 'maplibre-gl';
import Heatmap from '../components/Heatmap';
import NavigationBar from '../components/NavigationBar';
import OverallStatistics from '../components/OverallStatistics';
import POIStatistics from '../components/POIStatistics';
import {
  availableDates,
  availableMetrics,
  callMockAllCityPOIs,
  type CityPOIArea,
  type CityPOIAreaMap,
  type HeatmapMetricValue,
} from '../api/map';
import { callMockStatistics } from '../api/statistics';
import { determineCityView } from '../services/cityViews';
import { eachDay } from '../services/simulation';
import type { ViewState } from '../types/viewState';
import type { GeocodeResult } from '../types/search';
import type { TooltipState } from '../types/components';
import type { OverallStatisticsProps, POIStatisticsProps } from '../types/statistics';
import useSimulationRunner from '../hooks/useSimulationRunner';
import { getSimulatedPointsByDate } from '../api/simulation';

import usePlacedObjects, {
  PLACED_OBJECT_CATEGORIES,
  type BasePlacedObject,
  type BasePlacedObjectCategorized,
  type PlacedObjectCategory,
} from '../hooks/usePlacedObjects';

import { getHeatmapPointsByCityDateMetric } from '../api/map';

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
  const [displayedHeatmapPoints, setDisplayedHeatmapPoints] =
    useState<HeatmapMetricValue[]>([]);
  const [baselineHeatmapPoints, setBaselineHeatmapPoints] =
    useState<HeatmapMetricValue[]>([]);

  // --- Date and timeline state ---
  // Controls the active date and simulation period.
  const [selectedDate, setSelectedDate] = useState<string | null>('2020-01-01');
  const [baselineSelectedDate] = useState<string | null>('2020-01-01');
  const [fromDate, setFromDate] = useState<string | null>('2020-01-01');
  const [toDate, setToDate] = useState<string | null>('2020-01-01');

  // --- Simulation state ---
  // Controls simulation data and playback.
  const [, setSimulationByDate] =
    useState<Record<string, HeatmapMetricValue[]> | null>(null);
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

  const { runTimeline, stop, isRunning } = useSimulationRunner();

  const onStopSimulation = () => {
    stop();
    setSelectedDate(baselineSelectedDate);
    setDisplayedHeatmapPoints(baselineHeatmapPoints);
  };

  const onStartSimulation = async () => {
    if (!selectedCity || !fromDate || !toDate) return;

    const metric = selectedMetric ?? availableMetrics[0];
    const date = selectedDate ?? baselineSelectedDate;
    if (!date) return;

    // 1. Simulate over the baseline points-by-date, then re-wrap each date's
    //    points into one frame per date for the timeline runner.
    let framesByDate: Record<string, HeatmapMetricValue[]>;
    try {
      const simulatedPointsByDate = await getSimulatedPointsByDate(
        metric,
        { [date]: baselineHeatmapPoints },
        toCategorizedPlacedObjects(placedObjectsControls.placedObjects),
      );
      framesByDate = simulatedPointsByDate;
    } catch (error) {
      console.error('Failed to simulate points by date', error);
      return;
    }
    // 2. Play the timeline. runTimeline calls stop() first (resets timer +
    //    isRunning), stores the result via onStart, then updates the page-owned
    //    displayed point set each frame.
    runTimeline<HeatmapMetricValue[]>({
      fromDate,
      toDate,
      framesByDate,
      eachDay,
      onStart: (frames) => setSimulationByDate(frames),
      onFrame: (date, frame) => {
        setSelectedDate(date);
        setDisplayedHeatmapPoints(frame);
      },
      onComplete: () => {
        setSelectedDate(baselineSelectedDate);
        setDisplayedHeatmapPoints(baselineHeatmapPoints);
      }
    });

  };





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
  // Load the current city/date/metric slice from the backend.
  useEffect(() => {
    if (!selectedCity || !selectedMetric || !selectedDate) {
      setBaselineHeatmapPoints([]);
      setDisplayedHeatmapPoints([]);
      return;
    }

    const controller = new AbortController();
    let ignore = false;

    getHeatmapPointsByCityDateMetric(
      selectedCity,
      selectedDate,
      selectedMetric,
      {
        additionalMetrics: [],
        signal: controller.signal,
      },
    )
      .then(({ points }) => {
        if (ignore) return;
        setBaselineHeatmapPoints(points);
      })
      .catch((error) => {
        if (ignore || controller.signal.aborted) return;
        console.error('Failed to load baseline heatmap point', error);
        setBaselineHeatmapPoints([]);
        setDisplayedHeatmapPoints([]);
      });

    return () => {
      ignore = true;
      controller.abort();
    };
  }, [selectedCity, selectedDate, selectedMetric]);

  useEffect(() => {
    console.log(displayedHeatmapPoints)

  }, [displayedHeatmapPoints])

 

  useEffect(() => {
    if (isRunning) return;
    setDisplayedHeatmapPoints(baselineHeatmapPoints);
  }, [baselineHeatmapPoints, isRunning]);

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
              displayedHeatmapPoints={displayedHeatmapPoints}
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
                onPlacedObjectsChange={(placedObjects) => placedObjectsControls.setPlacedObjects(placedObjects)}
                onStartSimulation={onStartSimulation}
                onStopSimulation={onStopSimulation}
                isRunning={isRunning}
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
