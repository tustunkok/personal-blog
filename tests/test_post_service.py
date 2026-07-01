from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import pytest

from app.database import Base
from app import models  # noqa: F401
from app.services.post_service import InvalidTransitionError, PostService


def _setup_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_create_draft_post():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Hello World", body="Some content", excerpt="Summary")

    assert post.title == "Hello World"
    assert post.body == "Some content"
    assert post.excerpt == "Summary"
    assert post.status == "draft"
    assert post.slug == "hello-world"
    assert post.publish_at is None
    assert post.deleted_at is None
    assert post.created_at is not None
    assert post.updated_at is not None

    db.close()


def test_update_post_fields():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(
        title="Original", body="original body", excerpt="original excerpt"
    )
    updated = svc.update_post(
        post, title="Updated Title", body="new body", excerpt="new excerpt"
    )

    assert updated.title == "Updated Title"
    assert updated.body == "new body"
    assert updated.excerpt == "new excerpt"
    assert updated.status == "draft"

    db.close()


def test_slug_auto_generated_from_title():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="A Complex Title! With Symbols?")
    assert post.slug == "a-complex-title-with-symbols"

    db.close()


def test_custom_slug_on_create():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Hello World", slug_override="my-custom-slug")
    assert post.slug == "my-custom-slug"

    db.close()


def test_update_does_not_reset_custom_slug():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Hello", slug_override="kept-slug")
    updated = svc.update_post(post, title="Changed Title")

    assert updated.slug == "kept-slug"

    db.close()


def test_slug_can_be_overridden_on_edit():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Hello World")
    assert post.slug == "hello-world"

    updated = svc.update_post(post, slug_override="better-slug")
    assert updated.slug == "better-slug"

    db.close()


def test_publish_draft():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Draft Post")
    published = svc.publish_post(post)

    assert published.status == "published"
    assert published.id == post.id

    db.close()


def test_schedule_post():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Future Post")
    scheduled = svc.schedule_post(post, "2030-01-01T12:00:00")

    assert scheduled.status == "scheduled"
    assert scheduled.publish_at is not None

    db.close()


def test_unpublish_post():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Published Post")
    svc.publish_post(post)
    unpublished = svc.unpublish_post(post)

    assert unpublished.status == "draft"

    db.close()


def test_soft_delete_post():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Delete Me")
    deleted = svc.soft_delete_post(post)

    assert deleted.deleted_at is not None

    db.close()


def test_restore_post():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Restore Me")
    svc.soft_delete_post(post)
    restored = svc.restore_post(post)

    assert restored.deleted_at is None

    db.close()


def test_cannot_publish_deleted_post():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Gone")
    svc.soft_delete_post(post)

    with pytest.raises(InvalidTransitionError):
        svc.publish_post(post)

    db.close()


def test_cannot_unpublish_non_published_post():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Draft Only")

    with pytest.raises(InvalidTransitionError):
        svc.unpublish_post(post)

    db.close()


def test_cannot_delete_already_deleted_post():
    db = _setup_db()
    svc = PostService(db)

    post = svc.create_post(title="Double Delete")
    svc.soft_delete_post(post)

    with pytest.raises(InvalidTransitionError):
        svc.soft_delete_post(post)

    db.close()
