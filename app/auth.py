import logging
import os
import secrets
from pathlib import Path

from itsdangerous import URLSafeTimedSerializer

logger = logging.getLogger(__name__)


def resolve_session_secret() -> bytes:
    """Return the stable secret used to sign session cookies.

    Prefers the ``BLOG_SESSION_SECRET`` environment variable. When it is unset
    (a common misconfiguration), fall back to a generated secret that is
    persisted next to the SQLite database, so sessions survive restarts and stay
    consistent across multiple workers instead of being silently invalidated by
    a fresh per-process random value.
    """
    env = os.environ.get("BLOG_SESSION_SECRET")
    if env:
        return env.encode()

    db_path = os.environ.get("BLOG_DB_PATH", "blog.db")
    secret_file = Path(db_path).resolve().parent / ".session_secret"

    if secret_file.exists():
        stored = secret_file.read_bytes()
        if len(stored) == 32:
            return stored

    value = secrets.token_bytes(32)
    try:
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_bytes(value)
        os.chmod(secret_file, 0o600)
    except OSError:
        logger.warning(
            "BLOG_SESSION_SECRET is unset and could not persist a generated "
            "secret to %s; sessions will not survive a restart.",
            secret_file,
        )
        return value
    return value


_SECRET = resolve_session_secret()
_signer = URLSafeTimedSerializer(_SECRET, salt="blog-session")


def create_session() -> str:
    return _signer.dumps({"authenticated": True})


def verify_session(token: str) -> bool:
    try:
        data = _signer.loads(token, max_age=86400 * 30)
        return data.get("authenticated", False)
    except Exception:
        return False


def check_password(password: str) -> bool:
    admin_password = os.environ.get("BLOG_ADMIN_PASSWORD", "")
    if not admin_password:
        return False
    return secrets.compare_digest(password, admin_password)
