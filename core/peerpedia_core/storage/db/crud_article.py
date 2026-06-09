"""Article CRUD operations."""
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Article


def create_article(
    session: Session,
    authors: list[str],
    status: str = "draft",
    **kwargs,
) -> Article:
    """Create a new article record."""
    a = Article(status=status, authors=authors, **kwargs)
    session.add(a)
    session.commit()
    return a


def get_article(session: Session, article_id: str) -> Article | None:
    return session.get(Article, article_id)


def list_articles(session: Session, status: str | None = None,
                  author_id: str | None = None,
                  limit: int | None = None, offset: int = 0) -> list[Article]:
    q = session.query(Article)
    if status:
        q = q.filter(Article.status == status)
    if author_id:
        q = q.filter(Article.authors.contains(author_id))
    q = q.order_by(Article.created_at.desc())
    if limit is not None:
        q = q.limit(limit).offset(offset)
    return q.all()


def count_articles(session: Session, status: str | None = None,
                   author_id: str | None = None) -> int:
    q = session.query(Article)
    if status:
        q = q.filter(Article.status == status)
    if author_id:
        q = q.filter(Article.authors.contains(author_id))
    return q.count()


def update_article_compiled(
    session: Session,
    article_id: str,
    html_format: str,
    output: str | None,
    pages: list[str] | None,
) -> Article:
    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    a.compiled_format = html_format
    a.compiled_output = output
    a.compiled_pages = pages
    session.commit()
    return a


def update_article_status(session: Session, article_id: str, new_status: str) -> Article:
    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    a.status = new_status
    session.commit()
    return a


def increment_fork_count(session: Session, article_id: str) -> Article:
    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    a.fork_count += 1
    session.commit()
    return a


def set_sink_start(session: Session, article_id: str, duration_days: int) -> Article:
    from datetime import datetime, timezone
    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    a.status = "sedimentation"
    a.sink_start = datetime.now(timezone.utc)
    a.sink_duration_days = duration_days
    session.commit()
    return a


def delete_article(session: Session, article_id: str) -> None:
    """Delete an article from the database and remove its git repository.

    Cascades to related records: reviews, bookmarks, citations, merge_proposals.
    Raises ValueError if the article does not exist.
    """
    import shutil
    from pathlib import Path

    from peerpedia_core.storage.db.models import (
        Bookmark,
        Citation,
        MergeProposal,
        Review,
    )
    from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR

    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")

    # Delete related records
    session.query(Review).filter(Review.article_id == article_id).delete()
    session.query(Bookmark).filter(Bookmark.article_id == article_id).delete()
    session.query(Citation).filter(
        (Citation.from_article_id == article_id) | (Citation.to_article_id == article_id)
    ).delete()
    session.query(MergeProposal).filter(
        (MergeProposal.fork_article_id == article_id) | (MergeProposal.target_article_id == article_id)
    ).delete()

    session.delete(a)
    session.commit()

    repo_path = Path(DEFAULT_ARTICLES_DIR) / article_id
    if repo_path.exists():
        shutil.rmtree(str(repo_path))


def extend_sink(session: Session, article_id: str, extra_days: int, max_days: int = 180) -> Article:
    """Author extends sink time. Can be called repeatedly up to max_days.

    Raises ValueError if extra_days <= 0.
    Only increments sink_extended_count when the duration actually increases.
    """
    if extra_days <= 0:
        raise ValueError(f"extra_days must be positive, got {extra_days}")
    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    old_total = a.sink_duration_days
    new_total = a.sink_duration_days + extra_days
    if new_total > max_days:
        new_total = max_days
    a.sink_duration_days = new_total
    if new_total > old_total:
        a.sink_extended_count += 1
    session.commit()
    return a
