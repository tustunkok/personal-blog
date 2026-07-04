from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Post, Share
from app.services.reaction_service import ReactionService

reactions_router = APIRouter()


@reactions_router.get("/posts/{slug}/reactions", response_class=HTMLResponse)
def get_reactions(slug: str, request: Request, db: Session = Depends(get_db)):
    post = (
        db.query(Post)
        .filter(
            Post.slug == slug,
            Post.deleted_at.is_(None),
            Post.status == "published",
        )
        .first()
    )
    if not post:
        return HTMLResponse(status_code=404)

    svc = ReactionService(db)
    counts = svc.get_counts(post.id)

    return request.app.state.templates.TemplateResponse(
        request,
        "_reactions.html",
        {"post": post, "reaction_counts": counts},
    )


@reactions_router.post("/posts/{slug}/reactions")
def add_reaction(
    slug: str,
    request: Request,
    reaction_type: str = Form(...),
    fingerprint: str | None = Form(None),
    scroll_position: float | None = Form(None),
    time_to_react: float | None = Form(None),
    db: Session = Depends(get_db),
):
    post = (
        db.query(Post)
        .filter(
            Post.slug == slug,
            Post.deleted_at.is_(None),
            Post.status == "published",
        )
        .first()
    )
    if not post:
        return HTMLResponse(status_code=404)

    ip = (
        request.headers.get("X-Forwarded-For") or request.client.host
        if request.client
        else None
    )
    user_agent = request.headers.get("User-Agent")

    svc = ReactionService(db)
    svc.add_reaction(
        post_id=post.id,
        reaction_type=reaction_type,
        ip=ip,
        user_agent=user_agent,
        fingerprint=fingerprint,
        scroll_position=scroll_position,
        time_to_react=time_to_react,
    )

    counts = svc.get_counts(post.id)

    return request.app.state.templates.TemplateResponse(
        request,
        "_reactions.html",
        {"post": post, "reaction_counts": counts},
    )


shares_router = APIRouter()


@shares_router.get("/posts/{slug}/shares", response_class=HTMLResponse)
def get_shares(slug: str, request: Request, db: Session = Depends(get_db)):
    post = (
        db.query(Post)
        .filter(
            Post.slug == slug,
            Post.deleted_at.is_(None),
            Post.status == "published",
        )
        .first()
    )
    if not post:
        return HTMLResponse(status_code=404)

    return request.app.state.templates.TemplateResponse(
        request,
        "_shares.html",
        {"post": post},
    )


@shares_router.post("/posts/{slug}/shares")
def add_share(
    slug: str,
    request: Request,
    platform: str = Form(...),
    db: Session = Depends(get_db),
):
    post = (
        db.query(Post)
        .filter(
            Post.slug == slug,
            Post.deleted_at.is_(None),
            Post.status == "published",
        )
        .first()
    )
    if not post:
        return HTMLResponse(status_code=404)

    ip = (
        request.headers.get("X-Forwarded-For") or request.client.host
        if request.client
        else None
    )
    user_agent = request.headers.get("User-Agent")

    share = Share(
        post_id=post.id,
        platform=platform,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(share)
    db.commit()

    return request.app.state.templates.TemplateResponse(
        request,
        "_shares.html",
        {"post": post},
    )
