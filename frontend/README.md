# HeatSafe AI Frontend

React + TypeScript frontend for exploring heat risk across host cities, viewing POIs, and rendering map-based risk layers.

## Run Locally

```bash
npm install
npm run dev
```

## Technology Stack

- Framework: React 19 + TypeScript
- Bundler/Dev Server: Vite 8
- Mapping & Visualization:
  - maplibre-gl
  - deck.gl (`@deck.gl/react`, `@deck.gl/layers`, `@deck.gl/aggregation-layers`)
  - react-map-gl
- Routing: react-router-dom
- Styling:
  - Tailwind CSS 4 (`tailwindcss`, `@tailwindcss/vite`)
  - Component-level utility classes + inline styles for map UI overlays
- Icons: lucide-react
- Linting/Code Quality:
  - ESLint 10
  - typescript-eslint
  - eslint-plugin-react-hooks
  - eslint-plugin-react-refresh

## Folder Structure

```text
frontend/
├── public/
├── src/
│   ├── api/                  # Mock API modules (map + statistics)
│   ├── assets/               # Static frontend assets
│   ├── components/           # UI components
│   │   ├── Heatmap.tsx
│   │   ├── POIStatistics.tsx
│   │   ├── OverallStatistics.tsx
│   │   ├── SearchBar.tsx
│   │   ├── Toolbox.tsx
│   │   ├── SelectDate.tsx
│   │   ├── SimulateButton.tsx
│   │   ├── simulate-panel.tsx
│   │   └── toolbox-table.tsx
│   ├── data/                 # Seed/mock data, model config
│   ├── hooks/                # Custom React hooks
│   │   ├── useFullScreen.ts
│   │   ├── useHeatmapLayers.ts
│   │   ├── usePlacedObjects.ts
│   │   └── useSimulationRunner.ts
│   ├── pages/                # Page-level containers (Explore, Simulation)
│   ├── types/                # Shared TypeScript contracts
│   ├── utils/                # Pure utilities (map, interpolation, simulation)
│   ├── App.tsx
│   └── main.tsx
├── index.html
├── eslint.config.js
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── vite.config.ts
└── package.json
```

## Component Architecture

The frontend follows a page-container + presentational component pattern.

- Entry and routing:
  - `src/main.tsx` bootstraps the app.
  - `src/App.tsx` handles top-level composition/routing.
- Page containers:
  - `src/pages/ExplorePage.tsx` handles map exploration and dashboard display.
  - `src/pages/SimulationPage.tsx` extends exploration with simulation controls and playback.
- Core map module:
  - `src/components/Heatmap.tsx` is the central interaction surface for city selection, layer rendering, drawing areas, object placement, hover tooltip, and fullscreen.
  - `src/hooks/useHeatmapLayers.ts` builds and memoizes the deck.gl layer stack.
- Dashboard module:
  - `src/components/POIStatistics.tsx` renders POI table, simulation controls, toolbox table, and panel fullscreen behavior.
  - `src/components/OverallStatistics.tsx` renders summary cards/charts.
- Interaction and controls:
  - `src/components/SearchBar.tsx` handles search input, suggestions, and fly-to behavior.
  - `src/components/Toolbox.tsx` handles date/metric toggles and POI-area drawing controls.
  - `src/components/SelectDate.tsx` provides reusable date picking for all date fields.
  - `src/components/simulate-panel.tsx` isolates date-range + simulate action UI.
  - `src/components/toolbox-table.tsx` provides object-level parameter and schedule editing.

## State Management

State is managed with React hooks and is kept local to the narrowest feature boundary that needs it.

### State Categories

#### 1. Map and viewport state

Controls the map's position, lifecycle, and interactive overlays.

- `viewState`: Controls the current location view and zoom on heatmap

- `tooltip`: Controls the display of information when user hovers a coordinate on heatmap

- `hoveringHeatmap`

- `isFullscreen`: Controls the fullscreen state of POIStatistics and Heatmap

- `selectedCity`: Controls the current city being viewed. Updated when the user clicks on a city.

