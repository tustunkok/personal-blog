import hashlib
import json

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Fingerprint, NavigationPath, Visit


FINGERPRINT_FIELDS = [
    "screen_resolution",
    "color_depth",
    "timezone",
    "os",
    "browser",
    "browser_version",
    "touch_support",
    "languages",
    "do_not_track",
    "reduced_motion",
    "cpu_cores",
    "memory_gb",
    "connection_type",
    "dark_mode_preferred",
]


def _compute_fingerprint_hash(attrs: dict) -> str:
    raw = "|".join(f"{k}={attrs.get(k)}" for k in sorted(FINGERPRINT_FIELDS))
    return hashlib.sha256(raw.encode()).hexdigest()


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def register_fingerprint(self, attrs: dict) -> str:
        fp_hash = _compute_fingerprint_hash(attrs)

        existing = (
            self.db.query(Fingerprint).filter(Fingerprint.hash == fp_hash).first()
        )
        if existing:
            return fp_hash

        fingerprint = Fingerprint(
            hash=fp_hash,
            screen_resolution=attrs.get("screen_resolution"),
            color_depth=attrs.get("color_depth"),
            timezone=attrs.get("timezone"),
            os=attrs.get("os"),
            browser=attrs.get("browser"),
            browser_version=attrs.get("browser_version"),
            touch_support=attrs.get("touch_support"),
            languages=attrs.get("languages"),
            do_not_track=attrs.get("do_not_track"),
            reduced_motion=attrs.get("reduced_motion"),
            cpu_cores=attrs.get("cpu_cores"),
            memory_gb=attrs.get("memory_gb"),
            connection_type=attrs.get("connection_type"),
            dark_mode_preferred=attrs.get("dark_mode_preferred"),
        )
        self.db.add(fingerprint)
        self.db.commit()
        self.db.refresh(fingerprint)
        return fp_hash

    def record_visit(
        self,
        path: str,
        fingerprint_hash: str | None = None,
        post_id: int | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        referrer: str | None = None,
        accept_language: str | None = None,
        country: str | None = None,
        city: str | None = None,
        region: str | None = None,
        isp: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> int:
        fingerprint_id = None
        if fingerprint_hash:
            fp = (
                self.db.query(Fingerprint)
                .filter(Fingerprint.hash == fingerprint_hash)
                .first()
            )
            if fp:
                fingerprint_id = fp.id

        visit = Visit(
            fingerprint_id=fingerprint_id,
            post_id=post_id,
            path=path[:2048],
            ip=ip,
            user_agent=user_agent[:512] if user_agent else None,
            referrer=referrer[:2048] if referrer else None,
            accept_language=accept_language[:200] if accept_language else None,
            country=country,
            city=city,
            region=region,
            isp=isp,
            latitude=latitude,
            longitude=longitude,
        )
        self.db.add(visit)
        self.db.commit()
        self.db.refresh(visit)
        return visit.id

    def record_heartbeat(
        self,
        visit_id: int,
        post_id: int | None,
        scroll_depth: float | None = None,
        end_reached: bool = False,
    ) -> None:
        from app.models import PageSession
        import datetime

        page_session = PageSession(
            visit_id=visit_id,
            post_id=post_id,
            entry_time=datetime.datetime.now(datetime.UTC),
            scroll_depth=scroll_depth,
            end_reached=end_reached,
        )
        self.db.add(page_session)
        self.db.commit()

    def record_event(
        self,
        visit_id: int,
        event_type: str,
        post_id: int | None = None,
        data: dict | None = None,
    ) -> None:
        from app.models import EngagementEvent

        event = EngagementEvent(
            visit_id=visit_id,
            post_id=post_id,
            event_type=event_type[:50],
            data=json.dumps(data) if data else None,
        )
        self.db.add(event)
        self.db.commit()

    def record_navigation(
        self,
        visit_id: int,
        to_url: str,
        from_url: str | None = None,
    ) -> None:
        nav = NavigationPath(
            visit_id=visit_id,
            from_url=from_url[:2048] if from_url else None,
            to_url=to_url[:2048],
        )
        self.db.add(nav)
        self.db.commit()

    def visits_today_count(self) -> int:
        return (
            self.db.query(Visit)
            .filter(
                func.date(Visit.created_at) == func.date(func.now()),
            )
            .count()
        )

    def visits_total_count(self) -> int:
        return self.db.query(Visit).count()

    def top_posts_by_visits(self, limit: int = 5) -> list[dict]:
        from app.models import Post

        results = (
            self.db.query(Post.title, func.count(Visit.id).label("cnt"))
            .join(Visit, Visit.post_id == Post.id)
            .filter(Post.deleted_at.is_(None))
            .group_by(Post.id)
            .order_by(func.count(Visit.id).desc())
            .limit(limit)
            .all()
        )
        return [{"title": r.title, "count": r.cnt} for r in results]

    def new_comment_count(self) -> int:
        from app.models import Comment

        return (
            self.db.query(Comment)
            .filter(Comment.is_approved.is_(False), Comment.is_spam.is_(False))
            .count()
        )

    def reaction_counts(self) -> dict[str, int]:
        from app.models import Reaction

        rows = (
            self.db.query(Reaction.reaction_type, func.count(Reaction.id).label("cnt"))
            .group_by(Reaction.reaction_type)
            .all()
        )
        return {r.reaction_type: r.cnt for r in rows}

    def visits_by_date(self, days: int = 30) -> list[dict]:
        rows = (
            self.db.query(
                func.date(Visit.created_at).label("day"),
                func.count(Visit.id).label("cnt"),
            )
            .group_by(func.date(Visit.created_at))
            .order_by(func.date(Visit.created_at).desc())
            .limit(days)
            .all()
        )
        return [{"day": str(r.day), "count": r.cnt} for r in rows]

    def top_referrers(self, limit: int = 10) -> list[dict]:
        rows = (
            self.db.query(Visit.referrer, func.count(Visit.id).label("cnt"))
            .filter(Visit.referrer.isnot(None), Visit.referrer != "")
            .group_by(Visit.referrer)
            .order_by(func.count(Visit.id).desc())
            .limit(limit)
            .all()
        )
        return [{"referrer": r.referrer, "count": r.cnt} for r in rows]

    def avg_scroll_depth(self) -> float | None:
        from app.models import PageSession

        result = self.db.query(func.avg(PageSession.scroll_depth)).scalar()
        return round(float(result), 1) if result else None

    def scroll_depth_distribution(self) -> list[dict]:
        from app.models import PageSession

        buckets = [
            ("0-25%", (0, 0.25)),
            ("25-50%", (0.25, 0.50)),
            ("50-75%", (0.50, 0.75)),
            ("75-99%", (0.75, 1.0)),
            ("100%", (1.0, 1.1)),
        ]
        result = []
        for label, (lo, hi) in buckets:
            cnt = (
                self.db.query(PageSession)
                .filter(PageSession.scroll_depth >= lo, PageSession.scroll_depth < hi)
                .count()
            )
            result.append({"bucket": label, "count": cnt})
        return result

    def countries_breakdown(self) -> list[dict]:
        rows = (
            self.db.query(Visit.country, func.count(Visit.id).label("cnt"))
            .filter(Visit.country.isnot(None), Visit.country != "")
            .group_by(Visit.country)
            .order_by(func.count(Visit.id).desc())
            .all()
        )
        result = []
        for r in rows:
            cities = (
                self.db.query(Visit.city, func.count(Visit.id).label("cnt"))
                .filter(
                    Visit.country == r.country, Visit.city.isnot(None), Visit.city != ""
                )
                .group_by(Visit.city)
                .order_by(func.count(Visit.id).desc())
                .all()
            )
            cities_list = [{"city": c.city, "count": c.cnt} for c in cities]
            result.append(
                {
                    "country": r.country,
                    "count": r.cnt,
                    "cities": cities_list,
                }
            )
        return result

    def browser_breakdown(self) -> list[dict]:
        from app.models import Fingerprint

        rows = (
            self.db.query(Fingerprint.browser, func.count(Visit.id).label("cnt"))
            .join(Visit, Visit.fingerprint_id == Fingerprint.id)
            .filter(Fingerprint.browser.isnot(None))
            .group_by(Fingerprint.browser)
            .order_by(func.count(Visit.id).desc())
            .all()
        )
        return [{"browser": r.browser, "count": r.cnt} for r in rows]

    def os_breakdown(self) -> list[dict]:
        from app.models import Fingerprint

        rows = (
            self.db.query(Fingerprint.os, func.count(Visit.id).label("cnt"))
            .join(Visit, Visit.fingerprint_id == Fingerprint.id)
            .filter(Fingerprint.os.isnot(None))
            .group_by(Fingerprint.os)
            .order_by(func.count(Visit.id).desc())
            .all()
        )
        return [{"os": r.os, "count": r.cnt} for r in rows]

    def device_breakdown(self) -> list[dict]:
        from app.models import Fingerprint

        rows = (
            self.db.query(Fingerprint.touch_support, func.count(Visit.id).label("cnt"))
            .join(Visit, Visit.fingerprint_id == Fingerprint.id)
            .group_by(Fingerprint.touch_support)
            .all()
        )
        result = []
        for r in rows:
            label = "Mobile" if r.touch_support else "Desktop"
            result.append({"type": label, "count": r.cnt})
        return result

    def engagement_breakdown(self) -> list[dict]:
        from app.models import EngagementEvent

        rows = (
            self.db.query(
                EngagementEvent.event_type, func.count(EngagementEvent.id).label("cnt")
            )
            .group_by(EngagementEvent.event_type)
            .order_by(func.count(EngagementEvent.id).desc())
            .all()
        )
        return [{"event_type": r.event_type, "count": r.cnt} for r in rows]

    def top_navigation_paths(self, limit: int = 10) -> list[dict]:
        from app.models import NavigationPath

        rows = (
            self.db.query(
                NavigationPath.from_url, func.count(NavigationPath.id).label("cnt")
            )
            .filter(NavigationPath.from_url.isnot(None), NavigationPath.from_url != "")
            .group_by(NavigationPath.from_url)
            .order_by(func.count(NavigationPath.id).desc())
            .limit(limit)
            .all()
        )
        return [{"from_url": r.from_url, "count": r.cnt} for r in rows]

    def geo_visits_for_map(self) -> list[dict]:
        rows = (
            self.db.query(
                Visit.city,
                Visit.country,
                Visit.latitude,
                Visit.longitude,
                func.count(Visit.id).label("cnt"),
            )
            .filter(
                Visit.latitude.isnot(None),
                Visit.longitude.isnot(None),
                Visit.city.isnot(None),
            )
            .group_by(Visit.city, Visit.country, Visit.latitude, Visit.longitude)
            .all()
        )
        return [
            {
                "city": r.city,
                "country": r.country,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "count": r.cnt,
            }
            for r in rows
        ]

    def comment_activity_by_date(self, days: int = 30) -> list[dict]:
        from app.models import Comment

        rows = (
            self.db.query(
                func.date(Comment.created_at).label("day"),
                func.count(Comment.id).label("cnt"),
            )
            .group_by(func.date(Comment.created_at))
            .order_by(func.date(Comment.created_at).desc())
            .limit(days)
            .all()
        )
        return [{"day": str(r.day), "count": r.cnt} for r in rows]
