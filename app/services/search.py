from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models import Post


def ensure_fts(db: Session) -> None:
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
    db.execute(text("INSERT INTO posts_fts(posts_fts) VALUES('rebuild')"))
    db.commit()


def search_posts(db: Session, query: str, limit: int = 50) -> list[Post]:
    ensure_fts(db)
    rows = db.execute(
        text(
            "SELECT rowid FROM posts_fts WHERE posts_fts MATCH :query ORDER BY rank LIMIT :limit"
        ),
        {"query": query, "limit": limit},
    ).fetchall()
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
