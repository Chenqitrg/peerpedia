"""Sedimentation pool logic — sink time calculation and auto-publish."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from peerpedia_core.config.params import params
from peerpedia_core.storage.db.models import Article


def compute_sink_eta(
    sink_start: datetime,
    avg_score: float,
    min_days: int = 2,
    max_days: int = 180,
) -> datetime:
    """Compute when an article exits the sedimentation pool.

    Uses a linear interpolation: score 5.0 → min_days, score 0.0 → max_days.
    Higher scores mean shorter (faster) sink times.

    The function is replaceable via params.score.score_to_sink_multiplier.
    """
    multiplier = params.score.score_to_sink_multiplier(avg_score)
    # multiplier = 0 for 5.0 (shortest), multiplier = 1 for 0.0 (longest)
    actual_days = min_days + multiplier * (max_days - min_days)
    return sink_start + timedelta(days=actual_days)


def is_ready_to_publish(sink_eta: datetime | None) -> bool:
    """Check if the sink time has elapsed. Returns False if sink_eta is None."""
    if sink_eta is None:
        return False
    now = datetime.now(timezone.utc)
    if sink_eta.tzinfo is None:
        sink_eta = sink_eta.replace(tzinfo=timezone.utc)
    return now >= sink_eta


def apply_no_review_penalty(scores: dict | None) -> dict:
    """Apply penalty when an article receives zero reviews in the pool.

    Returns a new scores dict with penalty applied (each dimension reduced).
    Returns empty dict if scores is None.
    """
    if scores is None:
        return {}
    penalty = params.score.no_review_penalty()
    return {
        dim: max(0.0, value - penalty)
        for dim, value in scores.items()
    }


def publish_ready_articles(session: Session) -> int:
    """Scan all articles in sedimentation, publish those whose sink time has elapsed.

    For each ready article:
    1. Compute the final score from reviews for the current commit.
    2. If there are zero community reviews, apply the no-review penalty.
    3. Update status to "published" and save the score.
    4. Recalculate reputations for all authors.

    Returns the number of articles published in this call.
    """
    from peerpedia_core.storage.db.crud_review import get_reviews_for_article
    from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, get_commit_history
    from peerpedia_core.workflow.reputation import compute_author_reputation
    from peerpedia_core.workflow.scoring import compute_article_score_for_commit

    articles = session.query(Article).filter(Article.status == "sedimentation").all()

    published_count = 0

    for article in articles:
        if article.sink_start is None:
            continue

        st = article.sink_start
        if st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        eta = st + timedelta(days=article.sink_duration_days)

        if not is_ready_to_publish(eta):
            continue

        # Get the latest commit hash for score computation
        rp = DEFAULT_ARTICLES_DIR / article.id
        commit_hash = None
        if (rp / ".git").is_dir():
            commits = get_commit_history(rp)
            if commits:
                commit_hash = commits[0]["hash"]

        # Compute final score
        if commit_hash:
            score = compute_article_score_for_commit(session, article.id, commit_hash)
        else:
            score = article.score

        # Check for community reviews and apply penalty if none
        all_reviews = get_reviews_for_article(session, article.id)
        authors = get_article_authors(session, article.id)
        community_reviews = [r for r in all_reviews if r.reviewer_id not in authors]
        if len(community_reviews) == 0:
            score = apply_no_review_penalty(score)

        # Update article
        article.status = "published"
        if score:
            article.score = score
        session.commit()

        # Recalculate reputation for all authors
        for author_id in authors:
            compute_author_reputation(session, author_id)

        published_count += 1

    return published_count
