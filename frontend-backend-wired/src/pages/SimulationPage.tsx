import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import Heatmap, { type GeocodeResult, type TooltipState } from '../components/Heatmap';
import NavigationBar from '../components/NavigationBar';
import OverallStatistics, { type OverallStatisticsProps } from '../components/OverallStatistics';
import POIStatistics, { type POIStatisticsProps } from '../components/POIStatistics';
import {
  callHeatmapMetricsGrid,
  callMockLocationPOIs,
  type CityPOIArea,
  type HeatmapMetricGridResponse,
  type TimelineFilter,
} from '../api/map';
import { callMockStatistics } from '../api/statistics';
import { determineCityView } from '../utils/cityViews';

interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}


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
  const [cityPOIAreas, setCityPOIAreas] = useState<CityPOIArea[]>([]);
  const [metricGridsByCity, setMetricGridsByCity] =
    useState<HeatmapMetricGridResponse>({});
  const [timelineFilter, setTimelineFilter] = useState<TimelineFilter>({});
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [is3DMode, setIs3DMode] = useState(false);
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
  const [overallStatisticsProps, setOverallStatisticsProps] =
    useState<OverallStatisticsProps>();
  const [poiStatisticsProps, setPOIStatisticsProps] = useState<POIStatisticsProps>();

  useEffect(() => {
    let isMounted = true;

    const loadMockPOIs = async () => {
      try {
        const pois = await callMockLocationPOIs();
        if (isMounted) {
          setCityPOIAreas(pois);
        }
      } catch (error) {
        console.error('Failed to load mock location POIs', error);
      }
    };

    loadMockPOIs();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadMetricGrids = async () => {
      try {
        const gridsByCity = await callHeatmapMetricsGrid(timelineFilter);
        if (isMounted) {
          setMetricGridsByCity(gridsByCity);
        }
      } catch (error) {
        console.error('Failed to load heatmap metric grids', error);
      }
    };

    loadMetricGrids();

    return () => {
      isMounted = false;
    };
  }, [timelineFilter.year, timelineFilter.month, timelineFilter.season]);

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

    mapRef.current.on('load', () => {
      const map = mapRef.current;
      if (!map) return;
      try {
        map.addLayer({ id: 'simulation-3d-buildings', type: 'fill-extrusion', source: 'carto', 'source-layer': 'building', minzoom: 14, paint: { 'fill-extrusion-color': '#334155', 'fill-extrusion-height': ['coalesce', ['get', 'render_height'], ['get', 'height'], 9], 'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], ['get', 'min_height'], 0], 'fill-extrusion-opacity': 0.88 }, layout: { visibility: 'none' } });
      } catch { /* Basemap has no building source; 2D remains available. */ }
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
    const map = mapRef.current;
    if (!map) return;
    const nextPitch = is3DMode ? 58 : 0;
    const nextBearing = is3DMode ? -24 : 0;
    setViewState((previous) => ({
      ...previous,
      pitch: nextPitch,
      bearing: nextBearing,
      zoom: is3DMode ? Math.max(previous.zoom, 14.5) : previous.zoom,
    }));
    const apply = () => {
      if (map.getLayer('simulation-3d-buildings')) map.setLayoutProperty('simulation-3d-buildings', 'visibility', is3DMode ? 'visible' : 'none');
      map.easeTo({ pitch: nextPitch, bearing: nextBearing, zoom: is3DMode ? Math.max(map.getZoom(), 14.5) : map.getZoom(), duration: 450 });
    };
    if (map.isStyleLoaded()) apply(); else map.once('load', apply);
  }, [is3DMode]);

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
          <section className="relative min-h-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
            <div className="absolute left-3 top-3 z-30 flex gap-2 rounded-lg border border-slate-700 bg-slate-950/95 p-2 text-xs shadow-lg">
              <select aria-label="Heatmap year" value={timelineFilter.year ?? ''} onChange={(e) => setTimelineFilter((f) => ({ ...f, year: e.target.value ? Number(e.target.value) : undefined }))} className="rounded bg-slate-800 px-2 py-1">
                <option value="">Latest snapshot</option>{[2020, 2021, 2022, 2023, 2024, 2025, 2026].map((year) => <option key={year} value={year}>{year}</option>)}
              </select>
              <select aria-label="Heatmap month" value={timelineFilter.month ?? ''} onChange={(e) => setTimelineFilter((f) => ({ ...f, month: e.target.value ? Number(e.target.value) : undefined, season: undefined }))} className="rounded bg-slate-800 px-2 py-1">
                <option value="">All months</option>{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].map((name, index) => <option key={name} value={index + 1}>{name}</option>)}
              </select>
              <select aria-label="Heatmap season" value={timelineFilter.season ?? ''} onChange={(e) => setTimelineFilter((f) => ({ ...f, season: (e.target.value || undefined) as TimelineFilter['season'], month: undefined }))} className="rounded bg-slate-800 px-2 py-1">
                <option value="">All seasons</option><option value="winter">Winter</option><option value="spring">Spring</option><option value="summer">Summer</option><option value="fall">Fall</option>
              </select>
            </div>
            <Heatmap
              viewState={viewState}
              setViewState={setViewState}
              selectedCity={selectedCity}
              setSelectedCity={setSelectedCity}
              cityPOIAreas={cityPOIAreas}
              metricGridsByCity={metricGridsByCity}
              mapContainerRef={mapContainerRef}
              mapRef={mapRef}
              mapSyncFrameRef={mapSyncFrameRef}
              tooltip={tooltip}
              setTooltip={setTooltip}
              isFullscreen={isFullscreen}
              setIsFullscreen={setIsFullscreen}
              is3DMode={is3DMode}
              setIs3DMode={setIs3DMode}
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
              displayToolbox={true}
            />
          </section>

          <section className="min-h-0 h-full">
            <POIStatistics {...poiStatisticsProps} />
          </section>

          <section className="col-span-2 min-h-0 overflow-auto">
            <OverallStatistics {...overallStatisticsProps} />
          </section>
        </div>
      </main>
    </div>
  );
};

export default SimulationPage;
