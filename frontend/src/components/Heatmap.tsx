import React, { useMemo, useCallback } from 'react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, PolygonLayer } from '@deck.gl/layers';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import {
  type CityPOIArea,
  type HeatmapMetricPoint,
  type HeatmapMetricsPointResponse,
} from '../api/map';
import { cities, type City } from '../data/hostCities';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';



interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

interface HeatmapProps {
  viewState: ViewState;
  setViewState: React.Dispatch<React.SetStateAction<ViewState>>;
  selectedCity: string | null;
  setSelectedCity: React.Dispatch<React.SetStateAction<string | null>>;
  cityPOIAreas: CityPOIArea[];
  heatmapPointsByCity: HeatmapMetricsPointResponse;
  hoveredGridCellId: string | null;
  setHoveredGridCellId: React.Dispatch<React.SetStateAction<string | null>>;
  selectedGridCellId: string | null;
  setSelectedGridCellId: React.Dispatch<React.SetStateAction<string | null>>;
  coordinateColors: Record<string, RGBA>;
  mapContainerRef: React.RefObject<HTMLDivElement | null>;
  mapRef: React.MutableRefObject<maplibregl.Map | null>;
  mapSyncFrameRef: React.MutableRefObject<number | null>;
}

type RGBA = [number, number, number, number];

interface CityGridCell {
  id: string;
  cityName: string;
  polygon: [number, number][];
  coordKey: string;
}

const GRID_HOVER_COLOR: RGBA = [134, 239, 172, 130];
const GRID_SELECTED_COLOR: RGBA = [251, 191, 36, 155];

function coordKey(lon: number, lat: number, precision = 3): string {
  return `${lon.toFixed(precision)},${lat.toFixed(precision)}`;
}

function buildGridCells(city: City): CityGridCell[] {
  const cells: CityGridCell[] = [];
  const halfSpanLon = 0.24;
  const halfSpanLat = 0.2;
  const step = 0.03;

  const minLon = city.longitude - halfSpanLon;
  const maxLon = city.longitude + halfSpanLon;
  const minLat = city.latitude - halfSpanLat;
  const maxLat = city.latitude + halfSpanLat;

  for (let lat = minLat; lat < maxLat - 1e-9; lat += step) {
    for (let lon = minLon; lon < maxLon - 1e-9; lon += step) {
      const centerLon = Number((lon + step / 2).toFixed(3));
      const centerLat = Number((lat + step / 2).toFixed(3));
      cells.push({
        id: `${city.name}-${centerLon}-${centerLat}`,
        cityName: city.name,
        polygon: [
          [lon, lat],
          [lon + step, lat],
          [lon + step, lat + step],
          [lon, lat + step],
        ],
        coordKey: coordKey(centerLon, centerLat),
      });
    }
  }

  return cells;
}

