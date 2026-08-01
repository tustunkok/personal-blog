"""Client-side JS regression test for the empty "Top Posts" analytics panel.

The bug lives in the served HTML: base.html loads analytics.js synchronously in
the head, while window.__post_id is set afterwards (post.html's {% block head %}
renders at the bottom of <head>). analytics.js therefore never sees __post_id,
so visits are recorded without post_id and the Top Posts panel is always empty.

The test renders the REAL post page through the FastAPI app, then runs the REAL
analytics.js against it in jsdom (preserving script order) and asserts the visit
payload contains post_id. Requires node + tests/js/node_modules (see
tests/js/package.json); skipped when unavailable so `uv run pytest` still works
on a Python-only checkout.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.dependencies import get_scheduler
from app.main import app
from app.models import Post

JS_DIR = Path(__file__).parent / "js"
TEST_SCRIPT = JS_DIR / "analytics-load-order.test.js"
REPO_ROOT = Path(__file__).parent.parent


class FakeScheduler:
    def schedule_post(self, post_id, publish_at):
        pass

    def unschedule_post(self, post_id):
        pass


def _node_available() -> bool:
    return shutil.which("node") is not None


def _deps_available() -> bool:
    return (JS_DIR / "node_modules" / "jsdom").is_dir()


pytestmark = pytest.mark.skipif(
    not (_node_available() and _deps_available()),
    reason="node + tests/js/node_modules required (cd tests/js && npm install)",
)


def test_post_page_sends_post_id_with_visit(client):
    c, _ = client
    resp = c.get("/posts/hello-world")
    assert resp.status_code == 200
    html = resp.text
    assert "window.__post_id" in html

    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html)
        html_path = f.name
    try:
        result = subprocess.run(
            ["node", str(TEST_SCRIPT), html_path, str(REPO_ROOT)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        os.unlink(html_path)

    assert result.returncode == 0, (
        f"analytics load-order regression test failed:\n"
        f"{result.stdout}\n{result.stderr}"
    )


@pytest.fixture(autouse=True)
def clear_env():
    old = os.environ.pop("BLOG_ADMIN_PASSWORD", None)
    os.environ["BLOG_ADMIN_PASSWORD"] = "testpass"
    yield
    os.environ.pop("BLOG_ADMIN_PASSWORD", None)
    if old is not None:
        os.environ["BLOG_ADMIN_PASSWORD"] = old


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test_analytics_load_order.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_scheduler] = lambda: FakeScheduler()
    db = TestingSession()
    db.add(Post(title="Hello World", slug="hello-world", body="Hi", status="published"))
    db.commit()
    db.close()

    yield TestClient(app), engine
    app.dependency_overrides.clear()
    engine.dispose()
