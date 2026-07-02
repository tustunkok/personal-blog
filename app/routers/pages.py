import markdown

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Setting

router = APIRouter()


@router.get("/about")
def about(request: Request, db: Session = Depends(get_db)):
    setting = db.query(Setting).filter(Setting.key == "about_content").first()
    content = setting.value if setting else "About page coming soon."
    content_html = markdown.markdown(content, extensions=["fenced_code"])
    return request.app.state.templates.TemplateResponse(
        request, "page.html", {"title": "About", "content_html": content_html}
    )


@router.get("/now")
def now(request: Request, db: Session = Depends(get_db)):
    setting = db.query(Setting).filter(Setting.key == "now_content").first()
    content = setting.value if setting else "Now page coming soon."
    content_html = markdown.markdown(content, extensions=["fenced_code"])
    return request.app.state.templates.TemplateResponse(
        request, "page.html", {"title": "Now", "content_html": content_html}
    )


admin_router = APIRouter(prefix="/admin/pages")


@admin_router.get("/about")
def admin_about_form(request: Request, db: Session = Depends(get_db)):
    setting = db.query(Setting).filter(Setting.key == "about_content").first()
    content = setting.value if setting else ""
    return request.app.state.templates.TemplateResponse(
        request,
        "admin/page_edit.html",
        {"page_key": "about", "title": "Edit About Page", "content": content},
    )


@admin_router.post("/about")
def admin_about_save(
    request: Request,
    content: str = Form(""),
    db: Session = Depends(get_db),
):
    setting = db.query(Setting).filter(Setting.key == "about_content").first()
    if setting:
        setting.value = content
    else:
        db.add(Setting(key="about_content", value=content))
    db.commit()
    return RedirectResponse(url="/admin/pages/about", status_code=302)


@admin_router.get("/now")
def admin_now_form(request: Request, db: Session = Depends(get_db)):
    setting = db.query(Setting).filter(Setting.key == "now_content").first()
    content = setting.value if setting else ""
    return request.app.state.templates.TemplateResponse(
        request,
        "admin/page_edit.html",
        {"page_key": "now", "title": "Edit Now Page", "content": content},
    )


@admin_router.post("/now")
def admin_now_save(
    request: Request,
    content: str = Form(""),
    db: Session = Depends(get_db),
):
    setting = db.query(Setting).filter(Setting.key == "now_content").first()
    if setting:
        setting.value = content
    else:
        db.add(Setting(key="now_content", value=content))
    db.commit()
    return RedirectResponse(url="/admin/pages/now", status_code=302)
