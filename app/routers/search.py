from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.search import search_posts

router = APIRouter()


@router.get("/search")
def search(
    request: Request, q: str = Query("", min_length=1), db: Session = Depends(get_db)
):
    posts = search_posts(db, q)
    return request.app.state.templates.TemplateResponse(
        request, "search.html", {"posts": posts, "query": q}
    )
