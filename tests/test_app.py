from fastapi.testclient import TestClient
from app.main import app


def test_root_returns_200():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200


def test_root_uses_jinja2_template():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text.lower()
    assert "<html" in html
    assert "tailwindcss" in html


def test_dark_mode_toggle_present():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "theme-toggle" in html


def test_htmx_loaded():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "htmx.org" in html
