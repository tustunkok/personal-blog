import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db as original_get_db
from app.dependencies import get_scheduler as original_get_scheduler
from app import models
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
        "sqlite:///test_seo.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[original_get_db] = override_get_db
    app.dependency_overrides[original_get_scheduler] = lambda: FakeScheduler()
    yield TestClient(app), session_factory
    app.dependency_overrides.clear()
    engine.dispose()
    try:
        os.remove("test_seo.db")
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


def test_robots_txt_returns_text(client):
    c, _ = client
    resp = c.get("/robots.txt")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "Sitemap:" in resp.text
    assert "Disallow:" in resp.text


def test_sitemap_xml_lists_published_posts_and_static_pages(client):
    c, _ = client
    ac = _auth_client(c)
    ac.post(
        "/admin/posts",
        data={"title": "Sitemap Post", "body": "Body", "excerpt": "Excerpt"},
        follow_redirects=False,
    )
    ac.post("/admin/posts/1/publish", follow_redirects=False)

    resp = c.get("/sitemap.xml")
    assert resp.status_code == 200
    assert "xml" in resp.headers["content-type"]
    assert "<urlset" in resp.text
    assert "/posts/sitemap-post" in resp.text
    assert "/about" in resp.text
    assert "/now" in resp.text


def test_feed_xml_returns_valid_rss_with_published_posts(client):
    c, _ = client
    ac = _auth_client(c)
    ac.post(
        "/admin/posts",
        data={
            "title": "Published Feed Post",
            "body": "Published content",
            "excerpt": "Pub",
        },
        follow_redirects=False,
    )
    ac.post("/admin/posts/1/publish", follow_redirects=False)
    ac.post(
        "/admin/posts",
        data={"title": "Draft Feed Post", "body": "Draft content", "excerpt": "Draft"},
        follow_redirects=False,
    )

    resp = c.get("/feed.xml")
    assert resp.status_code == 200
    assert "xml" in resp.headers["content-type"]
    assert "<rss" in resp.text
    assert "<channel>" in resp.text
    assert "Published Feed Post" in resp.text
    assert "Published content" in resp.text
    assert "Draft Feed Post" not in resp.text


def test_feed_xml_limits_to_20_posts(client):
    c, _ = client
    ac = _auth_client(c)
    for i in range(25):
        ac.post(
            "/admin/posts",
            data={"title": f"Feed Post {i}", "body": f"Body {i}", "excerpt": f"Ex {i}"},
            follow_redirects=False,
        )
        ac.post(f"/admin/posts/{i + 1}/publish", follow_redirects=False)

    resp = c.get("/feed.xml")
    assert resp.status_code == 200
    assert resp.text.count("<item>") == 20


def test_post_page_has_open_graph_tags(client):
    c, _ = client
    ac = _auth_client(c)
    ac.post(
        "/admin/posts",
        data={"title": "OG Post", "body": "Body", "excerpt": "OG excerpt"},
        follow_redirects=False,
    )
    ac.post("/admin/posts/1/publish", follow_redirects=False)

    resp = c.get("/posts/og-post")
    assert resp.status_code == 200
    assert 'property="og:title"' in resp.text
    assert "OG Post" in resp.text
    assert 'property="og:description"' in resp.text
    assert "OG excerpt" in resp.text
    assert 'property="og:image"' in resp.text
    assert 'property="og:url"' in resp.text
    assert 'property="og:type"' in resp.text
    assert 'content="article"' in resp.text


def test_post_page_has_twitter_card_tags(client):
    c, _ = client
    ac = _auth_client(c)
    ac.post(
        "/admin/posts",
        data={"title": "Twitter Post", "body": "Body", "excerpt": "Twitter excerpt"},
        follow_redirects=False,
    )
    ac.post("/admin/posts/1/publish", follow_redirects=False)

    resp = c.get("/posts/twitter-post")
    assert resp.status_code == 200
    assert 'name="twitter:card"' in resp.text
    assert 'content="summary_large_image"' in resp.text
    assert 'name="twitter:title"' in resp.text
    assert 'name="twitter:description"' in resp.text
    assert 'name="twitter:image"' in resp.text


def test_post_page_has_json_ld_structured_data(client):
    c, _ = client
    ac = _auth_client(c)
    ac.post(
        "/admin/posts",
        data={"title": "JSON LD Post", "body": "Body", "excerpt": "Schema excerpt"},
        follow_redirects=False,
    )
    ac.post("/admin/posts/1/publish", follow_redirects=False)

    resp = c.get("/posts/json-ld-post")
    assert resp.status_code == 200
    assert "application/ld+json" in resp.text
    assert '"BlogPosting"' in resp.text
    assert '"headline"' in resp.text
    assert '"JSON LD Post"' in resp.text


def test_post_page_has_description_meta(client):
    c, _ = client
    ac = _auth_client(c)
    ac.post(
        "/admin/posts",
        data={"title": "Meta Desc", "body": "Body", "excerpt": "Meta description"},
        follow_redirects=False,
    )
    ac.post("/admin/posts/1/publish", follow_redirects=False)

    resp = c.get("/posts/meta-desc")
    assert resp.status_code == 200
    assert 'name="description"' in resp.text
    assert 'content="Meta description"' in resp.text


def test_post_page_canonical_url_when_set(client):
    c, sf = client
    ac = _auth_client(c)
    ac.post(
        "/admin/posts",
        data={"title": "Canonical Post", "body": "Body", "excerpt": "Excerpt"},
        follow_redirects=False,
    )

    db = sf()
    post = db.query(models.Post).filter(models.Post.id == 1).first()
    post.canonical_url = "https://example.com/original"
    db.commit()
    db.close()

    ac.post("/admin/posts/1/publish", follow_redirects=False)

    resp = c.get("/posts/canonical-post")
    assert resp.status_code == 200
    assert 'rel="canonical"' in resp.text
    assert 'href="https://example.com/original"' in resp.text


def test_og_image_route_returns_image(client):
    c, _ = client
    ac = _auth_client(c)
    ac.post(
        "/admin/posts",
        data={"title": "OG Image Post", "body": "Content", "excerpt": "Excerpt"},
        follow_redirects=False,
    )
    ac.post("/admin/posts/1/publish", follow_redirects=False)

    resp = c.get("/posts/og-image-post/og-image")
    assert resp.status_code == 200
    assert "image/" in resp.headers["content-type"]
    assert len(resp.content) > 0


def test_og_image_returns_404_for_nonexistent_post(client):
    c, _ = client
    resp = c.get("/posts/no-such-post/og-image")
    assert resp.status_code == 404


def test_og_image_returns_404_for_draft_post(client):
    c, _ = client
    ac = _auth_client(c)
    ac.post(
        "/admin/posts",
        data={"title": "Draft OG", "body": "Body", "excerpt": "Excerpt"},
        follow_redirects=False,
    )

    resp = c.get("/posts/draft-og/og-image")
    assert resp.status_code == 404
