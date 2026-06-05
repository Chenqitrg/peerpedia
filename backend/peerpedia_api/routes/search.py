"""Search API route."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.helpers import (
    resolve_authors,
    get_commit_hash,
    get_content_preview,
    get_commit_count,
)
from peerpedia_api.schemas.article import ArticleSummary
from peerpedia_core.storage.db.models import Article
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR

router = APIRouter(prefix="/search", tags=["search"])


def _read_source(article_id: str) -> str:
    """Read article source content for full-text search."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            return f.read_text().lower()
    return ""


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
            authors=resolve_authors(db, a.authors or []),
            content_preview=get_content_preview(a.id),
            commit_hash=get_commit_hash(a.id),
            fork_count=a.fork_count or 0,
            forked_from=a.forked_from,
            commit_count=get_commit_count(a.id),
            score=a.score,
            is_bookmarked=False,
            is_own_article=False,
            created_at=a.created_at,
        ).model_dump())

    return {"articles": summaries, "total": len(summaries), "query": q}
