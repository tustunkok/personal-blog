import io

from PIL import Image, ImageDraw, ImageFont

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Comment, Post
from app.services.post_service import PostService
from app.services.reaction_service import ReactionService
from app.utils.markdown import render as render_markdown

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

    content_html = render_markdown(post.body)

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
            "comments_html": _render_comments(request, db, post),
            "reactions_html": _render_reactions(request, db, post),
            "shares_html": _render_shares(request, post),
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


@router.get("/posts/{slug}/og-image")
def serve_og_image(slug: str, request: Request, db: Session = Depends(get_db)):
    post = (
        db.query(Post)
        .filter(
            Post.slug == slug, Post.deleted_at.is_(None), Post.status == "published"
        )
        .first()
    )
    if not post:
        return Response(status_code=404)

    img = Image.new("RGB", (1200, 630), color=(17, 24, 39))
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("arial.ttf", 48)
        sub_font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    date_str = (
        post.publish_at.strftime("%B %d, %Y")
        if post.publish_at
        else post.created_at.strftime("%B %d, %Y")
    )

    draw.text((60, 200), post.title, fill=(255, 255, 255), font=title_font)
    draw.text((60, 380), "Tolga Ustunkok", fill=(156, 163, 175), font=sub_font)
    draw.text((60, 430), date_str, fill=(156, 163, 175), font=sub_font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")


def _render_reactions(request: Request, db: Session, post: Post) -> str:
    svc = ReactionService(db)
    counts = svc.get_counts(post.id)
    return request.app.state.templates.get_template("_reactions.html").render(
        {"request": request, "post": post, "reaction_counts": counts}
    )


def _render_shares(request: Request, post: Post) -> str:
    return request.app.state.templates.get_template("_shares.html").render(
        {"request": request, "post": post}
    )


def _render_comments(request: Request, db: Session, post: Post) -> str:
    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post.id, Comment.is_approved.is_(True))
        .order_by(Comment.created_at.asc())
        .all()
    )
    return request.app.state.templates.get_template("_comments.html").render(
        {"request": request, "post": post, "comments": comments}
    )
