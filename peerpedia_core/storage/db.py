"""Layer 0: SQLAlchemy database layer for PeerPedia metadata.

All article metadata, user profiles, reviews, and reputation vectors
are stored in SQLite. The git repos themselves live on the filesystem
under ~/.peerpedia/articles/.

This module provides:
- SQLAlchemy ORM models (mirroring Pydantic protocol models)
- Engine/session factory
- CRUD operations for articles
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    Engine,
)
from sqlalchemy.orm import Session, DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator


# ── JSON column type for list/dict fields ──────────────────────────────────────

class JSONList(TypeDecorator):
    """Store Python list as JSON string in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


class JSONDict(TypeDecorator):
    """Store Python dict as JSON string in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


# ── ArticleStatus (mirrors protocol enum) ──────────────────────────────────────

class ArticleStatus:
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    REVISIONS_REQUESTED = "revisions_requested"
    ACCEPTED = "accepted"
    PUBLISHED = "published"
    REJECTED = "rejected"


# ── Base + Engine ──────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


def get_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine. Uses SQLite with WAL mode for concurrency."""
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        echo=False,
    )
    # Enable WAL mode for better concurrent reads
    if "sqlite" in database_url:
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def init_db(engine: Engine) -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_session(engine: Engine) -> Session:
    """Create a new session bound to the given engine."""
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


# ── ORM Model: Article ────────────────────────────────────────────────────────

class Article(Base):
    """SQLAlchemy model for article metadata. Mirrors protocol ArticleMeta."""

    __tablename__ = "articles"

    # Primary
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    founding_authors = Column(JSONList, nullable=False, default=list)

    # Metadata
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

    # References
    references = Column(JSONList, nullable=False, default=list)
    cited_by = Column(JSONList, nullable=False, default=list)

    # Content addressing
    cid = Column(String(128), nullable=True)
    pinned_by = Column(Integer, nullable=False, default=0)

    # Git
    git_repo_path = Column(String(500), nullable=True)

    # Mirror/import
    source_arxiv_id = Column(String(50), nullable=True)   # e.g. "2301.00001"
    mirror_by = Column(String(100), nullable=True)          # user_id of importer

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to a dict suitable for JSON serialization / template rendering."""
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ── ORM Model: Review ──────────────────────────────────────────────────────────

class Review(Base):
    """SQLAlchemy model for peer reviews. Mirrors protocol ReviewMessage."""

    __tablename__ = "reviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    reviewer_id = Column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("article_id", "reviewer_id", name="uq_article_reviewer"),
    )
    decision = Column(String(20), nullable=False)  # accept | revise | reject
    comments = Column(Text, nullable=False, default="")
    scientific_correctness = Column(Integer, nullable=False, default=0)  # 1-5
    clarity = Column(Integer, nullable=False, default=0)  # 1-5
    collaboration_request = Column(Integer, nullable=False, default=0)  # SQLite bool
    collaboration_message = Column(Text, nullable=False, default="")
    points_earned = Column(Integer, nullable=False, default=0)
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── ORM Model: ContributionRecord ──────────────────────────────────────────────

class ContributionRecord(Base):
    """Per-commit contribution record for git blame timeline."""

    __tablename__ = "contribution_records"

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
    # "new_theorem" | "proof_fix" | "content" | "prose" | "format"
    contribution_weight = Column(Integer, nullable=False, default=0)
    # Scaled integer: weight * 100 to avoid floating point in DB

    __table_args__ = (
        Index("ix_contrib_article_user", "article_id", "user_id"),
    )

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


# ── ORM Model: EditProposal ───────────────────────────────────────────────────

class EditProposal(Base):
    """Post-publication edit proposal."""

    __tablename__ = "edit_proposals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    proposer_id = Column(String(100), nullable=False)
    proposal_type = Column(String(20), nullable=False)
    # "minor" | "medium" | "major"
    description = Column(Text, nullable=False, default="")
    git_branch = Column(String(200), nullable=False, default="")
    diff_stat = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default="pending")
    # "pending" | "approved" | "rejected" | "auto_approved"
    reviewer_id = Column(String(100), nullable=True)
    review_comment = Column(Text, nullable=False, default="")
    points_stake = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_ep_status", "status"),
    )

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


# ── CRUD Operations ────────────────────────────────────────────────────────────

def create_article(
    session: Session,
    *,
    id: Optional[str] = None,
    title: str,
    founding_authors: list[str],
    abstract: str,
    git_repo_path: str,
    about_person: Optional[str] = None,
    original_works: Optional[list[dict]] = None,
    abstract_zh: Optional[str] = None,
    categories: Optional[list[str]] = None,
    keywords: Optional[list[str]] = None,
    language: str = "en",
    format: str = "typst",
) -> Article:
    """Create a new article record in the database."""
    article = Article(
        id=id or str(uuid.uuid4()),
        title=title,
        founding_authors=founding_authors,
        about_person=about_person,
        original_works=original_works or [],
        abstract=abstract,
        abstract_zh=abstract_zh,
        categories=categories or [],
        keywords=keywords or [],
        language=language,
        status=ArticleStatus.DRAFT,
        version="v0.1",
        format=format,
        git_repo_path=git_repo_path,
    )
    session.add(article)
    return article


def get_article(session: Session, article_id: str) -> Optional[Article]:
    """Get an article by ID, or None."""
    return session.query(Article).filter(Article.id == article_id).first()


def list_articles(
    session: Session,
    *,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Article]:
    """List articles, most recent first. Optionally filter by status."""
    q = session.query(Article).order_by(Article.created_at.desc())
    if status:
        q = q.filter(Article.status == status)
    return q.offset(offset).limit(limit).all()


def update_article_status(
    session: Session, article_id: str, new_status: str
) -> Optional[Article]:
    """Update an article's status."""
    article = get_article(session, article_id)
    if article:
        article.status = new_status
        article.updated_at = datetime.now(timezone.utc)
    return article


