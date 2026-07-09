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
        "sqlite:///test_posts.db", connect_args={"check_same_thread": False}
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
        os.remove("test_posts.db")
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


def test_admin_posts_list_empty(client):
    _auth_client(client)
    resp = client.get("/admin/posts")
    assert resp.status_code == 200
    assert "New Post" in resp.text


def test_create_draft_via_form(client):
    _auth_client(client)
    resp = client.post(
        "/admin/posts",
        data={
            "title": "My First Post",
            "body": "Hello world content",
            "excerpt": "A summary",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    from app.models import Post

    db = app.dependency_overrides[original_get_db]
    g = db()
    s = next(g)
    posts = s.query(Post).all()
    assert len(posts) == 1
    assert posts[0].title == "My First Post"
    assert posts[0].status == "draft"
    assert posts[0].slug == "my-first-post"


def test_update_post_via_form(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "Original", "body": "Original body", "excerpt": "Orig"},
        follow_redirects=False,
    )

    from app.models import Post

    g = app.dependency_overrides[original_get_db]()
    db = next(g)
    post = db.query(Post).first()
    resp = client.post(
        f"/admin/posts/{post.id}",
        data={"title": "Updated", "body": "Updated body", "excerpt": "Upd"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db.refresh(post)
    assert post.title == "Updated"


def test_publish_post(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "Publish Me", "body": "Content"},
        follow_redirects=False,
    )

    from app.models import Post

    g = app.dependency_overrides[original_get_db]()
    db = next(g)
    post = db.query(Post).first()
    resp = client.post(f"/admin/posts/{post.id}/publish", follow_redirects=False)
    assert resp.status_code == 302
    db.refresh(post)
    assert post.status == "published"


def test_unpublish_post(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "Unpublish Me", "body": "Content"},
        follow_redirects=False,
    )

    from app.models import Post

    g = app.dependency_overrides[original_get_db]()
    db = next(g)
    post = db.query(Post).first()
    client.post(f"/admin/posts/{post.id}/publish")
    client.post(f"/admin/posts/{post.id}/unpublish")
    db.refresh(post)
    assert post.status == "draft"


def test_soft_delete_post(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "Delete Me", "body": "Content"},
        follow_redirects=False,
    )

    from app.models import Post

    g = app.dependency_overrides[original_get_db]()
    db = next(g)
    post = db.query(Post).first()
    resp = client.post(f"/admin/posts/{post.id}/delete", follow_redirects=False)
    assert resp.status_code == 302
    db.refresh(post)
    assert post.deleted_at is not None


def test_restore_post(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "Restore Me", "body": "Content"},
        follow_redirects=False,
    )

    from app.models import Post

    g = app.dependency_overrides[original_get_db]()
    db = next(g)
    post = db.query(Post).first()
    client.post(f"/admin/posts/{post.id}/delete")
    client.post(f"/admin/posts/{post.id}/restore")
    db.refresh(post)
    assert post.deleted_at is None


def test_post_routes_require_auth(client):
    resp = client.get("/admin/posts", follow_redirects=False)
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["location"]


def test_post_list_shows_non_deleted_posts(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "Visible", "body": "Content"},
        follow_redirects=False,
    )

    from app.models import Post

    g = app.dependency_overrides[original_get_db]()
    db = next(g)
    post = db.query(Post).filter(Post.title == "Visible").first()
    client.post(f"/admin/posts/{post.id}/delete")

    resp = client.get("/admin/posts")
    assert resp.status_code == 200
    assert "Visible" not in resp.text


def test_version_history_page_accessible(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "Versioned Post", "body": "Body v1"},
        follow_redirects=False,
    )

    from app.models import Post

    g = app.dependency_overrides[original_get_db]()
    db = next(g)
    post = db.query(Post).first()
    resp = client.get(f"/admin/posts/{post.id}/versions")
    assert resp.status_code == 200
    assert "Version History" in resp.text


def test_version_history_shows_versions_after_edits(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "V Post", "body": "v1"},
        follow_redirects=False,
    )

    from app.models import Post, PostVersion

    g = app.dependency_overrides[original_get_db]()
    db = next(g)
    post = db.query(Post).first()
    client.post(
        f"/admin/posts/{post.id}",
        data={"title": "V Post", "body": "v2", "excerpt": ""},
        follow_redirects=False,
    )
    client.post(
        f"/admin/posts/{post.id}",
        data={"title": "V Post v3", "body": "v3", "excerpt": ""},
        follow_redirects=False,
    )

    versions = db.query(PostVersion).filter(PostVersion.post_id == post.id).count()
    assert versions == 2

    resp = client.get(f"/admin/posts/{post.id}/versions")
    assert resp.status_code == 200
    assert "V Post" in resp.text
    assert "Version 2" in resp.text


