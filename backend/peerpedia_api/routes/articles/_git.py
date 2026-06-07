"""Article git-backed routes: history, diff, fork, rollback."""
from fastapi import Depends, HTTPException
from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import (
    create_article,
    get_article,
    increment_fork_count,
    set_sink_start,
)
from peerpedia_core.storage.db.crud_review import create_review
from peerpedia_core.storage.db.models import User
from peerpedia_core.storage.git_backend import (
    commit_article,
    get_commit_history as _get_commit_history,
    get_diff_between,
    init_article_repo,
)
from peerpedia_core.workflow.scoring import compute_article_score_for_commit
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.schemas.article import ArticleDetail

from ._crud import repo_path, build_article_detail
from ._router import router


@router.get("/{article_id}/history")
def api_get_history(article_id: str, db: Session = Depends(deps.get_db)):
    rp = repo_path(article_id)
    if not (rp / ".git").is_dir():
        raise HTTPException(status_code=404, detail="Article repo not found")
    commits = _get_commit_history(rp)
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
    import shutil
    import uuid

    original = get_article(db, article_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Article not found")

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
    return {"id": fork.id, "forked_from": article_id, "status": "draft"}


@router.get("/{article_id}/has-forked")
def api_has_forked(
    article_id: str,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    """Check if a user has already forked this article."""
    from peerpedia_core.storage.db.crud_article import list_articles
    all_articles = list_articles(db)
    for a in all_articles:
        if a.forked_from == article_id and current_user.id in (a.authors or []):
            return {"has_forked": True, "fork_article_id": a.id}
    return {"has_forked": False, "fork_article_id": None}


@router.post("/{article_id}/rollback/{hash}")
def api_rollback(
    article_id: str, hash: str,
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    """Rollback to a previous commit (creates a new commit, not force-push)."""
    import git

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
        create_review(
            db, article_id=article_id, commit_hash=new_hash,
            reviewer_id=article.authors[0] if article.authors else "system",
            scope="pool",
            scores={"originality": neutral, "rigor": neutral,
                    "completeness": neutral, "pedagogy": neutral, "impact": neutral},
        )
        score = compute_article_score_for_commit(db, article_id, new_hash)
        if score is not None:
            article.score = score
            db.commit()

    return {"commit_hash": new_hash, "message": f"Rollback to {hash[:8]}"}
