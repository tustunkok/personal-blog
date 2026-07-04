import csv
import io
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Visit
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/admin/analytics")
def analytics_page(request: Request, db: Session = Depends(get_db)):
    svc = AnalyticsService(db)

    visits_total = svc.visits_total_count()
    visits_today = svc.visits_today_count()
    top_posts = svc.top_posts_by_visits(5)
    reactions = svc.reaction_counts()
    avg_scroll = svc.avg_scroll_depth()
    scroll_dist = svc.scroll_depth_distribution()
    visits_by_date = svc.visits_by_date(30)
    top_referrers = svc.top_referrers(10)
    comments_by_date = svc.comment_activity_by_date(30)
    new_comments = svc.new_comment_count()
    countries = svc.countries_breakdown()
    browsers = svc.browser_breakdown()
    os_data = svc.os_breakdown()
    devices = svc.device_breakdown()
    engagement = svc.engagement_breakdown()
    nav_paths = svc.top_navigation_paths(10)
    geo_visits = svc.geo_visits_for_map()

    return request.app.state.templates.TemplateResponse(
        request,
        "admin/analytics.html",
        {
            "visits_total": visits_total,
            "visits_today": visits_today,
            "top_posts": top_posts,
            "reactions": reactions,
            "avg_scroll": avg_scroll,
            "scroll_dist": scroll_dist,
            "visits_by_date": visits_by_date,
            "top_referrers": top_referrers,
            "comments_by_date": comments_by_date,
            "new_comments": new_comments,
            "countries": countries,
            "browsers": browsers,
            "os_data": os_data,
            "devices": devices,
            "engagement": engagement,
            "nav_paths": nav_paths,
            "geo_visits": geo_visits,
        },
    )


@router.get("/admin/analytics/visits.csv")
def export_visits_csv(db: Session = Depends(get_db)):
    visits = db.query(Visit).order_by(Visit.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "path", "ip", "referrer", "created_at"])
    for v in visits:
        writer.writerow([v.id, v.path, v.ip or "", v.referrer or "", str(v.created_at)])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=visits.csv"},
    )


@router.get("/admin/analytics/visits.json")
def export_visits_json(db: Session = Depends(get_db)):
    visits = db.query(Visit).order_by(Visit.created_at.desc()).all()
    data = [
        {
            "id": v.id,
            "path": v.path,
            "ip": v.ip,
            "referrer": v.referrer,
            "created_at": str(v.created_at),
        }
        for v in visits
    ]
    return Response(
        content=json.dumps(data),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=visits.json"},
    )
