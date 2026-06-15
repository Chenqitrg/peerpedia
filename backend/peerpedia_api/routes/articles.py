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
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response
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
    MergeConflictError,
    apply_bundle,
    commit_article,
    create_bundle,
    get_article_lock,
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

    # Validate publish-time requirements before any disk operations.
    if body.publish and body.self_review is None:
        raise HTTPException(status_code=400, detail="self_review is required when publishing")

    rp = repo_path(a.id)
    is_new_repo = not (rp / ".git").is_dir()

    if body.repo_bundle:
        # Phase B: bundle-based create — client sends full git repo as tar.gz.
        # Extract the bundle instead of init+commit. Commits are preserved as-is.
        import base64
        import logging
        logger = logging.getLogger(__name__)

        try:
            tar_bytes = base64.b64decode(body.repo_bundle)
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid repo_bundle: base64 decode failed")

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tf:
            tf.write(tar_bytes)
            tar_path = Path(tf.name)

        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(path=rp.parent)
            # Verify extraction produced a git repo
            if not (rp / ".git").is_dir():
                raise HTTPException(
                    status_code=422,
                    detail="repo_bundle does not contain a valid git repository",
                )
            # Parse article.json from extracted repo for metadata sync
            try:
                _refresh_db_from_git(a.id, rp, db)
            except Exception:
                logger.warning("Bundle extraction ok but DB refresh failed for %s", a.id)

            repo = git.Repo(rp)
            commit_hash = repo.head.commit.hexsha if repo.head.is_valid() else None
        except tarfile.ReadError as e:
            raise HTTPException(status_code=422, detail=f"Invalid tar.gz: {e}")
        finally:
            tar_path.unlink(missing_ok=True)
    else:
        # Web mode: server writes content + commits to git.  Tauri clients
        # send a repo_bundle instead — same git repo, different transport.
        if is_new_repo:
            init_article_repo(a.id)
        ext = ".typ" if body.format == "typst" else ".md"
        (rp / f"article{ext}").write_text(body.content)
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

    # Publish to pool if requested
    if body.publish:
        sink_days = params.sink.new_article_default_days
        a = set_sink_start(db, a.id, sink_days)

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

    # Validate publish-time requirements before any disk operations.
    if body.publish and body.self_review is None:
        raise HTTPException(status_code=400, detail="self_review is required when publishing")

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

    # Web mode: write content to git.  Tauri clients push bundles via /sync.
    content_changed = body.content is not None
    if content_changed:
        commit_hash = commit_article(rp, commit_msg, author, f"{author}@peerpedia")
    else:
        import git as gitmod
        commit_hash = gitmod.Repo(rp).head.commit.hexsha if gitmod.Repo(rp).head.is_valid() else None

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

        if body.self_review is not None:
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
    # @deprecated Phase B: rollback via revert commit in bundle, not server-side.
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


# ═══════════════════════════════════════════════════════════════════════════════
# Bundle Sync Endpoints (Phase B — git-first network model)
# ═══════════════════════════════════════════════════════════════════════════════


def _refresh_db_from_git(article_id: str, rp: Path, db: "Session | None" = None) -> None:
    """Best-effort DB cache refresh from article.json and reviews in git.

    Syncs title, abstract, status, and keywords from article.json to the
    articles DB cache. Also triggers sink_start if status changed to 'pool'
    and the DB hasn't recorded it yet. Failures are logged — git is truth.
    """
    import json
    import logging
    logger = logging.getLogger(__name__)

    article_json = rp / "article.json"
    if not article_json.exists():
        return

    try:
        data = json.loads(article_json.read_text())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        logger.warning("Failed to parse article.json for %s", article_id)
        return

    if db is None:
        logger.debug("No DB session for %s — skipping DB sync", article_id)
        return

    try:
        from peerpedia_core.config.params import params
        from peerpedia_core.storage.db.crud_article import (
            get_article,
            set_sink_start,
        )

        a = get_article(db, article_id)
        if a is None:
            return

        updated = False

        # Sync title — use presence check so empty string can clear the field
        if "title" in data and a.title != data["title"]:
            a.title = data["title"]
            updated = True

        # Sync abstract
        if "abstract" in data and a.abstract != data["abstract"]:
            a.abstract = data["abstract"]
            updated = True

        # Sync status — trigger sink on pool transition
        new_status = data.get("status")
        if new_status is not None and new_status != a.status:
            a.status = new_status
            updated = True
            if new_status == "pool":
                sink_days = params.sink.new_article_default_days
                set_sink_start(db, article_id, sink_days)

        # Sync keywords — use presence check so [] can clear the field
        if "keywords" in data and a.keywords != data["keywords"]:
            a.keywords = data["keywords"]
            updated = True

        # Sync categories — use presence check so [] can clear the field
        if "categories" in data and a.categories != data["categories"]:
            a.categories = data["categories"]
            updated = True

        if updated:
            db.commit()
            logger.info("DB synced from article.json for %s (status=%s)", article_id, new_status or a.status)
    except Exception:
        logger.exception("DB sync failed for %s — git is truth, continuing", article_id)


