from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app import auth
from app import models  # noqa: F401
from app.database import SessionLocal, get_db
from app.models import Post
from app.ratelimit import (
    LOGIN_WINDOW_SECONDS,
    MAX_LOGIN_ATTEMPTS,
    SlidingWindowRateLimiter,
)
from app.routers import (
    admin_analytics,
    admin_posts,
    admin_settings,
    analytics,
    archive,
    comments,
    images,
    pages,
    public_posts,
    reactions_shares,
    search,
    seo,
    tags,
)
from app.utils.markdown import render as render_markdown
from app.scheduler import PostScheduler
from app.services.search import ensure_fts as ensure_search_fts

PAGE_SIZE = 10

# Security hardening headers applied to every response.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
    "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com "
    "https://cdn.tailwindcss.com; "
    "style-src 'self' 'unsafe-inline' "
    "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com "
    "https://cdn.tailwindcss.com; "
    "img-src 'self' data: https:; "
    "font-src 'self' data: https://cdn.jsdelivr.net; "
    "connect-src 'self' https:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

_SECURITY_HEADERS = {
    "Content-Security-Policy": _CSP,
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = PostScheduler(SessionLocal)
    scheduler.start()
    app.state.scheduler = scheduler
    # Reconcile the full-text search index once at startup (after migrations run
    # in the container), then let the per-row triggers keep it in sync.
    try:
        db = SessionLocal()
        try:
            ensure_search_fts(db, rebuild=True)
        finally:
            db.close()
    except Exception:
        pass
    yield
    scheduler.stop()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Brute-force throttle for /admin/login, keyed by client IP.
app.state.login_limiter = SlidingWindowRateLimiter(
    max_attempts=MAX_LOGIN_ATTEMPTS, window_seconds=LOGIN_WINDOW_SECONDS
)

templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["render_markdown"] = render_markdown
app.state.templates = templates

app.include_router(admin_analytics.router)
app.include_router(admin_posts.router)
app.include_router(admin_settings.router)
app.include_router(images.router)
app.include_router(images.public_router)
app.include_router(public_posts.router)
app.include_router(tags.router)
app.include_router(search.router)
app.include_router(archive.router)
app.include_router(pages.router)
app.include_router(pages.admin_router)
app.include_router(seo.router)
app.include_router(comments.router)
app.include_router(comments.public_router)
app.include_router(reactions_shares.reactions_router)
app.include_router(reactions_shares.shares_router)
app.include_router(analytics.router)


class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/admin") and request.url.path != "/admin/login":
            session_token = request.cookies.get("blog_session")
            if not session_token or not auth.verify_session(session_token):
                return RedirectResponse(url="/admin/login", status_code=302)
        response = await call_next(request)
        for name, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for name, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response


app.add_middleware(AdminAuthMiddleware)
# Security headers must be applied on every response, including static assets
# and the login page, so add after (i.e. outside of) the admin auth check.
app.add_middleware(SecurityHeadersMiddleware)


def _query_published_posts(db: Session, page: int = 1, page_size: int = PAGE_SIZE):
    total = (
        db.query(func.count(Post.id))
        .filter(Post.status == "published", Post.deleted_at.is_(None))
        .scalar()
    )
    posts = (
        db.query(Post)
        .filter(Post.status == "published", Post.deleted_at.is_(None))
        .order_by(func.coalesce(Post.publish_at, Post.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = max(1, (total + page_size - 1) // page_size)
    return posts, total, total_pages


@app.get("/")
def root(request: Request, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    posts, total, total_pages = _query_published_posts(db, page=page)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "posts": posts,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "page_size": PAGE_SIZE,
        },
    )


@app.get("/posts-page")
def posts_page(
    request: Request, page: int = Query(1, ge=1), db: Session = Depends(get_db)
):
    posts, total, total_pages = _query_published_posts(db, page=page)
    return templates.TemplateResponse(
        request,
        "_post_cards.html",
        {
            "posts": posts,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "page_size": PAGE_SIZE,
        },
    )


@app.get("/admin/login")
def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html")


def _client_ip(request: Request) -> str:
    # Trust the left-most X-Forwarded-For entry set by the reverse proxy; fall
    # back to the direct socket address.
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.post("/admin/login")
def admin_login(request: Request, password: str = Form(...)):
    limiter = request.app.state.login_limiter
    ip = _client_ip(request)
    if limiter.is_blocked(ip):
        return HTMLResponse(
            "Too many login attempts. Please wait a few minutes and try again.",
            status_code=429,
        )
    if auth.check_password(password):
        limiter.reset(ip)
        response = RedirectResponse(url="/admin", status_code=302)
        response.set_cookie(
            key="blog_session",
            value=auth.create_session(),
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
            max_age=86400 * 30,
        )
        return response
    limiter.record_failure(ip)
    return templates.TemplateResponse(
        request, "admin/login.html", {"error": "Invalid password"}
    )


@app.get("/admin")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    from app.services.analytics_service import AnalyticsService

    svc = AnalyticsService(db)
    views_today = svc.visits_today_count()
    top_posts = svc.top_posts_by_visits(5)
    new_comments = svc.new_comment_count()
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "views_today": views_today,
            "top_posts": top_posts,
            "new_comments": new_comments,
        },
    )


@app.get("/admin/logout")
def admin_logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("blog_session")
    return response
