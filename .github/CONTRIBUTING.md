# Contributing Guide

This project is not open to external contributors. This guide is mainly for team members to get familiarised with the suggested Git workflow and setup.

## Core principles

- The `main` branch should only contain code for the final product. 
- Do active development on personal or feature branches.
- Do not merge a PR that contains unfinished features, experimental code, or unnecessary files. A PR that does not pass CI is considered unfinished and should not be merged into `main`
- Do not force push, unless the change is really trivial (one-line bugfix or anything that does not merit its own branch and PR)
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

See [Readme](README.md#app-guide)

### Create a Branch

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

0. It is strongly advised that you check for merge conflicts before opening a PR. You can do that by running `git pull origin main`
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