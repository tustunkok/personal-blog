import datetime
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.dependencies import get_scheduler
from app.main import app
from app.models import Comment, Post, Reaction, Setting, Visit


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
        "sqlite:///test_admin_dashboard.db", connect_args={"check_same_thread": False}
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
    try:
        os.remove("test_admin_dashboard.db")
    except OSError:
        pass


def _login(client):
    resp = client.post(
        "/admin/login",
        data={"password": "testpass"},
        follow_redirects=False,
    )
    cookie = resp.cookies.get("blog_session")
    client.cookies.set("blog_session", cookie)


# --- Settings tests ---


def test_settings_page_requires_auth(client):
    c, _ = client
    resp = c.get("/admin/settings", follow_redirects=False)
    assert resp.status_code == 302


def test_settings_page_returns_form(client):
    c, _ = client
    _login(c)
    resp = c.get("/admin/settings")
    assert resp.status_code == 200
    assert "settings" in resp.text.lower()


def test_settings_page_shows_saved_values(client):
    c, engine = client
    _login(c)
    db = Session(engine)
    db.add(Setting(key="blog_name", value="Test Blog"))
    db.add(Setting(key="blog_tagline", value="A tagline"))
    db.commit()
    db.close()

    resp = c.get("/admin/settings")
    assert "Test Blog" in resp.text
    assert "A tagline" in resp.text


def test_save_settings(client):
    c, engine = client
    _login(c)
    resp = c.post(
        "/admin/settings",
        data={
            "blog_name": "My Blog",
            "blog_tagline": "Cool Stuff",
            "blog_author": "Tolga",
            "rss_post_count": "15",
            "date_format": "%B %d, %Y",
            "bot_time_gate": "5",
            "turnstile_site_key": "key123",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/admin/settings" in resp.headers["location"]

    db = Session(engine)
    blog_name = db.query(Setting).filter(Setting.key == "blog_name").first()
    rss_count = db.query(Setting).filter(Setting.key == "rss_post_count").first()
    db.close()
    assert blog_name.value == "My Blog"
    assert rss_count.value == "15"


def test_settings_page_preserves_about_now_keys(client):
    c, engine = client
    _login(c)
    db = Session(engine)
    db.add(Setting(key="about_content", value="About me"))
    db.add(Setting(key="now_content", value="Now doing"))
    db.commit()
    db.close()

    c.post(
        "/admin/settings",
        data={"blog_name": "X"},
        follow_redirects=False,
    )

    db2 = Session(engine)
    about = db2.query(Setting).filter(Setting.key == "about_content").first()
    now = db2.query(Setting).filter(Setting.key == "now_content").first()
    db2.close()
    assert about.value == "About me"
    assert now.value == "Now doing"


# --- Dashboard snapshot tests ---


def test_dashboard_shows_views_today(client):
    c, engine = client
    _login(c)
    db = Session(engine)
    today = datetime.datetime.now(datetime.UTC)
    db.add(Visit(path="/", created_at=today))
    db.add(Visit(path="/about", created_at=today))
    db.commit()
    db.close()

    resp = c.get("/admin")
    assert "2" in resp.text


def test_dashboard_shows_top_posts(client):
    c, engine = client
    _login(c)
    db = Session(engine)
    p1 = Post(title="Post A", slug="post-a", body="a", status="published")
    p2 = Post(title="Post B", slug="post-b", body="b", status="published")
    db.add_all([p1, p2])
    db.commit()
    db.add_all(
        [
            Visit(post_id=p1.id, path="/posts/post-a"),
            Visit(post_id=p1.id, path="/posts/post-a"),
            Visit(post_id=p2.id, path="/posts/post-b"),
        ]
    )
    db.commit()
    db.close()

    resp = c.get("/admin")
    assert "Post A" in resp.text


def test_dashboard_shows_new_comment_count(client):
    c, engine = client
    _login(c)
    db = Session(engine)
    p = Post(title="T", slug="t", body="b", status="published")
    db.add(p)
    db.commit()
    db.add_all(
        [
            Comment(post_id=p.id, body="c1"),
            Comment(post_id=p.id, body="c2", is_approved=True),
        ]
    )
    db.commit()
    db.close()

    resp = c.get("/admin")
    assert "1" in resp.text


# --- Analytics page tests ---


def test_analytics_page_requires_auth(client):
    c, _ = client
    resp = c.get("/admin/analytics", follow_redirects=False)
    assert resp.status_code == 302


def test_analytics_page_returns_200(client):
    c, _ = client
    _login(c)
    resp = c.get("/admin/analytics")
    assert resp.status_code == 200
    assert "analytics" in resp.text.lower()


def test_analytics_page_shows_visit_count(client):
    c, engine = client
    _login(c)
    db = Session(engine)
    db.add_all([Visit(path="/"), Visit(path="/about"), Visit(path="/posts/s")])
    db.commit()
    db.close()

    resp = c.get("/admin/analytics")
    assert "3" in resp.text


def test_analytics_page_shows_reaction_counts(client):
    c, engine = client
    _login(c)
    db = Session(engine)
    p = Post(title="T", slug="t", body="b", status="published")
    db.add(p)
    db.commit()
    db.add_all(
        [
            Reaction(post_id=p.id, reaction_type="like"),
            Reaction(post_id=p.id, reaction_type="like"),
            Reaction(post_id=p.id, reaction_type="clap"),
        ]
    )
    db.commit()
    db.close()

    resp = c.get("/admin/analytics")
    assert "2" in resp.text
    assert "1" in resp.text


# --- CSV/JSON export tests ---


def test_csv_export_visits(client):
    c, engine = client
    _login(c)
    db = Session(engine)
    db.add(Visit(path="/", ip="1.2.3.4"))
    db.commit()
    db.close()

    resp = c.get("/admin/analytics/visits.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "1.2.3.4" in resp.text


def test_json_export_visits(client):
    c, engine = client
    _login(c)
    db = Session(engine)
    db.add(Visit(path="/"))
    db.commit()
    db.close()

    resp = c.get("/admin/analytics/visits.json")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    assert '"/"' in resp.text