Owned by:

- `SimulationPage`

- `ExplorePage`

- `useFullScreen`

#### 2. City and heatmap data

Stores the selected city and loaded environmental data.


- `cityPOIAreas`: Controls the list of POI Areas on the map

- `heatmapPointsByCity`: Controls the display of heatmap points

- `heatmapAnchorsByCity`: Controls the heatmap anchors, which are used and interpolated by `heatmapPointsByCity`

- `baselineHeatmapAnchorsByCity`: Controls the original reference data (used to compute simulation so each run starts from baseline, not from already-simulated frames)

Owned by:

- `SimulationPage`

- `ExplorePage`

#### 3. Date and timeline state

Controls the active date and simulation period.

- `selectedDate`: Controls the date that the heatmap snapshots are displayed

- `fromDate`: Controls the display of from date in simulate subsection in POIStatistic

- `toDate`: Controls the display of to date in simulate subsection in POIStatistic

- `open`: Controls whether the calender is open or not

- `viewDate`: Controls which month the user is browsing

Owned by:

- Pages

- `SelectDate`

#### 4. Simulation state

Stores simulation configuration, execution status, and results.

- `containSimulation`: Determines whether the page should contain simulation. Currenly only allowed for `Simulation Page`

- `simulationByDate`: Controls the display of simulation 

- `placedObjects`: Controls the information of placed urban intervention on map

- `isRunning`: Controls whether if simulation is runnning

Owned by:

- `SimulationPage`

- `Heatmap`

- `usePlacedObjects`

- `useSimulationRunner`

#### 5. Drawing and POI editing state

Controls creation and editing of user-defined areas.

- `isDrawing`: Controls whether the user is current in the "Draw Mode"

- `draftPoints`: Contains the current list of vertices that the in-progress polygon is drawn

- `draftColorHex`: Selected color for the new area being drafted

- `draftName`: Temporary name input for the area being drafted.

- `userPOIAreas`: saved custom POI areas created by the user.

- `editingAreaId`: ID of the user area currently in edit mode (or null when none)

- `isAreaDragging`: whether an existing area is currently being dragged.

Owned by:

- `SimulationPage`

- `ExplorePage`

#### 6. Search state

Controls location search and suggestions.

- `searchQuery`: Contain the current search query

- `geoResults`: Contain the search query results

- `isSearching`: Determines whether the user is querying the search bar

- `showSuggestions`: controls whether the search suggestion dropdown is visible in the search UI.

Owned by:

- `SimulationPage`

- `ExplorePage`

#### 7. Dashboard and metric state

Controls statistics panels and the displayed metric.

- `selectedMetric`: Determines the selected metric being displayed on map

- `overallStatisticsProps`: Controls the statistics being displayed in `OverallStatistics` component

- `poiStatisticsProps`: Controls the statistics being displayed in `POIStatistics` component

Owned by:

- `SimulationPage`

- `ExplorePage`

#### 8. Local UI state

State that affects only one component.

- `NavigationBar.collapsed`

- `SelectDate.open`

- `SelectDate.viewDate`

### Refs and imperative state

Map instances, animation frames, DOM elements, and timers are stored in refs because changes to them should not trigger React renders.

Examples:

- `mapRef`

- `mapContainerRef`

- `mapSyncFrameRef`

- timer refs

### State ownership rules

- All states are stored in `ExplorePage` and `SimulationPage`

- Page-level state is used when multiple sibling components need the same value.

- Component-local state is used for isolated UI behavior.

- Custom hooks own reusable feature logic and expose a controlled interface.

- Derived values should be calculated with `useMemo` rather than duplicated in `useState`.

## Custom Hooks

Custom hooks in `src/hooks` encapsulate reusable behavior and separate interaction logic from UI markup.

- `useFullScreen.ts`
  - Manages element-level fullscreen state.
  - Exposes fullscreen boolean + toggle handler.
- `useHeatmapLayers.ts`
  - Creates deck.gl layers for cities, heatmap, POI polygons, draft geometry, and toolbox objects.
  - Encapsulates drag/edit behavior tied to layers.
