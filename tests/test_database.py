from sqlalchemy import create_engine, inspect
from app.database import Base
from app import models  # noqa: F401 — needed for Base.metadata registration


def test_all_tables_defined():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected = {
        "posts",
        "post_versions",
        "tags",
        "post_tags",
        "series",
        "series_posts",
        "visits",
        "fingerprints",
        "page_sessions",
        "engagement_events",
        "navigation_paths",
        "comments",
        "reactions",
        "shares",
        "settings",
    }
    assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"
