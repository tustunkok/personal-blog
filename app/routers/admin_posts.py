from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_scheduler
from app.models import Post
from app.services.post_service import InvalidTransitionError, PostService

router = APIRouter(prefix="/admin/posts")


@router.get("")
def post_list(request: Request, db: Session = Depends(get_db)):
    posts = (
        db.query(Post)
        .filter(Post.deleted_at.is_(None))
        .order_by(Post.updated_at.desc())
        .all()
    )
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
    scheduler=Depends(get_scheduler),
):
    svc = PostService(db, scheduler=scheduler)
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
    scheduler=Depends(get_scheduler),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)

    svc = PostService(db, scheduler=scheduler)
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
def publish_post(
    post_id: int, db: Session = Depends(get_db), scheduler=Depends(get_scheduler)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    svc = PostService(db, scheduler=scheduler)
    try:
        svc.publish_post(post)
    except InvalidTransitionError:
        pass
    return RedirectResponse(url="/admin/posts", status_code=302)


@router.post("/{post_id}/unpublish")
def unpublish_post(
    post_id: int, db: Session = Depends(get_db), scheduler=Depends(get_scheduler)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    svc = PostService(db, scheduler=scheduler)
    try:
        svc.unpublish_post(post)
    except InvalidTransitionError:
        pass
    return RedirectResponse(url="/admin/posts", status_code=302)


@router.post("/{post_id}/delete")
def delete_post(
    post_id: int, db: Session = Depends(get_db), scheduler=Depends(get_scheduler)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    svc = PostService(db, scheduler=scheduler)
    try:
        svc.soft_delete_post(post)
    except InvalidTransitionError:
        pass
    return RedirectResponse(url="/admin/posts", status_code=302)


@router.post("/{post_id}/restore")
def restore_post(
    post_id: int, db: Session = Depends(get_db), scheduler=Depends(get_scheduler)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    svc = PostService(db, scheduler=scheduler)
    svc.restore_post(post)
    return RedirectResponse(url="/admin/posts", status_code=302)


@router.get("/{post_id}/versions")
def version_history(post_id: int, request: Request, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    svc = PostService(db)
    versions = svc.get_versions(post)
    return request.app.state.templates.TemplateResponse(
        request,
        "admin/posts/versions.html",
        {"post": post, "versions": versions},
    )


@router.post("/{post_id}/versions/{version_id}/revert")
def revert_to_version(post_id: int, version_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    svc = PostService(db)
    try:
        svc.revert_to_version(post, version_id)
    except ValueError:
        return RedirectResponse(url=f"/admin/posts/{post_id}/versions", status_code=302)
    return RedirectResponse(url=f"/admin/posts/{post_id}/edit", status_code=302)


@router.post("/{post_id}/autosave")
def autosave_post(
    post_id: int,
    request: Request,
    title: str = Form(...),
    body: str = Form(""),
    excerpt: str = Form(""),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return PlainTextResponse("not found", status_code=404)
    svc = PostService(db)
    svc.autosave_post(post, title=title, body=body, excerpt=excerpt)
    return PlainTextResponse("ok")
