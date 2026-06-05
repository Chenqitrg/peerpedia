"""Feed API route."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.schemas.article import ArticleSummary, AuthorInfo
from peerpedia_core.storage.db.crud_user import get_following, get_user
from peerpedia_core.storage.db.crud_article import list_articles
from peerpedia_core.storage.db.crud_bookmark import is_bookmarked
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, get_commit_history

router = APIRouter(prefix="/feed", tags=["feed"])


def _resolve_authors(db: Session, author_ids: list[str]) -> list[AuthorInfo]:
    result: list[AuthorInfo] = []
    for uid in author_ids:
        u = get_user(db, uid)
        if u:
            result.append(AuthorInfo(
                id=u.id, name=u.name, anonymous_name=u.anonymous_name,
                affiliation=u.affiliation, expertise=u.expertise,
            ))
        else:
            result.append(AuthorInfo(id=uid, name="unknown"))
    return result


def _get_commit_hash(article_id: str) -> str:
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        return ""
    commits = get_commit_history(rp, max_count=1)
    return commits[0]["hash"][:8] if commits else ""


def _get_content_preview(article_id: str, max_chars: int = 200) -> str:
    rp = DEFAULT_ARTICLES_DIR / article_id
    for ext in [".md", ".typ"]:
        f = rp / f"article{ext}"
        if f.exists():
            text = f.read_text()
            return text[:max_chars] + ("..." if len(text) > max_chars else "")
    return ""


def _get_commit_count(article_id: str) -> int:
    rp = DEFAULT_ARTICLES_DIR / article_id
    if not (rp / ".git").is_dir():
        return 0
    return len(get_commit_history(rp))


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
            authors=_resolve_authors(db, a.authors or []),
            content_preview=_get_content_preview(a.id),
            commit_hash=_get_commit_hash(a.id),
            fork_count=a.fork_count,
            forked_from=a.forked_from,
            commit_count=_get_commit_count(a.id),
            score=a.score,
            is_bookmarked=is_bookmarked(db, user_id, a.id),
            is_own_article=user_id in (a.authors or []),
            created_at=a.created_at,
        )
        for a in feed_articles
    ]
    return {"articles": [s.model_dump() for s in summaries], "total": len(summaries)}
