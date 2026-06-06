"""Search API route — SQL-level filtering with file-based source fallback."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.types import String

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

# Max number of articles to scan source files for text-search fallback.
# Only scanned when compiled_output is NULL and SQL title search didn't match.
_MAX_SOURCE_SCAN = 50


def _score_avg_expr():
    """SQL expression for the average of five-dimension scores."""
    return (
        func.coalesce(func.json_extract(Article.score, '$.originality'), 0) +
        func.coalesce(func.json_extract(Article.score, '$.rigor'), 0) +
        func.coalesce(func.json_extract(Article.score, '$.completeness'), 0) +
        func.coalesce(func.json_extract(Article.score, '$.pedagogy'), 0) +
        func.coalesce(func.json_extract(Article.score, '$.impact'), 0)
    ) / 5.0


def _read_source(article_id: str) -> str:
    """Read article source content for full-text search fallback."""
    rp = DEFAULT_ARTICLES_DIR / article_id
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            return f.read_text().lower()
    return ""


def _build_summary(db: Session, a: Article) -> dict:
    """Build an ArticleSummary dict from an Article ORM object."""
    return ArticleSummary(
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
    ).model_dump()


@router.get("")
def search(
    q: str = Query(default=""),
    category: str = Query(default=""),
    sort: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(deps.get_db),
):
    """Search articles with SQL-level filtering and file-based source fallback.

    - Category: SQL LIKE on JSON categories column (case-insensitive)
    - Title: SQL ILIKE (case-insensitive)
    - Content: SQL ILIKE on compiled_output + file-based source fallback
    - Sort: SQL ORDER BY (newest → created_at DESC, score → avg score DESC)
    - Pagination: SQL LIMIT/OFFSET with accurate total count

    Source file fallback: when a text query is provided, articles that don't
    match via title/compiled_output are checked against their source files.
    This is limited to _MAX_SOURCE_SCAN candidates to avoid scanning every
    article in the database.
    """
    q_lower = q.strip().lower()
    category_lower = category.strip().lower()
    sort_lower = sort.strip().lower()

    # ── Base query (visible articles only) ────────────────────────────
    base = db.query(Article).filter(
        Article.status.in_(["published", "sedimentation"])
    )

    # ── Category filter (SQL JSON) ────────────────────────────────────
    if category_lower:
        base = base.filter(
            func.lower(Article.categories.cast(String)).contains(category_lower)
        )

    # ── Text search: title + compiled_output (SQL) ────────────────────
    if q_lower:
        query = base.filter(or_(
            Article.title.ilike(f'%{q_lower}%'),
            Article.compiled_output.ilike(f'%{q_lower}%'),
        ))
    else:
        query = base

    # ── Sort ──────────────────────────────────────────────────────────
    if sort_lower == "newest":
        query = query.order_by(Article.created_at.desc())
    elif sort_lower == "score":
        query = query.order_by(_score_avg_expr().desc())

    # ── Paginate ──────────────────────────────────────────────────────
    total = query.count()
    offset = (page - 1) * size
    results = query.offset(offset).limit(size).all()

    # ── File-based source fallback ────────────────────────────────────
    # Only activated when text query is provided and SQL results are
    # fewer than requested (suggesting some matches may be in source files
    # whose compiled_output is NULL).
    if q_lower and len(results) < size:
        # Gather IDs we already have (SQL matches).
        already = {a.id for a in results}

        # Get candidates: articles matching status + category but NOT the
        # title/compiled_output SQL condition.
        fallback = base
        if sort_lower == "newest":
            fallback = fallback.order_by(Article.created_at.desc())
        elif sort_lower == "score":
            fallback = fallback.order_by(_score_avg_expr().desc())

        candidates = fallback.limit(_MAX_SOURCE_SCAN).all()

        # Check source files for text matches, skipping what we already have.
        for a in candidates:
            if a.id in already:
                continue
            if q_lower in _read_source(a.id):
                results = list(results) + [a]
                already.add(a.id)
            if len(results) >= size:
                break

        # Re-count total: SQL total + any source-only matches found.
        # This is approximate but prevents under-counting.
        if len(results) > query.count():
            total = query.count() + 1  # at least one source-only match exists

    # ── Build summaries ───────────────────────────────────────────────
    summaries = [_build_summary(db, a) for a in results]

    return {
        "articles": summaries,
        "total": total,
        "page": page,
        "size": size,
        "query": q,
        "category": category,
        "sort": sort,
    }
