# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review API routes."""
from fastapi import APIRouter, Depends, HTTPException
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids
from peerpedia_core.storage.db.crud_review import (
    add_thread_message,
    create_review,
    get_review,
    get_review_by_user_scope,
    get_reviews_for_article,
    update_review_scores,
)
from peerpedia_core.storage.db.models import User
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    commit_article,
    get_article_lock,
    get_commit_history,
)
from peerpedia_core.workflow.scoring import compute_article_score_for_commit
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.schemas.review import (
    ReviewCreate,
    ReviewOut,
    ThreadMessageCreate,
)

router = APIRouter(prefix="/articles/{article_id}/reviews", tags=["reviews"])


def _write_review_to_git_blocking(
    article_id: str,
    reviewer_id: str,
    scores: dict,
    content: str,
    reviewer_user: User,
    article,
) -> None:
    """Write review scores.json and .md to git repo, then commit.

    Blocking: raises HTTPException on failure so DB stays consistent.
    Call this BEFORE DB commit.
    """
    import json
    import logging
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        logger.warning("No git repo for article %s — skipping review file write", article_id)
        return

    review_dir = rp / "reviews" / reviewer_id
    review_dir.mkdir(parents=True, exist_ok=True)

    # Determine reviewer display identity
    is_self = reviewer_id in (getattr(article, 'authors', None) or [])
    if is_self:
        display_name = reviewer_user.name
        author_email = f"{reviewer_id}@peerpedia"
    elif article.status == "sedimentation":
        display_name = "Anonymous Contributor"
        author_email = "anonymous@peerpedia"
    else:
        display_name = reviewer_user.name
        author_email = f"{reviewer_id}@peerpedia"

    # Commit — blocking, raises on failure. File writes AND git commit
    # are inside the lock for atomicity — no other writer can interleave.
    lock = get_article_lock(article_id)
    acquired = lock.acquire(timeout=10)
    if not acquired:
        raise HTTPException(status_code=503, detail="Article busy — retry later")
    try:
        # Write scores.json
        (review_dir / "scores.json").write_text(json.dumps(scores, indent=2))

        # Write review .md with timestamp
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        md_content = f"{reviewer_id}\n\n{content or '(scores only)'}"
        (review_dir / f"{ts}.md").write_text(md_content)

        commit_article(
            rp,
            f"Review by {display_name}",
            display_name,
            author_email,
        )
    finally:
        lock.release()


def _build_review_out(r, user_map: dict[str, User], article_authors: list[str]) -> ReviewOut:
    u = user_map.get(r.reviewer_id)
    is_self = r.reviewer_id in article_authors
    reviewer_name = "unknown"
    if u is not None:
        if is_self:
            reviewer_name = u.name                     # 自评始终实名
        elif r.scope == "published":
            reviewer_name = u.name                     # 池外实名
        else:
            reviewer_name = u.anonymous_name or u.name # 池内匿名，出池不变
    return ReviewOut(
        id=r.id, article_id=r.article_id, commit_hash=r.commit_hash,
        reviewer_id=r.reviewer_id, scope=r.scope, scores=r.scores,
        contributions=r.contributions,
        thread=r.thread, reviewer_name=reviewer_name,
        is_self_review=is_self,
        created_at=r.created_at, updated_at=r.updated_at,
    )


def _batch_load_reviewers(db: Session, reviews) -> dict[str, User]:
    ids = {r.reviewer_id for r in reviews}
    if not ids:
        return {}
    users = db.query(User).filter(User.id.in_(ids)).all()
    return {u.id: u for u in users}


def _write_thread_reply_to_git(
    article_id: str,
    review_owner_uuid: str,
    sender: User,
    content: str,
    article,
) -> None:
    """Write a thread reply .md to the review's git directory and commit.

    Blocking: raises HTTPException on failure so DB stays consistent.
    Call this BEFORE DB commit.
    """
    import logging
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        logger.warning("No git repo for article %s — skipping thread reply write", article_id)
        return

    review_dir = rp / "reviews" / review_owner_uuid
    review_dir.mkdir(parents=True, exist_ok=True)

    if article.status == "sedimentation":
        display_name = "Anonymous Contributor"
        author_email = "anonymous@peerpedia"
    else:
        display_name = sender.name or sender.username
        author_email = f"{sender.id}@peerpedia"

    # Write .md reply and commit — all inside the lock for atomicity.
    lock = get_article_lock(article_id)
    acquired = lock.acquire(timeout=10)
    if not acquired:
        raise HTTPException(status_code=503, detail="Article busy — retry later")
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        md_content = f"{sender.id}\n\n{content}"
        (review_dir / f"{ts}.md").write_text(md_content)

        commit_article(rp, f"Reply by {display_name}", display_name, author_email)
    finally:
        lock.release()


