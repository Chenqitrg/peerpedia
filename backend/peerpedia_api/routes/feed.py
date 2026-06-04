"""Feed API route."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_core.storage.db.crud_user import get_following
from peerpedia_core.storage.db.crud_article import list_articles

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("")
def get_feed(user_id: str, db: Session = Depends(deps.get_db)):
    """Articles from users the viewer follows, newest first."""
    following = get_following(db, user_id)
    followed_ids = [u.id for u in following]
    if not followed_ids:
        return {"articles": [], "total": 0}

    all_articles = list_articles(db, status="published")
    feed_articles = [a for a in all_articles if any(aid in followed_ids for aid in a.authors)]
    feed_articles.sort(key=lambda a: a.created_at, reverse=True)

    return {
        "articles": [
            {"id": a.id, "title": getattr(a, "title", ""), "authors": a.authors,
             "status": a.status, "created_at": a.created_at.isoformat(),
             "score": a.score}
            for a in feed_articles
        ],
        "total": len(feed_articles),
    }
