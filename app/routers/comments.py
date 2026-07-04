from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Comment, Fingerprint, Post
from app.services.comment_service import CommentService, RateLimitError

router = APIRouter()
public_router = APIRouter()


@public_router.get("/posts/{slug}/comments", response_class=HTMLResponse)
def get_comments(slug: str, request: Request, db: Session = Depends(get_db)):
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

    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post.id, Comment.is_approved.is_(True))
        .order_by(Comment.created_at.asc())
        .all()
    )

    return request.app.state.templates.TemplateResponse(
        request,
        "_comments.html",
        {"post": post, "comments": comments},
    )


@public_router.post("/posts/{slug}/comments")
def submit_comment(
    slug: str,
    request: Request,
    name: str | None = Form(None),
    email: str | None = Form(None),
    body: str = Form(...),
    website: str | None = Form(None),
    load_time: float | None = Form(None),
    fingerprint: str | None = Form(None),
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

    svc = CommentService(db)
    try:
        svc.submit(
            post_id=post.id,
            name=name,
            email=email,
            body=body,
            ip=ip,
            user_agent=user_agent,
            honeypot=website,
            load_time=load_time,
            fingerprint=fingerprint,
        )
    except RateLimitError:
        return HTMLResponse(status_code=429, content="Too many comments.")

    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post.id, Comment.is_approved.is_(True))
        .order_by(Comment.created_at.asc())
        .all()
    )

    return request.app.state.templates.TemplateResponse(
        request,
        "_comments.html",
        {"post": post, "comments": comments, "message": "Comment submitted!"},
    )


@router.get("/admin/comments")
def admin_comment_list(request: Request, db: Session = Depends(get_db)):
    comments = db.query(Comment).order_by(Comment.created_at.desc()).all()
    return request.app.state.templates.TemplateResponse(
        request,
        "admin/comments.html",
        {"comments": comments},
    )


@router.post("/admin/comments/{comment_id}/approve")
def admin_approve_comment(
    comment_id: int, request: Request, db: Session = Depends(get_db)
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if comment:
        comment.is_approved = True
        db.commit()
    return RedirectResponse(url="/admin/comments", status_code=302)


@router.post("/admin/comments/{comment_id}/delete")
def admin_delete_comment(
    comment_id: int, request: Request, db: Session = Depends(get_db)
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if comment:
        db.delete(comment)
        db.commit()
    return RedirectResponse(url="/admin/comments", status_code=302)


@router.post("/admin/comments/ban-fingerprint/{fp_id}")
def admin_ban_fingerprint(fp_id: int, request: Request, db: Session = Depends(get_db)):
    fp = db.query(Fingerprint).filter(Fingerprint.id == fp_id).first()
    if fp:
        fp.banned = True
        db.commit()
    return RedirectResponse(url="/admin/comments", status_code=302)
