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


@pytest.fixture(autouse=True)
def reset_counter():
    global _post_counter
    _post_counter = 0


class FakeScheduler:
    def schedule_post(self, post_id, publish_at):
        pass

    def unschedule_post(self, post_id):
        pass


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///test_public_site.db", connect_args={"check_same_thread": False}
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
        os.remove("test_public_site.db")
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


_post_counter = 0


def _create_published_post(
    c: TestClient, title: str, body: str = "Content", excerpt: str = "Summary"
) -> int:
    global _post_counter
    resp = c.post(
        "/admin/posts",
        data={"title": title, "body": body, "excerpt": excerpt},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    _post_counter += 1
    post_id = _post_counter
    c.post(f"/admin/posts/{post_id}/publish", follow_redirects=False)
    return post_id


def test_home_page_shows_published_posts(client):
    ac = _auth_client(client)
    _create_published_post(ac, "First Post", "Body one", "Excerpt one")
    _create_published_post(ac, "Second Post", "Body two", "Excerpt two")

    resp = client.get("/")
    assert resp.status_code == 200
    assert "First Post" in resp.text
    assert "Second Post" in resp.text
    assert "Excerpt one" in resp.text
    assert "Excerpt two" in resp.text


def test_home_page_hides_draft_and_scheduled_and_deleted(client):
    ac = _auth_client(client)
    _create_published_post(ac, "Visible Post", "Body", "Excerpt")
    ac.post(
        "/admin/posts",
        data={"title": "Draft Post", "body": "draft", "excerpt": "d"},
        follow_redirects=False,
    )
    pid = _create_published_post(ac, "To Delete", "Body", "x")
    ac.post(f"/admin/posts/{pid}/delete", follow_redirects=False)

    resp = client.get("/")
    assert resp.status_code == 200
    assert "Visible Post" in resp.text
    assert "Draft Post" not in resp.text
    assert "To Delete" not in resp.text


def test_home_page_pagination_10_per_page(client):
    ac = _auth_client(client)
    for i in range(12):
        _create_published_post(ac, f"Post {i + 1}", f"Body {i + 1}", f"Excerpt {i + 1}")

    resp = client.get("/")
    assert resp.status_code == 200
    assert "Excerpt 1<" in resp.text
    assert "Excerpt 10<" in resp.text
    assert "Excerpt 11<" not in resp.text
    assert "Excerpt 12<" not in resp.text

    resp = client.get("/?page=2")
    assert resp.status_code == 200
    assert "Excerpt 11<" in resp.text
    assert "Excerpt 12<" in resp.text
    assert "Excerpt 10<" not in resp.text


def test_htmx_load_more_returns_next_page(client):
    ac = _auth_client(client)
    for i in range(12):
        _create_published_post(ac, f"Post {i + 1}", f"Body {i + 1}", f"Excerpt {i + 1}")

    resp = client.get("/posts-page?page=2")
    assert resp.status_code == 200
    assert "Excerpt 11<" in resp.text
    assert "Excerpt 12<" in resp.text
    assert "Excerpt 10<" not in resp.text


def test_search_returns_matching_published_posts(client):
    ac = _auth_client(client)
    _create_published_post(
        ac, "Python Tips", "Python is great for web dev", "Python stuff"
    )
    _create_published_post(ac, "Rust Guide", "Rust is fast and safe", "Rust stuff")
    _create_published_post(ac, "Django vs Flask", "Comparing frameworks", "Comparison")

    resp = client.get("/search?q=python")
    assert resp.status_code == 200
    assert "Python Tips" in resp.text
    assert "Rust Guide" not in resp.text
    assert "Django vs Flask" not in resp.text


def test_search_hides_draft_scheduled_deleted(client):
    ac = _auth_client(client)
    _create_published_post(ac, "Visible Python", "Python rocks", "visible")
    ac.post(
        "/admin/posts",
        data={"title": "Draft Python", "body": "secret python", "excerpt": "d"},
        follow_redirects=False,
    )
    pid = _create_published_post(ac, "Deleted Python", "gone", "x")
    ac.post(f"/admin/posts/{pid}/delete", follow_redirects=False)

    resp = client.get("/search?q=python")
    assert resp.status_code == 200
    assert "Visible Python" in resp.text
    assert "Draft Python" not in resp.text
    assert "Deleted Python" not in resp.text


def test_archive_page_groups_posts_by_year_month(client):
    ac = _auth_client(client)
    _create_published_post(ac, "Post A", "Body A", "Excerpt A")
    _create_published_post(ac, "Post B", "Body B", "Excerpt B")
    _create_published_post(ac, "Post C", "Body C", "Excerpt C")

    resp = client.get("/archive")
    assert resp.status_code == 200
    assert "Post A" in resp.text
    assert "Post B" in resp.text
    assert "Post C" in resp.text


def test_archive_page_hides_draft_scheduled_deleted(client):
    ac = _auth_client(client)
    _create_published_post(ac, "Visible Archive", "Body", "Visible")
    ac.post(
        "/admin/posts",
        data={"title": "Draft Archive", "body": "draft", "excerpt": "d"},
        follow_redirects=False,
    )

    resp = client.get("/archive")
    assert resp.status_code == 200
    assert "Visible Archive" in resp.text
    assert "Draft Archive" not in resp.text


def test_about_page_renders_default(client):
    resp = client.get("/about")
    assert resp.status_code == 200
    assert "About" in resp.text


def test_about_page_renders_stored_content(client):
    _auth_client(client)
    client.post(
        "/admin/pages/about",
        data={"content": "# About Me\n\nI write code."},
        follow_redirects=False,
    )

    resp = client.get("/about")
    assert resp.status_code == 200
    assert "<h1>About Me</h1>" in resp.text
    assert "I write code." in resp.text


def test_now_page_renders_default(client):
    resp = client.get("/now")
    assert resp.status_code == 200
    assert "Now" in resp.text


def test_now_page_renders_stored_content(client):
    _auth_client(client)
    client.post(
        "/admin/pages/now",
        data={"content": "## Currently\n\nBuilding things."},
        follow_redirects=False,
    )

    resp = client.get("/now")
    assert resp.status_code == 200
    assert "<h2>Currently</h2>" in resp.text
    assert "Building things." in resp.text


def test_about_now_editing_requires_auth(client):
    resp = client.post(
        "/admin/pages/about",
        data={"content": "test"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["location"]
