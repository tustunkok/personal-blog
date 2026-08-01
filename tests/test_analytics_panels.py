"""Regression test for the admin analytics page's Top Posts and Comment Activity panels.

Drives the real /admin/analytics route with seeded visits (post_id set) and
comments, then asserts the rendered HTML contains chart data for both panels.
"""

import datetime
import os
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.dependencies import get_scheduler
from app.main import app
from app.models import Comment, PageSession, Post, Visit


class FakeScheduler:
    def schedule_post(self, post_id, publish_at):
        pass

    def unschedule_post(self, post_id):
        pass


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
    db_path = tmp_path / "test_analytics_panels.db"
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
    yield TestClient(app), engine
    app.dependency_overrides.clear()
    engine.dispose()


def _login(client):
    resp = client.post(
        "/admin/login",
        data={"password": "testpass"},
        follow_redirects=False,
    )
    cookie = resp.cookies.get("blog_session")
    client.cookies.set("blog_session", cookie)


def _seed(client):
    """Seed one published post with visits and comments, like the live site."""
    _, engine = client
    db = Session(engine)
    p = Post(
        title="The Popular Post", slug="popular-post", body="body", status="published"
    )
    db.add(p)
    db.commit()

    today = datetime.datetime.now(datetime.UTC)
    db.add_all(
        [
            Visit(post_id=p.id, path="/posts/popular-post", created_at=today),
            Visit(post_id=p.id, path="/posts/popular-post", created_at=today),
            Comment(post_id=p.id, body="Great post!", created_at=today),
            Comment(post_id=p.id, body="Thanks!", created_at=today),
        ]
    )
    db.commit()
    db.close()


def test_new_comments_card_counts_comment_added_today(client):
    c, engine = client
    _login(c)

    db = Session(engine)
    p = Post(title="Comment Post", slug="comment-post", body="b", status="published")
    db.add(p)
    db.commit()
    db.close()

    # A visitor submits a comment through the public form, exactly like the
    # live scenario that left the card stuck at 0.
    resp = c.post(
        "/posts/comment-post/comments",
        data={"name": "Reader", "body": "Nice post!"},
    )
    assert resp.status_code == 200

    # The New Comments card on the analytics page must reflect it.
    page = c.get("/admin/analytics")
    assert page.status_code == 200
    m = re.search(
        r"New Comments</p>\s*<p class=\"text-2xl font-bold\">(\d+)</p>",
        page.text,
    )
    assert m, "New Comments card not found in rendered analytics page"
    assert m.group(1) == "1", (
        "New Comments card shows " + m.group(1) + " after adding a comment; expected 1"
    )


def test_scroll_depth_panel_renders_session_buckets(client):
    c, engine = client
    _login(c)

    db = Session(engine)
    p = Post(title="Scroll Post", slug="scroll-post", body="b", status="published")
    db.add(p)
    db.commit()
    v = Visit(post_id=p.id, path="/posts/scroll-post")
    db.add(v)
    db.commit()
    db.add(
        PageSession(
            visit_id=v.id,
            post_id=p.id,
            entry_time=datetime.datetime.now(datetime.UTC),
            scroll_depth=0.8,
        )
    )
    db.commit()
    db.close()

    resp = c.get("/admin/analytics")
    assert resp.status_code == 200

    # Panel must render, and the 0.8-depth session must land in the 75-99%
    # bucket: buckets are [0-25, 25-50, 50-75, 75-99, 100].
    assert "new Chart(document.getElementById('scrollDistChart')" in resp.text
    assert "0, 0, 0, 1, 0" in resp.text


def test_analytics_top_posts_and_comment_activity_panels_show_data(client):
    c, _ = client
    _login(c)
    _seed(client)

    resp = c.get("/admin/analytics")
    assert resp.status_code == 200

    # Top Posts panel: the post title must be rendered into the chart labels
    # and the chart must actually be created (guard is `if (labels.length)`).
    assert "The Popular Post" in resp.text
    assert "new Chart(document.getElementById('topPostsChart')" in resp.text

    # Comment Activity panel: same, chart must be created with the day label.
    assert "new Chart(document.getElementById('commentsChart')" in resp.text
