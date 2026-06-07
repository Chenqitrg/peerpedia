"""Article CRUD operations."""
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Article, ArticleAuthor


def create_article(
    session: Session,
    author_ids: list[str],
    status: str = "draft",
    **kwargs,
) -> Article:
    """Create a new article record with author associations."""
    a = Article(status=status, **kwargs)
    session.add(a)
    session.flush()  # get article.id without commit
    for pos, author_id in enumerate(author_ids):
        session.add(ArticleAuthor(article_id=a.id, author_id=author_id, position=pos))
    session.commit()
    return a


def get_article(session: Session, article_id: str) -> Article | None:
    return session.get(Article, article_id)


def list_articles(session: Session, status: str | None = None,
                  author_id: str | None = None) -> list[Article]:
    q = session.query(Article)
    if status:
        q = q.filter(Article.status == status)
    if author_id:
        q = q.join(ArticleAuthor).filter(ArticleAuthor.author_id == author_id)
    return q.order_by(Article.created_at.desc()).all()


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


# ── Author associations ────────────────────────────────────────────────────


def get_article_authors(session: Session, article_id: str) -> list[str]:
    """Get ordered list of author IDs for an article."""
    rows = (
        session.query(ArticleAuthor.author_id)
        .filter(ArticleAuthor.article_id == article_id)
        .order_by(ArticleAuthor.position)
        .all()
    )
    return [r.author_id for r in rows]


def set_article_authors(session: Session, article_id: str, author_ids: list[str]) -> None:
    """Replace all author associations for an article."""
    session.query(ArticleAuthor).filter(ArticleAuthor.article_id == article_id).delete()
    for pos, author_id in enumerate(author_ids):
        session.add(ArticleAuthor(article_id=article_id, author_id=author_id, position=pos))
    session.commit()


# ── Compile cache ──────────────────────────────────────────────────────────


def get_compile_cache_path(article_id: str, commit_hash: str, fmt: str) -> str:
    """Return filesystem path for the compile cache file."""
    from pathlib import Path
    cache_dir = Path.home() / ".peerpedia" / "cache" / article_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    return str(cache_dir / f"{commit_hash}.{fmt}")


def read_compile_cache(article_id: str, commit_hash: str, fmt: str) -> str | None:
    """Read cached compile output. Returns None on cache miss."""
    from pathlib import Path
    path = Path(get_compile_cache_path(article_id, commit_hash, fmt))
    if path.exists():
        return path.read_text()
    return None


def write_compile_cache(article_id: str, commit_hash: str, fmt: str, output: str) -> None:
    """Write compile output to file cache."""
    from pathlib import Path
    path = Path(get_compile_cache_path(article_id, commit_hash, fmt))
    path.write_text(output)
