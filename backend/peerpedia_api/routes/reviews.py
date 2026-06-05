"""Review API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.schemas.review import (
    ReviewCreate, ReviewOut, ThreadMessageCreate,
)
from peerpedia_core.storage.db.crud_review import (
    create_review, get_review, get_reviews_for_article,
    get_review_by_user_scope, update_review_scores, add_thread_message,
)
from peerpedia_core.storage.db.crud_article import get_article
from peerpedia_core.storage.db.crud_user import get_user
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, get_commit_history
from peerpedia_core.workflow.scoring import compute_article_score_for_commit

router = APIRouter(prefix="/articles/{article_id}/reviews", tags=["reviews"])


def _build_review_out(r, db: Session, article_authors: list[str]) -> ReviewOut:
    u = get_user(db, r.reviewer_id)
    reviewer_name = "unknown"
    if u is not None:
        reviewer_name = u.name if r.scope == "published" else (u.anonymous_name or u.name)
    return ReviewOut(
        id=r.id, article_id=r.article_id, commit_hash=r.commit_hash,
        reviewer_id=r.reviewer_id, scope=r.scope, scores=r.scores,
        contributions=r.contributions,
        thread=r.thread, reviewer_name=reviewer_name,
        is_self_review=r.reviewer_id in article_authors,
        created_at=r.created_at, updated_at=r.updated_at,
    )


@router.get("", response_model=list[ReviewOut])
def list_reviews(article_id: str, db: Session = Depends(deps.get_db)):
    article = get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    reviews = get_reviews_for_article(db, article_id)
    return [_build_review_out(r, db, article.authors) for r in reviews]


@router.post("", status_code=201, response_model=ReviewOut)
def submit_review(article_id: str, body: ReviewCreate, db: Session = Depends(deps.get_db)):
    article = get_article(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    existing = get_review_by_user_scope(db, article_id, body.reviewer_id,
                                        body.scope.value, commit_hash=body.commit_hash)
    if existing:
        r = update_review_scores(db, existing.id, body.scores)
    else:
        r = create_review(db, article_id=article_id, commit_hash=body.commit_hash,
                           reviewer_id=body.reviewer_id, scope=body.scope.value,
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
    for author_id in article.authors:
        compute_author_reputation(db, author_id)
    return _build_review_out(r, db, article.authors)


@router.post("/{review_id}/messages", status_code=201, response_model=dict)
def post_thread_message(article_id: str, review_id: str, body: ThreadMessageCreate,
                         author_id: str, db: Session = Depends(deps.get_db)):
    """Post a message in a review thread. `author_id` query param identifies sender."""
    r = get_review(db, review_id)
    if r is None or r.article_id != article_id:
        raise HTTPException(status_code=404, detail="Review not found")
    from peerpedia_core.types.messages import ThreadMessage
    msg = ThreadMessage(author_id=author_id, content=body.content)
    add_thread_message(db, review_id, msg.to_dict())
    return {"status": "ok", "message": msg.to_dict()}
