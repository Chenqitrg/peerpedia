"""Review CRUD operations."""
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Review, ReviewMessage


def create_review(
    session: Session,
    article_id: str,
    commit_hash: str,
    reviewer_id: str,
    scope: str,
    scores: dict,
    contributions: dict | None = None,
) -> Review:
    r = Review(
        article_id=article_id,
        commit_hash=commit_hash,
        reviewer_id=reviewer_id,
        scope=scope,
        scores=scores,
        contributions=contributions,
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
    session: Session, article_id: str, reviewer_id: str, scope: str,
    commit_hash: str | None = None,
) -> Review | None:
    q = (
        session.query(Review)
        .filter(
            Review.article_id == article_id,
            Review.reviewer_id == reviewer_id,
            Review.scope == scope,
        )
    )
    if commit_hash is not None:
        q = q.filter(Review.commit_hash == commit_hash)
    return q.first()


def upsert_review(
    session: Session,
    article_id: str,
    commit_hash: str,
    reviewer_id: str,
    scope: str,
    scores: dict,
    contributions: dict | None = None,
) -> Review:
    """Create or update a review for the given (article, reviewer, scope, commit_hash)."""
    existing = get_review_by_user_scope(session, article_id, reviewer_id, scope,
                                        commit_hash=commit_hash)
    if existing:
        existing.scores = scores
        if contributions is not None:
            existing.contributions = contributions
        session.commit()
        return existing
    return create_review(session, article_id, commit_hash, reviewer_id, scope,
                         scores, contributions=contributions)


def update_review_scores(session: Session, review_id: str, scores: dict) -> Review:
    r = session.get(Review, review_id)
    if r is None:
        raise ValueError(f"Review {review_id} not found")
    r.scores = scores
    session.commit()
    return r


# ── Thread messages (ReviewMessage table) ──────────────────────────────────


def add_thread_message(
    session: Session,
    review_id: str,
    author_id: str,
    content: str,
    parent_id: str | None = None,
) -> ReviewMessage:
    """Add a reply to a review thread. Returns the new message."""
    # Verify review exists
    if session.get(Review, review_id) is None:
        raise ValueError(f"Review {review_id} not found")
    msg = ReviewMessage(
        review_id=review_id,
        author_id=author_id,
        content=content,
        parent_id=parent_id,
    )
    session.add(msg)
    session.commit()
    return msg


def get_thread_messages(
    session: Session,
    review_id: str,
    page: int = 1,
    page_size: int = 20,
) -> list[ReviewMessage]:
    """Get paginated thread messages for a review, oldest first."""
    return (
        session.query(ReviewMessage)
        .filter(ReviewMessage.review_id == review_id)
        .order_by(ReviewMessage.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def get_thread_message_count(session: Session, review_id: str) -> int:
    """Count total messages in a review thread."""
    return (
        session.query(ReviewMessage)
        .filter(ReviewMessage.review_id == review_id)
        .count()
    )
