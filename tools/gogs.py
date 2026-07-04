"""
Minimal Gogs API client for issue tracker and pull request operations.

Token sourced from TOKEN file at repo root.
Base URL: https://git.toliga.com/api/v1
Repository: tustunkok/personal-blog

Note: Gogs API v1 has no dedicated PR endpoints. Pull requests are issues
with a ``pull_request`` key. Creating PRs via the API is not supported;
use the web UI or git push to a branch and open a PR from there.
"""

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TOKEN = (ROOT / "TOKEN").read_text().strip()
BASE = "https://git.toliga.com/api/v1"
REPO_OWNER = "tustunkok"
REPO_NAME = "personal-blog"


def _req(method: str, path: str, data: dict | None = None) -> Any:
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"token {TOKEN}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            if not content:
                return None
            return json.loads(content)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} -> {e.code}: {body}") from e


def _issues_path() -> str:
    return f"/repos/{REPO_OWNER}/{REPO_NAME}/issues"


def _labels_path() -> str:
    return f"/repos/{REPO_OWNER}/{REPO_NAME}/labels"


def _require_pull_request(issue: dict) -> dict:
    if "pull_request" not in issue:
        raise RuntimeError(f"Issue #{issue.get('number')} is not a pull request")
    return issue


# -- Issues ------------------------------------------------------------------


def create_issue(title: str, body: str = "", labels: list[int] | None = None) -> dict:
    payload: dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    return _req("POST", _issues_path(), payload)


def edit_issue(
    index: int,
    *,
    title: str | None = None,
    body: str | None = None,
    state: str | None = None,
) -> dict:
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if state is not None:
        payload["state"] = state
    return _req("PATCH", f"{_issues_path()}/{index}", payload)


def get_issue(index: int) -> dict:
    return _req("GET", f"{_issues_path()}/{index}")


def list_issues() -> list[dict]:
    return _req("GET", _issues_path())


# -- Labels ------------------------------------------------------------------


def create_label(name: str, color: str) -> dict:
    return _req("POST", _labels_path(), {"name": name, "color": color})


def list_labels() -> list[dict]:
    return _req("GET", _labels_path())


def update_label(
    label_id: int, *, name: str | None = None, color: str | None = None
) -> dict:
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if color is not None:
        payload["color"] = color
    return _req("PATCH", f"{_labels_path()}/{label_id}", payload)


def add_labels_to_issue(index: int, label_ids: list[int]) -> list[dict]:
    return _req("POST", f"{_issues_path()}/{index}/labels", {"labels": label_ids})


def replace_labels_on_issue(index: int, label_ids: list[int]) -> list[dict]:
    return _req("PUT", f"{_issues_path()}/{index}/labels", {"labels": label_ids})


# -- Pull Requests -----------------------------------------------------------
# Gogs API v1 has no dedicated PR endpoints. PRs are issues whose response
# includes a ``pull_request`` key. Creating PRs is not available via the API.


def list_pull_requests() -> list[dict]:
    """List all pull requests (issues with a ``pull_request`` key)."""
    return [i for i in list_issues() if "pull_request" in i]


def get_pull_request(index: int) -> dict:
    """Get a pull request by issue index. Raises if not a PR."""
    return _require_pull_request(get_issue(index))


def edit_pull_request(
    index: int,
    *,
    title: str | None = None,
    body: str | None = None,
    state: str | None = None,
) -> dict:
    """Edit a pull request's title, body, or state. Raises if not a PR.

    State may be ``"open"`` or ``"closed"``.
    """
    _require_pull_request(get_issue(index))
    return edit_issue(index, title=title, body=body, state=state)


def close_pull_request(index: int) -> dict:
    """Close a pull request. Raises if not a PR."""
    return edit_pull_request(index, state="closed")


def reopen_pull_request(index: int) -> dict:
    """Reopen a closed pull request. Raises if not a PR."""
    return edit_pull_request(index, state="open")


def list_open_pull_requests() -> list[dict]:
    """List all open pull requests."""
    return [pr for pr in list_pull_requests() if pr.get("state") == "open"]


def list_closed_pull_requests() -> list[dict]:
    """List all closed pull requests."""
    return [pr for pr in list_pull_requests() if pr.get("state") == "closed"]


if __name__ == "__main__":
    import sys

    cmds: dict[str, tuple] = {
        "list-issues": (list_issues, []),
        "list-labels": (list_labels, []),
        "list-prs": (list_pull_requests, []),
    }

    usage = "usage: uv run python tools/gogs.py <" + "|".join(cmds) + "> [args]"

    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(usage)
        sys.exit(1)

    fn, args = cmds[sys.argv[1]]
    result = fn(*args, *sys.argv[2:])
    print(json.dumps(result, indent=2))
