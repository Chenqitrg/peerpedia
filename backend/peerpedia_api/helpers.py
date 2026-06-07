"""Shared route helpers — used by articles, feed, pool, and search routes."""

from pathlib import Path
from typing import Any, Optional

from peerpedia_core.storage.db.crud_bookmark import is_bookmarked as _is_bookmarked
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, get_commit_history
from sqlalchemy.orm import Session

from peerpedia_api.schemas.article import ArticleSummary, AuthorInfo

# ── Author resolution ─────────────────────────────────────────────────────

def resolve_authors(db: Session, author_ids: list[str]) -> list[AuthorInfo]:
    """Resolve a list of author user IDs to AuthorInfo objects."""
    result: list[AuthorInfo] = []
    for uid in author_ids:
        u = get_user(db, uid)
        if u:
            result.append(AuthorInfo(
                id=u.id, name=u.name, anonymous_name=u.anonymous_name,
                affiliation=u.affiliation, expertise=u.expertise,
            ))
        else:
            result.append(AuthorInfo(id=uid, name="unknown"))
    return result


# ── Git metadata (combined to avoid double git-log) ──────────────────────────

def _repo_path(article_id: str) -> Path:
    return DEFAULT_ARTICLES_DIR / article_id


def get_commit_hash(article_id: str) -> str:
    """Get HEAD commit hash for an article, or empty string."""
    rp = _repo_path(article_id)
    if not (rp / ".git").is_dir():
        return ""
    commits = get_commit_history(rp, max_count=1)
    return commits[0]["hash"][:8] if commits else ""


def get_content_preview(article_id: str, max_chars: int = 200) -> str:
    """Get first ~max_chars characters of article source content."""
    rp = _repo_path(article_id)
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            text = f.read_text()
            return text[:max_chars] + ("..." if len(text) > max_chars else "")
    return ""


def get_commit_count(article_id: str) -> int:
    """Get total number of commits for an article."""
    rp = _repo_path(article_id)
    if not (rp / ".git").is_dir():
        return 0
    return len(get_commit_history(rp))


def get_git_meta(article_id: str) -> tuple[str, int]:
    """Get both HEAD hash (short) and commit count from a single git-log call."""
    rp = _repo_path(article_id)
    if not (rp / ".git").is_dir():
        return "", 0
    commits = get_commit_history(rp)
    if not commits:
        return "", 0
    return commits[0]["hash"][:8], len(commits)


# ── Article summary builder (shared across 4+ route modules) ──────────────

def build_article_summary(
    db: Session,
    a: Any,
    *,
    current_user: Any = None,
    sink_eta: Any = None,
    days_remaining: Any = None,
    sink_duration_days: Any = None,
    authors: Optional[list[AuthorInfo]] = None,
    is_bookmarked: Optional[bool] = None,
    is_own_article: Optional[bool] = None,
) -> ArticleSummary:
    """Build an ArticleSummary from a DB Article model.

    Accepts pre-computed values for sink/bookmark/author to avoid repeated
    computations when processing multiple articles in a loop.
    """
    ghash, gcount = get_git_meta(a.id)

    if authors is None:
        authors = resolve_authors(db, a.authors or [])

    if is_bookmarked is None and current_user is not None:
        uid = getattr(current_user, 'id', None)
        is_bookmarked = _is_bookmarked(db, uid, a.id) if uid else False

    if is_own_article is None and current_user is not None:
        user_id = getattr(current_user, 'id', None)
        is_own_article = user_id in (a.authors or []) if user_id else False

    return ArticleSummary(
        id=a.id,
        title=a.title or "",
        status=a.status,
        authors=authors,
        abstract=getattr(a, 'abstract', None),
        content_preview=get_content_preview(a.id),
        commit_hash=ghash,
        fork_count=a.fork_count,
        forked_from=a.forked_from,
        commit_count=gcount,
        score=a.score,
        sink_eta=sink_eta,
        days_remaining=days_remaining,
        sink_duration_days=sink_duration_days,
        is_bookmarked=bool(is_bookmarked),
        is_own_article=bool(is_own_article),
        created_at=a.created_at,
    )
