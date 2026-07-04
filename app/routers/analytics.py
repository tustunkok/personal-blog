from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.analytics_service import AnalyticsService
from app.utils.geoip import lookup_ip_async

router = APIRouter(prefix="/api/analytics")


@router.post("/fingerprint")
async def register_fingerprint(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    attrs = {}
    for field in [
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
    ]:
        if field in body:
            attrs[field] = body[field]

    svc = AnalyticsService(db)
    fp_hash = svc.register_fingerprint(attrs)
    return {"fingerprint_hash": fp_hash}


@router.post("/visit")
async def record_visit(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    svc = AnalyticsService(db)

    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
        request.client.host if request.client else None
    )

    geo = await lookup_ip_async(ip) if ip else None

    visit_id = svc.record_visit(
        path=body.get("path", "/"),
        fingerprint_hash=body.get("fingerprint_hash"),
        post_id=body.get("post_id"),
        ip=ip,
        user_agent=request.headers.get("User-Agent"),
        referrer=body.get("referrer"),
        accept_language=request.headers.get("Accept-Language"),
        country=geo.get("country") if geo else None,
        city=geo.get("city") if geo else None,
        region=geo.get("region") if geo else None,
        isp=geo.get("isp") if geo else None,
        latitude=geo.get("latitude") if geo else None,
        longitude=geo.get("longitude") if geo else None,
    )
    return {"visit_id": visit_id}


@router.post("/heartbeat")
async def record_heartbeat(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    svc = AnalyticsService(db)
    svc.record_heartbeat(
        visit_id=body.get("visit_id"),
        post_id=body.get("post_id"),
        scroll_depth=body.get("scroll_depth"),
        end_reached=body.get("end_reached", False),
    )
    return {"ok": True}


@router.post("/event")
async def record_event(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    svc = AnalyticsService(db)
    svc.record_event(
        visit_id=body.get("visit_id"),
        event_type=body.get("event_type", ""),
        post_id=body.get("post_id"),
        data=body.get("data"),
    )
    return {"ok": True}


@router.post("/navigate")
async def record_navigation(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    svc = AnalyticsService(db)
    svc.record_navigation(
        visit_id=body.get("visit_id"),
        from_url=body.get("from_url"),
        to_url=body.get("to_url", "/"),
    )
    return {"ok": True}
