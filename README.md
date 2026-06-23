# Rice-To-Meet-You

2026 Rice University FIFA Summer Hackathon Group

## Workspace Rule

> 🟦 **Personal Workspace**  
> Use your **`<name>` workspace** for brainstorming, AI-assisted experiments, notes, and prototypes.
>
> 🟩 **Production Workspace**  
> Only move work into **`production`** after the group approves it for the final demo or submission.

## Table of Contents

- [Project Mission](#project-mission)
- [Workspace Rule](#workspace-rule)
- [Git Tutorial](#git-tutorial)
- [Workspace Structure](#workspace-structure)
- [Expectations](#expectations)

## Project Mission

Build a useful, credible, and polished FIFA 2026 decision-support platform that helps host cities prepare for visitor surges, transportation pressure, sustainability demands, climate risk, and future growth opportunities.

Our goal is not only to make something that works. Our goal is to make something judges can understand quickly, trust as data-informed, and remember after the demo.

## Git Tutorial

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

## Workspace Structure

This repository is organized around two types of workspaces:

- 🟦 **`<name>` workspace**: Each teammate should use their own named workspace for brainstorming, experiments, AI-assisted exploration, and prototypes. This is where rough ideas, early notebooks, mockups, prompt experiments, data tests, and small proof-of-concept builds belong.
- 🟩 **`production` workspace**: Once an idea or prototype is reviewed and approved by the group, implement the polished version in the **`production`** workspace. Production should contain the version we are willing to demo, explain, and submit.

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

## Expectations

Inside your personal workspace, add a short `README.md` that explains what you are brainstorming or prototyping.

Include:

- What you are doing
- Which challenge track it supports
- How you used AI
- What data or assumptions you used
- A simple version history like `v0.1`, `v0.2`, or `v1.0`

Before moving anything into `production`, make sure the group approves it and that it is clear enough for someone else to understand, run, or present.
