# Rice-To-Meet-You

2026 Rice University FIFA Summer Hackathon Group

## Project Mission

Build a useful, credible, and polished FIFA 2026 decision-support platform that helps host cities prepare for visitor surges, transportation pressure, sustainability demands, climate risk, and future growth opportunities.

Our goal is not only to make something that works. Our goal is to make something judges can understand quickly, trust as data-informed, and remember after the demo.

## Git Quickstart

Use Git often so the team can see what changed, avoid losing work, and keep the repository organized.

### 1. Check what changed

Run this before and after you work:

```bash
git status
```

This shows which files are new, modified, staged, or ready to commit.

### 2. Get the latest version

Run this before starting work:

```bash
git pull
```

This downloads the newest changes from GitHub. If you are working directly on `main`, you can also use:

```bash
git pull origin main
```

### 3. Add your files

Add one file:

```bash
git add path/to/file
```

Add everything you changed:

```bash
git add .
```

### 4. Commit your changes

Write a short message that explains what you changed:

```bash
git commit -m "Add mobility prototype notes"
```

Good commit messages are specific, for example:

- `Add heat risk mapping prototype`
- `Update production README`
- `Clean transportation dataset`

### 5. Push to GitHub

Send your committed changes to the shared repo:

```bash
git push origin main
```

### Recommended everyday workflow

```bash
git status
git pull origin main
# make your changes
git status
git add .
git commit -m "Describe your change"
git push origin main
```

If Git shows a conflict or confusing message, stop and ask the group before forcing anything. Do not use commands like `git reset --hard` unless everyone agrees.

## Workspace Guidelines

This repository is organized around two types of workspaces:

- **`<name>` workspace**: Each teammate should use their own named workspace for brainstorming, experiments, AI-assisted exploration, and prototypes. This is where rough ideas, early notebooks, mockups, prompt experiments, data tests, and small proof-of-concept builds belong.
- **`production` workspace**: Once an idea or prototype is reviewed and approved by the group, implement the polished version in the **`production`** workspace. Production should contain the version we are willing to demo, explain, and submit.

Suggested structure:

```text
Rice-To-Meet-You/
├── production/
│   ├── README.md
│   ├── data/
│   ├── notebooks/
│   ├── src/
│   └── app/
├── <person-name>/
│   ├── README.md
│   ├── prototypes/
│   ├── prompts/
│   ├── notes/
│   └── data-tests/
└── README.md
```

## Personal Workspace Expectations

Inside each person's workspace, include a `README.md` that explains what you are brainstorming or prototyping. Keep it lightweight, but make it clear enough that another teammate can understand and build from it.

Each personal README should include:

- **Idea name**: Short title for the prototype or analysis.
- **Challenge track**: Which hackathon track this supports.
- **What you are doing**: A plain-language description of the experiment, feature, model, map, dataset, or design.
- **Why it matters**: How it helps host cities, visitors, sustainability, safety, or judges' understanding.
- **AI usage**: Note where AI helped: research, ideation, code generation, data cleaning, visualization, writing, model design, or demo scripting.
- **Data sources**: Link or describe any datasets, APIs, assumptions, or synthetic data used.
- **Version history**: Track major iterations in Markdown, for example `v0.1`, `v0.2`, `v1.0`.
- **Status**: Use simple labels such as `idea`, `prototype`, `needs review`, `approved`, or `moved to production`.

Example:

```markdown
# Visitor Heat Risk Prototype

**Track:** Track 3: Public Health & the Built Environment
**Version:** v0.2
**Status:** needs review

## What I am doing

I am testing whether visitor activity hotspots overlap with urban heat island zones near FIFA 2026 venues.

## AI usage

AI helped summarize public health risk factors, draft geospatial feature ideas, and generate starter Python code for mapping.

## Data sources

- NOAA heat data
- City open data
- Venue and transit station locations

## Version History

- `v0.1`: Initial map concept
- `v0.2`: Added venue buffers and risk scoring
```

## Hackathon Challenge

### Track 1: Transportation & Access

Build a FIFA 2026 Host City Mobility Readiness Platform that predicts visitor movement, identifies first/last-mile gaps, compares transportation resilience across host cities, and recommends investments, transit solutions, and traffic management strategies that improve access, reduce emissions, and relieve traffic.

### Track 2: Energy-Food-Water Nexus

Develop a FIFA 2026 Resource Intelligence Platform that quantifies and visualizes the Energy-Food-Water footprint of visitors, venues, hotels, and districts across all 11 U.S. host cities, while identifying the highest-impact sustainability interventions.

### Track 3: Public Health & the Built Environment

Identify locations where visitor activity, urban heat islands, and climate risks overlap to support heat mitigation and public health interventions during FIFA 2026.

### Track 4: High Intensity Corridors & Future Growth Districts

Develop a data-driven classification system that identifies and maps urban corridors, districts, and communities based on their economic intensity, mobility patterns, land use characteristics, and development potential.

## How We Win

Judges should see a project that is useful, technically credible, visually clear, and immediately relevant to FIFA 2026 host city planning.

Prioritize:

- **A sharp story**: Explain the problem, who it affects, what our platform does, and why it matters in under one minute.
- **A working demo**: Even if the model is simple, the user experience should feel complete and intentional.
- **Data credibility**: Clearly cite sources, label assumptions, and avoid pretending uncertain estimates are exact.
- **Decision value**: Every visualization should help someone decide where to invest, intervene, reroute, cool, staff, or prepare.
- **Comparison across cities**: Judges will remember a tool that helps compare host cities, not just a single static case study.
- **Actionable recommendations**: Include ranked interventions, expected impact, tradeoffs, and implementation difficulty.
- **Strong visuals**: Use maps, scorecards, charts, and scenario views that can be understood at a glance.
- **Human impact**: Connect outputs to visitors, residents, workers, emergency teams, city planners, and sustainability goals.
- **Demo readiness**: Keep the final presentation focused, rehearsed, and resilient if internet, APIs, or live data fail.

## Production Standards

Before moving work into `production`, check that it has:

- A clear owner
- A short README or documentation note
- Known data sources and assumptions
- Reproducible steps to run or inspect it
- Clean file names and folder structure
- No unused experiments, dead code, or confusing drafts
- Screenshots, charts, maps, or outputs when useful
- A clear connection to at least one challenge track

## Suggested Team Workflow

1. Brainstorm in personal workspaces.
2. Prototype quickly and document AI usage, assumptions, and version changes.
3. Review as a group: keep, combine, simplify, or discard.
4. Move approved work into `production`.
5. Integrate into one coherent platform and story.
6. Test the demo path repeatedly.
7. Prepare a short explanation of data, method, impact, and next steps.

## Demo Checklist

Before submission, make sure we can answer:

- What problem are we solving?
- Which FIFA 2026 host city decision does this support?
- What data did we use?
- What does the platform predict, classify, compare, or recommend?
- What should a city do differently because of our tool?
- What is the measurable impact on access, emissions, resilience, health, sustainability, or growth?
- What would we build next with more time?

## Guiding Principle

Prototype freely. Document clearly. Promote only the best ideas into production. Then make the final product simple enough to understand, strong enough to trust, and polished enough to win.
