# Rice-To-Meet-You

2026 Rice University FIFA Summer Hackathon Group

## Branch Rule

> **`main` = production**
>
> The `main` branch should only contain work that the group has approved for the final demo or submission.

> **Your branch = brainstorming and prototypes**
>
> Use your own Git branch for experiments, AI-assisted work, notes, prototypes, and rough ideas.

## Table of Contents

- [Chapter 1: Clone This Project](#chapter-1-clone-this-project)
- [Chapter 2: Understand the Branch Workflow](#chapter-2-understand-the-branch-workflow)
- [Chapter 3: Create Your Own Branch](#chapter-3-create-your-own-branch)
- [Chapter 4: Save Your Work](#chapter-4-save-your-work)
- [Chapter 5: Push Your Branch](#chapter-5-push-your-branch)
- [Chapter 6: Open a Pull Request](#chapter-6-open-a-pull-request)
- [Chapter 7: Daily Git Commands](#chapter-7-daily-git-commands)
- [Project Mission](#project-mission)

## Chapter 1: Clone This Project

If this is your first time working on the project, copy it from GitHub to your computer.

### 1. Open Terminal

On Mac, open the **Terminal** app.

### 2. Go to the folder where you want the project

Example:

```bash
cd Desktop
```

You can also use another folder:

```bash
cd Documents
```

### 3. Clone the repository

Run:

```bash
git clone https://github.com/CatFatOw/Rice-To-Meet-You.git
```

This creates a folder called `Rice-To-Meet-You` on your computer.

### 4. Enter the project folder

Run:

```bash
cd Rice-To-Meet-You
```

### 5. Confirm it worked

Run:

```bash
git status
```

If it worked, Git should say you are on the `main` branch.

## Chapter 2: Understand the Branch Workflow

Branches let everyone work without breaking the final version.

- Use **`main`** for approved production work only.
- Use a **personal or feature branch** for brainstorming, prototypes, AI-assisted experiments, and unfinished work.
- When the group approves your work, bring it into **`main`**.

Recommended branch names:

```text
name/short-description
```

Examples:

```text
michael/heat-map-prototype
zac/transit-gap-analysis
sarah/demo-dashboard
```

## Chapter 3: Create Your Own Branch

Before creating a branch, make sure your local `main` branch is updated.

```bash
git checkout main
git pull origin main
```

Create your own branch:

```bash
git checkout -b your-name/your-feature
```

Example:

```bash
git checkout -b michael/heat-map-prototype
```

Check which branch you are on:

```bash
git branch
```

The branch with the `*` next to it is your current branch.

## Chapter 4: Save Your Work

After editing files, check what changed:

```bash
git status
```

Add one file:

```bash
git add path/to/file
```

Add everything you changed:

```bash
git add .
```

Commit your changes with a clear message:

```bash
git commit -m "Add heat map prototype"
```

Good commit messages:

- `Add transit gap analysis notes`
- `Create visitor flow dashboard`
- `Clean venue dataset`
- `Update prototype README`

## Chapter 5: Push Your Branch

The first time you push your branch, run:

```bash
git push -u origin your-name/your-feature
```

Example:

```bash
git push -u origin michael/heat-map-prototype
```

After that, you can usually push with:

```bash
git push
```

## Chapter 6: Open a Pull Request

A pull request, or PR, is how you ask the group to review your branch before it becomes part of `main`.

Use a pull request when your prototype, notes, data work, or code is ready for the group to see.

### 1. Make sure your branch is pushed

If this is your first time pushing the branch:

```bash
git push -u origin your-name/your-feature
```

If you already pushed this branch before:

```bash
git push
```

### 2. Open GitHub

Go to:

```text
https://github.com/CatFatOw/Rice-To-Meet-You
```

GitHub may show a yellow box with a **Compare & pull request** button. Click it.

If you do not see that button:

1. Click the **Pull requests** tab.
2. Click **New pull request**.
3. Set **base** to `main`.
4. Set **compare** to your branch, such as `michael/heat-map-prototype`.

### 3. Write a clear PR title

Good titles:

- `Add heat map prototype`
- `Add transit gap analysis notes`
- `Create demo dashboard draft`

### 4. Write a short PR description

Use this format:

```markdown
## What changed

- Explain the files, prototype, data, or notes you added.

## Why it matters

- Explain how this helps the hackathon project.

## AI usage

- Say how AI helped, if you used it.

## Questions for the group

- Ask anything you want reviewers to check.
```

### 5. Ask for review

Send the PR link to the group. Do not merge it until the group approves it.

Reviewers should check:

- Does this help the project?
- Is the idea clear?
- Are the files in the right place?
- Is the work ready for `main`?

### 6. Merge after approval

After the group approves:

1. Click **Merge pull request**.
2. Click **Confirm merge**.
3. Delete the branch on GitHub if the work is finished.

### 7. Update your computer after the PR merges

After your PR is merged, update your local `main`:

```bash
git checkout main
git pull origin main
```

You can delete your old local branch if you are done with it:

```bash
git branch -d your-name/your-feature
```

If Git says the branch is not fully merged, ask the group before deleting it.

### Emergency option: merge from Terminal

Only do this if the group agrees and you understand what you are merging.

```bash
git checkout main
git pull origin main
git merge your-name/your-feature
git push origin main
```

## Chapter 7: Daily Git Commands

Use this flow whenever you start working:

```bash
git checkout main
git pull origin main
git checkout -b your-name/your-feature
```

Use this flow while working:

```bash
git status
git add .
git commit -m "Describe your change"
git push
```

Use this flow when returning to an existing branch:

```bash
git checkout your-name/your-feature
git pull
```

If Git shows a conflict or confusing message, stop and ask the group before forcing anything. Do not use commands like `git reset --hard` unless everyone agrees.

## Project Mission

Build a useful, credible, and polished FIFA 2026 decision-support platform that helps host cities prepare for visitor surges, transportation pressure, sustainability demands, climate risk, and future growth opportunities.

Our goal is not only to make something that works. Our goal is to make something judges can understand quickly, trust as data-informed, and remember after the demo.
