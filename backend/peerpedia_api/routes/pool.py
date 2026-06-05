"""Sedimentation pool API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.helpers import (
    resolve_authors,
    get_commit_hash,
    get_content_preview,
    get_commit_count,
)
from peerpedia_api.schemas.article import ArticleSummary
from peerpedia_core.storage.db.crud_article import list_articles
from peerpedia_core.storage.db.crud_review import get_reviews_for_article
from peerpedia_core.storage.db.crud_user import get_followers, get_following
from peerpedia_core.storage.db.crud_bookmark import is_bookmarked

router = APIRouter(prefix="/pool", tags=["pool"])


@router.get("")
def get_pool(
    user_id: str | None = None,
    db: Session = Depends(deps.get_db),
):
    """List sedimentation articles from followed/following users, sorted by remaining time descending."""
    from datetime import datetime, timezone, timedelta

    # Build the set of user IDs in the user's follow circle
    if user_id:
        follow_circle: set[str] = {user_id}
        for f in get_followers(db, user_id):
            follow_circle.add(f.id)
        for f in get_following(db, user_id):
            follow_circle.add(f.id)
    else:
        follow_circle = None

    articles = list_articles(db, status="sedimentation")
    now = datetime.now(timezone.utc)

    summaries = []
    for a in articles:
        # Only show articles from users in follow circle (if user_id provided)
        if follow_circle is not None and not any(aid in follow_circle for aid in (a.authors or [])):
            continue

        reviews = get_reviews_for_article(db, a.id)
        sink_eta, days_remaining = None, None
        if a.sink_start:
            st = a.sink_start
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
            eta = st + timedelta(days=a.sink_duration_days)
            sink_eta = eta
            days_remaining = max(0, (eta - now).days)

        summaries.append(ArticleSummary(
            id=a.id,
            title=a.title or "",
            status=a.status,
            authors=resolve_authors(db, a.authors or []),
            content_preview=get_content_preview(a.id),
            commit_hash=get_commit_hash(a.id),
            fork_count=a.fork_count,
            forked_from=a.forked_from,
            commit_count=get_commit_count(a.id),
            score=a.score,
            sink_eta=sink_eta,
            days_remaining=days_remaining,
            sink_duration_days=a.sink_duration_days,
            is_bookmarked=is_bookmarked(db, user_id, a.id) if user_id else False,
            is_own_article=user_id in (a.authors or []) if user_id else False,
            created_at=a.created_at,
        ))

    # Sort descending: highest days_remaining first ("sinking" effect)
    summaries.sort(key=lambda s: s.days_remaining or 0, reverse=True)
    return {"articles": [s.model_dump() for s in summaries], "total": len(summaries)}
