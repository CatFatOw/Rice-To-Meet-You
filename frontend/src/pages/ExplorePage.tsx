import React, { useEffect, useRef, useState } from 'react';
import { usePolygonDraw } from '../hooks/usePolygonDraw';
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

const ExplorePage: React.FC = () => {


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

  // --- Date and timeline state ---
  // Controls the active date and simulation period.
  const [selectedDate, setSelectedDate] = useState<string | null>('2026-07-07');
  const availableDates = ['2026-07-05', '2026-07-06', '2026-07-07', '2026-07-08'];

  // --- POI area drawing state ---
  // Controls the creation and management of user-drawn POI areas.
  const drawControls = usePolygonDraw(3);
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
  const [containSimulation] = useState(false);
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

  // Fetch heatmap anchor points from API on component mount
  useEffect(() => {
    let isMounted = true;

    const loadHeatmapAnchors = async () => {
      try {
        const anchorsByCity = await callHeatmapAnchors();
        if (isMounted) {
          setHeatmapAnchorsByCity(anchorsByCity);
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

  // --- Update heatmap visualization ---
  // Raw anchors for the selected city/date — no interpolation (matches SimulationPage)
  useEffect(() => {
    if (!selectedCity || !selectedDate) {
      setHeatmapPointsByCity({});
      return;
    }

    const snapshots =
      mergeCityDateRecords(heatmapAnchorsByCity[selectedCity])?.[selectedDate] ?? [];
    setHeatmapPointsByCity({ [selectedCity]: snapshots });
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
              drawControls={drawControls}
            />
          </section>

          <div className="min-h-0 flex h-full flex-col gap-3">
            <section className="min-h-0 flex-1">
              <POIStatistics
                {...poiStatisticsProps}
                containSimulation={containSimulation}
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

export default ExplorePage;
