from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_scheduler
from app.models import Post, Series, series_posts
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
def new_post_form(request: Request, db: Session = Depends(get_db)):
    series_list = db.query(Series).order_by(Series.title).all()
    return request.app.state.templates.TemplateResponse(
        request, "admin/posts/edit.html", {"post": None, "series_list": series_list}
    )


@router.get("/{post_id}/edit")
def edit_post_form(post_id: int, request: Request, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return RedirectResponse(url="/admin/posts", status_code=302)
    series_list = db.query(Series).order_by(Series.title).all()
    svc = PostService(db)
    current_series = svc.get_series(post)
    current_position = 1
    if current_series:
        row = db.query(series_posts).filter(series_posts.c.post_id == post.id).first()
        if row:
            current_position = row.position
    return request.app.state.templates.TemplateResponse(
        request,
        "admin/posts/edit.html",
        {
            "post": post,
            "series_list": series_list,
            "current_series": current_series,
            "current_position": current_position,
        },
    )


@router.post("")
def create_post(
    request: Request,
    title: str = Form(...),
    body: str = Form(""),
    excerpt: str = Form(""),
    slug: str = Form(""),
    publish_at: str = Form(""),
    tags: str = Form(""),
    series_id: str = Form(""),
    series_position: str = Form(""),
    new_series: str = Form(""),
    featured_image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    scheduler=Depends(get_scheduler),
):
    svc = PostService(db, scheduler=scheduler)
    slug_override = slug.strip() if slug.strip() else None
    featured_image_bytes = (
        featured_image.file.read()
        if featured_image and featured_image.filename
        else None
    )
    post = svc.create_post(
        title=title,
        body=body,
        excerpt=excerpt,
        slug_override=slug_override,
        tags=tags,
    )
    if featured_image_bytes:
        post.featured_image = featured_image_bytes
        db.commit()
    _handle_series_form(post, db, svc, series_id, series_position, new_series)
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
    tags: str = Form(""),
    series_id: str = Form(""),
    series_position: str = Form(""),
    new_series: str = Form(""),
    featured_image: UploadFile | None = File(None),
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
        tags=tags,
    )
    if featured_image and featured_image.filename:
        post.featured_image = featured_image.file.read()
        db.commit()
    _handle_series_form(post, db, svc, series_id, series_position, new_series)
    return RedirectResponse(url="/admin/posts", status_code=302)


def _handle_series_form(
    post: Post,
    db: Session,
    svc: PostService,
    series_id: str,
    series_position: str,
    new_series: str,
):
    position = int(series_position) if series_position.strip() else 1
    if new_series.strip():
        series = db.query(Series).filter(Series.title == new_series.strip()).first()
        if not series:
            series = Series(title=new_series.strip())
            db.add(series)
            db.commit()
        svc.set_series(post, series.id, position)
    elif series_id.strip():
        svc.set_series(post, int(series_id), position)
    else:
        svc.remove_from_series(post)


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
