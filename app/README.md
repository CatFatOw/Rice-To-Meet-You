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
| [`routers/`](routers/) | FastAPI route modules: [`routers/dataset.py`](routers/dataset.py), [`routers/users.py`](routers/users.py), and [`routers/login.py`](routers/login.py). |
| [`schemas/`](schemas/) | Pydantic request/response schemas for datasets, users, and auth tokens. |
| [`security/`](security/) | Password hashing and OAuth2/JWT helpers. |

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
