"""Review CRUD operations."""
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Review


def create_review(
    session: Session,
    article_id: str,
    commit_hash: str,
    reviewer_id: str,
    scope: str,
    scores: dict,
) -> Review:
    r = Review(
        article_id=article_id,
        commit_hash=commit_hash,
        reviewer_id=reviewer_id,
        scope=scope,
        scores=scores,
    )
    session.add(r)
    session.commit()
    return r


def get_review(session: Session, review_id: str) -> Review | None:
    return session.get(Review, review_id)


def get_reviews_for_article(session: Session, article_id: str) -> list[Review]:
    return (
        session.query(Review)
        .filter(Review.article_id == article_id)
        .order_by(Review.created_at.desc())
        .all()
    )


def get_review_by_user_scope(
    session: Session, article_id: str, reviewer_id: str, scope: str
) -> Review | None:
    return (
        session.query(Review)
        .filter(
            Review.article_id == article_id,
            Review.reviewer_id == reviewer_id,
            Review.scope == scope,
        )
        .first()
    )


def upsert_review(
    session: Session,
    article_id: str,
    commit_hash: str,
    reviewer_id: str,
    scope: str,
    scores: dict,
) -> Review:
    """Create or update a review for the given (article, reviewer, scope)."""
    existing = get_review_by_user_scope(session, article_id, reviewer_id, scope)
    if existing:
        existing.commit_hash = commit_hash
        existing.scores = scores
        session.commit()
        return existing
    return create_review(session, article_id, commit_hash, reviewer_id, scope, scores)


def update_review_scores(session: Session, review_id: str, scores: dict) -> Review:
    r = session.get(Review, review_id)
    if r is None:
        raise ValueError(f"Review {review_id} not found")
    r.scores = scores
    session.commit()
    return r


def add_thread_message(session: Session, review_id: str, message: dict) -> Review:
    r = session.get(Review, review_id)
    if r is None:
        raise ValueError(f"Review {review_id} not found")
    thread = list(r.thread) if r.thread else []
    thread.append(message)
    r.thread = thread
    session.commit()
    return r
