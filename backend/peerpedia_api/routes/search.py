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

VALID_SORTS = {"newest", "score"}


def _read_source(article_id: str) -> str:
    """Read article source content for full-text search."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            return f.read_text().lower()
    return ""


def _avg_score(article: Article) -> float:
    """Average of five-dimension scores, for sorting."""
    s = article.score
    if not s:
        return 0.0
    dims = ["originality", "rigor", "completeness", "pedagogy", "impact"]
    vals = [s.get(d, 0) or 0 for d in dims]
    return sum(vals) / len(vals)


@router.get("")
def search(
    q: str = Query(default=""),
    category: str = Query(default=""),
    sort: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(deps.get_db),
):
    """Search articles by title and source content, with optional filters and pagination."""
    articles_q = db.query(Article).filter(
        Article.status.in_(["published", "sedimentation"])
    )

    q_lower = q.strip().lower()
    category_lower = category.strip().lower()
    sort_lower = sort.strip().lower()

    # Collect results — apply text search if query provided, else list all
    results: list[Article] = []
    for a in articles_q.all():
        # Category filter
        if category_lower:
            cats = [c.lower() for c in (a.categories or [])]
            if category_lower not in cats:
                continue

        # Text search
        if q_lower:
            title = (a.title or "").lower()
            source = _read_source(a.id)
            if q_lower not in title and q_lower not in source:
                continue

        results.append(a)

    total = len(results)

    # Sort
    if sort_lower in VALID_SORTS:
        if sort_lower == "newest":
            results.sort(key=lambda a: a.created_at, reverse=True)
        elif sort_lower == "score":
            results.sort(key=_avg_score, reverse=True)

    # Paginate — apply offset/limit AFTER filtering and sorting
    offset = (page - 1) * size
    results = results[offset : offset + size]

    summaries = []
    for a in results:
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

    return {
        "articles": summaries,
        "total": total,
        "page": page,
        "size": size,
        "query": q,
        "category": category,
        "sort": sort,
    }
