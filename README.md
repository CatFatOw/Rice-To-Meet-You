# Rice-To-Meet-You: FIFA HeatSafe AI

2026 Rice University FIFA Summer Hackathon project.

Rice-To-Meet-You is a FIFA HeatSafe AI prototype: a backend-first decision-support tool for mapping heat, weather, crowd, infrastructure, and intervention risk across host-city grids.

## Start Here

| Need | Go To |
|---|---|
| Use the dev container | [Dev Container Setup](#dev-container-setup) |
| Run the backend locally | [Run Locally](#run-locally) |
| Understand the backend architecture | [Backend Architecture](#backend-architecture) |
| Test requests in Postman | [Postman Workflow](#postman-workflow) |
| See route groups | [API Map](#api-map) |
| Learn the simulation flow | [Simulation Workflow](#simulation-workflow) |
| Read detailed app docs | [App README](app/README.md) |

## Project Mission

The goal is to help visitors and city planners understand where heat risk, dehydration risk, crowd activity, weather conditions, and infrastructure pressure overlap.

The prototype turns city/state geometry and heat-safety signals into:

| Feature | Purpose |
|---|---|
| Grid generation | Split a city/state into simulation cells. |
| Grid metrics | Store heat, crowd, population, cooling-center, and infrastructure signals per cell. |
| Polygon impact regions | Save drawn simulation polygons and mark the grid cells inside them. |
| Interpolation | Fill metric values across grid centroids for map rendering and simulation. |
| NWS weather | Attach National Weather Service weather baselines to grid cells. |
| Postman collection | Provide repeatable API testing flows for teammates. |

## Dev Container Setup

For the easiest team setup, use the repository dev container.

Install and open:

| Tool | Link |
|---|---|
| Docker Desktop | <https://www.docker.com/products/docker-desktop/> |
| VS Code Dev Containers extension | <https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers> |

Windows users should also set up WSL 2:

```text
https://learn.microsoft.com/en-us/windows/wsl/setup/environment
```

After cloning the repository, VS Code should offer to reopen the workspace in a container. Accept that prompt, or run:

```text
Dev Containers: Rebuild and Reopen in Container
```

Dependencies should install automatically inside the container.

## Frontend APIs

### 1. Get Location POIs

**Purpose:** Retrieve polygon boundaries for points of interest (POIs) to display on the map.

**Request**

```http

GET /heatmap/location-pois

```

**Expected Response**

```ts

interface CityPOIArea {

  id: string;

  name: string;

  cityName: string;

  color: [number, number, number, number]; // RGBA

  polygon: [number, number][];

}

type Response = CityPOIArea[];

```

---

### 2. Get Heatmap Metric Points

**Purpose:** Retrieve weighted heatmap points for each city.

**Request**

```http

GET /heatmap/metrics/points

```

**Expected Response**

```ts

interface HeatmapMetricPoint {

  metric: string;

  value: number;

  location_name: string;

  location_coordinates: [number, number]; // [longitude, latitude]

}

type Response = Record<string, HeatmapMetricPoint[]>;

```

## App Guide

## Run Locally

If you are not using the dev container, install dependencies from the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set environment variables:

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
export JWT_KEY="dev-secret-key"
```

Run migrations:

```bash
cd app
alembic upgrade head
```

Start FastAPI from the `app/` folder:

```bash
python3 -m uvicorn main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Backend Architecture

The backend uses a router/service/repository structure:

```text
request
  -> routers/       FastAPI endpoints and HTTP errors
  -> services/      business logic, GeoJSON conversion, interpolation, NWS calls
  -> repository/    SQLAlchemy database reads/writes
  -> models/        SQLAlchemy tables
  -> schemas/       Pydantic payloads/responses
```

Key folders:

| Path | Purpose |
|---|---|
| [`app/routers/`](app/routers/) | API route definitions. |
| [`app/services/`](app/services/) | Business logic and external API calls. |
| [`app/repository/`](app/repository/) | Database query helpers. |
| [`app/models/`](app/models/) | SQLAlchemy models. |
| [`app/schemas/`](app/schemas/) | Pydantic schemas. |
| [`app/alembic/`](app/alembic/) | Migrations. |
| [`app/README.md`](app/README.md) | Detailed backend guide. |

## Simulation Workflow

Recommended backend flow:

1. Generate a city grid.
2. Draw or save a polygon impact region.
3. Compute impacted grids for the polygon.
4. Assign or run simulation changes against only those impacted grid IDs.
5. Interpolate metric values.
6. Render heatmap/mesh GeoJSON in the frontend.
7. Assign NWS weather as a regional baseline.
8. Combine weather + grid metrics for local simulation risk.

In Postman, that usually means:

```text
Grid Geometry / Generate N by N City Grid
Polygon / Create Polygon And Compute Impact Grids
Grid Metrics / Assign Metrics To All Grid Cells
Grid Interpolation / Interpolate City Grid
Grid Interpolation / Get Interpolated Heatmap GeoJSON
NWS Weather / Assign Weather To State Grid Cells
```

## API Map

Detailed routes are documented in [app/README.md](app/README.md). High-level route groups:

| Group | Prefix | Purpose |
|---|---|---|
| Users | `/users` | User creation, profile, password, deletion. |
| Login | `/login` | JWT bearer token login. |
| Datasets | `/dataset` | Protected CRUD for Rice dataset tables. |
| Grid Geometry | `/grid` | Generate/read state and city grid cells. |
| Grid Metrics | `/grid_metrics` | Create/read/update/delete simulation metrics. |
| Grid Interpolation | `/grid_interpolation` | Interpolate metrics and return GeoJSON. |
| NWS Weather | `/weather` | Fetch and assign National Weather Service observations. |
| Polygons | `/polygon` | Store drawn impact regions and compute impacted grid cells. |

## Postman Workflow

Import [`postman_dataset_routes_collection.json`](postman_dataset_routes_collection.json) into Postman.

Important collection variables:

| Variable | Purpose |
|---|---|
| `baseUrl` | API URL, usually `http://127.0.0.1:8000`. |
| `cityName` | City used for city grid/interpolation routes. |
| `stateName` | State used for grid/metric/weather routes. |
| `gridSize` | `n` for an `n x n` grid. |
| `metricTimestamp` | Timestamp for grid metrics. |
| `interpolationTimestamp` | Timestamp for interpolation; usually match `metricTimestamp`. |
| `interpolationMetric` | Metric to interpolate, such as `heat_index` or `population`. |
| `heatmapMetric` | Metric used for heatmap intensity. |
| `colorMetric` | Metric used for mesh color. |
| `polygonId` | Saved polygon ID used for impacted-grid reads and recomputation. |

Good first test order:

1. `Users and Auth / Create User`
2. `Users and Auth / Login`
3. `Grid Geometry / Generate N by N City Grid`
4. `Polygon / Create Polygon And Compute Impact Grids`
5. `Grid Metrics / Assign Metrics To All Grid Cells`
6. `Grid Interpolation / Interpolate City Grid`
7. `Grid Interpolation / Get Interpolated Heatmap GeoJSON`

For a full weather refresh, use:

```text
NWS Weather / Assign Weather To State Grid Cells
```

That request currently uses:

```text
/weather/assign_state?state={{stateName}}&max_workers=20&skip_existing=false
```

Weather assignment deduplicates repeated NWS forecast URLs during each run, so many app grid cells can share one NWS forecast request.

## Checks

Run these before pushing backend changes:

```bash
python3 -m compileall -q app
```

```bash
python3 -m json.tool postman_dataset_routes_collection.json >/tmp/postman.json
```

Optional import smoke test:

```bash
DATABASE_URL="sqlite:///./local.db" JWT_KEY="dev-secret-key" python3 -c "import sys; sys.path.insert(0, 'app'); import main"
```

## Reference Docs

| Resource | Link |
|---|---|
| Detailed backend guide | [app/README.md](app/README.md) |
| Dataset/model docs | [app/markdown_reference_guides/README.md](app/markdown_reference_guides/README.md) |

## Project Rules

- Keep `main` stable for approved final-demo or submission work.
- Do active development on personal or feature branches.
- Prefer small, clear commits with descriptive messages.
- Keep docs and Postman updated when routes change.
- Ask the group before destructive Git commands or deleting branches that Git says are not merged.
