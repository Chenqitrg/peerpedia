"""Feed API route."""
from fastapi import APIRouter, Depends
from peerpedia_core.storage.db.crud_article import list_articles
from peerpedia_core.storage.db.crud_user import get_following
from peerpedia_core.storage.db.models import User
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.helpers import (
    build_article_summary,
    resolve_authors,
)

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("")
def get_feed(current_user: User | None = Depends(deps.get_current_user),
             db: Session = Depends(deps.get_db)):
    """Articles from users the viewer follows, newest first."""
    all_articles = list_articles(db)
    if current_user:
        following = get_following(db, current_user.id)
        followed_ids = [u.id for u in following]
        if followed_ids:
            feed_articles = [a for a in all_articles
                             if any(aid in followed_ids for aid in (a.authors or []))
                             and a.status in ("sedimentation", "published")]
        else:
            feed_articles = []
    else:
        feed_articles = list(all_articles)

    feed_articles.sort(key=lambda a: a.created_at, reverse=True)

    # Batch-resolve all author IDs for efficiency
    all_author_ids: set[str] = set()
    for a in feed_articles:
        for aid in (a.authors or []):
            all_author_ids.add(aid)
    author_cache = {aid: resolve_authors(db, [aid])[0] for aid in all_author_ids}

    summaries = [
        build_article_summary(
            db, a,
            current_user=current_user,
            authors=[author_cache[aid] for aid in (a.authors or []) if aid in author_cache],
        )
        for a in feed_articles
    ]
    return {"articles": [s.model_dump() for s in summaries], "total": len(summaries)}
