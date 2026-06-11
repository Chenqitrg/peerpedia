"""Feed API route."""
from fastapi import APIRouter, Depends
from peerpedia_core.storage.db.crud_article import get_author_ids_batch, list_articles
from peerpedia_core.storage.db.crud_user import get_following
from peerpedia_core.storage.db.models import User
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.helpers import (
    build_article_summary,
    get_git_meta,
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
            # Batch-resolve all author IDs
            all_article_ids = [a.id for a in all_articles]
            author_map = get_author_ids_batch(db, all_article_ids)
            feed_articles = [a for a in all_articles
                             if any(aid in followed_ids for aid in author_map.get(a.id, []))
                             and a.status in ("sedimentation", "published")]
        else:
            feed_articles = []
    else:
        feed_articles = list(all_articles)

    feed_articles.sort(key=lambda a: a.created_at, reverse=True)

    # Batch-resolve all author IDs for efficiency
    feed_article_ids = [a.id for a in feed_articles]
    author_map = get_author_ids_batch(db, feed_article_ids)
    all_author_ids: set[str] = set()
    for aids in author_map.values():
        all_author_ids.update(aids)
    author_cache = {aid: resolve_authors(db, [aid])[0] for aid in all_author_ids}

    summaries = [
        build_article_summary(
            db, a,
            current_user=current_user,
            authors=[author_cache[aid] for aid in author_map.get(a.id, []) if aid in author_cache],
        )
        for a in feed_articles
    ]
    return {"articles": [s.model_dump() for s in summaries], "total": len(summaries)}


@router.get("/cache")
def get_feed_cache(
    current_user: User = Depends(deps.require_user),
    db: Session = Depends(deps.get_db),
):
    """Lightweight feed data for offline cache refresh.

    Returns the viewer's following IDs plus article metadata from followed
    authors — without abstract or content_preview to keep the cache small.
    """
    following = get_following(db, current_user.id)
    following_ids = [u.id for u in following]

    if not following_ids:
        return {"following_ids": [], "articles": []}

    all_articles = list_articles(db)
    all_article_ids = [a.id for a in all_articles]
    author_map = get_author_ids_batch(db, all_article_ids)
    feed_articles = [
        a for a in all_articles
        if any(aid in following_ids for aid in author_map.get(a.id, []))
        and a.status in ("sedimentation", "published")
    ]
    feed_articles.sort(key=lambda a: a.created_at, reverse=True)

    # Resolve authors for the feed articles.
    feed_article_ids = [a.id for a in feed_articles]
    author_map_feed = get_author_ids_batch(db, feed_article_ids)
    all_author_ids: set[str] = set()
    for aids in author_map_feed.values():
        all_author_ids.update(aids)
    author_cache = {aid: resolve_authors(db, [aid])[0] for aid in all_author_ids}

    articles = []
    for a in feed_articles:
        authors = [author_cache[aid] for aid in author_map_feed.get(a.id, []) if aid in author_cache]
        ghash, _gcount = get_git_meta(a.id)
        articles.append({
            "id": a.id,
            "title": a.title or "",
            "status": a.status,
            "authors": [m.model_dump() for m in authors],
            "commit_hash": ghash,
            "fork_count": a.fork_count,
            "forked_from": a.forked_from,
            "score": a.score,
            "created_at": a.created_at.isoformat(),
        })

    return {"following_ids": following_ids, "articles": articles}
