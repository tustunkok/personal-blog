import hashlib
import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from app.database import Base, get_db
from app.dependencies import get_scheduler
from app.main import app
from app.models import Fingerprint


class FakeScheduler:
    def schedule_post(self, post_id, publish_at):
        pass

    def unschedule_post(self, post_id):
        pass


@pytest.fixture(autouse=True)
def clear_env():
    old = os.environ.pop("BLOG_ADMIN_PASSWORD", None)
    os.environ["BLOG_ADMIN_PASSWORD"] = "testpass"
    yield
    os.environ.pop("BLOG_ADMIN_PASSWORD", None)
    if old is not None:
        os.environ["BLOG_ADMIN_PASSWORD"] = old


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///test_analytics.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    original_get_db = get_db

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[original_get_db] = override_get_db
    app.dependency_overrides[get_scheduler] = lambda: FakeScheduler()
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()
    try:
        os.remove("test_analytics.db")
    except OSError:
        pass


def _db():
    g = app.dependency_overrides[get_db]()
    return next(g)


def _expected_hash(attrs: dict) -> str:
    raw = "|".join(f"{k}={v}" for k, v in sorted(attrs.items()))
    return hashlib.sha256(raw.encode()).hexdigest()


def test_register_fingerprint_creates_new_record(client):
    payload = {
        "screen_resolution": "1920x1080",
        "color_depth": 24,
        "timezone": "Europe/London",
        "os": "Windows",
        "browser": "Chrome",
        "browser_version": "120",
        "touch_support": False,
        "languages": "en-US,en",
        "do_not_track": False,
        "reduced_motion": False,
        "cpu_cores": 8,
        "memory_gb": 16.0,
        "connection_type": "wifi",
        "dark_mode_preferred": True,
    }

    resp = client.post("/api/analytics/fingerprint", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "fingerprint_hash" in data
    expected = _expected_hash(payload)
    assert data["fingerprint_hash"] == expected

    db = _db()
    fp = db.query(Fingerprint).filter(Fingerprint.hash == expected).first()
    assert fp is not None
    assert fp.screen_resolution == "1920x1080"
    assert fp.color_depth == 24
    assert fp.timezone == "Europe/London"
    assert fp.os == "Windows"
    assert fp.browser == "Chrome"
    db.close()


def test_register_fingerprint_returns_existing_on_identical_attrs(client):
    payload = {
        "screen_resolution": "2560x1440",
        "color_depth": 30,
        "timezone": "America/New_York",
        "os": "macOS",
        "browser": "Firefox",
        "browser_version": "121",
        "touch_support": True,
        "languages": "en-US",
        "do_not_track": True,
        "reduced_motion": True,
        "cpu_cores": 4,
        "memory_gb": 8.0,
        "connection_type": "ethernet",
        "dark_mode_preferred": False,
    }

    resp1 = client.post("/api/analytics/fingerprint", json=payload)
    assert resp1.status_code == 200

    resp2 = client.post("/api/analytics/fingerprint", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["fingerprint_hash"] == resp1.json()["fingerprint_hash"]

    db = _db()
    count = db.query(Fingerprint).count()
    assert count == 1
    db.close()


def test_record_visit_stores_page_view(client):
    resp = client.post(
        "/api/analytics/visit",
        json={
            "path": "/posts/hello-world",
            "fingerprint_hash": "abc123",
            "post_id": 42,
            "referrer": "https://google.com",
        },
        headers={
            "X-Forwarded-For": "1.2.3.4",
            "User-Agent": "TestBrowser/1.0",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "visit_id" in data

    from app.models import Visit

    db = _db()
    visit = db.query(Visit).filter(Visit.id == data["visit_id"]).first()
    assert visit is not None
    assert visit.path == "/posts/hello-world"
    assert visit.post_id == 42
    assert visit.ip == "1.2.3.4"
    assert visit.user_agent == "TestBrowser/1.0"
    assert visit.referrer == "https://google.com"
    assert visit.accept_language == "en-US,en;q=0.9"
    db.close()


def test_record_visit_without_fingerprint(client):
    resp = client.post(
        "/api/analytics/visit",
        json={"path": "/about", "post_id": None},
        headers={"X-Forwarded-For": "5.5.5.5", "User-Agent": "curl/7.0"},
    )
    assert resp.status_code == 200
    data = resp.json()

    from app.models import Visit

    db = _db()
    visit = db.query(Visit).filter(Visit.id == data["visit_id"]).first()
    assert visit is not None
    assert visit.path == "/about"
    assert visit.fingerprint_id is None
    db.close()


def test_record_visit_links_fingerprint(client):
    payload = {
        "screen_resolution": "1024x768",
        "color_depth": 16,
        "timezone": "UTC",
        "os": "Linux",
        "browser": "Opera",
        "browser_version": "100",
        "touch_support": False,
        "languages": "en",
        "do_not_track": False,
        "reduced_motion": False,
        "cpu_cores": 2,
        "memory_gb": 4.0,
        "connection_type": "wifi",
        "dark_mode_preferred": False,
    }

    fp_resp = client.post("/api/analytics/fingerprint", json=payload)
    fp_hash = fp_resp.json()["fingerprint_hash"]

    visit_resp = client.post(
        "/api/analytics/visit",
        json={
            "path": "/posts/test",
            "fingerprint_hash": fp_hash,
            "post_id": 1,
        },
        headers={"X-Forwarded-For": "10.0.0.1", "User-Agent": "Test"},
    )
    assert visit_resp.status_code == 200

    from app.models import Fingerprint, Visit

    db = _db()
    visit = db.query(Visit).filter(Visit.id == visit_resp.json()["visit_id"]).first()
    assert visit.fingerprint_id is not None

    fp = db.query(Fingerprint).filter(Fingerprint.hash == fp_hash).first()
    assert visit.fingerprint_id == fp.id
    db.close()


def test_record_heartbeat_creates_page_session(client):
    visit_resp = client.post(
        "/api/analytics/visit",
        json={"path": "/posts/hb", "post_id": 1},
        headers={"X-Forwarded-For": "1.1.1.1", "User-Agent": "hb"},
    )
    visit_id = visit_resp.json()["visit_id"]

    resp = client.post(
        "/api/analytics/heartbeat",
        json={
            "visit_id": visit_id,
            "post_id": 1,
            "scroll_depth": 0.5,
            "end_reached": False,
        },
    )
    assert resp.status_code == 200

    from app.models import PageSession

    db = _db()
    session = db.query(PageSession).filter(PageSession.visit_id == visit_id).first()
    assert session is not None
    assert session.scroll_depth == 0.5
    assert session.end_reached is False
    assert session.post_id == 1
    db.close()


def test_record_heartbeat_end_reached(client):
    visit_resp = client.post(
        "/api/analytics/visit",
        json={"path": "/posts/end", "post_id": 2},
        headers={"X-Forwarded-For": "2.2.2.2", "User-Agent": "end"},
    )
    visit_id = visit_resp.json()["visit_id"]

    resp = client.post(
        "/api/analytics/heartbeat",
        json={
            "visit_id": visit_id,
            "post_id": 2,
            "scroll_depth": 1.0,
            "end_reached": True,
        },
    )
    assert resp.status_code == 200

    from app.models import PageSession

    db = _db()
    session = db.query(PageSession).filter(PageSession.visit_id == visit_id).first()
    assert session.end_reached is True
    assert session.scroll_depth == 1.0
    db.close()


def test_record_engagement_event(client):
    visit_resp = client.post(
        "/api/analytics/visit",
        json={"path": "/posts/ev", "post_id": 1},
        headers={"X-Forwarded-For": "1.1.1.1", "User-Agent": "ev"},
    )
    visit_id = visit_resp.json()["visit_id"]

    resp = client.post(
        "/api/analytics/event",
        json={
            "visit_id": visit_id,
            "event_type": "copy",
            "post_id": 1,
            "data": {"text": "Hello World"},
        },
    )
    assert resp.status_code == 200

    from app.models import EngagementEvent

    db = _db()
    event = (
        db.query(EngagementEvent).filter(EngagementEvent.visit_id == visit_id).first()
    )
    assert event is not None
    assert event.event_type == "copy"
    assert event.post_id == 1

    assert json.loads(event.data) == {"text": "Hello World"}
    db.close()


def test_record_click_event(client):
    visit_resp = client.post(
        "/api/analytics/visit",
        json={"path": "/posts/cl", "post_id": 1},
        headers={"X-Forwarded-For": "1.1.1.1", "User-Agent": "cl"},
    )
    visit_id = visit_resp.json()["visit_id"]

    resp = client.post(
        "/api/analytics/event",
        json={
            "visit_id": visit_id,
            "event_type": "code_block_click",
            "post_id": 1,
            "data": {"lang": "python"},
        },
    )
    assert resp.status_code == 200

    from app.models import EngagementEvent

    db = _db()
    event = (
        db.query(EngagementEvent).filter(EngagementEvent.visit_id == visit_id).first()
    )
    assert event.event_type == "code_block_click"
    db.close()


def test_record_external_link_click(client):
    visit_resp = client.post(
        "/api/analytics/visit",
        json={"path": "/posts/el", "post_id": 1},
        headers={"X-Forwarded-For": "1.1.1.1", "User-Agent": "el"},
    )
    visit_id = visit_resp.json()["visit_id"]

    resp = client.post(
        "/api/analytics/event",
        json={
            "visit_id": visit_id,
            "event_type": "external_link_click",
            "post_id": 1,
            "data": {"url": "https://example.com"},
        },
    )
    assert resp.status_code == 200

    from app.models import EngagementEvent

    db = _db()
    event = (
        db.query(EngagementEvent).filter(EngagementEvent.visit_id == visit_id).first()
    )
    assert event.event_type == "external_link_click"
    db.close()


def test_scroll_depth_distribution(client):
    visit_resp = client.post(
        "/api/analytics/visit",
        json={"path": "/posts/sd", "post_id": 1},
        headers={"X-Forwarded-For": "1.1.1.1", "User-Agent": "sd"},
    )
    visit_id = visit_resp.json()["visit_id"]

    for depth in [0.1, 0.2, 0.4, 0.7, 0.9, 1.0]:
        client.post(
            "/api/analytics/heartbeat",
            json={
                "visit_id": visit_id,
                "post_id": 1,
                "scroll_depth": depth,
                "end_reached": depth >= 1.0,
            },
        )

    from app.services.analytics_service import AnalyticsService

    db = _db()
    svc = AnalyticsService(db)
    dist = svc.scroll_depth_distribution()
    db.close()

    buckets = {d["bucket"]: d["count"] for d in dist}
    assert buckets["0-25%"] == 2
    assert buckets["25-50%"] == 1
    assert buckets["50-75%"] == 1
    assert buckets["75-99%"] == 1
    assert buckets["100%"] == 1


def test_countries_breakdown(client):
    from app.models import Visit

    db = _db()
    db.add_all(
        [
            Visit(path="/", ip="1.1.1.1", country="US", city="NYC"),
            Visit(path="/", ip="2.2.2.2", country="DE", city="Berlin"),
            Visit(path="/", ip="3.3.3.3", country="US", city="LA"),
        ]
    )
    db.commit()

    from app.services.analytics_service import AnalyticsService

    svc = AnalyticsService(db)
    breakdown = svc.countries_breakdown()

    by_country = {b["country"]: b["count"] for b in breakdown}
    assert by_country["US"] == 2
    assert by_country["DE"] == 1

    cities = {}
    for b in breakdown:
        if not b.get("cities"):
            continue
        for c in b["cities"]:
            cities[c["city"]] = c["count"]
    assert cities["NYC"] == 1
    assert cities["LA"] == 1
    assert cities["Berlin"] == 1
    db.close()


def test_browser_breakdown(client):
    payloads = [
        {
            "os": "Windows",
            "browser": "Chrome",
            "screen_resolution": "1920x1080",
            "color_depth": 24,
            "timezone": "UTC",
            "browser_version": "120",
            "touch_support": False,
            "languages": "en",
            "do_not_track": False,
            "reduced_motion": False,
            "cpu_cores": 8,
            "memory_gb": 16.0,
            "connection_type": "wifi",
            "dark_mode_preferred": False,
        },
        {
            "os": "Windows",
            "browser": "Firefox",
            "screen_resolution": "2560x1440",
            "color_depth": 30,
            "timezone": "UTC",
            "browser_version": "121",
            "touch_support": True,
            "languages": "en",
            "do_not_track": True,
            "reduced_motion": True,
            "cpu_cores": 4,
            "memory_gb": 8.0,
            "connection_type": "ethernet",
            "dark_mode_preferred": False,
        },
        {
            "os": "macOS",
            "browser": "Chrome",
            "screen_resolution": "1440x900",
            "color_depth": 30,
            "timezone": "UTC",
            "browser_version": "120",
            "touch_support": False,
            "languages": "en",
            "do_not_track": False,
            "reduced_motion": False,
            "cpu_cores": 10,
            "memory_gb": 32.0,
            "connection_type": "wifi",
            "dark_mode_preferred": True,
        },
    ]

    hashes = []
    for p in payloads:
        r = client.post("/api/analytics/fingerprint", json=p)
        hashes.append(r.json()["fingerprint_hash"])

    for fp_hash in hashes:
        client.post(
            "/api/analytics/visit",
            json={"path": "/", "fingerprint_hash": fp_hash, "post_id": 1},
            headers={"X-Forwarded-For": "1.1.1.1", "User-Agent": "test"},
        )

    from app.services.analytics_service import AnalyticsService

    db = _db()
    svc = AnalyticsService(db)
    browser = svc.browser_breakdown()
    os_breakdown = svc.os_breakdown()
    db.close()

    by_browser = {b["browser"]: b["count"] for b in browser}
    assert by_browser["Chrome"] == 2
    assert by_browser["Firefox"] == 1

    by_os = {b["os"]: b["count"] for b in os_breakdown}
    assert by_os["Windows"] == 2
    assert by_os["macOS"] == 1


def test_device_breakdown(client):
    payloads = [
        {
            "os": "Windows",
            "browser": "Chrome",
            "screen_resolution": "1920x1080",
            "color_depth": 24,
            "timezone": "UTC",
            "browser_version": "120",
            "touch_support": False,
            "languages": "en",
            "do_not_track": False,
            "reduced_motion": False,
            "cpu_cores": 8,
            "memory_gb": 16.0,
            "connection_type": "wifi",
            "dark_mode_preferred": False,
        },
        {
            "os": "MacIntel",
            "browser": "Safari",
            "screen_resolution": "390x844",
            "color_depth": 24,
            "timezone": "UTC",
            "browser_version": "17",
            "touch_support": True,
            "languages": "en",
            "do_not_track": False,
            "reduced_motion": False,
            "cpu_cores": 6,
            "memory_gb": 6.0,
            "connection_type": "4g",
            "dark_mode_preferred": True,
        },
        {
            "os": "MacIntel",
            "browser": "Safari",
            "screen_resolution": "834x1194",
            "color_depth": 24,
            "timezone": "UTC",
            "browser_version": "17",
            "touch_support": True,
            "languages": "en",
            "do_not_track": False,
            "reduced_motion": False,
            "cpu_cores": 8,
            "memory_gb": 8.0,
            "connection_type": "wifi",
            "dark_mode_preferred": True,
        },
    ]

    for p in payloads:
        r = client.post("/api/analytics/fingerprint", json=p)
        fp = r.json()["fingerprint_hash"]
        client.post(
            "/api/analytics/visit",
            json={"path": "/", "fingerprint_hash": fp, "post_id": 1},
            headers={"X-Forwarded-For": "1.1.1.1", "User-Agent": "test"},
        )

    from app.services.analytics_service import AnalyticsService

    db = _db()
    svc = AnalyticsService(db)
    devices = svc.device_breakdown()
    db.close()

    by_type = {d["type"]: d["count"] for d in devices}
    assert by_type["Desktop"] == 1
    assert by_type["Mobile"] == 2


def test_engagement_breakdown(client):
    visit_resp = client.post(
        "/api/analytics/visit",
        json={"path": "/posts/ev2", "post_id": 1},
        headers={"X-Forwarded-For": "1.1.1.1", "User-Agent": "ev2"},
    )
    visit_id = visit_resp.json()["visit_id"]

    for ev_type in ["copy", "copy", "external_link_click", "code_block_click"]:
        client.post(
            "/api/analytics/event",
            json={
                "visit_id": visit_id,
                "event_type": ev_type,
                "post_id": 1,
                "data": {},
            },
        )

    from app.services.analytics_service import AnalyticsService

    db = _db()
    svc = AnalyticsService(db)
    breakdown = svc.engagement_breakdown()
    db.close()

    by_type = {e["event_type"]: e["count"] for e in breakdown}
    assert by_type["copy"] == 2
    assert by_type["external_link_click"] == 1
    assert by_type["code_block_click"] == 1


def test_top_navigation_paths(client):
    visit_resp = client.post(
        "/api/analytics/visit",
        json={"path": "/posts/nav2", "post_id": 1},
        headers={"X-Forwarded-For": "1.1.1.1", "User-Agent": "nav2"},
    )
    visit_id = visit_resp.json()["visit_id"]

    client.post(
        "/api/analytics/navigate",
        json={"visit_id": visit_id, "from_url": "/", "to_url": "/posts/nav2"},
    )
    client.post(
        "/api/analytics/navigate",
        json={"visit_id": visit_id, "from_url": "/tags", "to_url": "/posts/nav2"},
    )
    client.post(
        "/api/analytics/navigate",
        json={"visit_id": visit_id, "from_url": "/", "to_url": "/posts/nav2"},
    )

    from app.services.analytics_service import AnalyticsService

    db = _db()
    svc = AnalyticsService(db)
    paths = svc.top_navigation_paths(limit=10)
    db.close()

    by_from = {p["from_url"]: p["count"] for p in paths}
    assert by_from.get("/") == 2
    assert by_from.get("/tags") == 1


def test_record_navigation_path(client):
    visit_resp = client.post(
        "/api/analytics/visit",
        json={"path": "/posts/nav", "post_id": 1},
        headers={"X-Forwarded-For": "1.1.1.1", "User-Agent": "nav"},
    )
    visit_id = visit_resp.json()["visit_id"]

    resp = client.post(
        "/api/analytics/navigate",
        json={
            "visit_id": visit_id,
            "from_url": "/posts/prev",
            "to_url": "/posts/nav",
        },
    )
    assert resp.status_code == 200

    from app.models import NavigationPath

    db = _db()
    nav = db.query(NavigationPath).filter(NavigationPath.visit_id == visit_id).first()
    assert nav is not None
    assert nav.from_url == "/posts/prev"
    assert nav.to_url == "/posts/nav"
    db.close()


def test_lookup_ip_returns_geo_data():
    from app.utils.geoip import lookup_ip

    mock_response = json.dumps(
        {
            "status": "success",
            "countryCode": "DE",
            "city": "Berlin",
            "regionName": "Berlin",
            "isp": "Deutsche Telekom",
            "lat": 52.52,
            "lon": 13.405,
        }
    ).encode()

    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.read.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_urlopen.return_value):
        result = lookup_ip("8.8.8.8")

    assert result is not None
    assert result["country"] == "DE"
    assert result["city"] == "Berlin"
    assert result["region"] == "Berlin"
    assert result["isp"] == "Deutsche Telekom"
    assert result["latitude"] == 52.52
    assert result["longitude"] == 13.405


def test_lookup_ip_returns_none_for_localhost():
    from app.utils.geoip import lookup_ip

    assert lookup_ip("127.0.0.1") is None
    assert lookup_ip("::1") is None
    assert lookup_ip("") is None
    assert lookup_ip(None) is None


def test_record_visit_stores_geo_fields(client):
    from app.models import Visit

    resp = client.post(
        "/api/analytics/visit",
        json={"path": "/posts/geo", "post_id": 1},
        headers={"X-Forwarded-For": "1.2.3.4", "User-Agent": "Test"},
    )
    assert resp.status_code == 200

    db = _db()
    visit = db.query(Visit).filter(Visit.id == resp.json()["visit_id"]).first()
    assert visit is not None
    db.close()


def test_record_visit_with_geo_params(client):
    from app.services.analytics_service import AnalyticsService
    from app.models import Visit

    db = _db()
    svc = AnalyticsService(db)
    visit_id = svc.record_visit(
        path="/posts/geo",
        ip="1.2.3.4",
        country="US",
        city="New York",
        region="NY",
        isp="Comcast",
        latitude=40.7128,
        longitude=-74.0060,
    )

    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    assert visit.country == "US"
    assert visit.city == "New York"
    assert visit.region == "NY"
    assert visit.isp == "Comcast"
    assert visit.latitude == 40.7128
    assert visit.longitude == -74.0060
    db.close()


def test_geo_visits_for_map(client):
    from app.models import Visit

    db = _db()
    db.add_all(
        [
            Visit(
                path="/",
                ip="1.1.1.1",
                city="NYC",
                country="US",
                latitude=40.7,
                longitude=-74.0,
            ),
            Visit(
                path="/",
                ip="2.2.2.2",
                city="NYC",
                country="US",
                latitude=40.7,
                longitude=-74.0,
            ),
            Visit(
                path="/",
                ip="3.3.3.3",
                city="Berlin",
                country="DE",
                latitude=52.5,
                longitude=13.4,
            ),
        ]
    )
    db.commit()

    from app.services.analytics_service import AnalyticsService

    svc = AnalyticsService(db)
    geo = svc.geo_visits_for_map()

    by_city = {}
    for g in geo:
        by_city[g["city"]] = g["count"]
    assert by_city["NYC"] == 2
    assert by_city["Berlin"] == 1
