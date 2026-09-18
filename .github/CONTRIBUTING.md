# Contributing Guide

This project is not open to external contributors. This guide is mainly for team members to get familiarised with the suggested Git workflow and setup.

## Core principles

- The `main` branch should only contain code for the final product. 
- Do active development on personal or feature branches.
- Do not merge a PR that contains unfinished features, experimental code, or unnecessary files. A PR that does not pass CI is considered unfinished and should not be merged into `main`
- Do not directly push into main, unless the change is really trivial (one-line bugfix or anything that does not merit its own branch and PR)
- DO NOT EVER FORCE PUSH WITHOUT PERMISSION. We had this problem once already.
- The `main` branch should always pass CI/CD. Fix immediately if not
- Prefer small, clear commits with descriptive messages.

## Quick Start

| Task | Link |
|---|---|
| Setup | [Setup](#setup) |
| Make your own branch | [Create a branch](#create-a-branch) |
| Save your work | [Commit changes](#commit-changes) |
| Push your work | [Push your branch](#push-your-branch) |
| Ask the team to review | [Open a pull request](#open-a-pull-request) |
| Clean up after merge | [After your PR is merged](#after-your-pr-is-merged) |
| Understand the app folder | [App Folder README](app/README.md) |
| Read dataset/model docs | [Markdown Reference Guides](app/markdown_reference_guides/README.md) |

## Setup

The suggested way to set up is to use a dev container. Both paths are described below; either way, finish with [Environment Variables](#environment-variables) and [Run The App](#run-the-app).

### Option A: Dev Container (Recommended)

Install and open:

| Tool | Link |
|---|---|
| Docker Desktop | <https://www.docker.com/products/docker-desktop/> |
| VS Code Dev Containers extension | <https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers> |

If you are on Windows, also set up WSL 2 first: <https://learn.microsoft.com/en-us/windows/wsl/setup/environment>. After installing WSL, right-click the Docker taskbar icon, open **Settings**, check **Use the WSL 2 based engine**, and enable your distribution under **Resources > WSL Integration**.

More background on dev containers: <https://code.visualstudio.com/docs/devcontainers/containers#_getting-started>

Clone the repository and open it in VS Code:

```bash
git clone https://github.com/CatFatOw/Rice-To-Meet-You.git
cd Rice-To-Meet-You
code .
```

VS Code should show a notification in the bottom-right corner asking if you want to reopen the workspace in a container. Click it. If the notification does not appear, open the command palette and run:

```text
Dev Containers: Rebuild and Reopen in Container
```

The container is defined in [.devcontainer/devcontainer.json](../.devcontainer/devcontainer.json). It ships Python 3 and Node 22, and its `postCreateCommand` installs both dependency sets for you:

```bash
npm install --prefix frontend && pip install -r app/requirements.txt
```

Ports 5173 (Vite dev server), 4173 (Vite preview), and 8000 (FastAPI) are forwarded automatically.

### Option B: Without The Dev Container

You need Python 3 and Node 22 installed locally.

Backend dependencies, from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
```

Frontend dependencies:

```bash
npm install --prefix frontend
```

Redis is optional for local work, but caching-backed routes fall back to slower direct queries without it. If you want it, run a local instance (for example, on macOS: `brew install redis && brew services start redis`), or point `REDIS_URL` at one you already have.

### Environment Variables

Both setups read a `.env` file at the repository root. It is gitignored, so create your own:

```bash
cat > .env <<'ENV'
DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
JWT_KEY="dev-secret-key"
CLAUDE_API_KEY="your-anthropic-api-key"
REDIS_URL="redis://localhost:6379/0"
ENV
```

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | No, but recommended | Defaults to `sqlite:///./local_dev.sqlite3`. Ask the team for the shared Neon Postgres URL. |
| `JWT_KEY` | For auth routes | Any string works locally. |
| `CLAUDE_API_KEY` | Yes | The app fails to import without it, even if you are not touching the chatbot. Use a throwaway value such as `"fake-local-key"` if you only need the app to start. |
| `REDIS_URL` | No | Defaults to `redis://localhost:6379/0`. |

Do not commit `.env` or paste real keys into issues or pull requests.

### Run The App

Start the backend from the `app/` folder:

```bash
cd app
python3 -m uvicorn main:app --reload
```

Interactive API docs: <http://127.0.0.1:8000/docs>

Start the frontend in a second terminal:

```bash
npm run dev --prefix frontend
```

The frontend is served at <http://localhost:5173>, which is already allowed by the backend's CORS settings.

By default the frontend talks to your local API at <http://127.0.0.1:8000>, so no
configuration is needed for local work. The origin comes from a single constant in
[frontend/src/api/config.ts](../frontend/src/api/config.ts), which reads the
`VITE_API_BASE_URL` environment variable and falls back to localhost.

To point the dev server at a deployed backend instead, create `frontend/.env`
(gitignored):

```bash
VITE_API_BASE_URL=https://your-service.up.railway.app
```

Vite only reads env files at startup, so restart `npm run dev` after changing it.
Never edit the constant in source to switch backends — that is what this variable
replaced.

### Run The Tests

CI runs the same checks, so run them before opening a pull request. From the repository root:

```bash
python3 -m compileall -q app
pytest
```

The test suite runs against SQLite and does not need the shared database.

## Create a Branch

Use your own branch for experiments, features, notes, and unfinished work.

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

## Commit Changes

```bash
git status
git add path/to/file
git commit -m "Describe your change"
```

## Push Your Branch

First push:

```bash
git push -u origin your-name/short-description
```

Later pushes:

```bash
git push
```

## Open a Pull Request

0. It is strongly advised that you check for merge conflicts before opening a PR. You can do that by running `git pull origin main`
1. Push your branch.
2. Open `https://github.com/CatFatOw/Rice-To-Meet-You`.
3. Click **Compare & pull request**, or go to **Pull requests** -> **New pull request**.
4. Set **base** to `main`.
5. Set **compare** to your branch.
6. Write what changed, why it matters, whether AI helped, and what reviewers should check.

Do not merge into `main` until the group approves the pull request.

## After Your PR Is Merged

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