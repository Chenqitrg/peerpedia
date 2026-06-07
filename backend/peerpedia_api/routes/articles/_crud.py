"""Article CRUD routes: list, get, create, update."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, HTTPException
from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import (
    create_article,
    get_article,
    list_articles,
    set_sink_start,
)
from peerpedia_core.storage.db.crud_bookmark import is_bookmarked
from peerpedia_core.storage.db.crud_review import (
    create_review,
    get_reviews_for_article,
    upsert_review,
)
from peerpedia_core.storage.db.models import User
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    commit_article,
    get_commit_history,
    init_article_repo,
)
from peerpedia_core.workflow.scoring import compute_article_score_for_commit
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.helpers import (
    build_article_summary,
    get_commit_count,
    get_commit_hash,
    get_content_preview,
    get_git_meta,
    resolve_authors,
)
from peerpedia_api.schemas.article import (
    ArticleCreate,
    ArticleDetail,
    ArticleSummary,
    ArticleUpdate,
)

from ._router import router


# ── Shared helpers ──────────────────────────────────────────────────────

def repo_path(article_id: str) -> Path:
    """Return the git repository path for an article."""
    return DEFAULT_ARTICLES_DIR / article_id


def compute_sink(a) -> tuple[datetime | None, int | None]:
    """Compute sink ETA and days remaining from article."""
    if a.sink_start and a.status == "sedimentation":
        st = a.sink_start
        if st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        eta = st + timedelta(days=a.sink_duration_days)
        now = datetime.now(timezone.utc)
        remaining = max(0, (eta - now).days)
        return eta, remaining
    return None, None


def build_article_detail(
    db: Session, article_id: str, current_user: User | None = None
) -> ArticleDetail:
    """Build ArticleDetail from DB."""
    a = get_article(db, article_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Article not found")

    # Lazy-check: trigger auto-publish when someone views the article
    if a.status == "sedimentation":
        from peerpedia_core.workflow.sedimentation import publish_ready_articles
        publish_ready_articles(db)
        db.refresh(a)

    # Backfill: if score is None, walk commits newest→oldest for a valid score
    if a.score is None:
        rp = repo_path(article_id)
        if (rp / ".git").is_dir():
            for commit in get_commit_history(rp):
                score = compute_article_score_for_commit(db, article_id, commit["hash"])
                if score is not None:
                    a.score = score
                    db.commit()
                    break

    reviews = get_reviews_for_article(db, article_id)
    sink_eta, days_remaining = compute_sink(a)
    distinct_reviewers = len({(r.reviewer_id, r.scope) for r in reviews})
    authors = resolve_authors(db, a.authors or [])
    return ArticleDetail(
        id=a.id,
        title=a.title or "",
        status=a.status,
        authors=authors,
        commit_hash=get_commit_hash(a.id),
        fork_count=a.fork_count,
        forked_from=a.forked_from,
        commit_count=get_commit_count(a.id),
        compiled_format=a.compiled_format,
        compiled_output=a.compiled_output,
        compiled_pages=a.compiled_pages,
        score=a.score,
        sink_eta=sink_eta,
        days_remaining=days_remaining,
        sink_duration_days=getattr(a, "sink_duration_days", None),
        review_count=distinct_reviewers,
        is_bookmarked=is_bookmarked(db, current_user.id, a.id) if current_user else False,
        is_own_article=current_user.id in (a.authors or []) if current_user else False,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


# ── Routes ─────────────────────────────────────────────────────────────

@router.get("", response_model=dict)
def api_list_articles(
    status: str | None = None,
    author_id: str | None = None,
    current_user: User | None = Depends(deps.get_current_user),
    page: int = 1,
    size: int = 20,
    db: Session = Depends(deps.get_db),
):
    articles = list_articles(db, status=status, author_id=author_id)
    total = len(articles)
    start = (page - 1) * size
    paged = articles[start:start + size]
    summaries = [
        build_article_summary(
            db, a,
            current_user=current_user,
            sink_eta=compute_sink(a)[0],
            days_remaining=compute_sink(a)[1],
            sink_duration_days=getattr(a, "sink_duration_days", None),
        )
        for a in paged
    ]
    return {"articles": [s.model_dump() for s in summaries], "total": total,
            "page": page, "size": size}


@router.get("/{article_id}", response_model=ArticleDetail)
def api_get_article(
    article_id: str,
    current_user: User | None = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    return build_article_detail(db, article_id, current_user=current_user)


@router.post("", status_code=201, response_model=ArticleDetail)
def api_create_article(
    body: ArticleCreate,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    if not body.authors:
        raise HTTPException(status_code=422, detail="authors must not be empty")
    a = create_article(
        db,
        authors=body.authors,
        status="draft",
        title=body.title,
        abstract=body.abstract,
        keywords=body.keywords,
        categories=body.categories,
        forked_from=body.forked_from,
    )
    rp = init_article_repo(a.id)
    ext = ".typ" if body.format == "typst" else ".md"
    (rp / f"article{ext}").write_text(body.content)
    commit_msg = body.commit_message or "Initial submission"
    commit_hash = commit_article(rp, commit_msg, body.authors[0],
                                  f"{body.authors[0]}@peerpedia", allow_empty=True)
    a = set_sink_start(db, a.id, params.sink.new_article_default_days)

    contributions = None
    if body.contributions:
        contributions = {aid: c.model_dump() for aid, c in body.contributions.items()}
    create_review(
        db,
        article_id=a.id,
        commit_hash=commit_hash,
        reviewer_id=body.authors[0],
        scope="pool",
        scores=body.self_review.model_dump(),
        contributions=contributions,
    )
    score = compute_article_score_for_commit(db, a.id, commit_hash)
    if score is not None:
        a.score = score
    db.commit()
    return build_article_detail(db, a.id)


@router.put("/{article_id}", response_model=ArticleDetail)
def api_update_article(
    article_id: str, body: ArticleUpdate,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    """Edit an article: update content, commit to git, re-enter pool."""
    a = get_article(db, article_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Article not found")

    rp = repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=400, detail="Article repo not found")

    author = a.authors[0] if a.authors else "unknown"
    commit_msg = body.commit_message or "Edit article"

    if body.content is not None:
        ext = ".md"
        for e in [".md", ".typ"]:
            if (rp / f"article{e}").exists():
                ext = e
                break
        (rp / f"article{ext}").write_text(body.content)
        if not body.commit_message:
            commit_msg = "Edit: content updated"

    if body.title is not None:
        a.title = body.title
    if body.abstract is not None:
        a.abstract = body.abstract
    if body.keywords is not None:
        a.keywords = body.keywords
    if body.categories is not None:
        a.categories = body.categories

    commit_hash = commit_article(rp, commit_msg, author, f"{author}@peerpedia")

    if body.publish:
        sink_days = (
            params.sink.new_article_default_days
            if a.status == "draft"
            else params.sink.edit_article_default_days
        )
        a = set_sink_start(db, article_id, sink_days)

        if body.self_review:
            contributions = None
            if body.contributions:
                contributions = {aid: c.model_dump() for aid, c in body.contributions.items()}
            upsert_review(
                db,
                article_id=a.id,
                commit_hash=commit_hash,
                reviewer_id=author,
                scope="pool",
                scores=body.self_review.model_dump(),
                contributions=contributions,
            )

        score = compute_article_score_for_commit(db, a.id, commit_hash)
        if score is not None:
            a.score = score
    db.commit()

    return build_article_detail(db, a.id)