def update_article_cid(
    session: Session, article_id: str, cid: str
) -> Optional[Article]:
    """Update an article's CID after publishing."""
    article = get_article(session, article_id)
    if article:
        article.cid = cid
        article.updated_at = datetime.now(timezone.utc)
    return article


# ── Review CRUD ────────────────────────────────────────────────────────────────

def create_review(
    session: Session,
    *,
    article_id: str,
    reviewer_id: str,
    decision: str,
    comments: str,
    scientific_correctness: int = 0,
    clarity: int = 0,
    collaboration_request: bool = False,
    collaboration_message: str = "",
    points_earned: int = 0,
) -> Review:
    """Create a new review record."""
    review = Review(
        id=str(uuid.uuid4()),
        article_id=article_id,
        reviewer_id=reviewer_id,
        decision=decision,
        comments=comments,
        scientific_correctness=scientific_correctness,
        clarity=clarity,
        collaboration_request=1 if collaboration_request else 0,
        collaboration_message=collaboration_message,
        points_earned=points_earned,
    )
    session.add(review)
    return review


def get_review(session: Session, review_id: str) -> Optional[Review]:
    """Get a review by ID."""
    return session.query(Review).filter(Review.id == review_id).first()


def get_reviews_for_article(session: Session, article_id: str) -> list[Review]:
    """Get all reviews for an article, oldest first."""
    return (
        session.query(Review)
        .filter(Review.article_id == article_id)
        .order_by(Review.created_at.asc())
        .all()
    )


# ── ContributionRecord CRUD ────────────────────────────────────────────────────

def create_contribution_record(
    session: Session,
    *,
    article_id: str,
    user_id: str,
    commit_hash: str,
    commit_message: str = "",
    lines_added: int = 0,
    lines_deleted: int = 0,
    files_changed: Optional[list[str]] = None,
    change_type: str = "content",
    contribution_weight: int = 0,
) -> ContributionRecord:
    """Create a contribution record."""
    record = ContributionRecord(
        id=str(uuid.uuid4()),
        article_id=article_id,
        user_id=user_id,
        commit_hash=commit_hash,
        commit_message=commit_message,
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        files_changed=files_changed or [],
        change_type=change_type,
        contribution_weight=contribution_weight,
    )
    session.add(record)
    return record


def get_contribution_records(
    session: Session,
    article_id: str,
) -> list[ContributionRecord]:
    """Get all contribution records for an article, oldest first."""
    return (
        session.query(ContributionRecord)
        .filter(ContributionRecord.article_id == article_id)
        .order_by(ContributionRecord.timestamp.asc())
        .all()
    )


def get_user_contribution_total(
    session: Session,
    article_id: str,
    user_id: str,
) -> int:
    """Get total contribution weight for a user on an article."""
    result = session.query(
        func.sum(ContributionRecord.contribution_weight)
    ).filter(
        ContributionRecord.article_id == article_id,
        ContributionRecord.user_id == user_id,
    ).scalar()
    return result or 0


# ── EditProposal CRUD ──────────────────────────────────────────────────────────

def create_edit_proposal(
    session: Session,
    *,
    article_id: str,
    proposer_id: str,
    proposal_type: str,
    description: str = "",
    git_branch: str = "",
    diff_stat: str = "",
    points_stake: int = 0,
) -> EditProposal:
    """Create an edit proposal record."""
    proposal = EditProposal(
        id=str(uuid.uuid4()),
        article_id=article_id,
        proposer_id=proposer_id,
        proposal_type=proposal_type,
        description=description,
        git_branch=git_branch,
        diff_stat=diff_stat,
        status="pending",
        points_stake=points_stake,
    )
    session.add(proposal)
    return proposal


def get_edit_proposal(session: Session, proposal_id: str) -> Optional[EditProposal]:
    """Get an edit proposal by ID."""
    return session.query(EditProposal).filter(EditProposal.id == proposal_id).first()


def get_edit_proposals_for_article(
    session: Session,
    article_id: str,
    *,
    status: Optional[str] = None,
) -> list[EditProposal]:
    """Get all edit proposals for an article, newest first."""
    q = (
        session.query(EditProposal)
        .filter(EditProposal.article_id == article_id)
        .order_by(EditProposal.created_at.desc())
    )
    if status:
        q = q.filter(EditProposal.status == status)
    return q.all()


def update_edit_proposal_status(
    session: Session,
    proposal_id: str,
    new_status: str,
    *,
    reviewer_id: Optional[str] = None,
    review_comment: str = "",
) -> Optional[EditProposal]:
    """Update an edit proposal's status."""
    proposal = get_edit_proposal(session, proposal_id)
    if proposal:
        proposal.status = new_status
        proposal.resolved_at = datetime.now(timezone.utc)
        if reviewer_id:
            proposal.reviewer_id = reviewer_id
        if review_comment:
            proposal.review_comment = review_comment
    return proposal


def update_article_founding_authors(
    session: Session,
    article_id: str,
    new_author_id: str,
) -> Optional[Article]:
    """Add a new author to the article's founding_authors list (co-author join)."""
    article = get_article(session, article_id)
    if article:
        authors = list(article.founding_authors)
        if new_author_id not in authors:
            authors.append(new_author_id)
            article.founding_authors = authors
            article.updated_at = datetime.now(timezone.utc)
    return article


def update_article_version(
    session: Session,
    article_id: str,
    new_version: str,
) -> Optional[Article]:
    """Set the article version string to the given value."""
    article = get_article(session, article_id)
    if article:
        article.version = new_version
        article.updated_at = datetime.now(timezone.utc)
    return article
