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
        "sqlite:///test_comments.db", connect_args={"check_same_thread": False}
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
        os.remove("test_comments.db")
    except OSError:
        pass


def _db():
    g = app.dependency_overrides[get_db]()
    return next(g)


def test_honeypot_filled_rejects_silently(client):
    db = _db()
    post = Post(
        title="Honeypot Post",
        slug="honeypot-post",
        body="Content",
        status="published",
        publish_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(post)
    db.commit()
    post_id = post.id
    db.close()

    resp = client.post(
        "/posts/honeypot-post/comments",
        data={
            "name": "Bot",
            "email": "bot@spam.com",
            "body": "Spam comment",
            "website": "http://spam.com",
        },
        headers={"X-Forwarded-For": "5.6.7.8", "User-Agent": "bot-agent"},
    )

    assert resp.status_code == 200

    db2 = _db()
    count = db2.query(Comment).filter(Comment.post_id == post_id).count()
    assert count == 0
    db2.close()


def test_time_gate_rejects_fast_submission(client):
    db = _db()
    post = Post(
        title="Time Gate Post",
        slug="time-gate-post",
        body="Content",
        status="published",
        publish_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(post)
    db.commit()
    post_id = post.id
    db.close()

    from time import time

    now = time()

    resp = client.post(
        "/posts/time-gate-post/comments",
        data={
            "name": "FastBot",
            "body": "Too fast",
            "load_time": str(now - 1),
        },
        headers={"X-Forwarded-For": "9.9.9.9", "User-Agent": "fast-agent"},
    )

    assert resp.status_code == 200

    db2 = _db()
    count = db2.query(Comment).filter(Comment.post_id == post_id).count()
    assert count == 0
    db2.close()


def test_submit_comment_on_published_post(client):
    db = _db()
    post = Post(
        title="Test Post",
        slug="test-post",
        body="Hello world",
        status="published",
        publish_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(post)
    db.commit()
    post_id = post.id
    db.close()

    resp = client.post(
        "/posts/test-post/comments",
        data={"name": "Alice", "email": "alice@example.com", "body": "Great post!"},
        headers={"X-Forwarded-For": "1.2.3.4", "User-Agent": "test-agent"},
    )

    assert resp.status_code == 200

    db2 = _db()
    comment = db2.query(Comment).filter(Comment.post_id == post_id).first()
    assert comment is not None
    assert comment.name == "Alice"
    assert comment.email == "alice@example.com"
    assert comment.body == "Great post!"
    assert comment.ip == "1.2.3.4"
    assert comment.user_agent == "test-agent"
    db2.close()


def test_rate_limit_blocks_4th_comment(client):
    db = _db()
    post = Post(
        title="Rate Limit Post",
        slug="rate-limit-post",
        body="Content",
        status="published",
        publish_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(post)
    db.commit()
    post_id = post.id
    db.close()

    fingerprint = "abc123def456"

    for i in range(3):
        resp = client.post(
            "/posts/rate-limit-post/comments",
            data={
                "name": f"User{i}",
                "body": f"Comment {i}",
                "fingerprint": fingerprint,
            },
            headers={"X-Forwarded-For": "10.0.0.1", "User-Agent": "rate-tester"},
        )
        assert resp.status_code == 200

    resp = client.post(
        "/posts/rate-limit-post/comments",
        data={
            "name": "User4",
            "body": "Fourth comment should fail",
            "fingerprint": fingerprint,
        },
        headers={"X-Forwarded-For": "10.0.0.1", "User-Agent": "rate-tester"},
    )
    assert resp.status_code == 429

    db2 = _db()
    count = db2.query(Comment).filter(Comment.post_id == post_id).count()
    assert count == 3
    db2.close()


def test_banned_fingerprint_comment_held_for_moderation(client):
    from app.models import Fingerprint

    db = _db()
    fp = Fingerprint(hash="banned-fingerprint-xyz", banned=True)
    db.add(fp)
    db.commit()

    post = Post(
        title="Ban Test Post",
        slug="ban-test-post",
        body="Content",
        status="published",
        publish_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(post)
    db.commit()
    post_id = post.id
    db.close()

    resp = client.post(
        "/posts/ban-test-post/comments",
        data={
            "name": "Banned User",
            "body": "I should be moderated",
            "fingerprint": "banned-fingerprint-xyz",
        },
        headers={"X-Forwarded-For": "10.0.0.99", "User-Agent": "banned-agent"},
    )
    assert resp.status_code == 200

    db2 = _db()
    comment = db2.query(Comment).filter(Comment.post_id == post_id).first()
    assert comment is not None
    assert comment.is_approved is False
    db2.close()


def _login(client: TestClient) -> str:
    resp = client.post(
        "/admin/login", data={"password": "testpass"}, follow_redirects=False
    )
    return resp.cookies.get("blog_session", "")


def test_admin_can_approve_comment(client):
    db = _db()
    post = Post(
        title="Mod Post",
        slug="mod-post",
        body="Content",
        status="published",
        publish_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(post)
    db.commit()
    db.close()

    session = _login(client)
    client.cookies.set("blog_session", session)

    resp = client.post(
        "/posts/mod-post/comments",
        data={"name": "Moderated", "body": "Pending approval"},
        headers={"X-Forwarded-For": "10.0.0.1", "User-Agent": "mod-tester"},
    )
    assert resp.status_code == 200

    db2 = _db()
    comment = db2.query(Comment).first()
    assert comment.is_approved is True
    comment.is_approved = False
    comment_id = comment.id
    db2.commit()
    db2.close()

    resp = client.post(f"/admin/comments/{comment_id}/approve", follow_redirects=False)
    assert resp.status_code == 302

    db3 = _db()
    updated = db3.query(Comment).filter(Comment.id == comment_id).first()
    assert updated.is_approved is True
    db3.close()


def test_admin_can_delete_comment(client):
    db = _db()
    post = Post(
        title="Del Post",
        slug="del-post",
        body="Content",
        status="published",
        publish_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(post)
    db.commit()
    db.close()

    session = _login(client)
    client.cookies.set("blog_session", session)

    resp = client.post(
        "/posts/del-post/comments",
        data={"name": "Delete Me", "body": "To be deleted"},
        headers={"X-Forwarded-For": "10.0.0.1", "User-Agent": "del-tester"},
    )
    assert resp.status_code == 200

    db2 = _db()
    comment = db2.query(Comment).first()
    comment_id = comment.id
    db2.close()

    resp = client.post(f"/admin/comments/{comment_id}/delete", follow_redirects=False)
    assert resp.status_code == 302

    db3 = _db()
    remaining = db3.query(Comment).count()
    assert remaining == 0
    db3.close()


def test_admin_can_ban_fingerprint(client):
    from app.models import Fingerprint

    db = _db()
    fp = Fingerprint(hash="soon-banned-abcd")
    db.add(fp)
    db.commit()
    fp_id = fp.id

    post = Post(
        title="Ban FP Post",
        slug="ban-fp-post",
        body="Content",
        status="published",
        publish_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(post)
    db.commit()
    db.close()

    session = _login(client)
    client.cookies.set("blog_session", session)

    resp = client.post(
        f"/admin/comments/ban-fingerprint/{fp_id}", follow_redirects=False
    )
    assert resp.status_code == 302

    db2 = _db()
    updated_fp = db2.query(Fingerprint).filter(Fingerprint.id == fp_id).first()
    assert updated_fp.banned is True
    db2.close()


def test_comment_list_shows_all_comments(client):
    db = _db()
    post = Post(
        title="List Post",
        slug="list-post",
        body="Content",
        status="published",
        publish_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(post)
    db.commit()
    db.close()

    client.post(
        "/posts/list-post/comments",
        data={"name": "Alice", "body": "Comment 1"},
        headers={"X-Forwarded-For": "10.0.0.1", "User-Agent": "list"},
    )
    client.post(
        "/posts/list-post/comments",
        data={"name": "Bob", "body": "Comment 2"},
        headers={"X-Forwarded-For": "10.0.0.2", "User-Agent": "list"},
    )

    session = _login(client)
    client.cookies.set("blog_session", session)

    resp = client.get("/admin/comments")
    assert resp.status_code == 200
    assert "Comment 1" in resp.text
    assert "Comment 2" in resp.text
