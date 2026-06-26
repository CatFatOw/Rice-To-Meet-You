# App Folder Guide

This folder contains the current backend app, database setup, SQLAlchemy dataset models, Alembic migrations, and dataset reference documentation.

## Table of Contents

| Go To | What It Covers |
|---|---|
| [Top-Level Files](#top-level-files) | Main backend files in `app/` |
| [Folders](#folders) | What each app subfolder is for |
| [Dataset Routes](#dataset-routes) | Current dataset CRUD API routes |
| [Run Checks](#run-checks) | Quick commands to verify the app imports |
| [Database Notes](#database-notes) | How `DATABASE_URL`, SQLAlchemy, and Alembic fit together |

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
| [`models/`](models/) | SQLAlchemy model definitions. Current dataset tables are defined in [`models/dataset_tables.py`](models/dataset_tables.py), and prediction outputs are defined in [`models/prediction_tables.py`](models/prediction_tables.py). |
| [`alembic/`](alembic/) | Alembic migration environment and migration scripts. Use this when database schemas change. |
| [`markdown_reference_guides/`](markdown_reference_guides/README.md) | Human-readable dataset/model reference docs with clickable links into each dataset guide. |
| [`routers/`](routers/) | FastAPI route modules. Current dataset routes live in [`routers/dataset.py`](routers/dataset.py). |
| [`schemas/`](schemas/) | Pydantic request and response schemas. Current dataset schemas live in [`schemas/dataset_schemas.py`](schemas/dataset_schemas.py). |

## Dataset Routes

Dataset CRUD routes are defined in [`routers/dataset.py`](routers/dataset.py) and registered by [`main.py`](main.py).

Base path:

```text
/dataset
```

Current resources:

| Resource | Supported Methods |
|---|---|
| `core_poi_geometry_table` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |
| `daily_spend_brand_state` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |
| `daily_weather` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |
| `spending_patterns` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |
| `store_visits` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |
| `urban_heat_index` | `GET`, `POST`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` |

Use [`../postman_dataset_routes_collection.json`](../postman_dataset_routes_collection.json) to test the routes in Postman. Import the file, set `baseUrl`, create a row first, then run the matching get/update/delete requests.

## Run Checks

From the repository root:

```bash
python3 -m compileall -q app
```

```bash
DATABASE_URL="sqlite:///./local.db" python3 - <<'PY'
import sys
sys.path.insert(0, "app")
import main
PY
```

## Database Notes

`database.py` expects `DATABASE_URL` to be set before the app imports the database layer.

Local SQLite example:

```bash
export DATABASE_URL="sqlite:///./local.db"
```

Postgres example:

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
```

The dataset table classes live in [`models/dataset_tables.py`](models/dataset_tables.py). Prediction table classes live in [`models/prediction_tables.py`](models/prediction_tables.py). The `models/__init__.py` file exports those classes so `import models` registers the table metadata with SQLAlchemy and Alembic.