@router.get("/{article_id}/head")
def api_get_head(article_id: str):
    """Return the current HEAD commit hash for an article's git repo."""
    rp = repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")

    import git as gitmod
    repo = gitmod.Repo(rp)
    if not repo.head.is_valid():
        raise HTTPException(status_code=404, detail="No commits in repo")

    return {"hash": repo.head.commit.hexsha}


@router.get("/{article_id}/bundle")
def api_get_bundle(
    article_id: str,
    since: str,
    current_user: User = Depends(deps.require_user),
):
    """Return an incremental git bundle from `since` to HEAD.

    The client pulls this to get server-side commits (reviews, platform
    updates) before pushing its own content.
    """
    rp = repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")

    import git as gitmod
    repo = gitmod.Repo(rp)
    if not repo.head.is_valid():
        raise HTTPException(status_code=404, detail="No commits in repo")

    try:
        bundle_bytes = create_bundle(rp, since)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Article repo not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return Response(
        content=bundle_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={article_id}.bundle",
        },
    )


@router.post("/{article_id}/sync")
async def api_sync_article(
    article_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    """Receive an incremental git bundle and fast-forward merge.

    Client uploads a bundle file (multipart). Server fetches objects,
    ff-only merges, and updates DB cache from article.json/reviews.
    Returns 409 if history diverged.
    """
    # Auth: only article authors can push bundles.
    a = get_article(db, article_id)
    if a is None:
        # Git repo exists but no DB record — first-time bundle push.
        # Auto-create the article record from git history.
        rp = repo_path(article_id)
        if not (rp / ".git").is_dir():
            raise HTTPException(status_code=404, detail="Article not found")
        from peerpedia_core.storage.db.crud_article import create_article as _create_article
        a = _create_article(db, authors=[], id=article_id, status="draft")
        # Rebuild authors from git commit history (single source of truth)
        from peerpedia_core.storage.db.crud_article import (
            get_authors_from_git,
            rebuild_article_authors,
        )
        git_authors = get_authors_from_git(rp, db)
        rebuild_article_authors(db, article_id, git_authors)
        # Refresh metadata from article.json
        _refresh_db_from_git(article_id, rp, db)

    if current_user.id not in get_author_ids(db, article_id):
        raise HTTPException(status_code=403, detail="Only authors can sync article content")

    rp = repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")

    import logging
    logger = logging.getLogger(__name__)

    # Size guard: academic articles with git history rarely exceed 50MB
    max_bundle_bytes = 50 * 1024 * 1024
    if file.size is not None and file.size > max_bundle_bytes:
        raise HTTPException(status_code=413, detail="Bundle too large — max 50MB")

    # Read the bundle fully before acquiring the lock — keep the lock
    # scope as short as possible (only git operations, not network I/O).
    bundle_bytes = await file.read()
    if len(bundle_bytes) > max_bundle_bytes:
        raise HTTPException(status_code=413, detail="Bundle too large — max 50MB")

    # Offload blocking git operations to a thread pool — threading.Lock
    # and libgit2 calls must not block the asyncio event loop.
    import asyncio

    def _apply_sync() -> str:
        lock = get_article_lock(article_id)
        acquired = lock.acquire(timeout=30)
        if not acquired:
            raise HTTPException(status_code=503, detail="Article busy — retry later")
        try:
            try:
                return apply_bundle(rp, bundle_bytes)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="Article repo not found")
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))
            except MergeConflictError:
                import git as gitmod
                repo = gitmod.Repo(rp)
                current_head = repo.head.commit.hexsha if repo.head.is_valid() else None
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "Fast-forward merge failed — history diverged",
                        "server_head": current_head,
                    },
                )
        finally:
            lock.release()

    _new_head = await asyncio.to_thread(_apply_sync)

    # Update DB cache — best-effort, git is truth
    try:
        _refresh_db_from_git(article_id, rp, db)
    except Exception:
        logger.warning("DB cache refresh failed for article %s", article_id)

    import git as gitmod
    repo = gitmod.Repo(rp)
    head_hash = repo.head.commit.hexsha if repo.head.is_valid() else None
    return {"head": head_hash}
