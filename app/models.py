import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base

post_tags = Table(
    "post_tags",
    Base.metadata,
    Column(
        "post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    ),
)

series_posts = Table(
    "series_posts",
    Base.metadata,
    Column(
        "series_id",
        Integer,
        ForeignKey("series.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("position", Integer, nullable=False, default=0),
)


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    body = Column(Text, nullable=False, default="")
    excerpt = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="draft", index=True)
    featured_image = Column(LargeBinary, nullable=True)
    canonical_url = Column(String(2048), nullable=True)
    publish_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )
    deleted_at = Column(DateTime, nullable=True)

    tags = relationship("Tag", secondary=post_tags, back_populates="posts")
    versions = relationship(
        "PostVersion", back_populates="post", cascade="all, delete-orphan"
    )


class PostVersion(Base):
    __tablename__ = "post_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    version_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    post = relationship("Post", back_populates="versions")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)

    posts = relationship("Post", secondary=post_tags, back_populates="tags")


class Series(Base):
    __tablename__ = "series"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)

    posts = relationship("Post", secondary=series_posts)


class Fingerprint(Base):
    __tablename__ = "fingerprints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hash = Column(String(64), unique=True, nullable=False, index=True)
    screen_resolution = Column(String(20), nullable=True)
    color_depth = Column(Integer, nullable=True)
    timezone = Column(String(50), nullable=True)
    os = Column(String(50), nullable=True)
    browser = Column(String(50), nullable=True)
    browser_version = Column(String(20), nullable=True)
    touch_support = Column(Boolean, nullable=True)
    languages = Column(String(200), nullable=True)
    do_not_track = Column(Boolean, nullable=True)
    reduced_motion = Column(Boolean, nullable=True)
    cpu_cores = Column(Integer, nullable=True)
    memory_gb = Column(Float, nullable=True)
    connection_type = Column(String(20), nullable=True)
    dark_mode_preferred = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fingerprint_id = Column(
        Integer, ForeignKey("fingerprints.id"), nullable=True, index=True
    )
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)
    path = Column(String(2048), nullable=False)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    referrer = Column(String(2048), nullable=True)
    accept_language = Column(String(200), nullable=True)
    country = Column(String(2), nullable=True)
    city = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    isp = Column(String(200), nullable=True)
    is_vpn = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class PageSession(Base):
    __tablename__ = "page_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    scroll_depth = Column(Float, nullable=True)
    end_reached = Column(Boolean, default=False)


class EngagementEvent(Base):
    __tablename__ = "engagement_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False)
    data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class NavigationPath(Base):
    __tablename__ = "navigation_paths"

    id = Column(Integer, primary_key=True, autoincrement=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=False, index=True)
    from_url = Column(String(2048), nullable=True)
    to_url = Column(String(2048), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    body = Column(Text, nullable=False)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    fingerprint_id = Column(Integer, ForeignKey("fingerprints.id"), nullable=True)
    is_approved = Column(Boolean, default=False)
    is_spam = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class Reaction(Base):
    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    reaction_type = Column(String(20), nullable=False)
    fingerprint_id = Column(Integer, ForeignKey("fingerprints.id"), nullable=True)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    scroll_position = Column(Float, nullable=True)
    time_to_react = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class Share(Base):
    __tablename__ = "shares"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    platform = Column(String(50), nullable=False)
    fingerprint_id = Column(Integer, ForeignKey("fingerprints.id"), nullable=True)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    data = Column(LargeBinary, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