def test_revert_to_version(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "Revert Me", "body": "original"},
        follow_redirects=False,
    )

    from app.models import Post, PostVersion

    g = app.dependency_overrides[original_get_db]()
    db = next(g)
    post = db.query(Post).filter(Post.title == "Revert Me").first()
    client.post(
        f"/admin/posts/{post.id}",
        data={"title": "Revert Me", "body": "changed", "excerpt": ""},
        follow_redirects=False,
    )

    version = (
        db.query(PostVersion)
        .filter(PostVersion.post_id == post.id)
        .order_by(PostVersion.version_number.asc())
        .first()
    )
    assert version.body == "original"

    resp = client.post(
        f"/admin/posts/{post.id}/versions/{version.id}/revert",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    db.refresh(post)
    assert post.body == "original"


def test_autosave_route_updates_post_without_version(client):
    _auth_client(client)
    client.post(
        "/admin/posts",
        data={"title": "Autosave Test", "body": "start"},
        follow_redirects=False,
    )

    from app.models import Post, PostVersion

    g = app.dependency_overrides[original_get_db]()
    db = next(g)
    post = db.query(Post).filter(Post.title == "Autosave Test").first()

    resp = client.post(
        f"/admin/posts/{post.id}/autosave",
        data={"title": "Autosave Test Updated", "body": "autosaved"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert resp.text == "ok"

    db.refresh(post)
    assert post.body == "autosaved"
    assert post.title == "Autosave Test Updated"

    version_count = db.query(PostVersion).filter(PostVersion.post_id == post.id).count()
    assert version_count == 0


def test_version_routes_require_auth(client):
    resp = client.get("/admin/posts/1/versions", follow_redirects=False)
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["location"]

    resp = client.post("/admin/posts/1/versions/1/revert", follow_redirects=False)
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["location"]


def test_edit_form_includes_easymde_css(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    assert "easymde.min.css" in resp.text


def test_edit_form_includes_easymde_js(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    assert "easymde.min.js" in resp.text


def test_edit_form_includes_paste_upload_js(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    assert 'src="/static/js/paste-upload.js"' in resp.text


def test_edit_form_has_easymde_target_textarea(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    assert 'id="body-editor"' in resp.text


def test_editor_preview_styles_headings(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    style = _extract_style_block(resp.text)
    assert ".editor-preview h1" in style
    assert ".editor-preview h2" in style
    assert ".editor-preview h3" in style


def test_editor_preview_styles_lists(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    style = _extract_style_block(resp.text)
    assert ".editor-preview ul" in style
    assert ".editor-preview ol" in style
    assert "list-style" in style


def test_editor_preview_styles_blockquote(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    style = _extract_style_block(resp.text)
    assert ".editor-preview blockquote" in style


def test_editor_preview_styles_code(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    style = _extract_style_block(resp.text)
    assert ".editor-preview code" in style
    assert ".editor-preview pre" in style


def test_editor_preview_styles_tables(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    style = _extract_style_block(resp.text)
    assert ".editor-preview table" in style


def test_editor_preview_styles_links(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    style = _extract_style_block(resp.text)
    assert ".editor-preview a" in style


def test_editor_preview_styles_images_and_hr(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    style = _extract_style_block(resp.text)
    assert ".editor-preview img" in style
    assert ".editor-preview hr" in style


def test_editor_preview_strong_has_font_weight(client):
    _auth_client(client)
    resp = client.get("/admin/posts/new")
    assert resp.status_code == 200
    style = _extract_style_block(resp.text)
    assert ".editor-preview strong" in style


def test_page_edit_has_editor_preview_styles(client):
    _auth_client(client)
    resp = client.get("/admin/pages/about")
    assert resp.status_code == 200
    style = _extract_style_block(resp.text)
    assert ".editor-preview h1" in style
    assert ".editor-preview h2" in style
    assert ".editor-preview ul" in style
    assert ".editor-preview blockquote" in style


def _extract_style_block(html: str) -> str:
    start = html.find("<style>")
    end = html.find("</style>", start)
    if start == -1 or end == -1:
        return ""
    return html[start + len("<style>") : end]
