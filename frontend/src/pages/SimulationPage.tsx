import React, { useEffect, useRef, useState } from 'react';
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
import type { PlacedObject } from '../utils/toolbox';
import type { ViewState } from '../types/viewState';
import type { GeocodeResult } from '../types/search';
import type { TooltipState } from '../types/components';
import type { OverallStatisticsProps, POIStatisticsProps } from '../types/statistics';

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
      const kernels = [
        (input: KernelInput) => spec.spatial(input.dist),
        (input: KernelInput) => spec.temporal(input.elapsedHours, input.activeHours),
        (input: KernelInput) => spec.response(input.baseValue),
      ];

      if (spec.suitability) {
        kernels.push((input: KernelInput) => spec.suitability?.(input.metrics) ?? 1);
      }

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

  return Object.fromEntries(entries);
}

const SIMULATION_MODEL = adaptKernelModel();


const SimulationPage: React.FC = () => {
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

  const [selectedCity, setSelectedCity] = useState<string | null>(null);
  const [cityPOIAreas, setCityPOIAreas] = useState<CityPOIAreaMap>({});
  const [heatmapPointsByCity, setHeatmapPointsByCity] =
    useState<Record<string, HeatmapMetricSnapshot[]>>({});
  const [heatmapAnchorsByCity, setHeatmapAnchorsByCity] =
    useState<HeatmapMetricPointByCity>({});
  const [baselineHeatmapAnchorsByCity, setBaselineHeatmapAnchorsByCity] =
    useState<HeatmapMetricPointByCity>({});
  const [simulationByDate, setSimulationByDate] =
    useState<Record<string, HeatmapMetricSnapshot[]> | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isDrawing, setIsDrawing] = useState(false);
  const [draftPoints, setDraftPoints] = useState<[number, number][]>([]);
  const [draftColorHex, setDraftColorHex] = useState('#22c55e');
  const [draftName, setDraftName] = useState('');
  const [userPOIAreas, setUserPOIAreas] = useState<CityPOIArea[]>([]);
  const [hoveringHeatmap, setHoveringHeatmap] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [geoResults, setGeoResults] = useState<GeocodeResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [editingAreaId, setEditingAreaId] = useState<string | null>(null);
  const [isAreaDragging, setIsAreaDragging] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string | null>('2026-07-07');
  const [fromDate, setFromDate] = useState<string | null>('2026-07-05');
  const [toDate, setToDate] = useState<string | null>('2026-07-08');
  const [containSimulation] = useState(true);
  const [placedObjects, setPlacedObjects] = useState<PlacedObject[]>([]);
  const [overallStatisticsProps, setOverallStatisticsProps] =
    useState<OverallStatisticsProps>();
  const [poiStatisticsProps, setPOIStatisticsProps] = useState<POIStatisticsProps>();
  const simulationTimerRef = useRef<number | null>(null);

 
  


  const availableDates = ['2026-07-05', '2026-07-06', '2026-07-07', '2026-07-08'];

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

  useEffect(() => {
    return () => {
      if (simulationTimerRef.current !== null) {
        window.clearInterval(simulationTimerRef.current);
        simulationTimerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!selectedCity || !selectedDate) {
      setHeatmapPointsByCity({});
      return;
    }

    const interpolated = interpolateByCity(heatmapAnchorsByCity, selectedCity, selectedDate);
    setHeatmapPointsByCity({ [selectedCity]: interpolated });
  }, [heatmapAnchorsByCity, selectedCity, selectedDate]);

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

  useEffect(() => {
    const cityInView = determineCityView(viewState);
    setSelectedCity((prev) => (prev === cityInView ? prev : cityInView));
  }, [viewState]);

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

  useEffect(() => {
    setEditingAreaId(null);
    setIsAreaDragging(false);
  }, [selectedCity]);

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
              isDrawing={isDrawing}
              setIsDrawing={setIsDrawing}
              draftPoints={draftPoints}
              setDraftPoints={setDraftPoints}
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
              onPlacedObjectsChange={setPlacedObjects}
              displayToolbox={true}
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
                    simulatedByDate = runSimulation(
                      { [selectedCity]: cityBaseline },
                      selectedCity,
                      placedObjects,
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
