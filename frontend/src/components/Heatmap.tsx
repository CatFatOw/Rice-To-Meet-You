import React, { useRef, useEffect, useMemo, useCallback } from 'react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, PolygonLayer } from '@deck.gl/layers';
import {
  type CityPOIArea,
} from '../api/map';
import { cities, type City } from '../data/hostCities';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

// ==========================================================
//                   Types and Interfaces
// ==========================================================

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
  cityPOIAreas: CityPOIArea[];
  hoveredGridCellId: string | null;
  setHoveredGridCellId: React.Dispatch<React.SetStateAction<string | null>>;
  selectedGridCellId: string | null;
  setSelectedGridCellId: React.Dispatch<React.SetStateAction<string | null>>;
  coordinateColors: Record<string, RGBA>;
  setCoordinateColor: (lon: number, lat: number, color: RGBA) => void;
}

type RGBA = [number, number, number, number];

interface CityGridCell {
  id: string;
  cityName: string;
  polygon: [number, number][];
  baseColor: RGBA;
  coordKey: string;
}

// ==========================================================
//                   Helper Functions
// ==========================================================

function coordKey(lon: number, lat: number, precision = 3): string {
  return `${lon.toFixed(precision)},${lat.toFixed(precision)}`;
}

function signedPolygonArea(polygon: [number, number][]): number {
  let area = 0;
  for (let i = 0; i < polygon.length; i += 1) {
    const [x1, y1] = polygon[i];
    const [x2, y2] = polygon[(i + 1) % polygon.length];
    area += x1 * y2 - x2 * y1;
  }
  return area / 2;
}

function lineIntersection(
  p1: [number, number],
  p2: [number, number],
  p3: [number, number],
  p4: [number, number],
): [number, number] {
  const [x1, y1] = p1;
  const [x2, y2] = p2;
  const [x3, y3] = p3;
  const [x4, y4] = p4;

  const denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);
  if (Math.abs(denominator) < 1e-12) {
    return p2;
  }

  const numeratorX =
    (x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4);
  const numeratorY =
    (x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4);

  return [numeratorX / denominator, numeratorY / denominator];
}

function clipPolygonToConvexBoundary(
  subjectPolygon: [number, number][],
  clipPolygon: [number, number][],
): [number, number][] {
  if (subjectPolygon.length < 3 || clipPolygon.length < 3) return [];

  const orientation = signedPolygonArea(clipPolygon) >= 0 ? 1 : -1;

  const isInside = (
    point: [number, number],
    edgeStart: [number, number],
    edgeEnd: [number, number],
  ): boolean => {
    const cross =
      (edgeEnd[0] - edgeStart[0]) * (point[1] - edgeStart[1]) -
      (edgeEnd[1] - edgeStart[1]) * (point[0] - edgeStart[0]);
    return orientation > 0 ? cross >= 0 : cross <= 0;
  };

  let output = subjectPolygon;

  for (let i = 0; i < clipPolygon.length; i += 1) {
    const clipStart = clipPolygon[i];
    const clipEnd = clipPolygon[(i + 1) % clipPolygon.length];
    const input = output;
    output = [];

    if (input.length === 0) {
      break;
    }

    let previousPoint = input[input.length - 1];

    for (const currentPoint of input) {
      const currentInside = isInside(currentPoint, clipStart, clipEnd);
      const previousInside = isInside(previousPoint, clipStart, clipEnd);

      if (currentInside) {
        if (!previousInside) {
          output.push(lineIntersection(previousPoint, currentPoint, clipStart, clipEnd));
        }
        output.push(currentPoint);
      } else if (previousInside) {
        output.push(lineIntersection(previousPoint, currentPoint, clipStart, clipEnd));
      }

      previousPoint = currentPoint;
    }
  }

  return output;
}

