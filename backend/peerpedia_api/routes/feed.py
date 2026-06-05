"""Feed API route."""
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
from peerpedia_core.storage.db.crud_user import get_following
from peerpedia_core.storage.db.crud_article import list_articles
from peerpedia_core.storage.db.crud_bookmark import is_bookmarked

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("")
def get_feed(user_id: str | None = None, db: Session = Depends(deps.get_db)):
    """Articles from users the viewer follows, newest first."""
    all_articles = list_articles(db)
    if user_id:
        following = get_following(db, user_id)
        followed_ids = [u.id for u in following]
        if followed_ids:
            feed_articles = [a for a in all_articles
                             if any(aid in followed_ids for aid in (a.authors or []))]
        else:
            feed_articles = []
    else:
        # No user_id: return all articles as feed
        feed_articles = list(all_articles)

    feed_articles.sort(key=lambda a: a.created_at, reverse=True)

    summaries = [
        ArticleSummary(
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
            is_bookmarked=is_bookmarked(db, user_id, a.id),
            is_own_article=user_id in (a.authors or []),
            created_at=a.created_at,
        )
        for a in feed_articles
    ]
    return {"articles": [s.model_dump() for s in summaries], "total": len(summaries)}
