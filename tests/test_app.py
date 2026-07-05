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
    os.environ["BLOG_ADMIN_PASSWORD"] = "testpass"
    yield
    os.environ.pop("BLOG_ADMIN_PASSWORD", None)
    if old is not None:
        os.environ["BLOG_ADMIN_PASSWORD"] = old


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///test_app.db", connect_args={"check_same_thread": False}
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
        os.remove("test_app.db")
    except OSError:
        pass


def test_root_returns_200(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200


def test_root_uses_jinja2_template(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text.lower()
    assert "<html" in html
    assert "tailwindcss" in html


def test_dark_mode_toggle_present(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "theme-toggle" in html


def test_htmx_loaded(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "htmx.org" in html
