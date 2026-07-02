import markdown

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Post

router = APIRouter()


@router.get("/posts/{slug}", response_class=HTMLResponse)
def view_post(slug: str, request: Request, db: Session = Depends(get_db)):
    post = (
        db.query(Post)
        .filter(
            Post.slug == slug, Post.deleted_at.is_(None), Post.status == "published"
        )
        .first()
    )
    if not post:
        return HTMLResponse(status_code=404)

    content_html = markdown.markdown(post.body, extensions=["fenced_code"])
    return request.app.state.templates.TemplateResponse(
        request,
        "post.html",
        {"post": post, "content_html": content_html},
    )
