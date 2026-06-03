"""ORM models for PeerPedia database.

Mirrors the protocol message schemas defined in peerpedia_core.protocol.messages.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from peerpedia_core.protocol.messages import ArticleStatus
from peerpedia_core.storage.db.engine import Base, JSONList

# ── ORM Model: Article ──────────────────────────────────────────────────────

class Article(Base):
    """SQLAlchemy model for article metadata. Mirrors protocol ArticleMeta."""

    __tablename__ = "articles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    founding_authors = Column(JSONList, nullable=False, default=list)
    about_person = Column(String(300), nullable=True)
    original_works = Column(JSONList, nullable=False, default=list)
    abstract = Column(Text, nullable=False, default="")
    abstract_zh = Column(Text, nullable=True)
    categories = Column(JSONList, nullable=False, default=list)
    keywords = Column(JSONList, nullable=False, default=list)
    language = Column(String(20), nullable=False, default="en")
    status = Column(String(30), nullable=False, default=ArticleStatus.DRAFT)
    version = Column(String(20), nullable=False, default="v0.1")
    format = Column(String(20), nullable=False, default="typst")
    references = Column(JSONList, nullable=False, default=list)
    cited_by = Column(JSONList, nullable=False, default=list)
    cid = Column(String(128), nullable=True)
    pinned_by = Column(Integer, nullable=False, default=0)
    git_repo_path = Column(String(500), nullable=True)
    source_arxiv_id = Column(String(50), nullable=True)
    mirror_by = Column(String(100), nullable=True)
    # Self-review dimensions (0-5, 0 = not self-rated)
    self_originality = Column(Integer, nullable=False, default=0)
    self_rigor = Column(Integer, nullable=False, default=0)
    self_completeness = Column(Integer, nullable=False, default=0)
    self_pedagogy = Column(Integer, nullable=False, default=0)
    self_impact = Column(Integer, nullable=False, default=0)
    forked_from = Column(String(36), nullable=True)
    fork_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "founding_authors": self.founding_authors,
            "about_person": self.about_person,
            "original_works": self.original_works,
            "abstract": self.abstract,
            "abstract_zh": self.abstract_zh,
            "categories": self.categories,
            "keywords": self.keywords,
            "language": self.language,
            "status": self.status,
            "version": self.version,
            "format": self.format,
            "references": self.references,
            "cited_by": self.cited_by,
            "cid": self.cid,
            "pinned_by": self.pinned_by,
            "git_repo_path": self.git_repo_path,
            "source_arxiv_id": self.source_arxiv_id,
            "mirror_by": self.mirror_by,
            "self_originality": self.self_originality,
            "self_rigor": self.self_rigor,
            "self_completeness": self.self_completeness,
            "self_pedagogy": self.self_pedagogy,
            "self_impact": self.self_impact,
            "forked_from": self.forked_from,
            "fork_count": self.fork_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ── ORM Model: Review ───────────────────────────────────────────────────────

class Review(Base):
    """SQLAlchemy model for peer reviews. Mirrors protocol ReviewMessage."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("article_id", "reviewer_id", name="uq_article_reviewer"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    reviewer_id = Column(String(100), nullable=False)
    decision = Column(String(20), nullable=False)
    comments = Column(Text, nullable=False, default="")
    scientific_correctness = Column(Integer, nullable=False, default=0)
    clarity = Column(Integer, nullable=False, default=0)
    collaboration_request = Column(Integer, nullable=False, default=0)
    collaboration_message = Column(Text, nullable=False, default="")
    points_earned = Column(Integer, nullable=False, default=0)
    review_originality = Column(Integer, nullable=False, default=0)
    review_rigor = Column(Integer, nullable=False, default=0)
    review_completeness = Column(Integer, nullable=False, default=0)
    review_pedagogy = Column(Integer, nullable=False, default=0)
    review_impact = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "reviewer_id": self.reviewer_id,
            "decision": self.decision,
            "comments": self.comments,
            "scientific_correctness": self.scientific_correctness,
            "clarity": self.clarity,
            "collaboration_request": bool(self.collaboration_request),
            "collaboration_message": self.collaboration_message,
            "points_earned": self.points_earned,
            "review_originality": self.review_originality,
            "review_rigor": self.review_rigor,
            "review_completeness": self.review_completeness,
            "review_pedagogy": self.review_pedagogy,
            "review_impact": self.review_impact,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── ORM Model: ContributionRecord ───────────────────────────────────────────

