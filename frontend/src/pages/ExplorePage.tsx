import React, { useState, useEffect, useCallback } from 'react';
import Heatmap from '../components/Heatmap';
import NavigationBar from '../components/NavigationBar';
import OverallStatistics, {
  type OverallStatisticsProps,
} from '../components/OverallStatistics';
import POIStatistics, {
  type POIStatisticsProps,
} from '../components/POIStatistics';
import {
  callMockLocationPOIs,
  type CityPOIArea,
  getCoordinateValue,
} from '../api/map';
import { callMockStatistics } from '../api/statistics';
import { determineCityView } from '../utils/cityViews';
import { getColor } from '../utils/colors';


interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

type RGBA = [number, number, number, number];

const ExplorePage: React.FC = () => {
  const [viewState, setViewState] = useState<ViewState>({
      longitude: -95.7129,
      latitude: 37.0902,
      zoom: 3.5,
      pitch: 0,
      bearing: 0,
    });
  const selectedCity = determineCityView(viewState);
  const [cityPOIAreas, setCityPOIAreas] = useState<CityPOIArea[]>([]);
  const [overallStatisticsProps, setOverallStatisticsProps] =
    useState<OverallStatisticsProps>();
  const [poiStatisticsProps, setPOIStatisticsProps] =
    useState<POIStatisticsProps>();

  // Heatmap states
  const [hoveredGridCellId, setHoveredGridCellId] = useState<string | null>(null);
  const [selectedGridCellId, setSelectedGridCellId] = useState<string | null>(null);
  const [coordinateColors, setCoordinateColors] = useState<Record<string, RGBA>>({});

  const setCoordinateColor = useCallback(
    (lon: number, lat: number, color: RGBA) => {
      setCoordinateColors((prev) => ({
        ...prev,
        [`${lon.toFixed(3)},${lat.toFixed(3)}`]: color,
      }));
    },
    [],
  );

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

  useEffect(() => {
    let isMounted = true;

    const loadCoordinateColors = async () => {
      try {
        const metricsData = await getCoordinateValue();
        if (!isMounted) return;

        // Process temperature metric
        const temperatureMetric = metricsData.find((m) => m.metric === 'temperature');
        if (temperatureMetric) {
          const newColors: Record<string, RGBA> = {};
          temperatureMetric.points.forEach(({ coordinate, value }) => {
            const [lon, lat] = coordinate;
            const key = `${lon.toFixed(3)},${lat.toFixed(3)}`;
            const [r, g, b] = getColor(value, 'temperature');
            newColors[key] = [r, g, b, 150]; // Add alpha channel
          });
          setCoordinateColors(newColors);
        }
      } catch (error) {
        console.error('Failed to load coordinate values', error);
      }
    };

    loadCoordinateColors();

    return () => {
      isMounted = false;
    };
  }, []);

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
              cityPOIAreas={cityPOIAreas}
              hoveredGridCellId={hoveredGridCellId}
              setHoveredGridCellId={setHoveredGridCellId}
              selectedGridCellId={selectedGridCellId}
              setSelectedGridCellId={setSelectedGridCellId}
              coordinateColors={coordinateColors}
              setCoordinateColor={setCoordinateColor}
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
