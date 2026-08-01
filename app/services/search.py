import threading

from sqlalchemy import func, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import Post

_LOCK = threading.Lock()


def _fts_table_exists(db: Session) -> bool:
    row = db.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='posts_fts'")
    ).fetchone()
    return row is not None


def ensure_fts(db: Session, *, rebuild: bool = False) -> None:
    """Create (once) the FTS5 index and its sync triggers.

    The full ``rebuild`` is expensive and only needed when the index is created
    for a database that already holds posts, or to reconcile a corrupt index.
    After the table exists, the triggers keep it in sync on every INSERT/UPDATE/
    DELETE, so we must NOT rebuild on every request (that was a cheap DoS /
    availability bug). The rebuild here runs only when the table is freshly
    created (or ``rebuild`` is forced, e.g. at startup).
    """
    with _LOCK:
        freshly_created = not _fts_table_exists(db)
        db.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(title, body, excerpt, content='posts', content_rowid='id')"
            )
        )
        db.execute(
            text(
                "CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN "
                "INSERT INTO posts_fts(rowid, title, body, excerpt) VALUES (new.id, new.title, new.body, new.excerpt); "
                "END"
            )
        )
        db.execute(
            text(
                "CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts BEGIN "
                "INSERT INTO posts_fts(posts_fts, rowid, title, body, excerpt) VALUES ('delete', old.id, old.title, old.body, old.excerpt); "
                "END"
            )
        )
        db.execute(
            text(
                "CREATE TRIGGER IF NOT EXISTS posts_au AFTER UPDATE ON posts BEGIN "
                "INSERT INTO posts_fts(posts_fts, rowid, title, body, excerpt) VALUES ('delete', old.id, old.title, old.body, old.excerpt); "
                "INSERT INTO posts_fts(rowid, title, body, excerpt) VALUES (new.id, new.title, new.body, new.excerpt); "
                "END"
            )
        )
        if rebuild or freshly_created:
            db.execute(text("INSERT INTO posts_fts(posts_fts) VALUES('rebuild')"))
        db.commit()


def search_posts(db: Session, query: str, limit: int = 50) -> list[Post]:
    ensure_fts(db)
    try:
        rows = db.execute(
            text(
                "SELECT rowid FROM posts_fts WHERE posts_fts MATCH :query ORDER BY rank LIMIT :limit"
            ),
            {"query": query, "limit": limit},
        ).fetchall()
    except OperationalError:
        # Unbalanced quotes, stray operators, etc. are not valid FTS5 syntax.
        # Treat them as "no results" instead of crashing with a 500.
        return []
    ids = [row[0] for row in rows]
    if not ids:
        return []
    return (
        db.query(Post)
        .filter(
            Post.id.in_(ids),
            Post.status == "published",
            Post.deleted_at.is_(None),
        )
        .order_by(func.coalesce(Post.publish_at, Post.created_at).desc())
        .all()
    )
