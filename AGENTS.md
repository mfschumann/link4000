# Directory structure
<main> - the checkout of the main branch
<main>/../link4000.worktrees/<branch> - a worktree for a feature branch

# Python environment
This is a Python project with environments managed by Pixi. Do not create ad-hoc virtual environments, and do not use conda, mamba, pip, or the system Python directly for project work.
- Always run Python, tools, and tests through Pixi.
- For local development and CI, use the `dev` environment unless the user explicitly tells you to use a different one.
- Prefer `pixi run -e dev <command>` for all project commands.
- If Pixi is not installed or the `dev` environment cannot be resolved, ask the user what to do.
- Never use the system python (for example `/usr/bin/python`) for this project.
- Never install packages on your own. If a package is missing, inform the user which package is needed and ask him to add it to the Pixi environment definition.

# Quality criteria
When creating or changing code:
- Add docstrings (Google style) to all methods that you write.
- Add comments to logic that is non-obvious.
- Use type hints.
- Add unit tests for new or changed functionality. If creating unit tests is difficult for the functionality you created or modified, inform the user about it and ask how to proceed. Do not start a major refactor without user confirmation.

When completing your changes:
- Update README.md if you changed or added functionality (not necessary for bug fixes).
- Update TODO.md.
- Iterate on `pixi run -e dev ruff check` until all checks pass.
- Run the pytest tests in the `tests` folder and make sure they pass. Set the environment variable `QT_QPA_PLATFORM=offscreen` for the test run to make the GUI tests work, for example:
  `QT_QPA_PLATFORM=offscreen pixi run -e dev pytest tests/`