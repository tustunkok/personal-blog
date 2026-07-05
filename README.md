# personal-blog

A single-author blogging platform with fine-grained post lifecycle, visitor analytics, and a server-rendered UI. SQLite-backed for single-file portability.

## Quick start

```bash
uv sync
set BLOG_ADMIN_PASSWORD=yourpassword
uv run python main.py
```

Open `http://localhost:8000`. Admin at `/admin`.

## Architecture

### Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI (Starlette) |
| Templates | Jinja2, server-rendered |
| Frontend | HTMX 2.0, Tailwind CSS (CDN), highlight.js, KaTeX |
| Database | SQLite via SQLAlchemy 2.0 ORM |
| Migrations | Alembic |
| Scheduler | APScheduler (in-process BackgroundScheduler) |
| Markdown | Python-Markdown + pymdown-extensions (arithmatex) |
| Auth | itsdangerous signed sessions (single-password) |
| Admin editor | EasyMDE |

### Directory layout

```
app/
  main.py              FastAPI app factory, lifespan, middleware, homepage
  models.py            15 SQLAlchemy ORM models
  database.py          SQLite engine, session factory, get_db()
  auth.py              Password check + signed session tokens
  dependencies.py      get_scheduler() FastAPI dependency
  scheduler.py         PostScheduler (APScheduler)
  routers/
    public_posts.py    GET /posts/{slug}, featured-image, og-image
    admin_posts.py     Admin post CRUD, lifecycle, versions, autosave
    admin_analytics.py Analytics dashboard + CSV/JSON export
    admin_settings.py  Blog settings CRUD
    analytics.py       /api/analytics/* (fingerprint, visit, heartbeat, event, navigate)
    archive.py         /archive grouped by year/month
    comments.py        Public comments + admin moderation
    images.py          Admin image upload + public serving
    pages.py           /about, /now + admin editing
    reactions_shares.py Reactions + share tracking
    search.py          /search with FTS5
    seo.py             /robots.txt, /sitemap.xml, /feed.xml
    tags.py            /tags, /tags/{name}
  services/
    post_service.py    Post lifecycle: create, publish, schedule, versioning, series
    analytics_service.py Visit tracking, fingerprinting, analytics queries
    comment_service.py Bot protection (honeypot, time gate, rate limit)
    reaction_service.py Reaction add/dedup/count
    search.py          FTS5 setup + query (SQLite virtual table)
  utils/
    markdown.py        Markdown → HTML
    geoip.py           IP geolocation via ip-api.com
  templates/
    base.html          Layout shell (Tailwind, HTMX, KaTeX CDNs)
    index.html         Homepage with paginated post cards
    post.html          Single post + comments + reactions + series nav
    archive.html       Archive by year/month
    tags.html          Tag cloud
    tag.html           Posts filtered by tag
    search.html        Search results
    page.html          Generic page (/about, /now)
    _post_cards.html   HTMX partial for load-more pagination
    _comments.html     Comment list + form (HTMX)
    _reactions.html    Reaction buttons (HTMX)
    _shares.html       Share buttons
    admin/             Admin templates (dashboard, login, analytics, etc.)
  static/js/
    fingerprint.js     Browser fingerprint → /api/analytics/fingerprint
    analytics.js       Visit recording, heartbeats, scroll, engagement events
    code-blocks.js     highlight.js + copy buttons + line numbers
    autosave.js        5-minute autosave for post editor
    paste-upload.js    Image paste upload for EasyMDE
tests/                 15 pytest files (HTTP integration + service unit tests)
tools/
  gogs.py             Gogs REST API v1 client (issues, labels, PRs)
```

### Database

Single-file SQLite (`blog.db`). All blobs (featured images, uploaded images) stored inline — no external storage. Backup = copy `blog.db`.

Key tables:
- `posts` — title, slug (unique), body (markdown), status (draft | scheduled | published), featured_image (blob), publish_at, soft-delete via deleted_at
- `post_versions` — snapshot on each update (title, body, version_number)
- `tags` + `post_tags` — freeform labels, many-to-many
- `series` + `series_posts` — ordered sequence of posts with position
- `fingerprints`, `visits`, `page_sessions`, `engagement_events`, `navigation_paths` — visitor analytics
- `comments`, `reactions`, `shares` — visitor interactions
- `settings` — key-value blog config (name, tagline, author, etc.)
- `images` — uploaded image blobs

FTS5 virtual table `posts_fts` powers full-text search across title + body.

Run migrations:
```bash
uv run alembic upgrade head
```

### Post lifecycle

```
Draft ──→ Scheduled ──(auto via APScheduler)──→ Published
  ↑                                                  │
  └──────────── Unpublish ←──────────────────────────┘
```

- **Draft**: Visible only in admin. Not in RSS.
- **Scheduled**: Has a future `publish_at`. Not public, but appears in RSS. APScheduler auto-transitions to Published.
- **Published**: Publicly visible. Can be reverted to Draft ("unpublish"). Soft-delete preserves the slug.

Every update creates a `PostVersion` snapshot. Admin can view version history and revert.

### Visitor analytics

Privacy-focused, no cookies. Each visitor is fingerprinted client-side from 14 browser attributes (screen, OS, browser, timezone, etc.) and hashed with SHA-256.

- **Visit**: Recorded on page load with IP geolocation (ip-api.com)
- **Page sessions**: Heartbeat every 30s, tracks scroll depth and whether end was reached
- **Engagement events**: Copy, text selection (≥10 chars), external link clicks, code block clicks
- **Navigation paths**: Sequence of internal URLs per session

Dashboard at `/admin/analytics` with CSV/JSON export.

### Admin

Single-password auth via `BLOG_ADMIN_PASSWORD` env var. Session cookie signed with itsdangerous (30-day expiry). Admin middleware redirects unauthenticated requests to `/admin/login`.

Post editor uses EasyMDE with paste-image upload, 5-minute autosave, and version history.

### RSS

`GET /feed.xml` returns RSS 2.0 with full content (rendered HTML) of the 20 most recent Published + Scheduled posts. Scheduled posts appear in RSS but not on the public site. Math is shipped as raw LaTeX (no KaTeX JS in feed).

### Testing

```bash
uv run pytest
```

Each test module uses a separate SQLite file, torn down after the run. `TestClient` (httpx) for integration tests; `FakeScheduler` stub avoids real background threads.
