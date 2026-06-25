# Markdown Reference Guides

This folder contains human-readable documentation for the app's dataset models. Use it when you need to understand what a table represents, which columns matter, how datasets connect, or where a model is defined in the backend.

## Table of Contents

| Go To | What It Explains |
|---|---|
| [Dataset Model Guides](#dataset-model-guides) | Clickable list of every current dataset guide |
| [How to Use These Guides](#how-to-use-these-guides) | What each guide section is for |
| [Model Source Files](#model-source-files) | Where the SQLAlchemy models live |
| [Dataset Relationship Map](#dataset-relationship-map) | Which datasets are useful together |
| [Adding a New Guide](#adding-a-new-guide) | Steps for documenting future datasets |

## Dataset Model Guides

| Dataset / Table | Reference Guide | Best For |
|---|---|---|
| `core_poi_geometry` | [core_poi_geometry.md](dataset_models_reference/core_poi_geometry.md) | POIs, building footprints, parking lots, categories, coordinates |
| `daily_spend_brand_state_rice` | [daily_spend_brand_state_rice.md](dataset_models_reference/daily_spend_brand_state_rice.md) | Brand-level spending by day, market, and state |
| `daily_weather_rice` | [daily_weather_rice.md](dataset_models_reference/daily_weather_rice.md) | Weather features for heat-risk modeling |
| `spend_patterns_rice` | [spend_patterns_rice.md](dataset_models_reference/spend_patterns_rice.md) | Business spending behavior, customer patterns, online vs in-person activity |
| `store_visits_rice` | [store_visits.md](dataset_models_reference/store_visits.md) | Daily foot traffic and commercial activity |
| `urban_heat_index` | [urban_heat_index.md](dataset_models_reference/urban_heat_index.md) | Urban Heat Island measurements and heat hotspot mapping |

## How to Use These Guides

| Section | Use It For |
|---|---|
| Overview | Understanding what the dataset represents |
| Most Useful Columns | Finding the fields most relevant to FIFA 2026 planning |
| Column Reference | Checking column names, types, examples, and plain-English meanings |
| Relationships | Seeing how this dataset can connect to other datasets |
| Possible Uses | Finding analysis, dashboard, and modeling ideas |
| Limitations | Knowing what the dataset cannot safely prove on its own |

## Model Source Files

| Source | Purpose |
|---|---|
| [`../models/dataset_tables.py`](../models/dataset_tables.py) | SQLAlchemy dataset table definitions |
| [`../models/prediction_tables.py`](../models/prediction_tables.py) | SQLAlchemy prediction table definitions |
| [`../models/__init__.py`](../models/__init__.py) | Exports the model classes so `import models` registers metadata |
| [`../database.py`](../database.py) | Database engine, session, and declarative base |
| [`../alembic/`](../alembic/) | Migration setup |

## Dataset Relationship Map

| Dataset | Connects Well With | Typical Link |
|---|---|---|
| `core_poi_geometry` | `spend_patterns_rice`, `urban_heat_index`, `store_visits_rice` | `placekey`, coordinates, market, category |
| `daily_weather_rice` | `daily_spend_brand_state_rice`, `store_visits_rice`, `urban_heat_index` | date, market/city, state, nearby station |
| `urban_heat_index` | `core_poi_geometry`, `store_visits_rice`, `spend_patterns_rice` | coordinates, geographic proximity, market |
| `store_visits_rice` | `daily_weather_rice`, `spend_patterns_rice`, `daily_spend_brand_state_rice` | date, brand, market, state, NAICS code |
| `spend_patterns_rice` | `core_poi_geometry`, `daily_weather_rice`, `daily_spend_brand_state_rice` | placekey, coordinates, brand, market, date range |
| `daily_spend_brand_state_rice` | `daily_weather_rice`, `spend_patterns_rice`, `store_visits_rice` | date, brand, market, state |

## Adding a New Guide

1. Add or update the SQLAlchemy model in [`../models/dataset_tables.py`](../models/dataset_tables.py).
2. Create a new markdown file in [`dataset_models_reference/`](dataset_models_reference/).
3. Include overview, useful columns, column reference, relationships, possible uses, and limitations.
4. Add the new guide to [Dataset Model Guides](#dataset-model-guides).
5. Run the app checks from the root [`README.md`](../../README.md#run-checks).
