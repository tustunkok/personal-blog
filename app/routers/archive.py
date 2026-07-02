from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Post

router = APIRouter()


@router.get("/archive")
def archive(request: Request, db: Session = Depends(get_db)):
    posts = (
        db.query(Post)
        .filter(Post.status == "published", Post.deleted_at.is_(None))
        .order_by(Post.publish_at.desc())
        .all()
    )

    archive_map: dict[str, dict[str, list[Post]]] = {}
    for post in posts:
        dt = post.publish_at or post.created_at
        year = str(dt.year)
        month = dt.strftime("%B")
        if year not in archive_map:
            archive_map[year] = {}
        if month not in archive_map[year]:
            archive_map[year][month] = []
        archive_map[year][month].append(post)

    return request.app.state.templates.TemplateResponse(
        request, "archive.html", {"archive_map": archive_map}
    )
