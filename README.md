# Rice-To-Meet-You · FIFA HeatSafe AI

<p align="center">
  <strong>Decision support for safer FIFA host-city experiences.</strong><br />
  Map heat, weather, infrastructure, POIs, and relative activity signals in one planning workspace.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/backend-Python%20%2B%20FastAPI-3776AB?logo=fastapi&logoColor=white" />
  <img alt="React" src="https://img.shields.io/badge/frontend-React%20%2B%20Vite-61DAFB?logo=react&logoColor=111827" />
  <img alt="PostgreSQL" src="https://img.shields.io/badge/data-PostgreSQL%20%2B%20PostGIS-4169E1?logo=postgresql&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/status-hackathon%20prototype-22C55E" />
</p>

> **Built for the 2026 Rice University FIFA Summer Hackathon.**
> This is a research/demo prototype. Its supplied datasets are transformed and
> anonymized; outputs demonstrate analytical workflows and must not be treated
> as real-world operational guidance.

---

## Why it exists

FIFA host cities need to reason about more than temperature alone. A hot grid
cell becomes materially more important when it intersects with crowd activity,
POIs, vulnerable infrastructure, and a planned event footprint.

Rice-To-Meet-You turns those signals into an interactive workspace for:

- exploring heat and weather risk across city grids;
- finding nearby real-world POI metadata from Foursquare;
- modeling polygon-based interventions and their impacted cells;
- comparing relative activity/traffic signals with local historical context;
- preparing ML-ready feature exports with transparent data provenance.

## What the app does

| Capability | What it provides |
| --- | --- |
| **Heat & weather map** | Grid-based metrics, interpolation, and NWS weather baselines. |
| **POI discovery** | Current Foursquare POIs by latitude/longitude, category, and distance. |
| **Relative traffic score** | On-demand BestTime busyness score when that provider covers the selected venue. |
| **Scenario simulation** | Draw polygons, identify affected grid cells, and apply simulated interventions. |
| **Data pipeline** | Point-level heat/weather and provenance-aware Foursquare/visitor CSV exports. |

## System overview

```mermaid
flowchart LR
  UI[React + Vite map workspace] --> API[FastAPI router layer]
  API --> GEO[Grid / polygon / interpolation services]
  API --> DB[(PostgreSQL + PostGIS)]
  API --> NWS[National Weather Service]
  API --> FSQ[Foursquare Places]
  API --> BT[BestTime traffic score]
  GEO --> UI
  DB --> GEO
```

## Live data, explained honestly

| Source | Used for | Important limitation |
| --- | --- | --- |
| **Foursquare Places** | POI name, category, coordinates, address, and distance. | Does **not** provide public daily visitor counts. |
| **BestTime** | Relative live/forecast busyness score, normally `0–100`. | It is not an absolute visitor count and may be unavailable for a venue. |
| **NWS** | Weather and forecast baselines. | Weather is station/grid data, not a crowd sensor. |
| **Rice hackathon datasets** | Historical transformed visitor, weather, UHI, spend, and POI signals. | Visitor data is sometimes only available at brand/market grain. |

The UI and CSV exports keep this distinction explicit: raw visitor counts,
relative traffic scores, interpolated values, and unavailable fields are never
presented as the same measurement.

## Quick start

### 1. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
export JWT_KEY="dev-secret-key"
export FOURSQUARE_API_KEY="your-foursquare-key"
export BESTTIME_API_KEY="your-besttime-key"

cd app
alembic upgrade head
python3 -m uvicorn main:app --reload
```

Backend docs: <http://127.0.0.1:8000/docs>

### 2. Frontend

```bash
cd frontend-backend-wired
npm install
npm run dev
```

Open <http://127.0.0.1:5173/explore>.

> Keep API keys in your shell, deployment secrets manager, or `.env` file that
> is ignored by Git. Never place them in client-side React code.

## Key API routes

| Route | Purpose |
| --- | --- |
| `GET /heatmap/metrics/grid` | Interpolated heatmap grid values. |
| `GET /heatmap/core-pois` | Stored core POI geometries. |
| `GET /foursquare/lookup?lat=...&lon=...` | Live nearby Foursquare POIs. |
| `GET /besttime/traffic?venue_name=...&venue_address=...` | On-demand relative BestTime score. |
| `POST /simulation/polygon` | Save an intervention polygon and compute impacted cells. |
| `POST /simulation/apply` | Apply a scenario to affected grid metrics. |

## Data outputs

| File | Purpose |
| --- | --- |
| `heat_weather_points.csv` | Dated weather-station point records with nearest-UHI context. |
| `foursquare_texas_poi_lookup.csv` | Current Houston/Dallas Foursquare POI snapshot. |
| `foursquare_visitor_metrics_cohesive.csv` | Provenance-aware Foursquare + historical visitor-market join. |
| `STREAM0_TABLE_BUILD_LOGIC.md` | Reproducible logic and provenance rules for the exported tables. |

The visitor-cohesive table only assigns a count to an individual POI when the
brand/market match is unambiguous. Ambiguous totals remain aggregate values.

## Project structure

```text
app/
├── routers/        # FastAPI endpoints and HTTP error handling
├── services/       # External APIs, geospatial logic, and interpolation
├── repository/     # SQLAlchemy query helpers
├── models/         # Database tables
├── schemas/        # Pydantic request/response contracts
└── alembic/        # Database migrations

frontend-backend-wired/
├── src/components/ # Map, POI, traffic, and dashboard UI
├── src/api/        # Typed backend API clients
└── src/pages/      # Explore and simulation views
```

## Development checks

```bash
python3 -m compileall -q app
npm --prefix frontend-backend-wired run build
```

## Team workflow

1. Create a feature branch.
2. Keep changes small and document new API/data fields.
3. Run backend and frontend checks.
4. Open a pull request with a concise summary and screenshots for UI work.

---

<p align="center">
  Made at Rice University for a safer, more resilient match-day experience.
</p>
