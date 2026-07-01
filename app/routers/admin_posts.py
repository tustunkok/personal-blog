from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Post
from app.services.post_service import InvalidTransitionError, PostService

router = APIRouter(prefix="/admin/posts")


@router.get("")
def post_list(request: Request, db: Session = Depends(get_db)):
    posts = (
        db.query(Post)
        .filter(Post.deleted_at == None)
        .order_by(Post.updated_at.desc())
        .all()
    )  # noqa: E711
    return request.app.state.templates.TemplateResponse(
        request, "admin/posts/list.html", {"posts": posts}
    )


@router.get("/new")
def new_post_form(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "admin/posts/edit.html", {"post": None}
    )


@router.get("/{post_id}/edit")
def edit_post_form(post_id: int, request: Request, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    return request.app.state.templates.TemplateResponse(
        request, "admin/posts/edit.html", {"post": post}
    )


@router.post("")
def create_post(
    request: Request,
    title: str = Form(...),
    body: str = Form(""),
    excerpt: str = Form(""),
    slug: str = Form(""),
    publish_at: str = Form(""),
    db: Session = Depends(get_db),
):
    svc = PostService(db)
    slug_override = slug.strip() if slug.strip() else None
    svc.create_post(
        title=title,
        body=body,
        excerpt=excerpt,
        slug_override=slug_override,
    )
    return RedirectResponse(url="/admin/posts", status_code=302)


@router.post("/{post_id}")
def update_post(
    post_id: int,
    request: Request,
    title: str = Form(...),
    body: str = Form(""),
    excerpt: str = Form(""),
    slug: str = Form(""),
    publish_at: str = Form(""),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)

    svc = PostService(db)
    slug_override = slug.strip() if slug.strip() else None
    pub_at = publish_at.strip() if publish_at.strip() else None
    svc.update_post(
        post,
        title=title,
        body=body,
        excerpt=excerpt,
        slug_override=slug_override,
        publish_at=pub_at,
    )
    return RedirectResponse(url="/admin/posts", status_code=302)


@router.post("/{post_id}/publish")
def publish_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    svc = PostService(db)
    try:
        svc.publish_post(post)
    except InvalidTransitionError:
        pass
    return RedirectResponse(url="/admin/posts", status_code=302)


@router.post("/{post_id}/unpublish")
def unpublish_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    svc = PostService(db)
    try:
        svc.unpublish_post(post)
    except InvalidTransitionError:
        pass
    return RedirectResponse(url="/admin/posts", status_code=302)


@router.post("/{post_id}/delete")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    svc = PostService(db)
    try:
        svc.soft_delete_post(post)
    except InvalidTransitionError:
        pass
    return RedirectResponse(url="/admin/posts", status_code=302)


@router.post("/{post_id}/restore")
def restore_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    svc = PostService(db)
    svc.restore_post(post)
    return RedirectResponse(url="/admin/posts", status_code=302)
