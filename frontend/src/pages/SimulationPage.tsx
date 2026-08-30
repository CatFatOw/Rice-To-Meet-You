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
  callAllCityPOIs,
  type CityPOIArea,
  type CityPOIAreaMap,
  type HeatmapMetricValue,
} from '../api/map';
import {
  callMockStatistics,
  fetchTopDestinations,
  getStatsInfo,
} from '../api/statistics';
import { determineCityView } from '../services/cityViews';
import { eachDay } from '../services/simulation';
import type { ViewState } from '../types/viewState';
import type { GeocodeResult } from '../types/search';
import type { TooltipState } from '../types/components';
import type {
  DistributionBucket,
  POIStatisticsProps,
  StatCardInfo,
  TopDestination,
} from '../types/statistics';
import useSimulationRunner from '../hooks/useSimulationRunner';
import { getSimulatedPointsByDate } from '../api/simulation';
import { fetchVisitorPOIs } from '../api/statistics';



import usePlacedObjects, {
  PLACED_OBJECT_CATEGORIES,
  type BasePlacedObject,
  type BasePlacedObjectCategorized,
  type PlacedObjectCategory,
} from '../hooks/usePlacedObjects';

import { getHeatmapPointsByCityDateMetric, getHeatRiskDataByCityDate, getVisitorDataByCityDate, getLocalTemperatureCByCityDate, getLocalTemperatureFByCityDate } from '../api/map';
import { getRiskDistributionByCityDate } from '../api/statistics';
import { fetchPlacedObjectsForCity } from '../api/tool';

function isPlacedObjectCategory(value: string): value is PlacedObjectCategory {
  return (PLACED_OBJECT_CATEGORIES as readonly string[]).includes(value);
}

const ARCHETYPE_CODE_TO_CATEGORY: Record<string, PlacedObjectCategory> = {
  vegetation: 'Vegetation',
  high_albedo_surface: 'High-albedo surface',
  shade_structure: 'Shade structure',
  evaporative_water: 'Evaporative / water',
};

function normalizeCategory(categoryOrArchetypeCode?: string): PlacedObjectCategory | null {
  if (!categoryOrArchetypeCode) return null;
  if (isPlacedObjectCategory(categoryOrArchetypeCode)) {
    return categoryOrArchetypeCode;
  }
  const normalizedCode = categoryOrArchetypeCode.trim().toLowerCase().replace(/[\s-]+/g, '_');
  return ARCHETYPE_CODE_TO_CATEGORY[normalizedCode] ?? null;
}

