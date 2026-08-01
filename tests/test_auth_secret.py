"""MEDIUM: session secret stability.

Previously `_SECRET` fell back to a per-process random value when
BLOG_SESSION_SECRET was unset, so sessions broke on every restart / across
multiple workers. The fix persists a generated secret next to the database so
signing/verification is stable. These tests exercise the resolver seam directly.
"""

from app import auth


def test_session_secret_honors_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("BLOG_SESSION_SECRET", "fixed-secret-value")
    monkeypatch.setenv("BLOG_DB_PATH", str(tmp_path / "data" / "blog.db"))
    assert auth.resolve_session_secret() == b"fixed-secret-value"


def test_session_secret_persisted_and_stable(monkeypatch, tmp_path):
    monkeypatch.delenv("BLOG_SESSION_SECRET", raising=False)
    monkeypatch.setenv("BLOG_DB_PATH", str(tmp_path / "data" / "blog.db"))

    first = auth.resolve_session_secret()
    assert len(first) == 32  # sufficient entropy for an HMAC signing key

    # Re-resolving (as a new process would) must return the SAME key, so
    # sessions survive a restart instead of being silently invalidated.
    second = auth.resolve_session_secret()
    assert second == first

    # And existing session tokens remain verifiable with the stored bytes.
    token = auth.create_session()
    assert auth.verify_session(token) is True


def test_sessions_still_work(monkeypatch):
    token = auth.create_session()
    assert auth.verify_session(token) is True
    assert auth.verify_session("garbage") is False
