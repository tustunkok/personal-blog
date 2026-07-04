from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.models import Post
from app.services.post_service import PostService


class PostScheduler:
    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._scheduler = BackgroundScheduler()

    def start(self):
        self._catch_up()
        self._scheduler.start()

    def stop(self):
        self._scheduler.shutdown(wait=False)

    def _catch_up(self):
        db = self._session_factory()
        try:
            posts = (
                db.query(Post)
                .filter(
                    Post.status == "scheduled",
                    Post.publish_at <= datetime.now(timezone.utc),
                    Post.deleted_at.is_(None),
                )
                .all()
            )
            for post in posts:
                svc = PostService(db)
                svc.publish_post(post)
        finally:
            db.close()

    def schedule_post(self, post_id: int, publish_at: datetime):
        job_id = f"publish_post_{post_id}"
        self._scheduler.add_job(
            self._publish_post,
            trigger="date",
            run_date=publish_at,
            args=[post_id],
            id=job_id,
            replace_existing=True,
        )

    def unschedule_post(self, post_id: int):
        job_id = f"publish_post_{post_id}"
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

    def _publish_post(self, post_id: int):
        db = self._session_factory()
        try:
            post = db.query(Post).filter(Post.id == post_id).first()
            if post and post.status == "scheduled":
                svc = PostService(db)
                svc.publish_post(post)
        finally:
            db.close()
