# Backend App Guide

This folder contains the FastAPI backend for the FIFA HeatSafe prototype. It owns the API routes, database models, request/response schemas, database migrations, and service code used to build grid-based heat, weather, and simulation layers.

## Navigation

| Need | Go To |
|---|---|
| Install and run the API | [Quick Start](#quick-start) |
| Understand code organization | [How The Backend Is Organized](#how-the-backend-is-organized) |
| Find route files and folders | [Folder Map](#folder-map) |
| See route groups | [Route Groups](#route-groups) |
| Run Postman in the right order | [Recommended Postman Flow](#recommended-postman-flow) |
| Debug common route issues | [Common Gotchas](#common-gotchas) |
| Run validation checks | [Quick Checks](#quick-checks) |

## Quick Start

Run these commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set the required environment variables:

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
export JWT_KEY="dev-secret-key"
```

Start the API from the `app/` folder:

```bash
cd app
python3 -m uvicorn main:app --reload
```

The default local API URL is:

```text
http://127.0.0.1:8000
```

Use the interactive docs at:

```text
http://127.0.0.1:8000/docs
```

## How The Backend Is Organized

The app now follows a router/service/repository style:

```text
HTTP request
  -> routers/       FastAPI endpoints, validation, HTTP errors
  -> services/      business logic, calculations, external API calls
  -> repository/    SQLAlchemy database queries and writes
  -> models/        database table definitions
  -> schemas/       Pydantic request and response shapes
```

Keep route files thin when possible. If code is mostly database querying, put it in `repository/`. If code is a calculation, GeoJSON conversion, NWS fetch, interpolation step, or other business rule, put it in `services/`.

## Folder Map

| Folder | Purpose |
|---|---|
| [`routers/`](routers/) | FastAPI route modules for auth, datasets, grids, metrics, interpolation, and weather. |
| [`services/`](services/) | Business logic and external API helpers. |
| [`repository/`](repository/) | SQLAlchemy query/write helpers. |
| [`models/`](models/) | SQLAlchemy table definitions. |
| [`schemas/`](schemas/) | Pydantic request and response models. |
| [`security/`](security/) | Password hashing, OAuth2, and JWT helpers. |
| [`alembic/`](alembic/) | Alembic migration environment and migration files. |
| [`markdown_reference_guides/`](markdown_reference_guides/README.md) | Human-readable dataset/model reference docs. |

## Main Files

| File | Purpose |
|---|---|
| [`main.py`](main.py) | Creates the FastAPI app and includes all routers. |
| [`database.py`](database.py) | Creates the SQLAlchemy engine, session factory, base model, and `get_db()` dependency. |
| [`alembic.ini`](alembic.ini) | Alembic configuration. |

## Route Groups

Routes are registered in [`main.py`](main.py).

### Auth And Users

| Action | Method | Path | Auth |
|---|---:|---|---|
| Create user | `POST` | `/users/` | No |
| Login | `POST` | `/login/` | No |
| Get current user | `GET` | `/users/me` | Yes |
| Change password | `PUT` | `/users/me/password` | Yes |
| Delete current user | `DELETE` | `/users/me` | Yes |
| Get user by ID | `GET` | `/users/{id}` | No |

Use `/login/` with form-data fields `username` and `password`. Protected dataset routes need `Authorization: Bearer <token>`.

### Dataset CRUD

Dataset routes are defined in [`routers/dataset.py`](routers/dataset.py). The reusable database logic lives in [`repository/dataset_repository.py`](repository/dataset_repository.py).

All dataset routes require a logged-in user.

| Resource | Path |
|---|---|
| Core POI geometry | `/dataset/core_poi_geometry_table` |
| Daily spend by brand/state | `/dataset/daily_spend_brand_state` |
| Daily weather | `/dataset/daily_weather` |
| Spending patterns | `/dataset/spending_patterns` |
| Store visits | `/dataset/store_visits` |
| Urban heat index | `/dataset/urban_heat_index` |

Each resource supports:

```text
GET /dataset/{resource}
POST /dataset/{resource}
GET /dataset/{resource}/{id}
PUT /dataset/{resource}/{id}
DELETE /dataset/{resource}/{id}
```

### Grid Geometry

Grid geometry routes are defined in [`routers/grid_geometry.py`](routers/grid_geometry.py). Database logic lives in [`repository/grid_geometry_repository.py`](repository/grid_geometry_repository.py), and GeoJSON/geometry helpers live in [`services/grid_geometry_services.py`](services/grid_geometry_services.py).

| Action | Method | Path |
|---|---:|---|
| Generate state grid | `POST` | `/grid/generate_nxn_grid?state_name=Texas&n=40` |
| Generate city grid | `POST` | `/grid/generate_nxn_grid_city?city=Houston&state=Texas&n=40` |
| Get all grid cells | `GET` | `/grid/all` |
| Get grid by DB ID | `GET` | `/grid/id/{id}` |
| Get grid by cell ID | `GET` | `/grid/cell/{cell_id}` |
| Get grids by state | `GET` | `/grid/state/{state}` |
| Get grids by city/state | `GET` | `/grid/city?city=Houston&state=Texas` |
| Get state grid GeoJSON | `GET` | `/grid/state/{state}/geojson` |
| Get grid map GeoJSON | `GET` | `/grid/map/geojson` |

Regenerating a grid replaces existing cells for that city/state or state. Dependent grid metrics, interpolated points, and weather observations can be removed during replacement, so treat grid regeneration as a reset step.

### Grid Metrics

Grid metrics routes are defined in [`routers/grid_metrics.py`](routers/grid_metrics.py). Database logic lives in [`repository/grid_metrics_repository.py`](repository/grid_metrics_repository.py), and response helpers live in [`services/grid_metrics_services.py`](services/grid_metrics_services.py).

| Action | Method | Path |
|---|---:|---|
| Create grid metrics | `POST` | `/grid_metrics/create` |
| Assign metrics to all grids | `POST` | `/grid_metrics/assign_all?state=Texas&replace_existing=true` |
| Get all metrics | `GET` | `/grid_metrics/all` |
| Get metrics for grid | `GET` | `/grid_metrics/grid/{grid_cell_id}` |
| Get latest metrics for grid | `GET` | `/grid_metrics/grid/{grid_cell_id}/latest` |
| Get latest metrics for all grids | `GET` | `/grid_metrics/latest` |
| Get metrics by state | `GET` | `/grid_metrics/state/{state}` |
| Get latest metrics by state | `GET` | `/grid_metrics/state/{state}/latest` |
| Update grid metrics | `PUT` | `/grid_metrics/update/{id}` |
| Delete grid metrics | `DELETE` | `/grid_metrics/delete/{id}` |

For testing, create or generate grid cells first. Then use `assign_all` to attach one metric row to every grid cell.

### Grid Interpolation

Grid interpolation routes are defined in [`routers/grid_interpolation.py`](routers/grid_interpolation.py). Database logic lives in [`repository/grid_interpolation_repository.py`](repository/grid_interpolation_repository.py), and interpolation/GeoJSON logic lives in [`services/grid_interpolation_service.py`](services/grid_interpolation_service.py).

| Action | Method | Path |
|---|---:|---|
| Get city grid cells as GeoJSON | `GET` | `/grid_interpolation/grid_cells_city?city=Houston&state=Texas` |
| Interpolate city grid | `POST` | `/grid_interpolation/interpolate` |
| Get all interpolated points as GeoJSON | `GET` | `/grid_interpolation/all` |
| Get interpolated mesh polygons | `GET` | `/grid_interpolation/mesh?city=Houston&state=Texas&timestamp=...&color_metric=heat_index` |
| Get heatmap-friendly points | `GET` | `/grid_interpolation/heatmap?city=Houston&state=Texas&timestamp=...&metric_key=heat_index` |
| Update interpolated point | `PUT` | `/grid_interpolation/update/{interpolated_id}` |
| Delete interpolated point | `DELETE` | `/grid_interpolation/delete/{interpolated_id}` |

Interpolation uses known metric values and fills values across grid-cell centroids. The mesh endpoint still returns grid-cell polygons, while the heatmap endpoint returns points with normalized intensity for smoother frontend heatmap rendering.

### NWS Weather

Weather routes are defined in [`routers/nws_weather.py`](routers/nws_weather.py). Database logic lives in [`repository/weather_repository.py`](repository/weather_repository.py), and National Weather Service fetch/assignment logic lives in [`services/nws_weather_service.py`](services/nws_weather_service.py).

| Action | Method | Path |
|---|---:|---|
| Get all weather observations | `GET` | `/weather/fetch/all` |
| Get weather for grid cell | `GET` | `/weather/fetch/{id}` |
| Create weather from NWS | `POST` | `/weather/fetch/create/{grid_cell_id}` |
| Update weather for grid cell | `PUT` | `/weather/fetch/update/{id}` |
| Delete weather observation | `DELETE` | `/weather/delete/{id}` |
| Get latest for grid cell | `GET` | `/weather/grid/{grid_cell_id}/latest` |
| Get history for grid cell | `GET` | `/weather/grid/{grid_cell_id}` |
| Assign weather to all cells | `POST` | `/weather/assign_all?max_workers=20&skip_existing=false` |
| Assign weather to state cells | `POST` | `/weather/assign_state?state=Texas&max_workers=20&skip_existing=false` |

Weather assignment calls the National Weather Service API. The backend fetches point metadata for each grid centroid, groups cells that share the same NWS hourly forecast URL, and fetches each repeated forecast only once per assignment run.

## Recommended Postman Flow

Import [`../postman_dataset_routes_collection.json`](../postman_dataset_routes_collection.json) into Postman and set `baseUrl` to your running API.

Recommended simulation setup order:

1. Run `Grid Geometry -> Generate N by N City Grid`.
2. Run `Grid Metrics -> Assign Metrics To All Grid Cells`.
3. Run `Grid Interpolation -> Interpolate City Grid`.
4. View either `Get Interpolated Heatmap GeoJSON` or `Get Interpolated Polygon Mesh GeoJSON`.
5. Run weather assignment only when you need NWS-backed weather observations.

For faster scoped weather testing, temporarily add a `limit` query parameter, such as `&limit=100`. For a full refresh, leave `limit` off.

Useful collection variables:

| Variable | Purpose |
|---|---|
| `baseUrl` | Local API base URL, usually `http://127.0.0.1:8000`. |
| `cityName` / `stateName` | City and state used for grid generation and filtered reads. |
| `gridSize` | `n` for an `n x n` grid. |
| `gridCellId` | Numeric database ID for one grid cell. |
| `gridCellIdText` | Human-readable cell ID string. |
| `metricTimestamp` | Timestamp used when creating grid metrics. |
| `interpolationTimestamp` | Timestamp used when reading/writing interpolated values. Match this to `metricTimestamp` during normal tests. |
| `interpolationMetric` | Metric interpolated by the Postman request, such as `heat_index` or `population`. |
| `colorMetric` | Metric used to color the polygon mesh. |
| `heatmapMetric` | Metric used for the heatmap point intensity. |

## Common Gotchas

If interpolation returns no useful metric values, make sure grid metrics exist for the same city/state and timestamp. During normal testing, keep `metricTimestamp` and `interpolationTimestamp` the same.

If a route says a grid cell was not found, regenerate a city grid and then rerun `Set Grid Cell ID From Grid List` in the Postman collection.

`/grid_metrics/all` can be slower than filtered metric routes because it returns every metric row. Prefer `/grid_metrics/latest`, `/grid_metrics/state/{state}`, or `/grid_metrics/state/{state}/latest` for normal map work.

The polygon mesh endpoint is still discrete because it returns one polygon per grid cell. For a smoother visual surface, feed the heatmap GeoJSON endpoint into a frontend heatmap layer.

## Quick Checks

From the repository root:

```bash
python3 -m compileall -q app
```

Validate the Postman JSON:

```bash
python3 -m json.tool postman_dataset_routes_collection.json >/tmp/postman.json
```
