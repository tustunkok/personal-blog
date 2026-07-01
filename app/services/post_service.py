import re
import unicodedata
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Post


def _generate_slug(title: str) -> str:
    slug = (
        unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^\w\s-]", "", slug).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:255]


class InvalidTransitionError(Exception):
    pass


class PostService:
    def __init__(self, db: Session):
        self.db = db

    def create_post(
        self,
        title: str,
        body: str = "",
        excerpt: str = "",
        slug_override: str | None = None,
        publish_at: str | None = None,
    ) -> Post:
        slug = slug_override.strip() if slug_override else _generate_slug(title)
        post = Post(
            title=title,
            slug=slug,
            body=body,
            excerpt=excerpt,
            status="draft",
            publish_at=datetime.fromisoformat(publish_at) if publish_at else None,
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def update_post(
        self,
        post: Post,
        title: str | None = None,
        body: str | None = None,
        excerpt: str | None = None,
        slug_override: str | None = None,
        publish_at: str | None = None,
    ) -> Post:
        if title is not None:
            post.title = title
        if body is not None:
            post.body = body
        if excerpt is not None:
            post.excerpt = excerpt
        if slug_override is not None:
            post.slug = slug_override.strip()
        if publish_at is not None:
            post.publish_at = datetime.fromisoformat(publish_at)

        self.db.commit()
        self.db.refresh(post)
        return post

    def publish_post(self, post: Post) -> Post:
        if post.deleted_at is not None:
            raise InvalidTransitionError("Cannot publish a soft-deleted post.")
        post.status = "published"
        self.db.commit()
        self.db.refresh(post)
        return post

    def schedule_post(self, post: Post, publish_at: str) -> Post:
        post.status = "scheduled"
        post.publish_at = datetime.fromisoformat(publish_at)
        self.db.commit()
        self.db.refresh(post)
        return post

    def unpublish_post(self, post: Post) -> Post:
        if post.status != "published":
            raise InvalidTransitionError(
                f"Cannot unpublish a post with status '{post.status}'. Only published posts can be unpublished."
            )
        post.status = "draft"
        post.publish_at = None
        self.db.commit()
        self.db.refresh(post)
        return post

    def soft_delete_post(self, post: Post) -> Post:
        if post.deleted_at is not None:
            raise InvalidTransitionError("Post is already soft-deleted.")
        post.deleted_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(post)
        return post

    def restore_post(self, post: Post) -> Post:
        post.deleted_at = None
        self.db.commit()
        self.db.refresh(post)
        return post
