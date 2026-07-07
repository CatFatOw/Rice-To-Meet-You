import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import Heatmap, { type GeocodeResult, type TooltipState } from '../components/Heatmap';
import LiveTrafficPanel from '../components/LiveTrafficPanel';
import NavigationBar from '../components/NavigationBar';
import OverallStatistics, { type OverallStatisticsProps } from '../components/OverallStatistics';
import POIStatistics, { type POIStatisticsProps } from '../components/POIStatistics';
import {
  callHeatmapMetricsGrid,
  callMockLocationPOIs,
  importCorePOIFile,
  type CityPOIArea,
  type HeatmapMetricValue,
  type HeatmapMetricGridResponse,
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

function poiCenter(poi: CityPOIArea): [number, number] {
  if (!poi.polygon.length) return [0, 0];
  const [lonSum, latSum] = poi.polygon.reduce(
    (acc, [lon, lat]) => [acc[0] + lon, acc[1] + lat],
    [0, 0],
  );
  return [lonSum / poi.polygon.length, latSum / poi.polygon.length];
}

function distanceMiles(from: [number, number], to: [number, number]): number {
  const lonScale = Math.cos((from[1] * Math.PI) / 180);
  const dLon = (to[0] - from[0]) * 69 * lonScale;
  const dLat = (to[1] - from[1]) * 69;
  return Math.sqrt(dLon * dLon + dLat * dLat);
}


const ExplorePage: React.FC = () => {
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
  const poiImportInputRef = useRef<HTMLInputElement>(null);

  const [selectedCity, setSelectedCity] = useState<string | null>(null);
  const [cityPOIAreas, setCityPOIAreas] = useState<CityPOIArea[]>([]);
  const [metricGridsByCity, setMetricGridsByCity] =
    useState<HeatmapMetricGridResponse>({});
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
  const [overallStatisticsProps, setOverallStatisticsProps] =
    useState<OverallStatisticsProps>();
  const [poiStatisticsProps, setPOIStatisticsProps] = useState<POIStatisticsProps>();
  const [selectedPOIArea, setSelectedPOIArea] = useState<CityPOIArea | null>(null);
  const [isImportingPOIs, setIsImportingPOIs] = useState(false);
  const [poiImportMessage, setPOIImportMessage] = useState<string | null>(null);
  const [nearestLongitude, setNearestLongitude] = useState('');
  const [nearestLatitude, setNearestLatitude] = useState('');
  const [nearestSourceLabel, setNearestSourceLabel] = useState<string | null>(null);
  const [poiSortMode, setPOISortMode] = useState<'x' | 'nearest'>('x');
  const [showAllCityHeatmaps, setShowAllCityHeatmaps] = useState(true);

  const loadPOIs = useCallback(async () => {
    const pois = await callMockLocationPOIs();
    setCityPOIAreas(pois);
  }, []);

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

  const handleCorePOIImport = async (file: File | undefined) => {
    if (!file) return;
    try {
      setIsImportingPOIs(true);
      setPOIImportMessage(`Importing ${file.name}...`);
      const result = await importCorePOIFile(file);
      if (poiImportInputRef.current) {
        poiImportInputRef.current.value = '';
      }
      await loadPOIs();
      setPOIImportMessage(
        `Imported ${result.imported_count.toLocaleString()} POIs` +
          (result.skipped_count ? `, skipped ${result.skipped_count.toLocaleString()}` : ''),
      );
    } catch (error) {
      console.error('Failed to import core POI file', error);
      setPOIImportMessage('Import failed. Check the file format and backend logs.');
    } finally {
      setIsImportingPOIs(false);
    }
  };

  useEffect(() => {
    let isMounted = true;

    const loadMetricGrids = async () => {
      try {
        const gridsByCity = await callHeatmapMetricsGrid();
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
  }, []);

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
    setSelectedPOIArea(null);
    setPOISortMode('x');
    setNearestSourceLabel(null);
  }, [selectedCity]);

  const corePOICount = selectedCity
    ? cityPOIAreas.filter((poi) => poi.cityName === selectedCity).length
    : cityPOIAreas.length;
  const customAreaCount = selectedCity
    ? userPOIAreas.filter((poi) => poi.cityName === selectedCity).length
    : userPOIAreas.length;
  const activeMetricCount = selectedCity
    ? Object.keys(metricGridsByCity[selectedCity]?.metrics ?? {}).length
    : Object.values(metricGridsByCity).reduce(
        (sum, grid) => sum + Object.keys(grid.metrics).length,
        0,
      );
  const parsedNearestPoint = useMemo<[number, number] | null>(() => {
    const lon = Number.parseFloat(nearestLongitude);
    const lat = Number.parseFloat(nearestLatitude);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
    if (Math.abs(lon) > 180 || Math.abs(lat) > 90) return null;
    return [lon, lat];
  }, [nearestLongitude, nearestLatitude]);
  const corePOIDirectory = useMemo(() => {
    const pois = selectedCity
      ? cityPOIAreas.filter((poi) => poi.cityName === selectedCity)
      : cityPOIAreas;

    return [...pois].sort((a, b) => {
      const aCenter = poiCenter(a);
      const bCenter = poiCenter(b);
      if (poiSortMode === 'nearest' && parsedNearestPoint) {
        return (
          distanceMiles(parsedNearestPoint, aCenter) -
          distanceMiles(parsedNearestPoint, bCenter)
        );
      }
      return aCenter[0] - bCenter[0];
    });
  }, [cityPOIAreas, parsedNearestPoint, poiSortMode, selectedCity]);

  const directorySubtitle =
    poiSortMode === 'nearest' && parsedNearestPoint
      ? `Nearest POIs to ${nearestSourceLabel ?? 'coordinate'}`
      : `Core POIs in ${selectedCity ?? 'all states'}`;

  const handlePOIDirectorySelect = (poi: CityPOIArea) => {
    setSelectedPOIArea(poi);
    const [lon, lat] = poiCenter(poi);
    setNearestLongitude(lon.toFixed(5));
    setNearestLatitude(lat.toFixed(5));
    setNearestSourceLabel(poi.name);
    setPOISortMode('nearest');
    const nextState = { longitude: lon, latitude: lat, zoom: 14, pitch: 0, bearing: 0 };
    setViewState(nextState);
    mapRef.current?.flyTo({ center: [lon, lat], zoom: 14, duration: 900 });
  };

  const handlePOIAreaSelect = (poi: CityPOIArea) => {
    setSelectedPOIArea(poi);
    const [lon, lat] = poiCenter(poi);
    setNearestLongitude(lon.toFixed(5));
    setNearestLatitude(lat.toFixed(5));
    setNearestSourceLabel(poi.name);
    setPOISortMode('nearest');
  };

  const handleMetricPointSelect = (point: HeatmapMetricValue) => {
    const [lon, lat] = point.location_coordinates;
    setNearestLongitude(lon.toFixed(5));
    setNearestLatitude(lat.toFixed(5));
    setNearestSourceLabel(point.location_name);
    setPOISortMode('nearest');
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#050914] text-white">
      <div className="shrink-0">
        <NavigationBar />
      </div>

      <main className="flex-1 overflow-hidden p-4">
        <div className="grid h-full grid-cols-[minmax(0,1fr)_390px] grid-rows-[minmax(0,1fr)_minmax(170px,23vh)] gap-4">
          <section className="min-h-0 overflow-hidden rounded-lg border border-slate-800 bg-slate-950 shadow-2xl shadow-black/30">
            <Heatmap
              viewState={viewState}
              setViewState={setViewState}
              selectedCity={selectedCity}
              setSelectedCity={setSelectedCity}
              cityPOIAreas={cityPOIAreas}
              metricGridsByCity={metricGridsByCity}
              showAllCityHeatmaps={showAllCityHeatmaps}
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
              onPOIAreaSelect={handlePOIAreaSelect}
              onMetricPointSelect={handleMetricPointSelect}
            
            />
          </section>

          <section className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto overscroll-contain pr-1">
            <div className="shrink-0 rounded-lg border border-slate-800 bg-[#07111f] p-4 shadow-lg">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Planner Workspace
                  </div>
                  <div className="mt-1 text-lg font-semibold text-slate-100">
                    {selectedCity ?? 'National View'}
                  </div>
                </div>
                <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs font-semibold text-emerald-200">
                  Live
                </span>
              </div>

              <div className="mb-4 grid grid-cols-3 gap-2">
                <div className="rounded-md border border-slate-800 bg-slate-950/70 p-3">
                  <div className="text-[11px] uppercase text-slate-500">Core POIs</div>
                  <div className="mt-1 text-lg font-bold text-sky-200">{corePOICount}</div>
                </div>
                <div className="rounded-md border border-slate-800 bg-slate-950/70 p-3">
                  <div className="text-[11px] uppercase text-slate-500">Plans</div>
                  <div className="mt-1 text-lg font-bold text-emerald-200">{customAreaCount}</div>
                </div>
                <div className="rounded-md border border-slate-800 bg-slate-950/70 p-3">
                  <div className="text-[11px] uppercase text-slate-500">Layers</div>
                  <div className="mt-1 text-lg font-bold text-violet-200">{activeMetricCount}</div>
                </div>
              </div>

              <label className="mb-4 flex items-center justify-between gap-3 rounded-md border border-slate-800 bg-slate-950/70 px-3 py-2">
                <span>
                  <span className="block text-xs font-semibold text-slate-200">All city heatmaps</span>
                  <span className="block text-[11px] text-slate-500">
                    {showAllCityHeatmaps ? 'Showing every city layer' : 'Showing current city only'}
                  </span>
                </span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={1}
                  value={showAllCityHeatmaps ? 1 : 0}
                  onChange={(event) => setShowAllCityHeatmaps(event.target.value === '1')}
                  className="w-20 accent-sky-400"
                />
              </label>

              <input
                ref={poiImportInputRef}
                type="file"
                accept=".csv,.xlsx"
                className="hidden"
                onChange={(event) => void handleCorePOIImport(event.target.files?.[0])}
              />
              <button
                type="button"
                disabled={isImportingPOIs}
                onClick={() => poiImportInputRef.current?.click()}
                className="w-full rounded-md border border-sky-500/40 bg-sky-500/15 px-3 py-2 text-sm font-semibold text-sky-100 transition hover:bg-sky-500/25 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isImportingPOIs ? 'Importing Core POIs...' : 'Import Core POI Layer'}
              </button>
              {poiImportMessage && (
                <div className="mt-2 rounded-md border border-slate-800 bg-slate-950/70 px-3 py-2 text-xs text-slate-300">
                  {poiImportMessage}
                </div>
              )}
            </div>
            <LiveTrafficPanel
              latitude={nearestLatitude}
              longitude={nearestLongitude}
              sourceLabel={nearestSourceLabel}
              onCoordinateChange={({ latitude, longitude, sourceLabel }) => {
                setNearestLatitude(latitude);
                setNearestLongitude(longitude);
                setNearestSourceLabel(sourceLabel);
              }}
            />
            <div className="flex min-h-0 flex-[1.05_1_0] flex-col rounded-lg border border-slate-800 bg-[#07111f] p-4 shadow-lg">
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Core POI Directory
                  </div>
                  <div className="mt-1 text-sm font-semibold text-slate-100">
                    {directorySubtitle}
                  </div>
                </div>
                <span className="rounded-md border border-slate-700 bg-slate-950/70 px-2 py-1 text-xs text-slate-300">
                  {corePOIDirectory.length}
                </span>
              </div>

              <div className="mb-3 grid grid-cols-2 gap-2">
                <label className="text-xs text-slate-400">
                  Longitude
                  <input
                    value={nearestLongitude}
                    onChange={(event) => {
                      setNearestLongitude(event.target.value);
                      setNearestSourceLabel('coordinate');
                      setPOISortMode('nearest');
                    }}
                    placeholder="-95.3698"
                    className="mt-1 w-full rounded-md border border-slate-800 bg-slate-950/80 px-2 py-1.5 text-xs text-slate-100 outline-none transition focus:border-sky-500"
                  />
                </label>
                <label className="text-xs text-slate-400">
                  Latitude
                  <input
                    value={nearestLatitude}
                    onChange={(event) => {
                      setNearestLatitude(event.target.value);
                      setNearestSourceLabel('coordinate');
                      setPOISortMode('nearest');
                    }}
                    placeholder="29.7604"
                    className="mt-1 w-full rounded-md border border-slate-800 bg-slate-950/80 px-2 py-1.5 text-xs text-slate-100 outline-none transition focus:border-sky-500"
                  />
                </label>
              </div>

              <div className="mb-3 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setPOISortMode('x')}
                  className={`rounded-md border px-2 py-1.5 text-xs font-semibold transition ${
                    poiSortMode === 'x'
                      ? 'border-sky-500/50 bg-sky-500/15 text-sky-100'
                      : 'border-slate-800 bg-slate-950/70 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  X order
                </button>
                <button
                  type="button"
                  onClick={() => setPOISortMode('nearest')}
                  disabled={!parsedNearestPoint}
                  className={`rounded-md border px-2 py-1.5 text-xs font-semibold transition ${
                    poiSortMode === 'nearest'
                      ? 'border-sky-500/50 bg-sky-500/15 text-sky-100'
                      : 'border-slate-800 bg-slate-950/70 text-slate-400 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50'
                  }`}
                >
                  Nearest
                </button>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-md border border-slate-800">
                {corePOIDirectory.map((poi) => {
                  const center = poiCenter(poi);
                  const miles = parsedNearestPoint
                    ? distanceMiles(parsedNearestPoint, center)
                    : null;
                  const isSelected = selectedPOIArea?.id === poi.id;
                  return (
                    <button
                      key={poi.id}
                      type="button"
                      onClick={() => handlePOIDirectorySelect(poi)}
                      className={`flex w-full items-center justify-between gap-3 border-b border-slate-800 px-3 py-2 text-left text-xs last:border-b-0 transition ${
                        isSelected
                          ? 'bg-sky-500/15 text-sky-100'
                          : 'bg-slate-950/40 text-slate-300 hover:bg-slate-900'
                      }`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-semibold">{poi.name}</span>
                        <span className="mt-0.5 block truncate text-slate-500">
                          {poi.category ?? 'Unknown'} · {center[0].toFixed(4)}, {center[1].toFixed(4)}
                        </span>
                      </span>
                      <span className="shrink-0 text-slate-400">
                        {miles === null ? center[0].toFixed(2) : `${miles.toFixed(1)} mi`}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="min-h-0 flex-[0.46_1_0] overflow-hidden">
              <POIStatistics {...poiStatisticsProps} selectedPOI={selectedPOIArea} />
            </div>
          </section>

          <section className="col-span-2 min-h-0 overflow-auto">
            <OverallStatistics {...overallStatisticsProps} />
          </section>
        </div>
      </main>
    </div>
  );
};

export default ExplorePage;