function buildCityBoundaryPolygon(
  cityName: string,
  cityCenter: City,
): [number, number][] {
  const centerLon = cityCenter.longitude;
  const centerLat = cityCenter.latitude;
  // Metropolitan area radii — ~130 km east-west, ~110 km north-south
  const baseWidth = 1.2;
  const baseHeight = 1.0;

  const seed = cityName.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const rx = baseWidth / 2;
  const ry = baseHeight / 2;
  const vertices = 14;
  const startAngle = (seed % 360) * (Math.PI / 180);

  const polygon: [number, number][] = [];

  for (let i = 0; i < vertices; i += 1) {
    const angle = startAngle + (i * 2 * Math.PI) / vertices;
    const noise = Math.abs(Math.sin((seed + i * 37) * 0.41));
    const radialScale = 0.86 + noise * 0.16;
    polygon.push([
      centerLon + Math.cos(angle) * rx * radialScale,
      centerLat + Math.sin(angle) * ry * radialScale,
    ]);
  }

  return polygon;
}

const GRID_HOVER_COLOR: RGBA = [134, 239, 172, 130];
const GRID_SELECTED_COLOR: RGBA = [251, 191, 36, 155];


// ==========================================================
//                     Main Component
// ==========================================================

const Heatmap: React.FC<HeatmapProps> = ({
  viewState,
  setViewState,
  selectedCity,
  cityPOIAreas,
  hoveredGridCellId,
  setHoveredGridCellId,
  selectedGridCellId,
  setSelectedGridCellId,
  coordinateColors,
  setCoordinateColor,
}) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const mapSyncFrame = useRef<number | null>(null);

  // Initialize map
  useEffect(() => {
    if (!mapContainer.current) return;

    if (map.current) return; // Prevent duplicate maps

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: [viewState.longitude, viewState.latitude],
      zoom: viewState.zoom,
      pitch: viewState.pitch,
      bearing: viewState.bearing,
    });

    return () => {
      if (mapSyncFrame.current !== null) {
        cancelAnimationFrame(mapSyncFrame.current);
        mapSyncFrame.current = null;
      }
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, []);

  const handleCityClick = useCallback((city: City) => {
    const newState = {
      longitude: city.longitude,
      latitude: city.latitude,
      zoom: 10,
      pitch: 0,
      bearing: 0,
    };
    setViewState(newState);

    // Update map camera
    if (map.current) {
      map.current.flyTo({
        center: [city.longitude, city.latitude],
        zoom: 10,
        duration: 1000,
      });
    }
  }, []);

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

  const displayedPOIAreas: CityPOIArea[] = useMemo(
    () => (selectedCity ? cityPOIAreas.filter((poi) => poi.cityName === selectedCity) : []),
    [selectedCity, cityPOIAreas],
  );

  const cityBoundaryPolygon = useMemo(() => {
    if (!selectedCity) return [];

    const city = cities.find((entry) => entry.name === selectedCity);
    if (!city) return [];

    return buildCityBoundaryPolygon(selectedCity, city);
  }, [selectedCity]);


  // ==================== Changing Individual Cells ====================

  const displayedGridCells: CityGridCell[] = useMemo(() => {
    if (!selectedCity) return [];
    if (cityBoundaryPolygon.length < 3) return [];

    const longitudes = cityBoundaryPolygon.map((point) => point[0]);
    const latitudes = cityBoundaryPolygon.map((point) => point[1]);
    const minLon = Math.min(...longitudes);
    const maxLon = Math.max(...longitudes);
    const minLat = Math.min(...latitudes);
    const maxLat = Math.max(...latitudes);

    const boundaryWidth = maxLon - minLon;
    const boundaryHeight = maxLat - minLat;
    // Fixed cell size of ~0.025° ≈ 2.5 km per cell across the metro area
    const lonStep = Math.max(0.02, boundaryWidth / 50);
    const latStep = Math.max(0.02, boundaryHeight / 50);

    const cells: CityGridCell[] = [];
    let rowIndex = 0;

    for (let lat = minLat; lat < maxLat; lat += latStep) {
      let colIndex = 0;

      for (let lon = minLon; lon < maxLon; lon += lonStep) {
        const maxCellLon = Math.min(maxLon, lon + lonStep);
        const maxCellLat = Math.min(maxLat, lat + latStep);
        const cellPolygon: [number, number][] = [
          [lon, lat],
          [maxCellLon, lat],
          [maxCellLon, maxCellLat],
          [lon, maxCellLat],
        ];

        const clippedPolygon = clipPolygonToConvexBoundary(cellPolygon, cityBoundaryPolygon);
        if (clippedPolygon.length >= 3 && Math.abs(signedPolygonArea(clippedPolygon)) > 1e-8) {
          const gradient = (rowIndex + colIndex) % 4;
          const alpha = 36 + gradient * 6;

          // Centroid of the clipped cell — used to derive this cell's
          // coordinate key so a color set at a coordinate can find it.
          const centroid = clippedPolygon.reduce(
            (acc, [x, y]) => [acc[0] + x, acc[1] + y] as [number, number],
            [0, 0] as [number, number],
          ).map((sum) => sum / clippedPolygon.length) as [number, number];

          cells.push({
            id: `${selectedCity}-grid-${rowIndex}-${colIndex}`,
            cityName: selectedCity,
            polygon: clippedPolygon,
            baseColor: [147, 197, 253, alpha],
            coordKey: coordKey(centroid[0], centroid[1]),
          });
        }

        colIndex += 1;
      }

      rowIndex += 1;
    }

    return cells;
  }, [selectedCity, cityBoundaryPolygon]);

  // =====================================================================

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

  const cityGridLayer = useMemo(
    () =>
      new PolygonLayer({
        id: 'city-grid-layer',
        data: displayedGridCells,
        pickable: true,
        stroked: true,
        filled: true,
        opacity: 0.75,
        getPolygon: (d: CityGridCell) => d.polygon,
        getLineColor: [180, 220, 255, 170],
        getLineWidth: 1,
        lineWidthUnits: 'pixels',
        getFillColor: (d: CityGridCell) => {
          const isSelected = d.id === selectedGridCellId;
          const isHovered = d.id === hoveredGridCellId;

          if (isSelected) return GRID_SELECTED_COLOR;
          if (isHovered) return GRID_HOVER_COLOR;

          // Coordinate-driven color: if this cell's centroid bucket has an
          // assigned color, use it; otherwise fall back to the base color.
          const mapped = coordinateColors[d.coordKey];
          if (mapped) return mapped;

          return d.baseColor;
        },
        // Tell deck.gl to recompute fill colors when hover/selection OR the
        // coordinate->color map changes. Without this, the GPU color buffer is
        // cached and updated colors never get applied.
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

          const nextId = (info.object as CityGridCell).id;
          setSelectedGridCellId((current) => (current === nextId ? null : nextId));
        },
      }),
    [displayedGridCells, hoveredGridCellId, selectedGridCellId, coordinateColors],
  );

  const layers = useMemo(
    () => [scatterplotLayer, cityGridLayer, poiAreaLayer],
    [scatterplotLayer, cityGridLayer, poiAreaLayer],
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

      if (!map.current) return;

      if (mapSyncFrame.current !== null) {
        cancelAnimationFrame(mapSyncFrame.current);
      }

      mapSyncFrame.current = requestAnimationFrame(() => {
        if (!map.current) return;
        map.current.jumpTo({
          center: [newState.longitude, newState.latitude],
          zoom: newState.zoom,
          pitch: newState.pitch,
          bearing: newState.bearing,
        });
      });
    },
    [],
  );

  return (
    <div style={{ width: '100%', height: '100%', minHeight: '480px', position: 'relative' }}>
      <div
        ref={mapContainer}
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

        {selectedCity && (
          <div style={{ marginTop: 20, paddingTop: 20, borderTop: '1px solid #ddd' }}>
            <h4 style={{ marginTop: 0, marginBottom: 10 }}>
              City Grid Coverage in {selectedCity}
            </h4>
            <div style={{ fontSize: '13px', color: '#333' }}>
              Total grid cells: {displayedGridCells.length}
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