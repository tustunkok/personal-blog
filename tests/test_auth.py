import os

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(autouse=True)
def clear_env():
    old = os.environ.pop("BLOG_ADMIN_PASSWORD", None)
    yield
    if old is not None:
        os.environ["BLOG_ADMIN_PASSWORD"] = old


def test_admin_login_page_returns_200():
    client = TestClient(app)
    response = client.get("/admin/login")
    assert response.status_code == 200
    assert "login" in response.text.lower()


def test_admin_login_redirects_on_correct_password():
    os.environ["BLOG_ADMIN_PASSWORD"] = "secret123"
    client = TestClient(app)
    response = client.post(
        "/admin/login",
        data={"password": "secret123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/admin" in response.headers["location"]


def test_admin_login_rejects_wrong_password():
    os.environ["BLOG_ADMIN_PASSWORD"] = "secret123"
    client = TestClient(app)
    response = client.post(
        "/admin/login",
        data={"password": "wrong"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "invalid" in response.text.lower()


def test_admin_routes_require_auth():
    os.environ["BLOG_ADMIN_PASSWORD"] = "secret123"
    client = TestClient(app)
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 302
    assert "/admin/login" in response.headers["location"]


def test_authenticated_session_can_access_admin():
    os.environ["BLOG_ADMIN_PASSWORD"] = "secret123"
    client = TestClient(app)
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
