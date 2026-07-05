import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db as original_get_db
from app.dependencies import get_scheduler as original_get_scheduler
from app import models  # noqa: F401
from app.main import app


class FakeScheduler:
    def schedule_post(self, post_id, publish_at):
        pass

    def unschedule_post(self, post_id):
        pass


@pytest.fixture(autouse=True)
def clear_env():
    old = os.environ.pop("BLOG_ADMIN_PASSWORD", None)
    yield
    if old is not None:
        os.environ["BLOG_ADMIN_PASSWORD"] = old


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///test_auth.db", connect_args={"check_same_thread": False}
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
        os.remove("test_auth.db")
    except OSError:
        pass


def test_admin_login_page_returns_200(client: TestClient):
    response = client.get("/admin/login")
    assert response.status_code == 200
    assert "login" in response.text.lower()


def test_admin_login_redirects_on_correct_password(client: TestClient):
    os.environ["BLOG_ADMIN_PASSWORD"] = "secret123"
    response = client.post(
        "/admin/login",
        data={"password": "secret123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/admin" in response.headers["location"]


def test_admin_login_rejects_wrong_password(client: TestClient):
    os.environ["BLOG_ADMIN_PASSWORD"] = "secret123"
    response = client.post(
        "/admin/login",
        data={"password": "wrong"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "invalid" in response.text.lower()


def test_admin_routes_require_auth(client: TestClient):
    os.environ["BLOG_ADMIN_PASSWORD"] = "secret123"
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 302
    assert "/admin/login" in response.headers["location"]


def test_authenticated_session_can_access_admin(client: TestClient):
    os.environ["BLOG_ADMIN_PASSWORD"] = "secret123"
    login_resp = client.post(
        "/admin/login",
        data={"password": "secret123"},
        follow_redirects=False,
    )
    session_cookie = login_resp.cookies.get("blog_session")
    assert session_cookie is not None

    client.cookies.set("blog_session", session_cookie)
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Dashboard" in response.text
