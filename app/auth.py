import os
import secrets

from itsdangerous import URLSafeTimedSerializer

_SECRET = os.environ.get("BLOG_SESSION_SECRET", secrets.token_hex(32))
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
