# AGENTS.md

## Python & Dependency Management

- Use `uv run` to execute Python scripts and commands (e.g. `uv run python main.py`, `uv run pytest`).
- Use `uv add <package>` to add dependencies. Do NOT manually edit `pyproject.toml` to add or update packages.
- Use `uv remove <package>` to remove dependencies.
- Use `uv sync` to sync the lockfile after changes.

## Git Commits

- Use [Conventional Commits](https://www.conventionalcommits.org/) format: `type(scope): description`
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- Keep the summary line under 72 characters.
- Write in imperative mood (e.g. "add" not "added").
- No period at the end of the summary.
