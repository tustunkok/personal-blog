import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Post, PostVersion, Series, Tag, series_posts


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
    def __init__(self, db: Session, scheduler=None):
        self.db = db
        self._scheduler = scheduler

    def _sync_tags(self, post: Post, tags_str: str) -> None:
        tag_names = [t.strip() for t in tags_str.split(",") if t.strip()]
        tags = []
        for name in tag_names:
            tag = self.db.query(Tag).filter(Tag.name == name).first()
            if not tag:
                tag = Tag(name=name)
                self.db.add(tag)
                self.db.flush()
            tags.append(tag)
        post.tags = tags

    def create_post(
        self,
        title: str,
        body: str = "",
        excerpt: str = "",
        slug_override: str | None = None,
        publish_at: str | None = None,
        tags: str = "",
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
        self.db.flush()
        if tags.strip():
            self._sync_tags(post, tags)
        self.db.commit()
        self.db.refresh(post)
        return post

    def _create_version(self, post: Post) -> PostVersion:
        max_version = (
            self.db.query(PostVersion).filter(PostVersion.post_id == post.id).count()
        )
        version = PostVersion(
            post_id=post.id,
            title=post.title,
            body=post.body,
            version_number=max_version + 1,
        )
        self.db.add(version)
        self.db.flush()
        return version

    def update_post(
        self,
        post: Post,
        title: str | None = None,
        body: str | None = None,
        excerpt: str | None = None,
        slug_override: str | None = None,
        publish_at: str | None = None,
        tags: str | None = None,
    ) -> Post:
        self._create_version(post)
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
            if post.status == "scheduled" and self._scheduler:
                self._scheduler.schedule_post(post.id, post.publish_at)
        if tags is not None:
            self._sync_tags(post, tags)

        self.db.commit()
        self.db.refresh(post)
        return post

    def get_versions(self, post: Post) -> list[PostVersion]:
        return (
            self.db.query(PostVersion)
            .filter(PostVersion.post_id == post.id)
            .order_by(PostVersion.created_at.desc())
            .all()
        )

    def revert_to_version(self, post: Post, version_id: int) -> Post:
        version = (
            self.db.query(PostVersion)
            .filter(
                PostVersion.id == version_id,
                PostVersion.post_id == post.id,
            )
            .first()
        )
        if not version:
            raise ValueError("Version not found for this post.")
        self._create_version(post)
        post.title = version.title
        post.body = version.body
        self.db.commit()
        self.db.refresh(post)
        return post

    def autosave_post(
        self,
        post: Post,
        title: str | None = None,
        body: str | None = None,
        excerpt: str | None = None,
    ) -> Post:
        if title is not None:
            post.title = title
        if body is not None:
            post.body = body
        if excerpt is not None:
            post.excerpt = excerpt
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
        dt = datetime.fromisoformat(publish_at)
        post.publish_at = dt
        self.db.commit()
        self.db.refresh(post)
        if self._scheduler:
            self._scheduler.schedule_post(post.id, dt)
        return post

    def unpublish_post(self, post: Post) -> Post:
        if post.status not in ("published", "scheduled"):
            raise InvalidTransitionError(
                f"Cannot unpublish a post with status '{post.status}'. Only published or scheduled posts can be unpublished."
            )
        post.status = "draft"
        post.publish_at = None
        self.db.commit()
        self.db.refresh(post)
        if self._scheduler:
            self._scheduler.unschedule_post(post.id)
        return post

    def soft_delete_post(self, post: Post) -> Post:
        if post.deleted_at is not None:
            raise InvalidTransitionError("Post is already soft-deleted.")
        post.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(post)
        return post

    def restore_post(self, post: Post) -> Post:
        post.deleted_at = None
        self.db.commit()
        self.db.refresh(post)
        return post

    def set_series(self, post: Post, series_id: int, position: int) -> None:
        self.db.execute(series_posts.delete().where(series_posts.c.post_id == post.id))
        self.db.execute(
            series_posts.insert().values(
                series_id=series_id, post_id=post.id, position=position
            )
        )
        self.db.commit()

    def remove_from_series(self, post: Post) -> None:
        self.db.execute(series_posts.delete().where(series_posts.c.post_id == post.id))
        self.db.commit()

    def get_series(self, post: Post) -> Series | None:
        row = (
            self.db.query(series_posts)
            .filter(series_posts.c.post_id == post.id)
            .first()
        )
        if not row:
            return None
        return self.db.query(Series).filter(Series.id == row.series_id).first()

    def get_series_posts(self, series_id: int) -> list[Post]:
        return (
            self.db.query(Post)
            .join(series_posts, Post.id == series_posts.c.post_id)
            .filter(series_posts.c.series_id == series_id)
            .order_by(series_posts.c.position)
            .all()
        )
