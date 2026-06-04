"""Article API routes."""
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.schemas.article import (
    ArticleCreate,
    ArticleDetail,
    ArticleSummary,
    ArticleUpdate,
    SinkExtensionRequest,
)
from peerpedia_core.storage.db.crud_article import (
    create_article,
    get_article,
    list_articles,
    set_sink_start,
    extend_sink,
    update_article_status,
    increment_fork_count,
)
from peerpedia_core.storage.db.crud_review import create_review, upsert_review, get_reviews_for_article
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    init_article_repo,
    commit_article,
    get_commit_history,
    get_diff,
    get_diff_between,
)


def _compute_sink(a) -> tuple[datetime | None, int | None]:
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

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=dict)
def api_list_articles(status: str | None = None, db: Session = Depends(deps.get_db)):
    articles = list_articles(db, status=status)
    summaries = [
        ArticleSummary(
            id=a.id,
            title=getattr(a, "title", ""),
            status=a.status,
            authors=a.authors,
            fork_count=a.fork_count,
            created_at=a.created_at,
            score=a.score,
        )
        for a in articles
    ]
    return {"articles": [s.model_dump() for s in summaries], "total": len(summaries)}


@router.get("/{article_id}", response_model=ArticleDetail)
def api_get_article(article_id: str, db: Session = Depends(deps.get_db)):
    a = get_article(db, article_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Article not found")
    reviews = get_reviews_for_article(db, article_id)
    sink_eta, days_remaining = _compute_sink(a)
    return ArticleDetail(
        id=a.id,
        title=getattr(a, "title", ""),
        status=a.status,
        authors=a.authors,
        fork_count=a.fork_count,
        forked_from=a.forked_from,
        created_at=a.created_at,
        updated_at=a.updated_at,
        compiled_format=a.compiled_format,
        compiled_output=a.compiled_output,
        compiled_pages=a.compiled_pages,
        score=a.score,
        sink_eta=sink_eta,
        days_remaining=days_remaining,
        review_count=len(reviews),
    )


@router.post("", status_code=201, response_model=ArticleDetail)
def api_create_article(body: ArticleCreate, db: Session = Depends(deps.get_db)):
    if not body.authors:
        raise HTTPException(status_code=422, detail="authors must not be empty")
    a = create_article(
        db,
        authors=body.authors,
        status="draft",
        forked_from=body.forked_from,
    )
    # Init git repo and commit content
    rp = init_article_repo(a.id)
    ext = ".typ" if body.format == "typst" else ".md"
    (rp / f"article{ext}").write_text(body.content)
    commit_hash = commit_article(rp, "Initial submission", body.authors[0],
                                 f"{body.authors[0]}@peerpedia", allow_empty=True)
    # Send to sedimentation pool
    from peerpedia_core.config.params import params
    a = set_sink_start(db, a.id, params.sink.new_article_default_days)
    # Create self-review tied to this commit
    create_review(
        db,
        article_id=a.id,
        commit_hash=commit_hash,
        reviewer_id=body.authors[0],
        scope="pool",
        scores=body.self_review.model_dump(),
    )
    return api_get_article(a.id, db)


@router.put("/{article_id}", response_model=ArticleDetail)
def api_update_article(article_id: str, body: ArticleUpdate,
                        db: Session = Depends(deps.get_db)):
    """Edit an article: update content, commit to git, re-enter pool."""
    a = get_article(db, article_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Article not found")

    rp = _repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=400, detail="Article repo not found")

    author = a.authors[0] if a.authors else "unknown"
    commit_msg = "Edit article"

    # Write new content if provided
    if body.content is not None:
        # Determine file extension from existing repo
        ext = ".md"
        for e in [".md", ".typ"]:
            if (rp / f"article{e}").exists():
                ext = e
                break
        (rp / f"article{ext}").write_text(body.content)
        commit_msg = f"Edit: content updated"

    # Commit
    commit_hash = commit_article(rp, commit_msg, author,
                                 f"{author}@peerpedia")

    # Re-enter pool with edit default duration
    from peerpedia_core.config.params import params
    a = set_sink_start(db, article_id, params.sink.edit_article_default_days)

    # Create or update self-review
    if body.self_review:
        upsert_review(
            db,
            article_id=a.id,
            commit_hash=commit_hash,
            reviewer_id=author,
            scope="pool",
            scores=body.self_review.model_dump(),
        )

    return api_get_article(a.id, db)


@router.put("/{article_id}/sink-extension", response_model=ArticleDetail)
def api_extend_sink(article_id: str, body: SinkExtensionRequest,
                     db: Session = Depends(deps.get_db)):
    from peerpedia_core.config.params import params
    try:
        a = extend_sink(db, article_id, body.extra_days, params.sink.max_days)
        return api_get_article(a.id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Git-backed routes ──────────────────────────────────────────────────

def _repo_path(article_id: str) -> Path:
    return DEFAULT_ARTICLES_DIR / article_id


@router.get("/{article_id}/history")
def api_get_history(article_id: str):
    rp = _repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")
    return {"commits": get_commit_history(rp)}


@router.get("/{article_id}/diff/{hash1}/{hash2}")
def api_get_diff(article_id: str, hash1: str, hash2: str):
    rp = _repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")
    try:
        result = get_diff_between(rp, hash1, hash2)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{article_id}/fork", status_code=201)
def api_fork_article(article_id: str, user_id: str, db: Session = Depends(deps.get_db)):
    """Fork an article: clone its git repo and create a new Article record."""
    original = get_article(db, article_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Article not found")

    import shutil, uuid
    fork_id = str(uuid.uuid4())
    src = _repo_path(article_id)
    dst = _repo_path(fork_id)

    if (src / ".git").is_dir():
        shutil.copytree(src, dst, symlinks=True)
    else:
        init_article_repo(fork_id)

    fork = create_article(db, authors=[user_id], status="draft",
                          forked_from=article_id)
    increment_fork_count(db, article_id)
    return {"id": fork.id, "forked_from": article_id, "status": "draft"}


@router.post("/{article_id}/rollback/{hash}")
def api_rollback(article_id: str, hash: str, db: Session = Depends(deps.get_db)):
    """Rollback to a previous commit (creates a new commit, not force-push)."""
    rp = _repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")

    import git
    repo = git.Repo(rp)
    old_commit = repo.commit(hash)
    # Checkout old content
    repo.git.checkout(hash, "--", ".")
    new_hash = commit_article(rp, f"Rollback to {hash[:8]}", "System", "system@peerpedia")

    # Create self-review for the rollback commit
    article = get_article(db, article_id)
    if article:
        set_sink_start(db, article_id, 3)  # edit default
        from peerpedia_core.config.params import params
        from peerpedia_core.storage.db.crud_review import create_review
        create_review(db, article_id=article_id, commit_hash=new_hash,
                      reviewer_id=article.authors[0] if article.authors else "system",
                      scope="pool", scores={"originality": 0, "rigor": 0, "completeness": 0,
                                             "pedagogy": 0, "impact": 0})

    return {"commit_hash": new_hash, "message": f"Rollback to {hash[:8]}"}
