"""Regression tests for the CRITICAL stored-XSS fix.

Chain previously exploitable by any anonymous visitor:
1. post a comment containing raw HTML/script (auto-approved, no moderation)
2. comment.body rendered through render_markdown()|safe with NO sanitization
3. payload executed in every visitor's browser - and in the admin's origin
   when they view their own commented post -> admin/DB compromise.

These tests verify that after the fix:
- new comments are held for moderation (is_approved=False, never auto-approved)
- even after an admin approves a hostile comment, the rendered HTML is
  sanitized so no active content reaches the page.
"""

import datetime
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.dependencies import get_scheduler
from app.main import app
from app.models import Comment, Post


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
def client():
    engine = create_engine(
        "sqlite:///test_xss_poc.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    original_get_db = get_db

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[original_get_db] = override_get_db
    app.dependency_overrides[get_scheduler] = lambda: FakeScheduler()
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()
    try:
        os.remove("test_xss_poc.db")
    except OSError:
        pass


def _db():
    g = app.dependency_overrides[get_db]()
    return next(g)


def _seed_post(slug="xss-post"):
    db = _db()
    db.add(
        Post(
            title="XSS Post",
            slug=slug,
            body="Hello world",
            status="published",
            publish_at=datetime.datetime.now(datetime.UTC),
        )
    )
    db.commit()
    db.close()


PAYLOADS = [
    ("<script>alert(document.domain)</script>", "alert(document.domain)"),
    ("<img src=x onerror=alert(2)>", "alert(2)"),
    ("<svg/onload=alert(document.cookie)>", "alert(document.cookie)"),
    ("[click me](javascript:alert(3))", "javascript:"),
    ("<iframe src=javascript:alert(5)>", "javascript:alert(5)"),
    ("<div onclick=alert(6)>evil</div>", "alert(6)"),
]


def _submit_comment(client, body, slug="xss-post"):
    return client.post(
        f"/posts/{slug}/comments",
        data={"name": "Attacker", "body": body},
        headers={"X-Forwarded-For": "1.2.3.4", "User-Agent": "poc"},
    )


@pytest.mark.parametrize("payload,marker", PAYLOADS)
def test_comment_sanitized_and_held(client, payload, marker):
    _seed_post()
    _submit_comment(client, payload)

    # Comment is stored but NOT auto-approved (requires admin approval).
    db = _db()
    c = db.query(Comment).filter(Comment.body == payload).first()
    assert c is not None
    assert c.is_approved is False, "comment must not auto-approve"
    db.close()

    # The payload's distinctive marker must never reach the rendered page.
    page = client.get("/posts/xss-post").text
    assert marker not in page, f"payload marker still present: {marker!r}"


def test_approved_malicious_comment_still_sanitized(client):
    """Admin approval must not re-enable the XSS: sanitization is the backstop."""
    _seed_post()
    _submit_comment(client, "<img src=x onerror=alert(2)>")

    db = _db()
    c = db.query(Comment).first()
    assert c is not None and c.is_approved is False
    c.is_approved = True  # simulate admin clicking approve
    comment_id = c.id
    db.commit()
    db.close()

    # Approve through the real admin route too.
    session = _login(client)
    client.cookies.set("blog_session", session)
    resp = client.post(f"/admin/comments/{comment_id}/approve", follow_redirects=False)
    assert resp.status_code == 302

    page = client.get("/posts/xss-post").text
    assert "alert(2)" not in page
    assert "onerror=alert" not in page
    assert "<script>alert" not in page


def test_safe_markdown_features_still_render(client):
    """Sanitization must not destroy legitimate markdown output."""
    _seed_post()
    # Add an approved comment that uses normal formatting.
    db = _db()
    c = Comment(
        post_id=db.query(Post).first().id,
        body="**bold** *italic* [link](https://example.com) and `code`",
        is_approved=True,
    )
    db.add(c)
    db.commit()
    db.close()

    page = client.get("/posts/xss-post").text
    assert "<strong>bold</strong>" in page
    assert "<em>italic</em>" in page
    assert 'href="https://example.com"' in page
    assert "<code>code</code>" in page


def _login(client: TestClient) -> str:
    resp = client.post(
        "/admin/login", data={"password": "testpass"}, follow_redirects=False
    )
    return resp.cookies.get("blog_session", "")
