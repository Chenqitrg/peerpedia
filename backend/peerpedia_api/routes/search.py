"""Search API route."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.schemas.article import ArticleSummary, AuthorInfo
from peerpedia_core.storage.db.models import Article
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, get_commit_history

router = APIRouter(prefix="/search", tags=["search"])


def _read_source(article_id: str) -> str:
    """Read article source content for full-text search."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            return f.read_text().lower()
    return ""


def _resolve_authors(db: Session, author_ids: list[str]) -> list[AuthorInfo]:
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


def _get_commit_hash(article_id: str) -> str:
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        return ""
    commits = get_commit_history(rp, max_count=1)
    return commits[0]["hash"][:8] if commits else ""


def _get_content_preview(article_id: str, max_chars: int = 200) -> str:
    rp = DEFAULT_ARTICLES_DIR / article_id
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            text = f.read_text()
            return text[:max_chars] + ("..." if len(text) > max_chars else "")
    return ""


def _get_commit_count(article_id: str) -> int:
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        return 0
    return len(get_commit_history(rp))


@router.get("")
def search(q: str = Query(default=""), db: Session = Depends(deps.get_db)):
    """Search articles by title and source content."""
    if not q.strip():
        return {"articles": [], "total": 0}

    articles = db.query(Article).filter(Article.status.in_(["published", "sedimentation"])).all()

    q_lower = q.lower()
    results = []
    for a in articles:
        title = (a.title or "").lower()
        source = _read_source(a.id)
        if q_lower in title or q_lower in source:
            results.append(a)

    summaries = []
    for a in results[:20]:
        summaries.append(ArticleSummary(
            id=a.id,
            title=a.title or "",
            status=a.status,
            authors=_resolve_authors(db, a.authors or []),
            content_preview=_get_content_preview(a.id),
            commit_hash=_get_commit_hash(a.id),
            fork_count=a.fork_count or 0,
            forked_from=a.forked_from,
            commit_count=_get_commit_count(a.id),
            score=a.score,
            is_bookmarked=False,
            is_own_article=False,
            created_at=a.created_at,
        ).model_dump())

    return {"articles": summaries, "total": len(summaries), "query": q}
