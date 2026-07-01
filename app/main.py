from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app import auth
from app.routers import admin_posts

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.state.templates = templates

app.include_router(admin_posts.router)


class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/admin") and request.url.path != "/admin/login":
            session_token = request.cookies.get("blog_session")
            if not session_token or not auth.verify_session(session_token):
                return RedirectResponse(url="/admin/login", status_code=302)
        response = await call_next(request)
        return response


app.add_middleware(AdminAuthMiddleware)


@app.get("/")
def root(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/admin/login")
def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html")


@app.post("/admin/login")
def admin_login(request: Request, password: str = Form(...)):
    if auth.check_password(password):
        response = RedirectResponse(url="/admin", status_code=302)
        response.set_cookie(
            key="blog_session",
            value=auth.create_session(),
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=86400 * 30,
        )
        return response
    return templates.TemplateResponse(
        request, "admin/login.html", {"error": "Invalid password"}
    )


@app.get("/admin")
def admin_dashboard(request: Request):
    return templates.TemplateResponse(request, "admin/dashboard.html")


@app.get("/admin/logout")
def admin_logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("blog_session")
    return response
