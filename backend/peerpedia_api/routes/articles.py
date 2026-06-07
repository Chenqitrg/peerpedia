"""Article API routes."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import (
    create_article,
    extend_sink,
    get_article,
    increment_fork_count,
    list_articles,
    set_sink_start,
    update_article_status,
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
    get_diff_between,
    init_article_repo,
)
from peerpedia_core.workflow.scoring import compute_article_score_for_commit
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.helpers import (
    get_commit_count,
    get_content_preview,
    get_git_meta,
    resolve_authors,
)
from peerpedia_api.schemas.article import (
    ArticleCreate,
    ArticleDetail,
    ArticleSourceResponse,
    ArticleSummary,
    ArticleUpdate,
    SinkExtensionRequest,
)

# ── Helpers ──────────────────────────────────────────────────────────────

def _repo_path(article_id: str) -> Path:
    return DEFAULT_ARTICLES_DIR / article_id


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
    # Paginate
    start = (page - 1) * size
    paged = articles[start:start + size]
    summaries: list[ArticleSummary] = []
    for a in paged:
        ghash, gcount = get_git_meta(a.id)
        summaries.append(ArticleSummary(
            id=a.id,
            title=a.title or "",
            status=a.status,
            authors=resolve_authors(db, a.authors or []),
            content_preview=get_content_preview(a.id),
            commit_hash=ghash,
            fork_count=a.fork_count,
            forked_from=a.forked_from,
            commit_count=gcount,
            score=a.score,
            sink_eta=_compute_sink(a)[0],
            days_remaining=_compute_sink(a)[1],
            sink_duration_days=getattr(a, "sink_duration_days", None),
            is_bookmarked=is_bookmarked(db, current_user.id, a.id) if current_user else False,
            is_own_article=current_user.id in (a.authors or []) if current_user else False,
            created_at=a.created_at,
        ))
    return {"articles": [s.model_dump() for s in summaries], "total": total,
            "page": page, "size": size}


def _build_article_detail(db: Session, article_id: str,
                         current_user: User | None = None) -> ArticleDetail:
    """Build ArticleDetail from DB. Internal callers pass current_user=None."""
    a = get_article(db, article_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Article not found")

    # Lazy-check: trigger auto-publish when someone views the article
    if a.status == "sedimentation":
        from peerpedia_core.workflow.sedimentation import publish_ready_articles
        publish_ready_articles(db)
        # Refresh after possible status change
        db.refresh(a)
    # Backfill: if score is None, walk commits newest→oldest for a valid score
    if a.score is None:
        rp = _repo_path(article_id)
        if (rp / ".git").is_dir():
            for commit in get_commit_history(rp):
                score = compute_article_score_for_commit(db, article_id,
                                                         commit["hash"])
                if score is not None:
                    a.score = score
                    db.commit()
                    break
    reviews = get_reviews_for_article(db, article_id)
    sink_eta, days_remaining = _compute_sink(a)
    distinct_reviewers = len({(r.reviewer_id, r.scope) for r in reviews})
    authors = resolve_authors(db, a.authors or [])
    return ArticleDetail(
        id=a.id,
        title=a.title or "",
        status=a.status,
        authors=authors,
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


@router.get("/{article_id}", response_model=ArticleDetail)
def api_get_article(
    article_id: str,
    current_user: User | None = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    return _build_article_detail(db, article_id, current_user=current_user)


@router.post("", status_code=201, response_model=ArticleDetail)
def api_create_article(body: ArticleCreate, db: Session = Depends(deps.get_db)):
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
    # Init git repo and commit content
    rp = init_article_repo(a.id)
    ext = ".typ" if body.format == "typst" else ".md"
    (rp / f"article{ext}").write_text(body.content)
    commit_msg = body.commit_message or "Initial submission"
    commit_hash = commit_article(rp, commit_msg, body.authors[0],
                                 f"{body.authors[0]}@peerpedia", allow_empty=True)
    # Send to sedimentation pool
    a = set_sink_start(db, a.id, params.sink.new_article_default_days)
    # Create self-review tied to this commit
    contributions = None
    if body.contributions:
        contributions = {
            aid: c.model_dump() for aid, c in body.contributions.items()
        }
    create_review(
        db,
        article_id=a.id,
        commit_hash=commit_hash,
        reviewer_id=body.authors[0],
        scope="pool",
        scores=body.self_review.model_dump(),
        contributions=contributions,
    )
    # Compute and cache article score (latest commit's score)
    score = compute_article_score_for_commit(db, a.id, commit_hash)
    if score is not None:
        a.score = score
    db.commit()
    return _build_article_detail(db, a.id)


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
    commit_msg = body.commit_message or "Edit article"

    # Write new content if provided
    if body.content is not None:
        # Determine file extension from existing repo
        ext = ".md"
        for e in [".md", ".typ"]:
            if (rp / f"article{e}").exists():
                ext = e
                break
        (rp / f"article{ext}").write_text(body.content)
        if not body.commit_message:
            commit_msg = "Edit: content updated"

    # Update metadata fields if provided
    if body.title is not None:
        a.title = body.title
    if body.abstract is not None:
        a.abstract = body.abstract
    if body.keywords is not None:
        a.keywords = body.keywords
    if body.categories is not None:
        a.categories = body.categories

    # Commit
    commit_hash = commit_article(rp, commit_msg, author,
                                 f"{author}@peerpedia")

    # Only publish to pool when explicitly requested
    if body.publish:
        if a.status == "draft":
            sink_days = params.sink.new_article_default_days
        else:
            sink_days = params.sink.edit_article_default_days
        a = set_sink_start(db, article_id, sink_days)

        # Create or update self-review
        if body.self_review:
            contributions = None
            if body.contributions:
                contributions = {
                    aid: c.model_dump() for aid, c in body.contributions.items()
                }
            upsert_review(
                db,
                article_id=a.id,
                commit_hash=commit_hash,
                reviewer_id=author,
                scope="pool",
                scores=body.self_review.model_dump(),
                contributions=contributions,
            )

        # Compute and cache article score (latest commit's score)
        score = compute_article_score_for_commit(db, a.id, commit_hash)
        if score is not None:
            a.score = score
    db.commit()

    return _build_article_detail(db, a.id)


@router.put("/{article_id}/sink-extension", response_model=ArticleDetail)
def api_extend_sink(article_id: str, body: SinkExtensionRequest,
                    current_user: User = Depends(deps.require_user),
                    db: Session = Depends(deps.get_db)):
    try:
        a = extend_sink(db, article_id, body.extra_days, params.sink.max_days)
        return _build_article_detail(db, a.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Actions ───────────────────────────────────────────────────────────

@router.get("/{article_id}/has-forked")
def api_has_forked(article_id: str, current_user: User = Depends(deps.require_user),
                   db: Session = Depends(deps.get_db)):
    """Check if a user has already forked this article."""
    all_articles = list_articles(db)
    for a in all_articles:
        if a.forked_from == article_id and current_user.id in (a.authors or []):
            return {"has_forked": True, "fork_article_id": a.id}
    return {"has_forked": False, "fork_article_id": None}


@router.post("/{article_id}/publish", response_model=ArticleDetail)
def api_publish_article(article_id: str, current_user: User = Depends(deps.require_user),
                        db: Session = Depends(deps.get_db)):
    """Explicitly publish a draft article to the sedimentation pool."""
    a = get_article(db, article_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Article not found")
    a = set_sink_start(db, article_id, params.sink.new_article_default_days)
    a = update_article_status(db, article_id, "sedimentation")
    return _build_article_detail(db, a.id)


# ── Source ─────────────────────────────────────────────────────────────

@router.get("/{article_id}/source", response_model=ArticleSourceResponse)
def api_get_source(article_id: str):
    rp = _repo_path(article_id)
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            fmt = "markdown" if ext == ".md" else "typst"
            return ArticleSourceResponse(content=f.read_text(), format=fmt)
    raise HTTPException(status_code=404, detail="Source file not found")


@router.get("/{article_id}/download/source")
def api_download_source(article_id: str):
    from fastapi.responses import PlainTextResponse
    rp = _repo_path(article_id)
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            return PlainTextResponse(
                content=f.read_text(),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=article{ext}"},
            )
    raise HTTPException(status_code=404, detail="Source file not found")


@router.get("/{article_id}/download/pdf")
def api_download_pdf(article_id: str):
    """Compile article to PDF and return as downloadable file."""
    import tempfile

    from fastapi.responses import FileResponse, PlainTextResponse

    rp = _repo_path(article_id)
    # Find source file
    for ext in [".typ", ".md"]:
        f = rp / f"article{ext}"
        if f.exists():
            if ext == ".typ":
                # Typst → PDF via compiler
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    out_dir = tmp_dir / "out"
                    out_dir.mkdir()
                    from peerpedia_core.storage.compiler import TypstBackend
                    result = TypstBackend().compile(f, out_dir, fmt="pdf")
                    if not result.success:
                        raise HTTPException(
                            status_code=500,
                            detail=result.error or "PDF compilation failed",
                        )
                    return FileResponse(
                        result.output_path,
                        media_type="application/pdf",
                        filename=f"{article_id}.pdf",
                    )
            else:
                # Markdown → HTML download
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    out_dir = tmp_dir / "out"
                    out_dir.mkdir()
                    from peerpedia_core.storage.compiler import MarkdownBackend
                    result = MarkdownBackend().compile(f, out_dir)
                    html = result.html_content or ""
                    if not html and result.output_path:
                        html = Path(result.output_path).read_text()
                    return PlainTextResponse(
                        content=html,
                        media_type="text/html",
                        headers={
                            "Content-Disposition":
                                f"attachment; filename={article_id}.html",
                        },
                    )
    raise HTTPException(status_code=404, detail="Source file not found")


# ── Git-backed routes ──────────────────────────────────────────────────

@router.get("/{article_id}/history")
def api_get_history(article_id: str, db: Session = Depends(deps.get_db)):
    rp = _repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")
    commits = get_commit_history(rp)
    # Attach per-commit scores
    for commit in commits:
        commit["score"] = compute_article_score_for_commit(db, article_id,
                                                           commit["hash"])
    return {"commits": commits}


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
def api_fork_article(article_id: str, current_user: User = Depends(deps.require_user),
                     db: Session = Depends(deps.get_db)):
    """Fork an article: clone its git repo and create a new Article record."""
    original = get_article(db, article_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Article not found")

    import shutil
    import uuid
    fork_id = str(uuid.uuid4())
    src = _repo_path(article_id)
    dst = _repo_path(fork_id)

    if (src / ".git").is_dir():
        shutil.copytree(src, dst, symlinks=True)
    else:
        init_article_repo(fork_id)

    fork = create_article(db, id=fork_id, title=original.title,
                          abstract=original.abstract,
                          keywords=original.keywords,
                          categories=original.categories,
                          authors=[current_user.id], status="draft",
                          forked_from=article_id)
    increment_fork_count(db, article_id)
    return {"id": fork.id, "forked_from": article_id, "status": "draft"}


@router.post("/{article_id}/rollback/{hash}")
def api_rollback(article_id: str, hash: str, current_user: User = Depends(deps.require_user),
                 db: Session = Depends(deps.get_db)):
    """Rollback to a previous commit (creates a new commit, not force-push)."""
    rp = _repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")

    import git
    repo = git.Repo(rp)
    repo.commit(hash)
    # Checkout old content
    repo.git.checkout(hash, "--", ".")
    new_hash = commit_article(rp, f"Rollback to {hash[:8]}", "System", "system@peerpedia")

    # Create self-review for the rollback commit
    article = get_article(db, article_id)
    if article:
        set_sink_start(db, article_id, params.sink.edit_article_default_days)
        # Use neutral mid-scale scores — rollback is a system action, not an assessment
        neutral = 3.0
        create_review(db, article_id=article_id, commit_hash=new_hash,
                      reviewer_id=article.authors[0] if article.authors else "system",
                      scope="pool", scores={"originality": neutral, "rigor": neutral,
                                             "completeness": neutral,
                                             "pedagogy": neutral, "impact": neutral})
        # Compute and cache article score for the rollback commit
        score = compute_article_score_for_commit(db, article_id, new_hash)
        if score is not None:
            article.score = score
            db.commit()

    return {"commit_hash": new_hash, "message": f"Rollback to {hash[:8]}"}
