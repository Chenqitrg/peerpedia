"""Sedimentation pool API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_core.storage.db.crud_article import list_articles, get_article
from peerpedia_core.storage.db.crud_review import get_reviews_for_article

router = APIRouter(prefix="/pool", tags=["pool"])


@router.get("")
def get_pool(db: Session = Depends(deps.get_db)):
    """List articles in the sedimentation pool, sorted by remaining time (ascending)."""
    articles = list_articles(db, status="sedimentation")
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    result = []
    for a in articles:
        days_remaining = 0
        sink_eta = None
        if a.sink_start:
            # SQLite stores naive datetime; assume UTC
            st = a.sink_start
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
            eta = st + timedelta(days=a.sink_duration_days)
            sink_eta = eta.isoformat()
            days_remaining = max(0, (eta - now).days)
        reviews = get_reviews_for_article(db, a.id)
        result.append({
            "id": a.id,
            "title": getattr(a, "title", ""),
            "authors": a.authors,
            "sink_eta": sink_eta,
            "days_remaining": days_remaining,
            "review_count": len(reviews),
            "forked_from": a.forked_from,
            "created_at": a.created_at.isoformat(),
        })
    result.sort(key=lambda x: x["days_remaining"])
    return {"articles": result, "total": len(result)}
