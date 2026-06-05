"""Shared route helpers — used by articles, feed, pool, and search routes."""

from pathlib import Path

from sqlalchemy.orm import Session

from peerpedia_api.schemas.article import AuthorInfo
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, get_commit_history


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
