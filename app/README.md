# App Folder Guide

This folder contains the current backend app, database setup, SQLAlchemy dataset models, Alembic migrations, and dataset reference documentation.

## Table of Contents

| Go To | What It Covers |
|---|---|
| [Top-Level Files](#top-level-files) | Main backend files in `app/` |
| [Folders](#folders) | What each app subfolder is for |
| [Route Reference](#route-reference) | Auth, user, and dataset routes |
| [Run Checks](#run-checks) | Quick commands to verify the app imports |
| [Database And Env Notes](#database-and-env-notes) | How environment variables, SQLAlchemy, and Alembic fit together |

## Top-Level Files

| File | Purpose |
|---|---|
| [`main.py`](main.py) | FastAPI entrypoint. Creates the `FastAPI()` app and imports models so table metadata is registered. |
| [`database.py`](database.py) | Sets up the SQLAlchemy engine, session factory, declarative `Base`, and `get_db()` dependency. |
| [`alembic.ini`](alembic.ini) | Alembic configuration file for database migrations. |
| [`README.md`](README.md) | This app-folder overview. |

## Folders

| Folder | Purpose |
|---|---|
| [`models/`](models/) | SQLAlchemy model definitions. Dataset tables live in [`models/dataset_tables.py`](models/dataset_tables.py), users live in [`models/user_tables.py`](models/user_tables.py), and prediction outputs live in [`models/prediction_tables.py`](models/prediction_tables.py). |
| [`alembic/`](alembic/) | Alembic migration environment and migration scripts. Use this when database schemas change. |
| [`markdown_reference_guides/`](markdown_reference_guides/README.md) | Human-readable dataset/model reference docs with clickable links into each dataset guide. |
| [`routers/`](routers/) | FastAPI route modules: [`routers/dataset.py`](routers/dataset.py), [`routers/users.py`](routers/users.py), [`routers/login.py`](routers/login.py), and [`routers/nws_weather.py`](routers/nws_weather.py). |
| [`schemas/`](schemas/) | Pydantic request/response schemas for datasets, users, and auth tokens. |
| [`security/`](security/) | Password hashing and OAuth2/JWT helpers. |
| [`services/`](services/) | External API clients and non-database business logic, such as National Weather Service helpers. |

## Route Reference

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

`/login/` expects form data with `username` and `password`. Use the returned bearer token for protected routes.

### Dataset Routes

All dataset routes require `Authorization: Bearer <token>`. Created rows are tied to the logged-in user.

Current resources:

| Resource | Supported Methods |
|---|---|
| `core_poi_geometry_table` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |
| `daily_spend_brand_state` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |
| `daily_weather` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |
| `spending_patterns` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |
| `store_visits` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |
| `urban_heat_index` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |

Use [`../postman_dataset_routes_collection.json`](../postman_dataset_routes_collection.json) to test the routes in Postman. Run `Create User`, then `Login`, then dataset requests.

### Grid Geometry Routes

Grid routes are defined in [`routers/grid_geometry.py`](routers/grid_geometry.py).

| Action | Method | Path |
|---|---:|---|
| Generate state grid | `POST` | `/grid/generate_nxn_grid?state_name=Texas&n=40` |
| Generate city grid | `POST` | `/grid/generate_nxn_grid_city?city=Houston&state=Texas&n=40` |
| Get all grid cells | `GET` | `/grid/all` |
| Get grid by DB ID | `GET` | `/grid/id/{id}` |
| Get grid by cell ID | `GET` | `/grid/cell/{cell_id}` |
| Get grids by state | `GET` | `/grid/state/{state}` |
| Get state grid GeoJSON | `GET` | `/grid/state/{state}/geojson` |
| Get grid map GeoJSON | `GET` | `/grid/map/geojson` |

Use the `Grid Geometry` folder in [`../postman_dataset_routes_collection.json`](../postman_dataset_routes_collection.json). Regenerating a grid replaces the existing grid cells for that state. Generate or load grid cells before creating NWS weather observations.

### Grid Metrics Routes

Grid metrics routes are defined in [`routers/grid_metrics.py`](routers/grid_metrics.py).

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

Use the `Grid Metrics` folder in [`../postman_dataset_routes_collection.json`](../postman_dataset_routes_collection.json). Metrics should be created after at least one grid cell exists.

### NWS Weather Routes

Weather routes are defined in [`routers/nws_weather.py`](routers/nws_weather.py). They use [`services/national_weather.py`](services/national_weather.py) to fetch selected National Weather Service data for a stored grid cell.

| Action | Method | Path |
|---|---:|---|
| Get all weather observations | `GET` | `/weather/fetch/all` |
| Get weather for grid cell | `GET` | `/weather/fetch/{id}` |
| Create weather from NWS | `POST` | `/weather/fetch/create/{grid_cell_id}` |
| Update weather for grid cell | `PUT` | `/weather/fetch/update/{id}` |
| Delete weather observation | `DELETE` | `/weather/delete/{id}` |
| Get latest for grid cell | `GET` | `/weather/grid/{grid_cell_id}/latest` |
| Get history for grid cell | `GET` | `/weather/grid/{grid_cell_id}` |

Use the `NWS Weather` folder in [`../postman_dataset_routes_collection.json`](../postman_dataset_routes_collection.json). Set `gridCellId` to an existing `grid_cell_geometry.id` before creating weather from NWS.

## Run Checks

From the repository root:

```bash
python3 -m compileall -q app
```

```bash
DATABASE_URL="sqlite:///./local.db" JWT_KEY="dev-secret-key" python3 - <<'PY'
import sys
sys.path.insert(0, "app")
import main
PY
```

## Database And Env Notes

`database.py` expects `DATABASE_URL` to be set before the app imports the database layer. JWT token creation also needs `JWT_KEY`.

Local SQLite example:

```bash
export DATABASE_URL="sqlite:///./local.db"
export JWT_KEY="dev-secret-key"
```

Postgres example:

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
```

The dataset table classes live in [`models/dataset_tables.py`](models/dataset_tables.py). Prediction table classes live in [`models/prediction_tables.py`](models/prediction_tables.py). The `models/__init__.py` file exports those classes so `import models` registers the table metadata with SQLAlchemy and Alembic.
