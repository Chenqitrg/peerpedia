"""Sedimentation pool API routes."""
from fastapi import APIRouter, Depends
from peerpedia_core.storage.db.crud_article import list_articles
from peerpedia_core.storage.db.crud_user import get_followers, get_following
from peerpedia_core.storage.db.models import User
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.helpers import (
    build_article_summary,
)

router = APIRouter(prefix="/pool", tags=["pool"])


@router.get("")
def get_pool(
    current_user: User | None = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """List sedimentation articles from followed/following users, sorted by remaining time descending."""
    from datetime import datetime, timedelta, timezone

    if current_user:
        follow_circle: set[str] = {current_user.id}
        for f in get_followers(db, current_user.id):
            follow_circle.add(f.id)
        for f in get_following(db, current_user.id):
            follow_circle.add(f.id)
    else:
        follow_circle = None

    articles = list_articles(db, status="sedimentation")
    now = datetime.now(timezone.utc)

    summaries = []
    for a in articles:
        if follow_circle is not None and not any(aid in follow_circle for aid in (a.authors or [])):
            continue

        # Compute sink ETA inline (same logic as helpers.compute_sink but kept local
        # to avoid circular dep between articles/_crud.py and pool.py)
        sink_eta, days_remaining = None, None
        if a.sink_start:
            st = a.sink_start
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
            eta = st + timedelta(days=a.sink_duration_days)
            sink_eta = eta
            days_remaining = max(0, (eta - now).days)

        summaries.append(build_article_summary(
            db, a,
            current_user=current_user,
            sink_eta=sink_eta,
            days_remaining=days_remaining,
            sink_duration_days=a.sink_duration_days,
        ))

    summaries.sort(key=lambda s: s.days_remaining or 0, reverse=True)
    return {"articles": [s.model_dump() for s in summaries], "total": len(summaries)}
