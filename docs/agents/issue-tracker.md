# Issue tracker: Gogs (self-hosted)

Issues for this repo live on the self-hosted Gogs instance at `https://git.toliga.com/tustunkok/personal-blog`.

## Conventions

- Issues are managed via Gogs Issues, not local markdown files.
- A Python helper script at [tools/gogs.py](../../tools/gogs.py) wraps the Gogs REST API (v1) for creating, editing, and labeling issues.
- The script reads the access token from the `TOKEN` file at the repo root.

## When a skill says "publish to the issue tracker"

Run the Python helper script:

```bash
uv run python tools/gogs.py create-issue --title "..." --body "..."
```

Or call the functions programmatically from `tools.gogs`.

## When a skill says "fetch the relevant ticket"

Use the Gogs API directly or navigate to `https://git.toliga.com/tustunkok/personal-blog/issues/{index}`.

Alternatively, call `tools.gogs.get_issue(index)` or `tools.gogs.list_issues()`.

## API reference

- Base URL: `https://git.toliga.com/api/v1`
- Repo: `tustunkok/personal-blog`
- Auth: `Authorization: token {TOKEN_CONTENT}` header
- Full docs: https://gogs.io/api-reference/introduction
