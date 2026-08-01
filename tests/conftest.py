"""Shared test fixtures.

The admin-login rate limiter is process-global by design (it must survive
across requests), which means state from one test leaks into the next. Reset it
before every test so tests are isolated.
"""

import pytest

from app.main import app


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    app.state.login_limiter.reset()
    yield