function toCategorizedPlacedObjects(
  placedObjects: BasePlacedObject[],
): BasePlacedObjectCategorized {
  const categorized = Object.fromEntries(
    PLACED_OBJECT_CATEGORIES.map((category) => [category, [] as BasePlacedObject[]]),
  ) as BasePlacedObjectCategorized;

  for (const object of placedObjects) {
    const category = normalizeCategory(object.category);
    if (!category) continue;
    categorized[category].push({
      ...object,
      category,
    });
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
  const [isPOIAreasLoading, setIsPOIAreasLoading] = useState(true);
  const [displayedHeatmapPoints, setDisplayedHeatmapPoints] =
    useState<HeatmapMetricValue[]>([]);
  const [isHeatmapPointsLoading, setIsHeatmapPointsLoading] = useState(false);
  const [baselineHeatmapPoints, setBaselineHeatmapPoints] =
    useState<HeatmapMetricValue[]>([]);

  // --- Date and timeline state ---
  // Controls the active date and simulation period.
  const [selectedDate, setSelectedDate] = useState<string | null>('2020-01-01');
  const [baselineSelectedDate, setBaselineSelectedDate] = useState<string | null>('2020-01-01');
  const [fromDate, setFromDate] = useState<string | null>('2020-01-01');
  const [toDate, setToDate] = useState<string | null>('2020-01-01');

  // --- Simulation state ---
  // Controls simulation data and playback.
  const [, setSimulationByDate] =
    useState<Record<string, HeatmapMetricValue[]> | null>(null);
  const [containSimulation] = useState(true);
  const [loadingSimulation, setLoadingSimulation] = useState(false);
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
  const [selectedMetric, setSelectedMetric] = useState<Record<string, string[]> | null>(  {
    avg_daily_visits: [
      "avg_daily_visits",
      "heat_risk_score",
    ],
  });
  const [summaryHeader, setSummaryHeader] =
    useState<{ title?: string; donutLabel?: string }>();
  const [topDestinations, setTopDestinations] = useState<TopDestination[]>();
  const [distribution, setDistribution] = useState<DistributionBucket[]>();
  const [statCardsInfo, setStatCardsInfo] = useState<StatCardInfo[]>();
  const [poiStatisticsProps, setPOIStatisticsProps] = useState<POIStatisticsProps>({ pois: [] });

  const { runTimeline, stop, isRunning } = useSimulationRunner({intervalMs: 3000});

  const selectedMetricKey = selectedMetric ? Object.keys(selectedMetric)[0] : null;
  const selectedAdditionalMetrics = selectedMetric ? Object.values(selectedMetric)[0] : [];


  const onStopSimulation = () => {
    stop();
    setSelectedDate(baselineSelectedDate);
    setDisplayedHeatmapPoints(baselineHeatmapPoints);
  };
  
  const getBaselinePointsByDate = async (
    fromDate: string,
    toDate: string,
    city: string,
    metric: string,
    selectedAdditionalMetrics: string[],
  ): Promise<Record<string, HeatmapMetricValue[]>> => {
    const baselinePointsByDate: Record<string, HeatmapMetricValue[]> = {};
    const dateList = eachDay(fromDate, toDate);
    for (const date of dateList){
      const result = await getHeatmapPointsByCityDateMetric(city, date, metric, {
        additionalMetrics: selectedAdditionalMetrics
    });
      baselinePointsByDate[date] = result.points;
      
    }
    return baselinePointsByDate;
  }

  const onStartSimulation = async () => {
    if (!selectedCity || !fromDate || !toDate) return;

    const metric = selectedMetricKey ?? Object.keys(availableMetrics[0] ?? {})[0];
  
    if (!selectedDate && !baselineSelectedDate) return;
    if (!metric) return;

    // 1. Simulate over the baseline points-by-date, then re-wrap each date's
    //    points into one frame per date for the timeline runner.
    let framesByDate: Record<string, HeatmapMetricValue[]>;
    setLoadingSimulation(true);
    try {

      const baselinePointsByDate = await getBaselinePointsByDate(fromDate, toDate, selectedCity, metric, selectedAdditionalMetrics)
      const placedObjects = placedObjectsControls.placedObjects.length > 0
        ? placedObjectsControls.placedObjects
        : await fetchPlacedObjectsForCity(fromDate, toDate, selectedCity);
      console.log('[Simulation] placed objects selected', {
        fromDate,
        toDate,
        city: selectedCity,
        count: placedObjects.length,
      });
      console.log(placedObjects)
      console.log(toCategorizedPlacedObjects(placedObjects))
      const simulatedPointsByDate = await getSimulatedPointsByDate(
        metric,
        baselinePointsByDate,
        toCategorizedPlacedObjects(placedObjects),
      );
      framesByDate = simulatedPointsByDate;

      // Log elements whose values changed compared to baseline
      const changedElements: Array<{
        date: string;
        index: number;
        coordinates: [number, number];
        baselineValue: number;
        simulatedValue: number;
        delta: number;
        point: HeatmapMetricValue;
      }> = [];

      for (const [date, simPoints] of Object.entries(simulatedPointsByDate)) {
        const basePoints = baselinePointsByDate[date] || [];
        simPoints.forEach((simPoint, index) => {
          const basePoint = basePoints[index];
          if (basePoint && Math.abs(simPoint.value - basePoint.value) > 1e-10) {
            changedElements.push({
              date,
              index,
              coordinates: simPoint.location_coordinates,
              baselineValue: basePoint.value,
              simulatedValue: simPoint.value,
              delta: simPoint.value - basePoint.value,
              point: simPoint,
            });
          }
        });
      }

      console.log('[Simulation] Elements with changed values:', changedElements);
      
    } catch (error) {
      console.error('Failed to simulate points by date', error);
      return;
    } finally {
      setLoadingSimulation(false);
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
      setIsPOIAreasLoading(true);
      try {
        const poisByCity = await callAllCityPOIs();
        if (isMounted) {
          setCityPOIAreas(poisByCity);
        }
      } catch (error) {
        console.error('Failed to load mock city POIs', error);
      } finally {
        if (isMounted) setIsPOIAreasLoading(false);
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
  if (!selectedCity || !selectedMetricKey || !selectedDate) {
    setIsHeatmapPointsLoading(false);
    setBaselineHeatmapPoints([]);
    setDisplayedHeatmapPoints([]);
    return;
  }

  const controller = new AbortController();
  let ignore = false;

  setIsHeatmapPointsLoading(true);

  const request =
    selectedMetricKey === "heat_risk_score"
      ? getHeatRiskDataByCityDate(
          selectedCity,
          selectedDate,
        ).then((points) => ({ points }))
      : selectedMetricKey === "avg_daily_visits"
        ? getVisitorDataByCityDate(
            selectedCity,
            selectedDate,
          ).then((points) => ({ points }))
        : selectedMetricKey === "local_temperature_c"
          ? getLocalTemperatureCByCityDate(selectedCity, selectedDate, {
              signal: controller.signal,
            }).then((points) => ({ points }))
          : selectedMetricKey === "local_temperature_f"
            ? getLocalTemperatureFByCityDate(selectedCity, selectedDate, {
                metric: "average_temperature_f",
                signal: controller.signal,
              }).then((points) => ({ points }))
            : getHeatmapPointsByCityDateMetric(
                selectedCity,
                selectedDate,
                selectedMetricKey,
                {
                  additionalMetrics: selectedAdditionalMetrics,
                  signal: controller.signal,
                },
              );

  request
    .then(({ points }) => {
      if (ignore) return;

      setBaselineHeatmapPoints(points);
      setDisplayedHeatmapPoints(points);
    })
    .catch((error) => {
      if (ignore || controller.signal.aborted) return;

      console.error("Failed to load baseline heatmap points", error);
      setBaselineHeatmapPoints([]);
      setDisplayedHeatmapPoints([]);
    })
    .finally(() => {
      if (!ignore) {
        setIsHeatmapPointsLoading(false);
      }
    });

  return () => {
    ignore = true;
    controller.abort();
  };
}, [
  selectedAdditionalMetrics,
  selectedCity,
  selectedDate,
  selectedMetricKey,
]);
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
          setSummaryHeader({
            title: statistics.overallStatistics.title,
            donutLabel: statistics.overallStatistics.donutLabel,
          });

          const liveTopDestinations = selectedCity && selectedDate
            ? await fetchTopDestinations(selectedCity, selectedDate)
            : statistics.overallStatistics.topDestinations;

          setTopDestinations(
            liveTopDestinations && liveTopDestinations.length > 0
              ? liveTopDestinations
              : statistics.overallStatistics.topDestinations,
          );

          setPOIStatisticsProps({ ...statistics.poiStatistics, pois: [] });

          if (selectedCity && selectedDate) {
            const visitorPOIs = await fetchVisitorPOIs(selectedCity, selectedDate);
            if (isMounted) {
              setPOIStatisticsProps((prev) => ({
                ...prev,
                pois: visitorPOIs.map((poi) => ({
                  name: poi.name,
                  type: poi.streetAddress,
                  heatRisk: poi.heatRisk ?? 0,
                  visitors: poi.visitors,
                })),
              }));
            }
          }
        }
      } catch (error) {
        console.error('Failed to load city statistics', error);
        if (isMounted) {
          setPOIStatisticsProps((prev) => ({ ...prev, pois: [] }));
        }
      }
    };

    loadStatistics();

    return () => {
      isMounted = false;
    };
  }, [selectedCity, selectedDate]);

  // --- Load live summary cards ---
  // Keep card values tied to the selected city and date.
  useEffect(() => {
    if (!selectedCity || !selectedDate) {
      setStatCardsInfo(undefined);
      return;
    }

    const controller = new AbortController();
    let isMounted = true;

    getStatsInfo(selectedCity, selectedDate, controller.signal)
      .then((statsInfo) => {
        if (isMounted) setStatCardsInfo(statsInfo);
      })
      .catch((error) => {
        if (isMounted && !controller.signal.aborted) {
          console.error('Failed to load summary statistics', error);
          setStatCardsInfo(undefined);
        }
      });

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [selectedCity, selectedDate]);

  // --- Load heat-risk distribution ---
  // Keep the donut distribution tied to the selected city and date.
  useEffect(() => {
    if (!selectedCity || !selectedDate) {
      setDistribution(undefined);
      return;
    }

    let isMounted = true;

    getRiskDistributionByCityDate(selectedCity, selectedDate)
      .then((riskDistribution) => {
        if (isMounted) setDistribution(riskDistribution);
      })
      .catch((error) => {
        console.error('Failed to load heat-risk distribution', error);
        if (isMounted) setDistribution(undefined);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedCity, selectedDate]);

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
              setBaselineSelectedDate={setBaselineSelectedDate}
              isLoading={!isRunning && (isPOIAreasLoading || isHeatmapPointsLoading)}
              isRunning={isRunning}
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
                loadingSimulation={loadingSimulation}
              />
            </section>
          </div>

          <section className="col-span-2 min-h-0 overflow-auto">
            <OverallStatistics
              {...summaryHeader}
              topDestinations={topDestinations}
              distribution={distribution}
              statCardsInfo={statCardsInfo}
            />
          </section>
        </div>
      </main>
    </div>
  );
};

export default SimulationPage;
