"""HIGH: admin login brute-force protection.

Seam under test: POST /admin/login. An unauthenticated attacker must not be
able to hammer the admin password indefinitely. After MAX_LOGIN_ATTEMPTS
consecutive failures for a client, further attempts are rejected with 429 until
the window elapses; a successful login resets the failure count.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.database import Base, get_db
from app.dependencies import get_scheduler
from app.main import app
from app.ratelimit import MAX_LOGIN_ATTEMPTS


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
    db_file = f"test_login_rate_{uuid.uuid4().hex}.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)

    def override_get_db():
        db = sessionmaker(bind=engine)()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_scheduler] = lambda: FakeScheduler()
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()
    try:
        os.remove(db_file)
    except OSError:
        pass


def _wrong(client, **kw):
    return client.post(
        "/admin/login", data={"password": "wrong"}, follow_redirects=False
    )


def test_rate_limited_after_max_attempts(client):
    os.environ["BLOG_ADMIN_PASSWORD"] = "secret123"
    codes = []
    for _ in range(MAX_LOGIN_ATTEMPTS + 1):
        codes.append(_wrong(client).status_code)
    # First MAX_LOGIN_ATTEMPTS are plain "invalid password" (200)...
    assert codes[:MAX_LOGIN_ATTEMPTS] == [200] * MAX_LOGIN_ATTEMPTS
    # ...the next is rejected outright (429).
    assert codes[MAX_LOGIN_ATTEMPTS] == 429


def test_valid_password_not_blocked_on_first_try(client):
    os.environ["BLOG_ADMIN_PASSWORD"] = "secret123"
    r = client.post(
        "/admin/login", data={"password": "secret123"}, follow_redirects=False
    )
    assert r.status_code == 302


def test_successful_login_resets_failure_count(client):
    os.environ["BLOG_ADMIN_PASSWORD"] = "secret123"
    # Under the limit, a correct password still logs in even after some failures.
    for _ in range(MAX_LOGIN_ATTEMPTS - 1):
        _wrong(client)
    ok = client.post(
        "/admin/login", data={"password": "secret123"}, follow_redirects=False
    )
    assert ok.status_code == 302

    # That success reset the counter, so the attacker's clock starts fresh:
    # a full MAX_LOGIN_ATTEMPTS more failures are needed before blocking.
    codes = [_wrong(client).status_code for _ in range(MAX_LOGIN_ATTEMPTS)]
    assert codes == [200] * MAX_LOGIN_ATTEMPTS