- `usePlacedObjects.ts`
  - Owns placed-object lifecycle: add, patch, remove, clear.
  - Supports HTML5 drag/drop placement from toolbox into map coordinates.
  - Supports optional parent sync via change callback.
- `useSimulationRunner.ts`
  - Plays date-keyed simulation frames on a controlled interval.
  - Handles timeline filtering, start/stop, completion, and interval cleanup on unmount.
- `usePolygonDraw.ts`
  - Handles drawing polygons on heatmap

### Hook Design Guidelines

- Keep hooks focused on one domain (layers, fullscreen, simulation playback, object placement).
- Return stable callbacks with `useCallback` when handlers are passed to heavy children.
- Keep rendering concerns in components and move side-effect-heavy logic into hooks.
- Type hook inputs/outputs with interfaces from `src/types` to preserve contract clarity.



## Frontend API Reference

The frontend currently uses local mock API modules under `src/api`.

### Map API (`src/api/map.ts`)

#### `callMockLocationPOIs()`

- Purpose: Fetches polygon overlays for known POIs.
- Returns: `Promise<CityPOIArea[]>`
- Current data: Houston polygons (NRG Stadium, Rice University).

**Main shape**

```ts
interface CityPOIArea {
  id: string;
  name: string;
  cityName: string;
  color: [number, number, number, number];
  polygon: [number, number][];
}
```

#### `callHeatmapMetricsPoints()`

- Purpose: Returns point-level heat risk data for map heatmap rendering.
- Returns: `Promise<Record<string, HeatmapMetricPoint[]>>`
- Current data: Dense interpolated field for Houston.

**Main shape**

```ts
interface HeatmapMetricPoint {
  metric: string; // e.g. "heat_risk_score"
  value: number; // 0-100 heat risk weight
  location_name: string;
  location_coordinates: [number, number]; // [lon, lat]
  individual_metrics?: {
    temperatureF: number;
    heatIndexF: number;
    relativeHumidityPct: number;
    landSurfaceTempF: number;
    nighttimeTempF: number;
    treeCanopyPct: number;
    imperviousSurfacePct: number;
  };
}
```

#### `getCoordinateValue()`

- Purpose: Returns dense coordinate-level heat profile values for full-grid analytics.
- Returns: `Promise<MetricCoordinateData[]>`
- Current metric key: `heat_profile`

**Main shape**

```ts
interface MetricCoordinateData {
  metric: 'heat_profile';
  points: CoordinateValue[];
}

interface CoordinateValue {
  coordinate: [number, number];
  value: number; // alias of temperatureF
  temperatureF: number;
  relativeHumidityPct: number;
  heatIndexF: number;
  landSurfaceTempF: number;
  nighttimeTempF: number;
  treeCanopyPct: number;
  imperviousSurfacePct: number;
  heatVulnerabilityIndex: number;
  category: 'low' | 'moderate' | 'high' | 'extreme';
}
```

### Statistics API (`src/api/statistics.ts`)

#### `callMockStatistics(city)`

- Purpose: Fetches dashboard cards + POI statistics for a selected city.
- Input: `city: string`
- Returns: `Promise<CityStatisticsResponse>`
- Fallback behavior: If city is unknown, data falls back to `Nationally`.

**Main shape**

```ts
interface CityStatisticsResponse {
  overallStatistics: OverallStatisticsProps;
  poiStatistics: POIStatisticsProps;
}
```

## Usage Example

```ts
import {
  callMockLocationPOIs,
  callHeatmapMetricsPoints,
  getCoordinateValue,
} from './src/api/map';
import { callMockStatistics } from './src/api/statistics';

const pois = await callMockLocationPOIs();
const pointsByCity = await callHeatmapMetricsPoints();
const coordinateMetrics = await getCoordinateValue();
const stats = await callMockStatistics('Houston');
```

## Notes

- These APIs are asynchronous and include simulated network latency.
- Data is mock data for frontend development and visualization behavior.
- Coordinate order is longitude, latitude across map APIs.