@router.get("", response_model=list[ReviewOut])
def list_reviews(article_id: str, db: Session = Depends(deps.get_db)):
    article = get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    reviews = get_reviews_for_article(db, article_id)
    article_author_ids = get_author_ids(db, article_id)
    user_map = _batch_load_reviewers(db, reviews)
    return [_build_review_out(r, user_map, article_author_ids) for r in reviews]


@router.post("", status_code=201, response_model=ReviewOut)
def submit_review(article_id: str, body: ReviewCreate,
                  current_user: User = Depends(deps.require_user),
                  db: Session = Depends(deps.get_db)):
    article = get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    # Freeze pool reviews after article leaves the pool
    if body.scope.value == "pool" and article.status not in ("sedimentation", "draft"):
        existing_pool = get_review_by_user_scope(db, article_id, current_user.id,
                                                  "pool", commit_hash=body.commit_hash)
        if existing_pool:
            raise HTTPException(
                status_code=403,
                detail="Pool reviews are frozen after the article leaves the sedimentation pool. "
                       "Submit a new published-scope review instead.",
            )
    existing = get_review_by_user_scope(db, article_id, current_user.id,
                                        body.scope.value, commit_hash=body.commit_hash)

    # Git-first: write review files to git BEFORE any DB mutation.
    # If git fails (lock timeout, I/O error), the request aborts with an error
    # and the DB stays clean — no orphaned review records. Git is source of truth.
    _write_review_to_git_blocking(
        article_id, current_user.id, body.scores, body.content,
        current_user, article,
    )

    if existing:
        r = update_review_scores(db, existing.id, body.scores)
    else:
        r = create_review(db, article_id=article_id, commit_hash=body.commit_hash,
                           reviewer_id=current_user.id, scope=body.scope.value,
                           scores=body.scores)

    # Compute per-commit score and cache latest commit's score on the article
    rp = DEFAULT_ARTICLES_DIR / article_id
    if (rp / ".git").is_dir():
        commits = get_commit_history(rp)
        if commits:
            score = compute_article_score_for_commit(db, article_id,
                                                     commits[0]["hash"])
            if score is not None:
                article.score = score
                db.commit()
    # Update reputation for all authors of the reviewed article
    from peerpedia_core.workflow.reputation import compute_author_reputation
    article_author_ids = get_author_ids(db, article_id)
    for author_id in article_author_ids:
        compute_author_reputation(db, author_id)

    user_map = _batch_load_reviewers(db, [r])
    return _build_review_out(r, user_map, article_author_ids)


@router.post("/{review_id}/messages", status_code=201, response_model=dict)
def post_thread_message(article_id: str, review_id: str, body: ThreadMessageCreate,
                         current_user: User = Depends(deps.require_user),
                         db: Session = Depends(deps.get_db)):
    """Post a message in a review thread. Only the article author and the review's
    reviewer can participate; bystanders get 403."""
    r = get_review(db, review_id)
    if r is None or r.article_id != article_id:
        raise HTTPException(status_code=404, detail="Review not found")

    # Permission: only article authors + the review's reviewer can reply
    article = get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    is_author = current_user.id in get_author_ids(db, article_id)
    is_reviewer = r.reviewer_id == current_user.id
    if not (is_author or is_reviewer):
        raise HTTPException(
            status_code=403,
            detail="Only the article author and reviewer can participate in this thread",
        )

    # Git-first: write reply to git BEFORE DB. If git fails, the DB stays clean.
    _write_thread_reply_to_git(
        article_id, r.reviewer_id, current_user, body.content,
        article,
    )

    from peerpedia_core.types.messages import ThreadMessage
    msg = ThreadMessage(author_id=current_user.id, content=body.content,
                        author_name=current_user.name)
    add_thread_message(db, review_id, msg.to_dict())

    return {"status": "ok", "message": msg.to_dict()}
