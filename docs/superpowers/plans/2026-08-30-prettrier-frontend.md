# Prettrier Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize the dashboard visual language and add a 2D/3D map-view switch plus a passive 2D minimap without changing APIs, business logic, calculations, simulation behavior, or existing data contracts.

**Architecture:** The main MapLibre map and its DeckGL overlay continue to share the existing `viewState`. A local map presentation state in `Heatmap` changes camera pitch/bearing only; the existing layer stack and selected metric remain untouched. A second, non-interactive MapLibre instance displays the main map’s camera context and viewport outline.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS 4, MapLibre GL, DeckGL, lucide-react.

**Spec:** Approved in chat on 2026-08-30.

## Global Constraints

- Do not change backend code, API modules, requests, endpoint contracts, data transformations, calculations, simulation timing, or simulation outcomes.
- Preserve existing routes, controls, analytics content, map layers, selected metric behavior, drawing behavior, and fullscreen behavior.
- Only add the approved 2D/3D presentation control and passive 2D minimap.
- Add only the additionally approved map presentation options: dark data, street, and satellite imagery basemaps; a compact map-control cluster; true 3D building extrusions; and a frontend-only simulation progress/ETA display.
- Satellite imagery is current provider imagery, not live video or application data; preserve required map-source attribution on the main map.
- Do not add dependencies or commit existing untracked `.idea/`, `app/cache/`, or generated `frontend/pnpm-lock.yaml` files.
- Use restrained motion and honor `prefers-reduced-motion`.

---

### Task 1: Establish a consistent visual system

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/App.css`
- Modify: `frontend/src/pages/ExplorePage.tsx`
- Modify: `frontend/src/components/NavigationBar.tsx`
- Modify: `frontend/src/components/OverallStatistics.tsx`
- Modify: `frontend/src/components/POIStatistics.tsx`
- Modify: `frontend/src/components/SimulatePanel.tsx`

**Interfaces:**
- Consumes: Existing component props and Tailwind class composition.
- Produces: Visual-only tokens and consistent shell/panel/control styling; no prop or behavior changes.

- [ ] Define shared neutral surfaces, typography, focus states, and reduced-motion behavior in global CSS.
- [ ] Apply the visual tokens to the page shell, navigation, analytics panels, table, and simulation controls.
- [ ] Preserve all existing component props, button handlers, labels, and data rendering.
- [ ] Run `pnpm lint` and `pnpm build`.

### Task 2: Add the map presentation controls

**Files:**
- Modify: `frontend/src/components/Heatmap.tsx`
- Modify: `frontend/src/types/components.ts`

**Interfaces:**
- Consumes: Existing `viewState`, `setViewState`, MapLibre ref, DeckGL layer stack, and `HeatmapProps`.
- Produces: Local `mapMode` state (`'2d' | '3d'`) which changes only camera pitch/bearing, maintaining current center and zoom.

- [ ] Add a compact accessible segmented control with `aria-pressed` state.
- [ ] Make 2D set pitch/bearing to `0`; make 3D set a fixed oblique camera pitch/bearing while preserving longitude, latitude, zoom, selected city, selected metric, and all layers.
- [ ] Sync the existing MapLibre camera with the updated view state so its basemap remains aligned with DeckGL.
- [ ] Verify the heatmap layer stays visible in both modes and fullscreen behavior is unchanged.

### Task 3: Add a passive 2D minimap

**Files:**
- Modify: `frontend/src/components/Heatmap.tsx`

**Interfaces:**
- Consumes: Existing main `viewState`.
- Produces: A lifecycle-managed non-interactive MapLibre minimap and viewport outline; no API calls, events, or page state updates.

- [ ] Create the minimap on mount with the same basemap and 2D camera.
- [ ] Update its center/zoom and viewport outline whenever main `viewState` changes.
- [ ] Prevent interaction and hide default controls/attribution from the minimap.
- [ ] Remove minimap resources on unmount and keep it out of fullscreen collisions.

### Task 4: Validate the unchanged experience

**Files:**
- Test: Existing frontend build, lint, and simulation test commands.

- [ ] Run `pnpm lint`.
- [ ] Run `pnpm build`.
- [ ] Run `npx vitest run src/tests/simulation_test.ts`.
- [ ] Exercise 2D/3D switching, minimap synchronization, explore route, simulation route, and fullscreen in the local browser.
- [ ] Review `git diff --check` and the final file list to confirm only intended frontend files and the plan are included.

### Task 5: Refine map presentation and add basemap choices

**Files:**
- Modify: `frontend/src/components/Heatmap.tsx`

**Interfaces:**
- Consumes: Existing MapLibre map refs, controlled `viewState`, DeckGL overlay, and map-mode controls.
- Produces: Local presentation-only basemap selection and a lifecycle-safe 3D building extrusion layer; no application data/API state.

- [ ] Replace the exposed 2D/3D control with a compact, accessible map-control group that keeps the map workspace uncluttered.
- [ ] Add Dark, Streets, and Satellite imagery basemaps; use the existing dark Carto style as the default and disclose satellite as imagery rather than real-time video.
- [ ] Re-apply the synchronized camera state after a style changes and preserve DeckGL heatmap layers, selected city, selected metric, simulation frames, and fullscreen behavior.
- [ ] Add/build a MapLibre `fill-extrusion` building layer in 3D mode where vector-building data is available, and remove or hide it in 2D mode.
- [ ] Keep required map-source attribution visible on the primary map and avoid adding an application API request.

### Task 6: Reduce map clutter and add simulation progress feedback

**Files:**
- Modify: `frontend/src/components/Heatmap.tsx`
- Modify: `frontend/src/components/SimulatePanel.tsx`
- Modify: `frontend/src/types/statistics.ts`
- Modify: `frontend/src/types/components.ts` if a prop contract requires it
- Modify: `frontend/src/pages/ExplorePage.tsx`
- Modify: `frontend/src/pages/SimulationPage.tsx`

**Interfaces:**
- Consumes: Existing simulation `isRunning`, `loadingSimulation`, selected date range, and date-update callbacks.
- Produces: Visual-only progress/ETA inputs derived from existing timeline state; does not alter the runner, interval, API calls, or outcomes.

- [ ] Shrink and move the passive minimap to a lower-clutter position while preserving its 2D overview and viewport indicator.
- [ ] Derive a display-only progress fraction, completed frame count, and ETA from the already selected range/current date and existing simulation cadence.
- [ ] Pass the display-only data through existing frontend page/component prop boundaries and render a restrained progress bar/ETA only while a simulation runs or loads.
- [ ] Apply short, purposeful transitions to the new controls/progress state and preserve `prefers-reduced-motion` behavior.
