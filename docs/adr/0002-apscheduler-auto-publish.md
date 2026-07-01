# In-process scheduler (APScheduler) for auto-publish

We chose APScheduler as the background scheduler to auto-transition Scheduled posts to Published when their datetime arrives. This runs in the same Python process as the FastAPI server rather than relying on an external mechanism (cron, systemd timer, Redis-based queue). The trade-off: in-process scheduling is simple and requires zero infrastructure, but if the server restarts, delayed jobs could be missed. Mitigation: on startup, query for any Scheduled posts whose datetime has passed and transition them immediately.

**Considered Options**: external cron/systemd timer (rejected: separate configuration, awkward to coordinate with app code), Redis + Celery (rejected: overkill for a single-writer blog, adds infrastructure), startup-only catch-up without scheduler (rejected: gaps between restarts where a post stays Scheduled past its time).
