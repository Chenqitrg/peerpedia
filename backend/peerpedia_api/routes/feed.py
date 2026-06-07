"""Feed API route."""
from fastapi import APIRouter, Depends
from peerpedia_core.storage.db.crud_article import list_articles
from peerpedia_core.storage.db.crud_bookmark import is_bookmarked
from peerpedia_core.storage.db.crud_user import get_following
from peerpedia_core.storage.db.models import User
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.helpers import (
    get_content_preview,
    get_git_meta,
    resolve_authors,
)
from peerpedia_api.schemas.article import ArticleSummary

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

    # Batch-resolve all author IDs
    all_author_ids: set[str] = set()
    for a in feed_articles:
        for aid in (a.authors or []):
            all_author_ids.add(aid)
    author_cache = {aid: resolve_authors(db, [aid])[0] for aid in all_author_ids}

    # Build summaries — get git meta once per article
    summaries: list[ArticleSummary] = []
    for a in feed_articles:
        ghash, gcount = get_git_meta(a.id)
        summaries.append(ArticleSummary(
            id=a.id,
            title=a.title or "",
            status=a.status,
            authors=[author_cache[aid] for aid in (a.authors or []) if aid in author_cache],
            content_preview=get_content_preview(a.id),
            commit_hash=ghash,
            fork_count=a.fork_count,
            forked_from=a.forked_from,
            commit_count=gcount,
            score=a.score,
            is_bookmarked=is_bookmarked(db, current_user.id, a.id) if current_user else False,
            is_own_article=current_user.id in (a.authors or []) if current_user else False,
            created_at=a.created_at,
        ))
    return {"articles": [s.model_dump() for s in summaries], "total": len(summaries)}
