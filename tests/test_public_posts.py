import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db as original_get_db
from app.dependencies import get_scheduler as original_get_scheduler
from app import models  # noqa: F401
from app.main import app


@pytest.fixture(autouse=True)
def clear_env():
    old = os.environ.pop("BLOG_ADMIN_PASSWORD", None)
    os.environ["BLOG_ADMIN_PASSWORD"] = "testpass"
    yield
    os.environ.pop("BLOG_ADMIN_PASSWORD", None)
    if old is not None:
        os.environ["BLOG_ADMIN_PASSWORD"] = old


class FakeScheduler:
    def schedule_post(self, post_id, publish_at):
        pass

    def unschedule_post(self, post_id):
        pass


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///test_public.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)

    def override_get_db():
        db = sessionmaker(bind=engine)()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[original_get_db] = override_get_db
    app.dependency_overrides[original_get_scheduler] = lambda: FakeScheduler()
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()
    try:
        os.remove("test_public.db")
    except OSError:
        pass


def _login(client: TestClient) -> str:
    resp = client.post(
        "/admin/login",
        data={"password": "testpass"},
        follow_redirects=False,
    )
    return resp.cookies.get("blog_session", "")


def _auth_client(client: TestClient) -> TestClient:
    session = _login(client)
    client.cookies.set("blog_session", session)
    return client


def test_public_post_page_renders_markdown(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={
            "title": "Hello World",
            "body": "# Hello\n\nThis is **bold**.",
            "excerpt": "Greetings",
        },
        follow_redirects=False,
    )
    client.post("/admin/posts/1/publish", follow_redirects=False)

    resp = client.get("/posts/hello-world")
    assert resp.status_code == 200
    assert "<h1>Hello</h1>" in resp.text
    assert "<strong>bold</strong>" in resp.text


def test_public_post_page_shows_title_and_excerpt(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "Test Post", "body": "Body", "excerpt": "Short summary"},
        follow_redirects=False,
    )
    client.post("/admin/posts/1/publish", follow_redirects=False)

    resp = client.get("/posts/test-post")
    assert resp.status_code == 200
    assert "Test Post" in resp.text
    assert "Short summary" in resp.text


def test_draft_post_returns_404_on_public_page(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "Draft Only", "body": "secret"},
        follow_redirects=False,
    )

    resp = client.get("/posts/draft-only")
    assert resp.status_code == 404


def test_nonexistent_slug_returns_404(client):
    resp = client.get("/posts/no-such-post")
    assert resp.status_code == 404


def test_public_post_page_has_code_block_with_syntax_highlighting(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={
            "title": "Code Post",
            "body": "```python\nprint('hello')\n```",
            "excerpt": "code",
        },
        follow_redirects=False,
    )
    client.post("/admin/posts/1/publish", follow_redirects=False)

    resp = client.get("/posts/code-post")
    assert resp.status_code == 200
    assert "<pre>" in resp.text
    assert "<code" in resp.text


def test_post_page_loads_highlight_js(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "HLJS Post", "body": "Hi", "excerpt": "hi"},
        follow_redirects=False,
    )
    client.post("/admin/posts/1/publish", follow_redirects=False)

    resp = client.get("/posts/hljs-post")
    assert resp.status_code == 200
    assert "highlight.js" in resp.text


def test_post_page_loads_code_blocks_js(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "CB Post", "body": "Hi", "excerpt": "hi"},
        follow_redirects=False,
    )
    client.post("/admin/posts/1/publish", follow_redirects=False)

    resp = client.get("/posts/cb-post")
    assert resp.status_code == 200
    assert 'src="/static/js/code-blocks.js"' in resp.text


def test_post_page_displays_tags(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={
            "title": "Tagged Post",
            "body": "Content",
            "excerpt": "x",
            "tags": "python, fastapi",
        },
        follow_redirects=False,
    )
    client.post("/admin/posts/1/publish", follow_redirects=False)

    resp = client.get("/posts/tagged-post")
    assert resp.status_code == 200
    assert "python" in resp.text
    assert "fastapi" in resp.text
    assert 'href="/tags/python"' in resp.text
    assert 'href="/tags/fastapi"' in resp.text


def test_post_page_shows_series_navigation(client):
    ac = _auth_client(client)
    ac.post(
        "/admin/posts",
        data={
            "title": "Part 1",
            "body": "First",
            "excerpt": "x",
            "new_series": "Trilogy",
            "series_position": "1",
        },
        follow_redirects=False,
    )
    ac.post(
        "/admin/posts",
        data={
            "title": "Part 2",
            "body": "Second",
            "excerpt": "x",
            "series_id": "1",
            "series_position": "2",
        },
        follow_redirects=False,
    )
    ac.post(
        "/admin/posts",
        data={
            "title": "Part 3",
            "body": "Third",
            "excerpt": "x",
            "series_id": "1",
            "series_position": "3",
        },
        follow_redirects=False,
    )
    ac.post("/admin/posts/1/publish", follow_redirects=False)
    ac.post("/admin/posts/2/publish", follow_redirects=False)
    ac.post("/admin/posts/3/publish", follow_redirects=False)

    resp = client.get("/posts/part-2")
    assert resp.status_code == 200
    assert "Part 2 of" in resp.text
    assert "Trilogy" in resp.text
    assert "Series Table of Contents" in resp.text
    assert "Part 1" in resp.text
    assert "Part 3" in resp.text
    assert "Previous" in resp.text
    assert "Next" in resp.text
