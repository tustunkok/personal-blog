from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Post, Tag
from sqlalchemy import func

router = APIRouter()


@router.get("/tags")
def tag_list(request: Request, db: Session = Depends(get_db)):
    tags = db.query(Tag).order_by(Tag.name).all()
    return request.app.state.templates.TemplateResponse(
        request, "tags.html", {"tags": tags}
    )


@router.get("/tags/{name}")
def tag_posts(name: str, request: Request, db: Session = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.name == name).first()
    if not tag:
        return RedirectResponse(url="/tags", status_code=302)
    posts = (
        db.query(Post)
        .join(Post.tags)
        .filter(
            Tag.name == name,
            Post.status == "published",
            Post.deleted_at.is_(None),
        )
        .order_by(func.coalesce(Post.publish_at, Post.created_at).desc())
        .all()
    )
    return request.app.state.templates.TemplateResponse(
        request, "tag.html", {"tag": tag, "posts": posts}
    )
