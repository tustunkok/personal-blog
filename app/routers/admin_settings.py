from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Setting

router = APIRouter()

SETTING_KEYS = [
    "blog_name",
    "blog_tagline",
    "blog_author",
    "rss_post_count",
    "date_format",
    "bot_time_gate",
    "turnstile_site_key",
]


def _load_settings(db: Session) -> dict[str, str]:
    rows = db.query(Setting).all()
    return {r.key: r.value for r in rows}


@router.get("/admin/settings")
def settings_form(request: Request, db: Session = Depends(get_db)):
    values = _load_settings(db)
    return request.app.state.templates.TemplateResponse(
        request,
        "admin/settings.html",
        {"values": values},
    )


@router.post("/admin/settings")
def settings_save(
    request: Request,
    blog_name: str = Form(""),
    blog_tagline: str = Form(""),
    blog_author: str = Form(""),
    rss_post_count: str = Form("20"),
    date_format: str = Form("%B %d, %Y"),
    bot_time_gate: str = Form("3"),
    turnstile_site_key: str = Form(""),
    db: Session = Depends(get_db),
):
    form_data = {
        "blog_name": blog_name,
        "blog_tagline": blog_tagline,
        "blog_author": blog_author,
        "rss_post_count": rss_post_count,
        "date_format": date_format,
        "bot_time_gate": bot_time_gate,
        "turnstile_site_key": turnstile_site_key,
    }

    for key, value in form_data.items():
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(Setting(key=key, value=value))
    db.commit()

    return RedirectResponse(url="/admin/settings", status_code=302)
