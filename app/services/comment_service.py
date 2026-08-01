import time as _time

from sqlalchemy.orm import Session

from app.models import Comment, Fingerprint


class BotRejectedError(Exception):
    pass


class RateLimitError(Exception):
    pass


TIME_GATE_SECONDS = 3
RATE_LIMIT_COUNT = 3
RATE_LIMIT_WINDOW = 300


class CommentService:
    def __init__(self, db: Session):
        self.db = db

    def submit(
        self,
        post_id: int,
        name: str | None,
        email: str | None,
        body: str,
        ip: str | None = None,
        user_agent: str | None = None,
        honeypot: str | None = None,
        load_time: float | None = None,
        fingerprint: str | None = None,
    ) -> Comment | None:
        if honeypot and honeypot.strip():
            return None

        if load_time is not None:
            elapsed = _time.time() - load_time
            if elapsed < TIME_GATE_SECONDS:
                return None

        fingerprint_id = None

        if fingerprint:
            cutoff = _time.time() - RATE_LIMIT_WINDOW
            count = (
                self.db.query(Comment)
                .filter(
                    Comment.fingerprint_hash == fingerprint,
                    Comment.created_at
                    >= _time.strftime("%Y-%m-%d %H:%M:%S", _time.gmtime(cutoff)),
                )
                .count()
            )
            if count >= RATE_LIMIT_COUNT:
                raise RateLimitError(
                    "Too many comments. Please wait before trying again."
                )

            fp = (
                self.db.query(Fingerprint)
                .filter(Fingerprint.hash == fingerprint)
                .first()
            )
            if fp and fp.banned:
                fingerprint_id = fp.id

        comment = Comment(
            post_id=post_id,
            name=name.strip() if name else None,
            email=email.strip() if email else None,
            body=body.strip(),
            ip=ip,
            user_agent=user_agent,
            fingerprint_hash=fingerprint,
            fingerprint_id=fingerprint_id,
            # New comments always start unapproved: nothing is shown publicly
            # until an admin reviews it (defense-in-depth against stored XSS).
            is_approved=False,
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment
