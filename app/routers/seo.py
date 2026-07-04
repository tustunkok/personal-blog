from app.utils.markdown import render as render_markdown

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Post

router = APIRouter()


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt(request: Request):
    return "User-agent: *\nAllow: /\nDisallow:\nSitemap: /sitemap.xml\n"


@router.get("/sitemap.xml")
def sitemap_xml(request: Request, db: Session = Depends(get_db)):
    posts = (
        db.query(Post)
        .filter(Post.status == "published", Post.deleted_at.is_(None))
        .order_by(Post.publish_at.desc())
        .all()
    )

    base_url = str(request.base_url).rstrip("/")
    urls = []

    urls.append(f"  <url><loc>{base_url}/about</loc></url>")
    urls.append(f"  <url><loc>{base_url}/now</loc></url>")

    for post in posts:
        urls.append(f"  <url><loc>{base_url}/posts/{post.slug}</loc></url>")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml")


@router.get("/feed.xml")
def feed_xml(request: Request, db: Session = Depends(get_db)):
    posts = (
        db.query(Post)
        .filter(
            Post.status.in_(["published", "scheduled"]),
            Post.deleted_at.is_(None),
        )
        .order_by(func.coalesce(Post.publish_at, Post.created_at).desc())
        .limit(20)
        .all()
    )

    base_url = str(request.base_url).rstrip("/")
    items = []
    for post in posts:
        content_html = render_markdown(post.body)
        pub_date = post.publish_at if post.publish_at else post.created_at
        items.append(
            "<item>\n"
            f"  <title>{_escape_xml(post.title)}</title>\n"
            f"  <link>{base_url}/posts/{post.slug}</link>\n"
            f"  <description>{_escape_xml(post.excerpt)}</description>\n"
            f"  <pubDate>{pub_date.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>\n"
            f'  <guid isPermaLink="true">{base_url}/posts/{post.slug}</guid>\n'
            f"  <content:encoded><![CDATA[{content_html}]]></content:encoded>\n"
            "</item>"
        )

    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">\n'
        "<channel>\n"
        f"  <title>Tolga Ustunkok</title>\n"
        f"  <link>{base_url}</link>\n"
        f"  <description>Personal blog by Tolga Ustunkok</description>\n"
        f"  <language>en</language>\n"
        f"  <lastBuildDate>{_last_build_date(posts)}</lastBuildDate>\n"
        + "\n".join(items)
        + "\n</channel>\n</rss>\n"
    )
    return Response(content=rss, media_type="application/xml")


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _last_build_date(posts: list[Post]) -> str:
    if posts:
        p = posts[0]
        dt = p.publish_at if p.publish_at else p.created_at
        return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
    from datetime import datetime

    return datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
