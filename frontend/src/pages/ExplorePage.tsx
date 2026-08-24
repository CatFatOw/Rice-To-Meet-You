import React, { useEffect, useRef, useState } from 'react';
import { usePolygonDraw } from '../hooks/usePolygonDraw';
import maplibregl from 'maplibre-gl';
import Heatmap from '../components/Heatmap';
import NavigationBar from '../components/NavigationBar';
import OverallStatistics from '../components/OverallStatistics';
import POIStatistics from '../components/POIStatistics';
import {
  callAllCityPOIs,
  type CityPOIArea,
  type CityPOIAreaMap,
  type HeatmapMetricValue,
} from '../api/map';
import { callMockStatistics } from '../api/statistics';
import { fetchCitySurface } from '../api/gridInterpolation';
import type { MetricSurface } from '../types/heatmap';
import { determineCityView } from '../services/cityViews';
import type { ViewState } from '../types/viewState';
import type { GeocodeResult } from '../types/search';
import type { TooltipState } from '../types/components';
import type { OverallStatisticsProps, POIStatisticsProps } from '../types/statistics';
import { getHeatmapPointsByCityDateMetric } from '../api/map';

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
  const [displayedHeatmapPoints, setDisplayedHeatmapPoints] =
    useState<HeatmapMetricValue[]>([]);
  // One independently kriged surface per city for the active metric; these
  // drive the continuous map.
  const [metricSurfaces, setMetricSurfaces] = useState<MetricSurface[]>([]);

  // --- Date and timeline state ---
  // Controls the active date and simulation period.
  const [selectedDate, setSelectedDate] = useState<string | null>('2020-01-01');

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
  const [selectedMetric, setSelectedMetric] = useState<Record<string, string[]> | null>(null);

  // Active metric key on its own; the surface request only needs the key, and
  // it must be defined before the kriging effect's dependency array reads it.
  const selectedMetricKeyForSurface = selectedMetric ? Object.keys(selectedMetric)[0] : null;
  // The extra metrics the tooltip reports. Interpolated onto the surface's
  // lattice by the backend, never drawn.
  const selectedAdditionalMetrics = selectedMetric ? Object.values(selectedMetric)[0] : [];

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
        const poisByCity = await callAllCityPOIs();
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

  // --- Krige the displayed readings into the surface for the city in view ---
  // Exactly one surface is requested: the city the map is currently on. Several
  // host-city rectangles overlap (New York and New Jersey share 0.84 x 0.59
  // degrees, and both overlap Philadelphia), so asking for every city whose
  // rectangle contains a reading would stack two surfaces over the same ground
  // and let whichever drew last win. Fetching only what is in view also means
  // no kriging is done for cities nobody is looking at.
  //
  // The backend reads the readings, kriges them and returns only the lattice.
  // Explore has no simulation, so nothing here ever needs to send readings up.
  useEffect(() => {
    // Zoomed out past any one city, or nothing selected yet: no surface to
    // build. Say which precondition stopped it - a blank map is otherwise
    // impossible to tell apart from a broken one.
    if (!selectedCity || !selectedMetricKeyForSurface || !selectedDate) {
      console.debug('[ExplorePage] no interpolated surface:', {
        selectedCity: selectedCity ?? '(none - zoomed out past a city)',
        metric: selectedMetricKeyForSurface ?? '(none)',
        date: selectedDate ?? '(none)',
      });
      setMetricSurfaces([]);
      return;
    }

    const controller = new AbortController();
    let ignore = false;

    fetchCitySurface(selectedMetricKeyForSurface, selectedCity, selectedDate, {
      additionalMetrics: selectedAdditionalMetrics,
      signal: controller.signal,
    })
      .then((surface) => {
        if (ignore) return;
        console.debug('[ExplorePage] interpolated surface:', {
          city: selectedCity,
          date: selectedDate,
          readings: surface?.source_count ?? 0,
        });
        setMetricSurfaces(surface ? [surface] : []);
      })
      .catch((error) => {
        if (ignore || controller.signal.aborted) return;
        console.error('Failed to interpolate city surface', error);
        setMetricSurfaces([]);
      });

    return () => {
      ignore = true;
      controller.abort();
    };
  }, [selectedCity, selectedDate, selectedMetricKeyForSurface, selectedMetric]);


  // --- Update heatmap visualization ---
  // Load exactly the active metric slice from the backend.
  useEffect(() => {
    if (!selectedCity || !selectedDate || !selectedMetric) {
      setDisplayedHeatmapPoints([]);
      return;
    }

    const controller = new AbortController();
    let ignore = false;

    getHeatmapPointsByCityDateMetric(selectedCity, selectedDate, Object.keys(selectedMetric)[0], {
      additionalMetrics: Object.values(selectedMetric)[0],
      signal: controller.signal,
    })
      .then(({ points }) => {
        if (!ignore) {
          setDisplayedHeatmapPoints(points);
        }
      })
      .catch((error) => {
        if (ignore || controller.signal.aborted) return;
        console.error('Failed to load heatmap points', error);
        setDisplayedHeatmapPoints([]);
      });

    return () => {
      ignore = true;
      controller.abort();
    };
  }, [selectedCity, selectedDate, selectedMetric]);

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
              metricSurfaces={metricSurfaces}
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
