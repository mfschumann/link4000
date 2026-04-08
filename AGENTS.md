# Python environment 
This is a python project with an environment managed by conda/mamba. The environment is already set up at the .env folder.
- Always use .env/bin/python as the python interpreter.
- If this python binary is not present, ask the user what to do.
- Never use the system python (like /usr/bin/python).
- Never attempt to install python packages on your own (neither using conda, mamba, nor pip). Instead, inform the user what package cannot be found and ask him to add it to the environment definition.

# Quality criteria 
When creating or changing code:
- Add docstrings (Google style) to all methods that you write.
- Add comments to logic that is non-obvious.
- Use type hints.
- Add unit tests for new or changed functionality. In case creating unit tests is difficult for the functionality you created/modified, inform the user about it and ask him how to proceed: Don't start a major refactor without user confirmation.

When completing your changes:
- Update README.md if you changed or added a functionality (not necessary for Bugfixes).
- Update TODO.md.
- Iterate over `.env/bin/ruff check` until all checks pass.
- Run the pytest tests in the tests folder and make sure they pass. Set the environment variable `QT_QPA_PLATFORM=offscreen` for the test run to make the GUI tests work.
