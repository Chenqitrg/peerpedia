# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article routes: CRUD, history, diff, fork, rollback, publish, source, download."""
import shutil
import tarfile
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import git
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import (
    count_articles,
    create_article,
    delete_article,
    extend_sink,
    get_article,
    get_author_ids,
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
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.db.models import User
from peerpedia_core.storage.git_backend import (
    commit_article,
    get_commit_history,
    get_diff_between,
    init_article_repo,
)
from peerpedia_core.workflow.scoring import compute_article_score_for_commit
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.helpers import (
    build_article_summary,
    get_commit_count,
    get_commit_hash,
    repo_path,
    resolve_authors,
)
from peerpedia_api.schemas.article import (
    ArticleCreate,
    ArticleDetail,
    ArticleSourceResponse,
    ArticleUpdate,
    SinkExtensionRequest,
)

router = APIRouter(prefix="/articles", tags=["articles"])

# ═══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════════


def compute_sink(a) -> tuple[datetime | None, int | None]:
    """Compute sink ETA and days remaining from article."""
    if a.sink_start and a.status == "sedimentation":
        duration = getattr(a, "sink_duration_days", None) or 7
        st = a.sink_start
        if st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        eta = st + timedelta(days=duration)
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
    author_ids = get_author_ids(db, a.id)
    authors = resolve_authors(db, author_ids)
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
        score=a.score if a.status != "draft" else None,
        sink_eta=sink_eta,
        days_remaining=days_remaining,
        sink_duration_days=getattr(a, "sink_duration_days", None),
        review_count=distinct_reviewers,
        is_bookmarked=is_bookmarked(db, current_user.id, a.id) if current_user else False,
        is_own_article=current_user.id in author_ids if current_user else False,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD routes
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("", response_model=dict)
def api_list_articles(
    status: str | None = None,
    author_id: str | None = None,
    current_user: User | None = Depends(deps.get_current_user),
    page: int = 1,
    size: int = 20,
    db: Session = Depends(deps.get_db),
):
    articles = list_articles(db, status=status, author_id=author_id,
                             limit=size, offset=(page - 1) * size)
    total = count_articles(db, status=status, author_id=author_id)
    summaries = [
        build_article_summary(
            db, a,
            current_user=current_user,
            sink_eta=(eta := compute_sink(a))[0],
            days_remaining=eta[1],
            sink_duration_days=getattr(a, "sink_duration_days", None),
        )
        for a in articles
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
    # Default to current user when no authors specified
    author_list = body.authors or [current_user.id]
    # Validate all authors exist in server DB — prevents FOREIGN KEY violation
    # when a local-only account (not synced to server) is passed as author_id.
    for author_id in author_list:
        if get_user(db, author_id) is None:
            raise HTTPException(
                status_code=400,
                detail=f"Author '{author_id}' is not synced to the server. "
                       "Please log out and log in again while the server is running.",
            )
    # Client-generated UUID: validate and check for duplicates.
    # Authors are always derived from current_user — client UUID is trusted
    # only for article identity, never for authorship.
    client_id = body.id
    if client_id is not None:
        try:
            uuid.UUID(client_id)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid article ID: {client_id}")
        if get_article(db, client_id) is not None:
            raise HTTPException(status_code=409, detail=f"Article '{client_id}' already exists")
    kwargs = {
        "title": body.title,
        "abstract": body.abstract,
        "keywords": body.keywords,
        "categories": body.categories,
        "forked_from": body.forked_from,
    }
    if client_id is not None:
        kwargs["id"] = client_id
    a = create_article(
        db,
        authors=author_list,
        status="draft",
        **kwargs,
    )
    rp = repo_path(a.id)
    is_new_repo = not (rp / ".git").is_dir()
    if is_new_repo:
        init_article_repo(a.id)
    ext = ".typ" if body.format == "typst" else ".md"
    (rp / f"article{ext}").write_text(body.content)
    # Only create server commit if repo was just initialized (no existing
    # commits from local gitInit). Author identity: name = display, email = UUID.
    commit_msg = body.commit_message or "Initial submission"
    author_name = current_user.name or current_user.username
    commit_hash = commit_article(rp, commit_msg, author_name,
                                  f"{author_list[0]}@peerpedia", allow_empty=True)

    # Rebuild authors from git history after first commit
    from peerpedia_core.storage.db.crud_article import (
        rebuild_article_authors,
    )
    rebuild_article_authors(db, a.id, set(author_list))

    # Self-review and scoring: only created when the author explicitly
    # provides scores (i.e., at publish time, not draft save).
    if body.self_review is not None:
        contributions = None
        if body.contributions:
            contributions = {aid: c.model_dump() for aid, c in body.contributions.items()}
        create_review(
            db,
            article_id=a.id,
            commit_hash=commit_hash,
            reviewer_id=author_list[0],
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

    if current_user.id not in get_author_ids(db, article_id):
        raise HTTPException(status_code=403, detail="Only authors can edit their articles")

    rp = repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=400, detail="Article repo not found")

    author_ids = get_author_ids(db, article_id)
    author = author_ids[0] if author_ids else "unknown"
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

    # Rebuild authors from git history (incremental scan when marker exists)
    from peerpedia_core.storage.db.crud_article import (
        get_authors_from_git,
        rebuild_article_authors,
    )
    git_authors = get_authors_from_git(rp, db, since_hash=a.last_author_rebuild_hash)
    rebuild_article_authors(db, article_id, git_authors)

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


@router.delete("/{article_id}", status_code=204)
def api_delete_article(
    article_id: str,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    """Delete an article. Only authors can delete their own articles."""
    a = get_article(db, article_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if current_user.id not in get_author_ids(db, article_id):
        raise HTTPException(status_code=403, detail="Only authors can delete their articles")
    delete_article(db, article_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Git routes: history, diff, fork, rollback
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{article_id}/history")
def api_get_history(article_id: str, db: Session = Depends(deps.get_db)):
    rp = repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")
    commits = get_commit_history(rp)
    for commit in commits:
        commit["score"] = compute_article_score_for_commit(db, article_id, commit["hash"])
    return {"commits": commits}


@router.get("/{article_id}/diff/{hash1}/{hash2}")
def api_get_diff(article_id: str, hash1: str, hash2: str):
    rp = repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")
    try:
        return get_diff_between(rp, hash1, hash2)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{article_id}/fork", status_code=201)
def api_fork_article(
    article_id: str,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    """Fork an article: clone its git repo and create a new Article record."""
    original = get_article(db, article_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Article not found")

    # Verify user exists in server DB — local-only accounts can't fork.
    user = get_user(db, current_user.id)
    if user is None:
        raise HTTPException(
            status_code=400,
            detail="Your account is not synced to the server. Please log out and log in again while the server is running.",
        )

    fork_id = str(uuid.uuid4())
    src = repo_path(article_id)
    dst = repo_path(fork_id)

    if (src / ".git").is_dir():
        shutil.copytree(src, dst, symlinks=True)
    else:
        init_article_repo(fork_id)

    fork = create_article(
        db, id=fork_id, title=original.title,
        abstract=original.abstract,
        keywords=original.keywords,
        categories=original.categories,
        authors=[current_user.id], status="draft",
        forked_from=article_id,
    )
    increment_fork_count(db, article_id)

    # Rebuild authors from git history — the single source of truth.
    # Fork preserves original commit history via shutil.copytree.
    from peerpedia_core.storage.db.crud_article import (
        get_authors_from_git,
        rebuild_article_authors,
    )
    if (dst / ".git").is_dir():
        git_authors = get_authors_from_git(dst, db)
        git_authors.add(current_user.id)
        rebuild_article_authors(db, fork_id, git_authors)

    return {"id": fork.id, "forked_from": article_id, "status": "draft"}


@router.get("/{article_id}/has-forked")
def api_has_forked(
    article_id: str,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    """Check if a user has already forked this article."""
    from peerpedia_core.storage.db.crud_article import get_article_by_fork_and_author
    a = get_article_by_fork_and_author(db, forked_from=article_id, author_id=current_user.id)
    if a is not None:
        return {"has_forked": True, "fork_article_id": a.id}
    return {"has_forked": False, "fork_article_id": None}


@router.post("/{article_id}/rollback/{hash}")
def api_rollback(
    article_id: str, hash: str,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    """Rollback to a previous commit (creates a new commit, not force-push)."""
    rp = repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")

    repo = git.Repo(rp)
    repo.commit(hash)
    repo.git.checkout(hash, "--", ".")
    new_hash = commit_article(rp, f"Rollback to {hash[:8]}", "System", "system@peerpedia")

    article = get_article(db, article_id)
    if article:
        set_sink_start(db, article_id, params.sink.edit_article_default_days)
        neutral = 3.0
        rollback_author_ids = get_author_ids(db, article_id)
        create_review(
            db, article_id=article_id, commit_hash=new_hash,
            reviewer_id=rollback_author_ids[0] if rollback_author_ids else "system",
            scope="pool",
            scores={"originality": neutral, "rigor": neutral,
                    "completeness": neutral, "pedagogy": neutral, "impact": neutral},
        )
        score = compute_article_score_for_commit(db, article_id, new_hash)
        if score is not None:
            article.score = score
            db.commit()

    return {"commit_hash": new_hash, "message": f"Rollback to {hash[:8]}"}


# ═══════════════════════════════════════════════════════════════════════════════
# Publish, sink, source, download routes
# ═══════════════════════════════════════════════════════════════════════════════


@router.put("/{article_id}/sink-extension", response_model=ArticleDetail)
def api_extend_sink(
    article_id: str, body: SinkExtensionRequest,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    try:
        a = extend_sink(db, article_id, body.extra_days, params.sink.max_days)
        return build_article_detail(db, a.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{article_id}/publish", response_model=ArticleDetail)
def api_publish_article(
    article_id: str,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    """Explicitly publish a draft article to the sedimentation pool."""
    a = get_article(db, article_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Article not found")
    a = set_sink_start(db, article_id, params.sink.new_article_default_days)
    a = update_article_status(db, article_id, "sedimentation")
    return build_article_detail(db, a.id)


# ── Source ─────────────────────────────────────────────────────────────


@router.get("/{article_id}/source", response_model=ArticleSourceResponse)
def api_get_source(article_id: str):
    rp = repo_path(article_id)
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            fmt = "markdown" if ext == ".md" else "typst"
            return ArticleSourceResponse(content=f.read_text(), format=fmt)
    raise HTTPException(status_code=404, detail="Source file not found")


@router.get("/{article_id}/download/source")
def api_download_source(article_id: str):
    rp = repo_path(article_id)
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
    rp = repo_path(article_id)
    for ext in [".typ", ".md"]:
        f = rp / f"article{ext}"
        if f.exists():
            if ext == ".typ":
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


@router.get("/{article_id}/download/repo")
def api_download_repo(article_id: str):
    """Export the entire article git repository as a tar.gz bundle."""
    rp = repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Git repo not found")

    tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    try:
        with tarfile.open(tmp.name, "w:gz") as tar:
            tar.add(str(rp), arcname=article_id)
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Failed to create archive")

    return FileResponse(
        tmp.name,
        media_type="application/gzip",
        filename=f"{article_id}.tar.gz",
    )
