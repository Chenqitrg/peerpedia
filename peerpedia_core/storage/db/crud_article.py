"""CRUD operations for Article and Review models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from peerpedia_core.protocol.messages import ArticleStatus
from peerpedia_core.storage.db.models import Article, Review, ReviewComment

# ── Article CRUD ────────────────────────────────────────────────────────────────

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
    self_originality: int = 0,
    self_rigor: int = 0,
    self_completeness: int = 0,
    self_pedagogy: int = 0,
    self_impact: int = 0,
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
        self_originality=self_originality,
        self_rigor=self_rigor,
        self_completeness=self_completeness,
        self_pedagogy=self_pedagogy,
        self_impact=self_impact,
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


# ── Review CRUD ─────────────────────────────────────────────────────────────────

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


# ── ReviewComment CRUD ──────────────────────────────────────────────────────────

def create_review_comment(
    session: Session,
    *,
    article_id: str,
    commit_hash: str,
    author_id: str,
    body: str,
    file_path: str = "",
    line_start: int = 0,
    line_end: Optional[int] = None,
    comment_type: str = "comment",
    suggestion: str = "",
) -> ReviewComment:
    """Create a line-level review comment on a commit diff."""
    comment = ReviewComment(
        id=str(uuid.uuid4()),
        article_id=article_id,
        commit_hash=commit_hash,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        author_id=author_id,
        body=body,
        suggestion=suggestion,
        comment_type=comment_type,
    )
    session.add(comment)
    return comment


def get_review_comment(session: Session, comment_id: str) -> Optional[ReviewComment]:
    """Get a review comment by ID."""
    return session.query(ReviewComment).filter(ReviewComment.id == comment_id).first()


def get_comments_for_article(
    session: Session,
    article_id: str,
    *,
    commit_hash: Optional[str] = None,
    resolved: Optional[bool] = None,
) -> list[ReviewComment]:
    """Get comments for an article, optionally filtered by commit hash and resolved status."""
    q = session.query(ReviewComment).filter(ReviewComment.article_id == article_id)
    if commit_hash:
        q = q.filter(ReviewComment.commit_hash == commit_hash)
    if resolved is not None:
        q = q.filter(ReviewComment.resolved == (1 if resolved else 0))
    return q.order_by(ReviewComment.created_at.asc()).all()


def resolve_review_comment(
    session: Session, comment_id: str, resolved: bool = True
) -> Optional[ReviewComment]:
    """Mark a review comment as resolved or unresolved."""
    comment = get_review_comment(session, comment_id)
    if comment:
        comment.resolved = 1 if resolved else 0
    return comment


def apply_comment_suggestion(
    session: Session, comment_id: str
) -> Optional[ReviewComment]:
    """Mark a suggestion comment as resolved (the actual git apply happens elsewhere)."""
    comment = get_review_comment(session, comment_id)
    if comment:
        comment.resolved = 1
    return comment