const Heatmap: React.FC<HeatmapProps> = ({
  viewState,
  setViewState,
  selectedCity,
  setSelectedCity,
  cityPOIAreas,
  heatmapPointsByCity,
  hoveredGridCellId,
  setHoveredGridCellId,
  selectedGridCellId,
  setSelectedGridCellId,
  coordinateColors,
  mapContainerRef,
  mapRef,
  mapSyncFrameRef,
}) => {

  const handleCityClick = useCallback((city: City) => {
    const newState = {
      longitude: city.longitude,
      latitude: city.latitude,
      zoom: 10,
      pitch: 0,
      bearing: 0,
    };
    setViewState(newState);
    setSelectedCity(city.name);

    // Update map camera
    if (mapRef.current) {
      mapRef.current.flyTo({
        center: [city.longitude, city.latitude],
        zoom: 10,
        duration: 1000,
      });
    }
  }, [setViewState, setSelectedCity, mapRef]);

  const scatterplotLayer = useMemo(
    () =>
      new ScatterplotLayer({
        id: 'scatterplot-layer',
        data: cities,
        pickable: true,
        opacity: 0.8,
        radiusScale: 20,
        radiusMinPixels: 8,
        radiusMaxPixels: 30,
        lineWidthMinPixels: 1,
        getPosition: (d: City) => [d.longitude, d.latitude],
        getFillColor: [255, 0, 0, 200],
        getLineColor: [255, 255, 255, 255],
        onClick: (info: any) => {
          if (info.object) {
            handleCityClick(info.object as City);
          }
        },
      }),
    [handleCityClick],
  );

  const displayedHeatmapPoints: HeatmapMetricPoint[] = useMemo(
    () => (selectedCity ? (heatmapPointsByCity[selectedCity] ?? []) : []),
    [selectedCity, heatmapPointsByCity],
  );

  const displayedPOIAreas: CityPOIArea[] = useMemo(
    () => (selectedCity ? cityPOIAreas.filter((poi) => poi.cityName === selectedCity) : []),
    [selectedCity, cityPOIAreas],
  );

  const displayedGridCells: CityGridCell[] = useMemo(() => {
    if (!selectedCity) return [];
    const city = cities.find((c) => c.name === selectedCity);
    if (!city) return [];
    return buildGridCells(city);
  }, [selectedCity]);

  const heatmapPointLayer = useMemo(
    () =>
      new HeatmapLayer({
        id: 'heatmap-point-layer',
        data: displayedHeatmapPoints,
        pickable: false,
        getPosition: (d: HeatmapMetricPoint) => d.location_coordinates,
        getWeight: (d: HeatmapMetricPoint) => d.value,
        radiusPixels: 40,
        intensity: 1.2,
        threshold: 0.05,
        colorRange: [
          [46, 125, 50, 80],
          [249, 168, 37, 140],
          [245, 124, 0, 180],
          [183, 28, 28, 220],
        ],
      }),
    [displayedHeatmapPoints],
  );

  const poiAreaLayer = useMemo(
    () =>
      new PolygonLayer({
        id: 'poi-area-layer',
        data: displayedPOIAreas,
        pickable: true,
        stroked: true,
        filled: true,
        opacity: 0.55,
        getPolygon: (d: CityPOIArea) => d.polygon,
        getFillColor: (d: CityPOIArea) => d.color,
        getLineColor: [255, 255, 255, 255],
        getLineWidth: 2,
        lineWidthUnits: 'pixels',
      }),
    [displayedPOIAreas],
  );

  const gridLayer = useMemo(
    () =>
      new PolygonLayer<CityGridCell>({
        id: 'grid-layer',
        data: displayedGridCells,
        pickable: true,
        stroked: true,
        filled: true,
        lineWidthUnits: 'pixels',
        getLineWidth: 1,
        getPolygon: (d) => d.polygon,
        getLineColor: [148, 163, 184, 140],
        getFillColor: (d) => {
          if (selectedGridCellId === d.id) return GRID_SELECTED_COLOR;
          if (hoveredGridCellId === d.id) return GRID_HOVER_COLOR;
          return coordinateColors[d.coordKey] ?? [100, 116, 139, 70];
        },
        updateTriggers: {
          getFillColor: [hoveredGridCellId, selectedGridCellId, coordinateColors],
        },
        onHover: (info: any) => {
          setHoveredGridCellId(info.object ? (info.object as CityGridCell).id : null);
        },
        onClick: (info: any) => {
          if (!info.object) {
            setSelectedGridCellId(null);
            return;
          }
          const id = (info.object as CityGridCell).id;
          setSelectedGridCellId((prev) => (prev === id ? null : id));
        },
      }),
    [displayedGridCells, hoveredGridCellId, selectedGridCellId, coordinateColors],
  );

  const layers = useMemo(
    () => [scatterplotLayer, heatmapPointLayer, poiAreaLayer, gridLayer],
    [scatterplotLayer, heatmapPointLayer, poiAreaLayer, gridLayer],
  );

  const handleViewStateChange = useCallback(
    (e: any) => {
      const nextState = e.viewState as {
        longitude: number;
        latitude: number;
        zoom: number;
        pitch: number;
        bearing: number;
      };
      const newState: ViewState = {
        longitude: nextState.longitude,
        latitude: nextState.latitude,
        zoom: nextState.zoom,
        pitch: nextState.pitch,
        bearing: nextState.bearing,
      };

      setViewState((prev) => {
        if (
          Math.abs(prev.longitude - newState.longitude) < 1e-6 &&
          Math.abs(prev.latitude - newState.latitude) < 1e-6 &&
          Math.abs(prev.zoom - newState.zoom) < 1e-4 &&
          Math.abs(prev.pitch - newState.pitch) < 1e-4 &&
          Math.abs(prev.bearing - newState.bearing) < 1e-4
        ) {
          return prev;
        }
        return newState;
      });

      if (!mapRef.current) return;

      if (mapSyncFrameRef.current !== null) {
        cancelAnimationFrame(mapSyncFrameRef.current);
      }

      mapSyncFrameRef.current = requestAnimationFrame(() => {
        if (!mapRef.current) return;
        mapRef.current.jumpTo({
          center: [newState.longitude, newState.latitude],
          zoom: newState.zoom,
          pitch: newState.pitch,
          bearing: newState.bearing,
        });
      });
    },
    [setViewState, mapRef, mapSyncFrameRef],
  );

  return (
    <div style={{ width: '100%', height: '100%', minHeight: '480px', position: 'relative' }}>
      <div
        ref={mapContainerRef}
        style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}
      />
      <DeckGL
        viewState={viewState}
        onViewStateChange={handleViewStateChange}
        controller={true}
        layers={layers}
        style={{ position: 'absolute', width: '100%', height: '100%' }}
      />
      <div
        style={{
          position: 'absolute',
          top: 20,
          left: 20,
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          padding: '15px',
          borderRadius: '8px',
          maxHeight: '400px',
          overflowY: 'auto',
          zIndex: 10,
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        }}
      >
        <h3 style={{ marginTop: 0, marginBottom: 10 }}>US Cities</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          {cities.map((city) => (
            <button
              key={city.name}
              onClick={() => handleCityClick(city)}
              style={{
                padding: '8px 12px',
                backgroundColor:
                  selectedCity === city.name ? '#0056b3' : '#007bff',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '14px',
                textAlign: 'left',
                transition: 'background-color 0.2s',
                fontWeight: selectedCity === city.name ? 'bold' : 'normal',
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.backgroundColor = '#0056b3')
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.backgroundColor =
                  selectedCity === city.name ? '#0056b3' : '#007bff')
              }
            >
              {city.name}
            </button>
          ))}
        </div>

        {selectedCity && displayedHeatmapPoints.length > 0 && (
          <div style={{ marginTop: 20, paddingTop: 20, borderTop: '1px solid #ddd' }}>
            <h4 style={{ marginTop: 0, marginBottom: 10 }}>
              Heatmap Point Density in {selectedCity}
            </h4>
            <div style={{ fontSize: '13px', color: '#333' }}>
              Total points: {displayedHeatmapPoints.length}
            </div>
            {displayedPOIAreas.length > 0 && (
              <div style={{ marginTop: 8, fontSize: '13px', color: '#333' }}>
                POIs: {displayedPOIAreas.map((poi) => poi.name).join(', ')}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Heatmap;
