import datetime
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.dependencies import get_scheduler
from app.main import app
from app.models import Post, Reaction, Share


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
        "sqlite:///test_reactions_shares.db", connect_args={"check_same_thread": False}
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
        os.remove("test_reactions_shares.db")
    except OSError:
        pass


def _db():
    g = app.dependency_overrides[get_db]()
    return next(g)


def _create_published_post(db, title, slug, body="Content"):
    post = Post(
        title=title,
        slug=slug,
        body=body,
        status="published",
        publish_at=datetime.datetime.now(datetime.UTC),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def test_add_reaction_to_published_post(client):
    db = _db()
    post = _create_published_post(db, "Reaction Post", "reaction-post")
    post_id = post.id
    db.close()

    resp = client.post(
        "/posts/reaction-post/reactions",
        data={
            "reaction_type": "like",
            "fingerprint": "fp-abc-123",
            "scroll_position": "0.5",
            "time_to_react": "12.3",
        },
        headers={"X-Forwarded-For": "1.2.3.4", "User-Agent": "test-agent"},
    )

    assert resp.status_code == 200
    assert "like" in resp.text

    db2 = _db()
    reaction = db2.query(Reaction).filter(Reaction.post_id == post_id).first()
    assert reaction is not None
    assert reaction.reaction_type == "like"
    assert reaction.ip == "1.2.3.4"
    assert reaction.user_agent == "test-agent"
    assert reaction.scroll_position == 0.5
    assert reaction.time_to_react == 12.3
    db2.close()


def test_duplicate_reaction_same_fingerprint_ignored(client):
    db = _db()
    post = _create_published_post(db, "Dup Reaction", "dup-reaction")
    post_id = post.id
    db.close()

    fingerprint = "fp-dup-456"

    resp1 = client.post(
        "/posts/dup-reaction/reactions",
        data={"reaction_type": "clap", "fingerprint": fingerprint},
        headers={"X-Forwarded-For": "5.5.5.5", "User-Agent": "dup-agent"},
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        "/posts/dup-reaction/reactions",
        data={"reaction_type": "clap", "fingerprint": fingerprint},
        headers={"X-Forwarded-For": "5.5.5.5", "User-Agent": "dup-agent"},
    )
    assert resp2.status_code == 200

    db2 = _db()
    count = (
        db2.query(Reaction)
        .filter(
            Reaction.post_id == post_id,
            Reaction.reaction_type == "clap",
        )
        .count()
    )
    assert count == 1
    db2.close()


def test_different_reaction_types_same_fingerprint_allowed(client):
    db = _db()
    post = _create_published_post(db, "Multi Reaction", "multi-reaction")
    post_id = post.id
    db.close()

    fingerprint = "fp-multi-789"

    for rtype in ["like", "clap", "bookmark", "insightful", "mind-blown"]:
        resp = client.post(
            "/posts/multi-reaction/reactions",
            data={"reaction_type": rtype, "fingerprint": fingerprint},
            headers={"X-Forwarded-For": "6.6.6.6", "User-Agent": "multi-agent"},
        )
        assert resp.status_code == 200

    db2 = _db()
    count = db2.query(Reaction).filter(Reaction.post_id == post_id).count()
    assert count == 5
    db2.close()


def test_get_reactions_returns_counts(client):
    db = _db()
    post = _create_published_post(db, "Reaction Counts", "reaction-counts")
    post_id = post.id

    r1 = Reaction(post_id=post_id, reaction_type="like", ip="1.1.1.1")
    r2 = Reaction(post_id=post_id, reaction_type="like", ip="2.2.2.2")
    r3 = Reaction(post_id=post_id, reaction_type="clap", ip="3.3.3.3")
    db.add_all([r1, r2, r3])
    db.commit()
    db.close()

    resp = client.get("/posts/reaction-counts/reactions")
    assert resp.status_code == 200
    assert "2" in resp.text
    assert "like" in resp.text
    assert "clap" in resp.text


def test_add_share_records_event(client):
    db = _db()
    post = _create_published_post(db, "Share Post", "share-post")
    post_id = post.id
    db.close()

    resp = client.post(
        "/posts/share-post/shares",
        data={"platform": "twitter"},
        headers={"X-Forwarded-For": "7.7.7.7", "User-Agent": "share-agent"},
    )

    assert resp.status_code == 200

    db2 = _db()
    share = db2.query(Share).filter(Share.post_id == post_id).first()
    assert share is not None
    assert share.platform == "twitter"
    assert share.ip == "7.7.7.7"
    assert share.user_agent == "share-agent"
    db2.close()


def test_get_shares_returns_share_buttons(client):
    db = _db()
    _create_published_post(db, "Share Buttons", "share-buttons")
    db.close()

    resp = client.get("/posts/share-buttons/shares")
    assert resp.status_code == 200
    assert "twitter" in resp.text or "Twitter" in resp.text


def test_reactions_not_visible_on_draft_post(client):
    db = _db()
    post = Post(
        title="Draft Reaction",
        slug="draft-reaction",
        body="Content",
        status="draft",
    )
    db.add(post)
    db.commit()
    db.close()

    resp = client.get("/posts/draft-reaction/reactions")
    assert resp.status_code == 404
