from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app import models  # noqa: F401
from app.models import Post


def _session_factory(engine):
    def factory():
        return Session(engine)

    return factory


def _setup_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, _session_factory(engine)


def test_catch_up_transitions_past_due_scheduled_posts():
    engine, sf = _setup_db()

    db = sf()
    post = Post(
        title="Past Due Post",
        slug="past-due-post",
        body="content",
        status="scheduled",
        publish_at=datetime.utcnow() - timedelta(hours=1),
    )
    db.add(post)
    db.commit()
    post_id = post.id
    db.close()

    assert post.status == "scheduled"

    from app.scheduler import PostScheduler

    scheduler = PostScheduler(sf)
    scheduler.start()
    scheduler.stop()

    db = sf()
    reloaded = db.query(Post).filter(Post.id == post_id).first()
    assert reloaded.status == "published"
    db.close()


def test_schedule_post_adds_job():
    engine, sf = _setup_db()

    from app.scheduler import PostScheduler

    scheduler = PostScheduler(sf)
    scheduler.start()

    publish_time = datetime.utcnow() + timedelta(days=7)
    scheduler.schedule_post(42, publish_time)

    job = scheduler._scheduler.get_job("publish_post_42")
    assert job is not None
    assert job.id == "publish_post_42"

    scheduler.stop()


def test_unschedule_post_removes_job():
    engine, sf = _setup_db()

    from app.scheduler import PostScheduler

    scheduler = PostScheduler(sf)
    scheduler.start()

    publish_time = datetime.utcnow() + timedelta(days=7)
    scheduler.schedule_post(42, publish_time)
    assert scheduler._scheduler.get_job("publish_post_42") is not None

    scheduler.unschedule_post(42)
    assert scheduler._scheduler.get_job("publish_post_42") is None

    scheduler.stop()


def test_reschedule_post_updates_run_date():
    engine, sf = _setup_db()

    from app.scheduler import PostScheduler

    scheduler = PostScheduler(sf)
    scheduler.start()

    first_time = datetime.utcnow() + timedelta(days=7)
    scheduler.schedule_post(42, first_time)

    second_time = datetime.utcnow() + timedelta(days=14)
    scheduler.schedule_post(42, second_time)

    job = scheduler._scheduler.get_job("publish_post_42")
    assert job is not None

    scheduler.stop()


def test_job_fires_and_publishes_post():
    from freezegun import freeze_time

    engine, sf = _setup_db()

    db = sf()
    post = Post(
        title="Future Post",
        slug="future-post",
        body="content",
        status="scheduled",
        publish_at=datetime.utcnow() + timedelta(hours=2),
    )
    db.add(post)
    db.commit()
    post_id = post.id
    db.close()

    from app.scheduler import PostScheduler

    scheduler = PostScheduler(sf)
    scheduler.start()

    schedule_time = datetime.utcnow() + timedelta(hours=2)
    scheduler.schedule_post(post_id, schedule_time)

    assert scheduler._scheduler.get_job(f"publish_post_{post_id}") is not None

    db = sf()
    post = db.query(Post).filter(Post.id == post_id).first()
    assert post.status == "scheduled"
    db.close()

    with freeze_time(datetime.utcnow() + timedelta(hours=3)):
        scheduler._publish_post(post_id)

    db = sf()
    reloaded = db.query(Post).filter(Post.id == post_id).first()
    assert reloaded.status == "published"
    db.close()

    scheduler.stop()


def test_scheduled_post_not_published_if_status_changed():
    engine, sf = _setup_db()

    db = sf()
    post = Post(
        title="Draft After Schedule",
        slug="draft-after-schedule",
        body="content",
        status="draft",
        publish_at=None,
    )
    db.add(post)
    db.commit()
    post_id = post.id
    db.close()

    from app.scheduler import PostScheduler

    scheduler = PostScheduler(sf)
    scheduler._publish_post(post_id)

    db = sf()
    reloaded = db.query(Post).filter(Post.id == post_id).first()
    assert reloaded.status == "draft"
    db.close()


def test_catch_up_does_not_publish_deleted_posts():
    engine, sf = _setup_db()

    db = sf()
    post = Post(
        title="Deleted Scheduled",
        slug="deleted-scheduled",
        body="content",
        status="scheduled",
        publish_at=datetime.utcnow() - timedelta(hours=1),
        deleted_at=datetime.utcnow(),
    )
    db.add(post)
    db.commit()
    post_id = post.id
    db.close()

    from app.scheduler import PostScheduler

    scheduler = PostScheduler(sf)
    scheduler.start()
    scheduler.stop()

    db = sf()
    reloaded = db.query(Post).filter(Post.id == post_id).first()
    assert reloaded.status == "scheduled"
    db.close()


class CountingScheduler:
    def __init__(self):
        self.scheduled = []
        self.unscheduled = []

    def schedule_post(self, post_id, publish_at):
        self.scheduled.append((post_id, publish_at))

    def unschedule_post(self, post_id):
        self.unscheduled.append(post_id)


def test_service_schedule_post_calls_scheduler():
    engine, sf = _setup_db()

    scheduler = CountingScheduler()
    db = sf()
    from app.services.post_service import PostService

    svc = PostService(db, scheduler=scheduler)
    post = svc.create_post(title="Future Post")
    svc.schedule_post(post, "2050-01-01T12:00:00")

    assert len(scheduler.scheduled) == 1
    assert scheduler.scheduled[0][0] == post.id
    db.close()


def test_service_unpublish_scheduled_unschedules_job():
    engine, sf = _setup_db()

    scheduler = CountingScheduler()
    db = sf()
    from app.services.post_service import PostService

    svc = PostService(db, scheduler=scheduler)
    post = svc.create_post(title="Cancel Me")
    svc.schedule_post(post, "2050-01-01T12:00:00")
    assert len(scheduler.unscheduled) == 0

    svc.unpublish_post(post)
    assert len(scheduler.unscheduled) == 1
    assert scheduler.unscheduled[0] == post.id
    db.close()


def test_service_update_publish_at_reschedules_on_scheduled_post():
    engine, sf = _setup_db()

    scheduler = CountingScheduler()
    db = sf()
    from app.services.post_service import PostService

    svc = PostService(db, scheduler=scheduler)
    post = svc.create_post(title="Reschedule Me")
    svc.schedule_post(post, "2050-01-01T12:00:00")
    scheduler.scheduled.clear()

    svc.update_post(post, publish_at="2050-06-01T12:00:00")
    assert len(scheduler.scheduled) == 1
    assert scheduler.scheduled[0][0] == post.id
    db.close()
