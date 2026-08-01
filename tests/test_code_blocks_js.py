"""Client-side JS regression test for code-blocks.py's line numbering.

The bug lives in browser JavaScript (app/static/js/code-blocks.js): it cannot be
exercised through the FastAPI test client. The test runs the REAL code-blocks.js
with the REAL highlight.js in jsdom and asserts the resulting DOM.

Requires Node.js and the JS dev dependencies installed in tests/js
(`cd tests/js && npm install`). The test is skipped when they are unavailable so
the plain `uv run pytest` suite still passes on a Python-only checkout.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

JS_DIR = Path(__file__).parent / "js"
TEST_SCRIPT = JS_DIR / "code-blocks.test.js"


def _node_available() -> bool:
    return shutil.which("node") is not None


def _deps_available() -> bool:
    return (JS_DIR / "node_modules" / "jsdom").is_dir() and (
        JS_DIR / "node_modules" / "highlight.js"
    ).is_dir()


pytestmark = pytest.mark.skipif(
    not (_node_available() and _deps_available()),
    reason="node + tests/js/node_modules required (cd tests/js && npm install)",
)


def test_code_blocks_line_numbers_survive_highlighting():
    result = subprocess.run(
        ["node", str(TEST_SCRIPT)],
        cwd=JS_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"code-blocks.js regression test failed:\n{result.stdout}\n{result.stderr}"
    )
