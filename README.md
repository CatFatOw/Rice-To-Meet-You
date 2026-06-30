# Rice-To-Meet-You: FIFA HeatSafe AI

2026 Rice University FIFA Summer Hackathon project.

Rice-To-Meet-You is building a FIFA HeatSafe AI prototype: an online decision-support tool that helps visitors and city professionals predict heat, dehydration, weather, energy-use, and crowd-overlap danger zones around FIFA 2026 host cities while simulating actions.

## Table of Contents

| Go To | What It Contains |
|---|---|
| [Project Mission](#project-mission) | What the project is trying to accomplish |
| [Project Idea](#project-idea) | Current product direction from team planning |
| [App Guide](#app-guide) | App structure, setup, checks, and key files |
| [App Folder README](app/README.md) | More detailed map of files inside `app/` |
| [Markdown Reference Guides](app/markdown_reference_guides/README.md) | Dataset/model documentation landing page |

## Project Mission

Build a useful, credible, and polished FIFA 2026 HeatSafe platform that helps host cities and visitors understand where heat risk, dehydration risk, crowd activity, weather conditions, and energy pressure may overlap.

The goal is to turn Rice-provided datasets into clear maps, timelines, risk scores, and planning simulations that help cities prepare safer routes, cooling zones, shade structures, medical staffing, and other heat-resilience interventions.

## Project Idea

The current prototype direction is **FIFA HeatSafe AI**.

| Feature | Purpose |
|---|---|
| Heat mapping | Show red, orange, and green risk zones across a selected city or state |
| Visitor mapping | Estimate where visitor and business activity may concentrate |
| Risk score mapping | Combine heat, weather, and visitor activity into an easy-to-read risk score |
| Future timeline | Extend predictions forward using historical weather and activity data |
| Simulation platform | Let planners test interventions such as shade structures and cooling zones |
| Planning recommendations | Help identify where hydration, cooling, shade, transit, and medical support may matter most |

Key datasets for the first version:

| Dataset | Why It Matters |
|---|---|
| Daily Weather | Climate, weather, and energy-risk prediction |
| Core POI Geometry | Locations, points of interest, business areas, and possible visitor activity |
| Urban Heat Index | Relative urban heat intensity across locations |
| Store Visits | Business traffic and possible crowd/activity signals |

## App Guide

| File or Folder | Purpose |
|---|---|
| [`app/README.md`](app/README.md) | App-folder overview and file map |
| [`app/main.py`](app/main.py) | FastAPI app entrypoint |
| [`app/database.py`](app/database.py) | SQLAlchemy engine, session, and base model setup |
| [`app/models/dataset_models.py`](app/models/dataset_models.py) | SQLAlchemy models for Rice-provided datasets |
| [`app/alembic/`](app/alembic/) | Database migration setup |
| [`app/markdown_reference_guides/`](app/markdown_reference_guides/README.md) | Human-readable model and dataset reference docs |
| [`requirements.txt`](requirements.txt) | Python dependencies for the current backend app |

### Environment Setup

Make sure you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and opened, and [Dev Containers VSCode extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) installed. 

If you are using Windows, you also need to set up Windows Subsystem for Linux. Guide [here](https://learn.microsoft.com/en-us/windows/wsl/setup/environment). After setting up WSL, ensure the WSL 2 back-end is enabled: Right-click on the Docker taskbar item and select Settings. Check Use the WSL 2 based engine and verify your distribution is enabled under Resources > WSL Integration.

If you are using Linux, you are on your own. Good luck. Check out more information below

More information [here](https://code.visualstudio.com/docs/devcontainers/containers#_getting-started)

Now you can clone the repository:
```bash
git clone https://github.com/CatFatOw/Rice-To-Meet-You.git
cd Rice-To-Meet-You
git status
```

When you open the repository in the workspace, you should see a notification in the bottom right corner that asks if you want to reopen the workspace in a container. Click it. Alternatively, run the command "Dev Containers: Rebuild and Reopen in Container." The dependencies should be installed for you automatically.

Set `DATABASE_URL` before importing or running the app:

```bash
export DATABASE_URL="sqlite:///./local.db"
```

For Postgres:

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
```

### Run Checks

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
