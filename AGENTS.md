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

## Agent skills

### Issue tracker

Issues live on the self-hosted Gogs instance at `https://git.toliga.com/tustunkok/personal-blog`. A Python helper script at `tools/gogs.py` wraps the Gogs REST API. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo. Read `CONTEXT.md` for glossary and `docs/adr/` for architectural decisions. See `docs/agents/domain.md`.

## Code Quality

- Use `uv run ruff check` to lint code before committing.
- Use `uv run ruff format` to format code before committing.
- Fix all lint errors and warnings before declaring work done.

## Gogs Interactions

- Use `tools/gogs.py` for all interactions with the Gogs issue tracker (create issues, edit issues, manage labels).
- Use the CLI: `uv run python tools/gogs.py <list-issues|list-labels|list-prs>` for read ops.
- For write ops, call functions from `tools.gogs` via `uv run python -c "import sys; sys.path.insert(0, 'tools'); import gogs; ..."`.
