# Rice-To-Meet-You: FIFA HeatSafe AI

2026 Rice University FIFA Summer Hackathon project.

Rice-To-Meet-You is building a FIFA HeatSafe AI prototype: an online decision-support tool that helps visitors and city professionals predict heat, dehydration, weather, energy-use, and crowd-overlap danger zones around FIFA 2026 host cities while simulating actions.

## Table of Contents

| Go To | What It Contains |
|---|---|
| [Project Mission](#project-mission) | What the project is trying to accomplish |
| [Quick Start](#quick-start) | First steps for new contributors |
| [Project Idea](#project-idea) | Current product direction from team planning |
| [Meeting Notes](#meeting-notes) | Link to meeting-note files |
| [Git Workflow](#git-workflow) | Branches, commits, pushes, PRs, and cleanup after merge |
| [App Guide](#app-guide) | App structure, setup, checks, and key files |
| [App Folder README](app/README.md) | More detailed map of files inside `app/` |
| [Markdown Reference Guides](app/markdown_reference_guides/README.md) | Dataset/model documentation landing page |
| [Project Rules](#project-rules) | Team expectations for keeping `main` stable |

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

## Meeting Notes

Meeting notes live in the [`meeting_notes/`](meeting_notes/README.md) folder.

Current notes:

| Date | File |
|---|---|
| June 24 | [Rice Hack FIFA PDF](meeting_notes/Rice%20Hack%20FIFA_june_24.pdf) |

## Quick Start

| Task | Link |
|---|---|
| Clone this repository | [Clone the repo](#clone-the-repo) |
| Make your own branch | [Create a branch](#create-a-branch) |
| Save your work | [Commit changes](#commit-changes) |
| Push your work | [Push your branch](#push-your-branch) |
| Ask the team to review | [Open a pull request](#open-a-pull-request) |
| Clean up after merge | [After your PR is merged](#after-your-pr-is-merged) |
| Understand the app folder | [App Folder README](app/README.md) |
| Read dataset/model docs | [Markdown Reference Guides](app/markdown_reference_guides/README.md) |

## Git Workflow

### Clone the Repo

```bash
git clone https://github.com/CatFatOw/Rice-To-Meet-You.git
cd Rice-To-Meet-You
git status
```

### Create a Branch

Use `main` only for approved demo/submission work. Use your own branch for experiments, features, notes, and unfinished work.

```bash
git checkout main
git pull origin main
git checkout -b your-name/short-description
```

Example branch names:

```text
michael/heat-map-prototype
zac/transit-gap-analysis
sarah/demo-dashboard
```

### Commit Changes

```bash
git status
git add path/to/file
git commit -m "Describe your change"
```

### Push Your Branch

First push:

```bash
git push -u origin your-name/short-description
```

Later pushes:

```bash
git push
```

### Open a Pull Request

1. Push your branch.
2. Open `https://github.com/CatFatOw/Rice-To-Meet-You`.
3. Click **Compare & pull request**, or go to **Pull requests** -> **New pull request**.
4. Set **base** to `main`.
5. Set **compare** to your branch.
6. Write what changed, why it matters, whether AI helped, and what reviewers should check.

Do not merge into `main` until the group approves the pull request.

### After Your PR Is Merged

After GitHub says your PR has been merged:

```bash
git checkout main
git pull origin main
```

Delete the old local branch if you are finished with it:

```bash
git branch -d your-name/short-description
```

Delete the old remote branch if GitHub did not already delete it:

```bash
git push origin --delete your-name/short-description
```

If Git says the branch is not fully merged, stop and ask the group before deleting it.

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

Install dependencies:

```bash
pip install -r requirements.txt
```

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

## Project Rules

- Keep `main` stable for approved final-demo or submission work.
- Do active development on personal or feature branches.
- Prefer small, clear commits with descriptive messages.
- Keep dataset/model documentation updated when schemas change.
- Ask the group before forcing Git commands or deleting branches that Git says are not merged.
