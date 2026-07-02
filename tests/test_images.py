import io
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
        "sqlite:///test_images.db", connect_args={"check_same_thread": False}
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
        os.remove("test_images.db")
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


def test_upload_image_requires_auth(client):
    image_data = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    image_data.name = "test.png"
    resp = client.post(
        "/admin/images/upload",
        files={"file": ("test.png", image_data, "image/png")},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["location"]


def test_upload_image_stores_blob_and_returns_id(client):
    _auth_client(client)
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    resp = client.post(
        "/admin/images/upload",
        files={"file": ("test.png", io.BytesIO(image_bytes), "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    image_id = data["id"]

    from app.models import Image

    g = app.dependency_overrides[original_get_db]()
    db = next(g)
    img = db.query(Image).filter(Image.id == image_id).first()
    assert img is not None
    assert img.filename == "test.png"
    assert img.content_type == "image/png"
    assert img.data == image_bytes


def test_serve_image_returns_correct_content_type(client):
    _auth_client(client)
    image_bytes = b"GIF89a" + b"\x00" * 50
    resp = client.post(
        "/admin/images/upload",
        files={"file": ("test.gif", io.BytesIO(image_bytes), "image/gif")},
    )
    image_id = resp.json()["id"]

    resp = client.get(f"/images/{image_id}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/gif"
    assert resp.content == image_bytes


def test_serve_nonexistent_image_returns_404(client):
    resp = client.get("/images/99999")
    assert resp.status_code == 404
