# Copilot Instructions

This repository is a small FIFA 2026 hackathon prototype. The current code surface is minimal:
- `README.md` contains the group branch and PR workflow.
- `heat_model_test.ipynb` is the only code artifact and shows the current environment setup.

Key guidance for working in this repo:

- Treat `main` as production-ready. Use a personal branch for any experimental or AI-assisted changes, following the README convention like `name/feature`.
- There is no existing build or test automation in the repository. Do not invent CI commands or hidden scripts.
- The notebook uses Jupyter cell magic for environment setup:
  - `%pip install pandas numpy scikit-learn xgboost matplotlib`
  - Keep notebook-specific syntax in `.ipynb` files and do not convert it blindly to plain Python without validation.
- If adding new functionality, prefer adding new notebook cells or a new `.py` file only when it is clearly needed.
- Documentation and workflow rules are authoritative in `README.md`. If you change workflows or developer instructions, update that file.
- For PR and commit guidance, follow the README style:
  - branch names like `michael/heat-map-prototype`
  - commit messages like `Add heat map prototype`
  - PR descriptions with sections: What changed, Why it matters, AI usage, Questions for the group.
- There are no data folders or external integration points defined in the repository. Do not assume hidden datasets or services exist.
- Keep changes focused and easy to review, since this repository is a demo-oriented hackathon project.

Useful references:
- `README.md` for branch workflow and project mission.
- `heat_model_test.ipynb` for current code style and dependency imports.
