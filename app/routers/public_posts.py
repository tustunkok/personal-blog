import markdown

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Post
from app.services.post_service import PostService

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

    svc = PostService(db)
    current_series = svc.get_series(post)
    series_posts_list = (
        svc.get_series_posts(current_series.id) if current_series else []
    )
    position = 0
    prev_post = None
    next_post = None
    if current_series:
        for i, sp in enumerate(series_posts_list):
            if sp.id == post.id:
                position = i + 1
                if i > 0:
                    prev_post = series_posts_list[i - 1]
                if i < len(series_posts_list) - 1:
                    next_post = series_posts_list[i + 1]
                break

    return request.app.state.templates.TemplateResponse(
        request,
        "post.html",
        {
            "post": post,
            "content_html": content_html,
            "series": current_series,
            "series_posts": series_posts_list,
            "position": position,
            "prev_post": prev_post,
            "next_post": next_post,
        },
    )


@router.get("/posts/{slug}/featured-image")
def serve_featured_image(slug: str, db: Session = Depends(get_db)):
    post = (
        db.query(Post)
        .filter(
            Post.slug == slug, Post.deleted_at.is_(None), Post.status == "published"
        )
        .first()
    )
    if not post or not post.featured_image:
        return Response(status_code=404)
    return Response(content=post.featured_image, media_type="image/jpeg")