class ContributionRecord(Base):
    """Per-commit contribution record for git blame timeline."""

    __tablename__ = "contribution_records"
    __table_args__ = (
        Index("ix_contrib_article_user", "article_id", "user_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    user_id = Column(String(100), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    commit_hash = Column(String(40), nullable=False)
    commit_message = Column(Text, nullable=False, default="")
    lines_added = Column(Integer, nullable=False, default=0)
    lines_deleted = Column(Integer, nullable=False, default=0)
    files_changed = Column(JSONList, nullable=False, default=list)
    change_type = Column(String(30), nullable=False, default="content")
    contribution_weight = Column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "commit_hash": self.commit_hash,
            "commit_message": self.commit_message,
            "lines_added": self.lines_added,
            "lines_deleted": self.lines_deleted,
            "files_changed": self.files_changed,
            "change_type": self.change_type,
            "contribution_weight": self.contribution_weight,
        }


# ── ORM Model: EditProposal ─────────────────────────────────────────────────

class EditProposal(Base):
    """Post-publication edit proposal."""

    __tablename__ = "edit_proposals"
    __table_args__ = (
        Index("ix_ep_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    proposer_id = Column(String(100), nullable=False)
    proposal_type = Column(String(20), nullable=False)
    description = Column(Text, nullable=False, default="")
    git_branch = Column(String(200), nullable=False, default="")
    diff_stat = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="pending")
    reviewer_id = Column(String(100), nullable=True)
    review_comment = Column(Text, nullable=False, default="")
    points_stake = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "proposer_id": self.proposer_id,
            "proposal_type": self.proposal_type,
            "description": self.description,
            "git_branch": self.git_branch,
            "diff_stat": self.diff_stat,
            "status": self.status,
            "reviewer_id": self.reviewer_id,
            "review_comment": self.review_comment,
            "points_stake": self.points_stake,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


# ── ORM Model: User ─────────────────────────────────────────────────────────

class User(Base):
    """SQLAlchemy model for user profiles. Mirrors protocol UserProfile."""

    __tablename__ = "users"

    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(300), nullable=False)
    affiliation = Column(String(500), nullable=True)
    expertise = Column(JSONList, nullable=False, default=list)
    bio = Column(Text, nullable=True)
    public_key = Column(Text, nullable=True)
    joined_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_active = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "affiliation": self.affiliation,
            "expertise": self.expertise,
            "bio": self.bio,
            "public_key": self.public_key,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "last_active": self.last_active.isoformat() if self.last_active else None,
        }


# ── ORM Model: Identity ─────────────────────────────────────────────────────

class Identity(Base):
    """SQLAlchemy model for verified identity bindings. Mirrors protocol Identity."""

    __tablename__ = "identities"
    __table_args__ = (
        Index("ix_identity_user_type", "user_id", "type"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(20), nullable=False)
    value = Column(String(300), nullable=False)
    verified = Column(Integer, nullable=False, default=0)
    trust_weight = Column(Integer, nullable=False, default=10)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "value": self.value,
            "verified": bool(self.verified),
            "trust_weight": self.trust_weight / 100.0,
        }


# ── ORM Model: ClickEvent ────────────────────────────────────────────────────

class ClickEvent(Base):
    """Citation click event for transition probability tracking."""

    __tablename__ = "click_events"
    __table_args__ = (
        Index("ix_click_from", "from_article_id"),
        Index("ix_click_to", "to_article_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    to_article_id = Column(String(36), ForeignKey("articles.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    node_id = Column(String(100), nullable=False)
    user_id = Column(String(100), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_article_id": self.from_article_id,
            "to_article_id": self.to_article_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "node_id": self.node_id,
            "user_id": self.user_id,
        }


# ── ORM Model: NodeInfo ──────────────────────────────────────────────────────

class NodeInfo(Base):
    """LAN peer node discovered via UDP broadcast."""

    __tablename__ = "lan_nodes"

    node_id = Column(String(100), primary_key=True)
    host = Column(String(100), nullable=False)
    port = Column(Integer, nullable=False)
    version = Column(String(20), nullable=False, default="0.2.0")
    articles_count = Column(Integer, nullable=False, default=0)
    last_seen = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_self = Column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "version": self.version,
            "articles_count": self.articles_count,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_self": bool(self.is_self),
        }


# ── ORM Model: Follow ───────────────────────────────────────────────────────

class Follow(Base):
    """Follow relationship between users."""

    __tablename__ = "follows"

    follower_id = Column(String(100), ForeignKey("users.id"), primary_key=True)
    followed_id = Column(String(100), ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "follower_id": self.follower_id,
            "followed_id": self.followed_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── ORM Model: ReviewComment ────────────────────────────────────────────────

class ReviewComment(Base):
    """Line-level comment on a git diff, referencing the Shiquge PR model.

    Comments are tied to a specific commit and file path. The line range
    (line_start, line_end) identifies which diff lines the comment is about.
    """

    __tablename__ = "review_comments"
    __table_args__ = (
        Index("ix_rc_article_commit", "article_id", "commit_hash"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    commit_hash = Column(String(40), nullable=False)
    file_path = Column(String(500), nullable=False, default="")
    line_start = Column(Integer, nullable=False)
    line_end = Column(Integer, nullable=True)
    author_id = Column(String(100), nullable=False)
    body = Column(Text, nullable=False, default="")
    suggestion = Column(Text, nullable=False, default="")
    comment_type = Column(String(20), nullable=False, default="comment")
    # "comment" | "suggestion"
    resolved = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "commit_hash": self.commit_hash,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "author_id": self.author_id,
            "body": self.body,
            "suggestion": self.suggestion,
            "comment_type": self.comment_type,
            "resolved": bool(self.resolved),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
