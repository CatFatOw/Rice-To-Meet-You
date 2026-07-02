import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import Heatmap from '../components/Heatmap';
import NavigationBar from '../components/NavigationBar';
import OverallStatistics, { type OverallStatisticsProps } from '../components/OverallStatistics';
import POIStatistics, { type POIStatisticsProps } from '../components/POIStatistics';
import {
  callHeatmapMetricsPoints,
  callMockLocationPOIs,
  getCoordinateValue,
  type CityPOIArea,
  type HeatmapMetricsPointResponse,
} from '../api/map';
import { callMockStatistics } from '../api/statistics';
import { getColor } from '../utils/colors';
import { determineCityView } from '../utils/cityViews';

interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

type RGBA = [number, number, number, number];

function coordKey(lon: number, lat: number, precision = 3): string {
  return `${lon.toFixed(precision)},${lat.toFixed(precision)}`;
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

  const [selectedCity, setSelectedCity] = useState<string | null>(null);
  const [cityPOIAreas, setCityPOIAreas] = useState<CityPOIArea[]>([]);
  const [heatmapPointsByCity, setHeatmapPointsByCity] =
    useState<HeatmapMetricsPointResponse>({});
  const [hoveredGridCellId, setHoveredGridCellId] = useState<string | null>(null);
  const [selectedGridCellId, setSelectedGridCellId] = useState<string | null>(null);
  const [coordinateColors, setCoordinateColors] = useState<Record<string, RGBA>>({});
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

    const loadCoordinateColors = async () => {
      try {
        const metricsData = await getCoordinateValue();
        if (!isMounted) return;

        const temperatureMetric = metricsData.find((m) => m.metric === 'temperature');
        if (!temperatureMetric) return;

        const newColors: Record<string, RGBA> = {};
        temperatureMetric.points.forEach(({ coordinate, value }) => {
          const [lon, lat] = coordinate;
          const key = coordKey(lon, lat);
          const [r, g, b] = getColor(value, temperatureMetric.metric);
          newColors[key] = [r, g, b, 150];
        });

        setCoordinateColors(newColors);
      } catch (error) {
        console.error('Failed to load coordinate values', error);
      }
    };

    loadCoordinateColors();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadHeatmapPoints = async () => {
      try {
        const pointsByCity = await callHeatmapMetricsPoints();
        if (isMounted) {
          setHeatmapPointsByCity(pointsByCity);
        }
      } catch (error) {
        console.error('Failed to load heatmap metric points', error);
      }
    };

    loadHeatmapPoints();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapRef.current) return;

    mapRef.current = new maplibregl.Map({
      container: mapContainerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
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
    setHoveredGridCellId(null);
    setSelectedGridCellId(null);
  }, [selectedCity]);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#020817] text-white">
      <div className="shrink-0">
        <NavigationBar />
      </div>

      <main className="flex-1 overflow-hidden p-4">
        <div className="grid h-full grid-cols-[minmax(0,1fr)_420px] grid-rows-[minmax(0,1fr)_minmax(220px,30vh)] gap-4">
          <section className="min-h-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
            <Heatmap
              viewState={viewState}
              setViewState={setViewState}
              selectedCity={selectedCity}
              setSelectedCity={setSelectedCity}
              cityPOIAreas={cityPOIAreas}
              heatmapPointsByCity={heatmapPointsByCity}
              hoveredGridCellId={hoveredGridCellId}
              setHoveredGridCellId={setHoveredGridCellId}
              selectedGridCellId={selectedGridCellId}
              setSelectedGridCellId={setSelectedGridCellId}
              coordinateColors={coordinateColors}
              mapContainerRef={mapContainerRef}
              mapRef={mapRef}
              mapSyncFrameRef={mapSyncFrameRef}
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

export default ExplorePage;
