# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

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
def get_feed(
    page: int = 1, size: int = 20, current_user: User | None = Depends(deps.get_current_user), db: Session = Depends(deps.get_db)
):
    """Articles from users the viewer follows, newest first."""
    if current_user:
        feed_articles = list_articles(
            db,
            follower_id=current_user.id,
            limit=size,
            offset=(page - 1) * size,
        )
        articles_for_count = list_articles(
            db,
            follower_id=current_user.id,
        )
    else:
        feed_articles = list_articles(
            db,
            limit=size,
            offset=(page - 1) * size,
        )
        articles_for_count = list_articles(db)

    # Batch-resolve author IDs
    feed_article_ids = [a.id for a in feed_articles]
    author_map = get_author_ids_batch(db, feed_article_ids)
    all_author_ids: set[str] = set()
    for aids in author_map.values():
        all_author_ids.update(aids)
    authors_list = resolve_authors(db, list(all_author_ids))
    author_cache = {a.id: a for a in authors_list}

    summaries = [
        build_article_summary(
            db,
            a,
            current_user=current_user,
            authors=[author_cache[aid] for aid in author_map.get(a.id, []) if aid in author_cache],
        )
        for a in feed_articles
    ]
    return {"articles": [s.model_dump() for s in summaries], "total": len(articles_for_count), "page": page, "size": size}


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

    articles = list_articles(db, follower_id=current_user.id)
    article_ids = [a.id for a in articles]
    author_map = get_author_ids_batch(db, article_ids)
    all_author_ids: set[str] = set()
    for aids in author_map.values():
        all_author_ids.update(aids)
    authors_list = resolve_authors(db, list(all_author_ids))
    author_cache = {a.id: a for a in authors_list}

    out = []
    for a in articles:
        authors = [author_cache[aid] for aid in author_map.get(a.id, []) if aid in author_cache]
        ghash, _gcount = get_git_meta(a.id)
        out.append(
            {
                "id": a.id,
                "title": a.title or "",
                "status": a.status,
                "authors": [m.model_dump() for m in authors],
                "commit_hash": ghash,
                "fork_count": a.fork_count,
                "forked_from": a.forked_from,
                "score": a.score,
                "created_at": a.created_at.isoformat(),
            }
        )

    return {"following_ids": following_ids, "articles": out}
