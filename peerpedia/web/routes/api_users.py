"""API routes for users, identities, and reputation."""

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

from peerpedia.web.db_session import get_db_session
from peerpedia_core.storage.db import (
    create_identity as db_create_identity,
)
from peerpedia_core.storage.db import (
    create_user as db_create_user,
)
from peerpedia_core.storage.db import (
    get_identities_for_user,
    get_user,
)


class UserCreateRequest(PydanticBaseModel):
    id: str
    name: str
    email: str
    affiliation: str | None = None
    expertise: list[str] = Field(default_factory=list)
    bio: str | None = None


class IdentityCreateRequest(PydanticBaseModel):
    type: str
    value: str
    verified: bool = False


router = APIRouter()


@router.get("/users/{user_id}")
async def api_get_user(user_id: str):
    """Get user profile with identities."""
    session = get_db_session()
    try:
        user = get_user(session, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        identities = get_identities_for_user(session, user_id)
        result = user.to_dict()
        result["identities"] = [i.to_dict() for i in identities]
        return result
    finally:
        session.close()


@router.post("/users")
async def api_create_user(req: UserCreateRequest):
    """Create (register) a new user."""
    session = get_db_session()
    try:
        existing = get_user(session, req.id)
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"User '{req.id}' already exists")
        user = db_create_user(
            session,
            id=req.id,
            name=req.name,
            email=req.email,
            affiliation=req.affiliation,
            expertise=req.expertise,
            bio=req.bio,
        )
        session.commit()
        return user.to_dict()
    finally:
        session.close()


@router.post("/users/{user_id}/identities")
async def api_create_identity(user_id: str, req: IdentityCreateRequest):
    """Bind a verified identity to a user."""
    session = get_db_session()
    try:
        user = get_user(session, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        weight_map = {
            "orcid": 100, "inst_email": 80, "arxiv": 60,
            "scholar": 50, "github": 30,
        }
        trust_weight_scaled = weight_map.get(req.type, 10)

        identity = db_create_identity(
            session,
            user_id=user_id,
            type=req.type,
            value=req.value,
            verified=req.verified,
            trust_weight=trust_weight_scaled,
        )
        session.commit()
        return identity.to_dict()
    finally:
        session.close()


@router.get("/users/{user_id}/reputation")
async def api_get_user_reputation(user_id: str):
    """Get the reputation vector for a user."""
    from peerpedia_core.reputation import ReputationV1

    session = get_db_session()
    try:
        algo = ReputationV1()
        vec = algo.compute(user_id, session=session)
        return vec.model_dump()
    finally:
        session.close()


# ── Follow ───────────────────────────────────────────────────────────────────


@router.post("/users/{user_id}/follow")
async def api_follow_user(user_id: str, follower_id: str = Form(...)):
    """Follow a user. Returns HTML button snippet."""
    from sqlalchemy.exc import IntegrityError

    from peerpedia_core.storage.db import (
        follow_user,
        get_user,
    )

    if follower_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    session = get_db_session()
    try:
        target = get_user(session, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="User not found")

        try:
            follow_user(session, follower_id=follower_id, followed_id=user_id)
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(status_code=409, detail="Already following")

        return HTMLResponse(f'''<div id="follow-area" style="margin-bottom: 12px;">
  <button hx-delete="/api/v1/users/{user_id}/follow"
          hx-vals='{{"follower_id": "{follower_id}"}}'
          hx-target="#follow-area"
          hx-swap="outerHTML"
          style="background: #28a745; color: white; border: none; padding: 6px 16px; border-radius: 4px; cursor: pointer;">
    已关注 ✓
  </button>
</div>''')
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/users/{user_id}/follow")
async def api_unfollow_user(user_id: str, follower_id: str = Form(...)):
    """Unfollow a user. Returns HTML button snippet."""
    from peerpedia_core.storage.db import (
        get_user,
        unfollow_user,
    )

    session = get_db_session()
    try:
        target = get_user(session, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="User not found")

        unfollow_user(session, follower_id=follower_id, followed_id=user_id)
        session.commit()

        return HTMLResponse(f'''<div id="follow-area" style="margin-bottom: 12px;">
  <button hx-post="/api/v1/users/{user_id}/follow"
          hx-vals='{{"follower_id": "{follower_id}"}}'
          hx-target="#follow-area"
          hx-swap="outerHTML"
          style="background: #007bff; color: white; border: none; padding: 6px 16px; border-radius: 4px; cursor: pointer;">
    + 关注
  </button>
</div>''')
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


def _render_user_list(users: list, viewer: str, *, field: str = "followed_id") -> str:
    """Render a following/followers list as an HTML fragment.

    field='followed_id' for following list, field='follower_id' for followers list.
    """
    if not users:
        return '<ul class="follow-list"><li class="follow-empty">暂无</li></ul>'
    items = []
    for u in users:
        uid = getattr(u, field, str(u))
        profile_url = f"/user/{uid}"
        if viewer:
            profile_url += f"?viewer={viewer}"
        items.append(f'<li><a href="{profile_url}" class="author-link">{uid}</a></li>')
    return f'<ul class="follow-list">{"".join(items)}</ul>'


@router.get("/users/{user_id}/following")
async def api_get_following(user_id: str, format: str = "json", viewer: str = ""):
    """Get users that user_id follows. format=html returns an HTML fragment."""
    from peerpedia_core.storage.db import get_following, get_user

    session = get_db_session()
    try:
        target = get_user(session, user_id)
        if target is None:
            if format == "html":
                return HTMLResponse('<p class="follow-empty">用户不存在</p>')
            raise HTTPException(status_code=404, detail="User not found")

        following = get_following(session, user_id)
        if format == "html":
            return HTMLResponse(_render_user_list(
                following, viewer, field="followed_id",
            ))

        return {
            "user_id": user_id,
            "users": [
                {
                    "user_id": f.followed_id,
                    "followed_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in following
            ],
            "total": len(following),
        }
    finally:
        session.close()


@router.get("/users/{user_id}/followers")
async def api_get_followers(user_id: str, format: str = "json", viewer: str = ""):
    """Get users that follow user_id. format=html returns an HTML fragment."""
    from peerpedia_core.storage.db import get_followers, get_user

    session = get_db_session()
    try:
        target = get_user(session, user_id)
        if target is None:
            if format == "html":
                return HTMLResponse('<p class="follow-empty">用户不存在</p>')
            raise HTTPException(status_code=404, detail="User not found")

        followers = get_followers(session, user_id)
        if format == "html":
            return HTMLResponse(_render_user_list(
                followers, viewer, field="follower_id",
            ))

        return {
            "user_id": user_id,
            "users": [
                {
                    "user_id": f.follower_id,
                    "followed_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in followers
            ],
            "total": len(followers),
        }
    finally:
        session.close()


def _collect_user_events(session, user_id: str, cutoff) -> list[dict]:
    """Collect new_article and new_version events for a single user within cutoff."""
    from peerpedia_core.storage.db import Article

    events = []
    # New articles
    articles = (
        session.query(Article)
        .filter(Article.founding_authors.contains(user_id), Article.created_at >= cutoff)
        .order_by(Article.created_at.desc())
        .all()
    )
    for a in articles:
        events.append({
            "type": "new_article", "user_id": user_id,
            "article_id": a.id, "article_title": a.title,
            "time": a.created_at.isoformat() if a.created_at else "",
        })

    # Version updates (exclude articles already counted as new_article)
    updated = (
        session.query(Article)
        .filter(Article.founding_authors.contains(user_id),
                Article.updated_at >= cutoff, Article.version > "v0.1")
        .order_by(Article.updated_at.desc())
        .all()
    )
    for a in updated:
        if a.created_at and a.created_at >= cutoff:
            continue
        events.append({
            "type": "new_version", "user_id": user_id,
            "article_id": a.id, "article_title": a.title,
            "version": a.version,
            "time": a.updated_at.isoformat() if a.updated_at else "",
        })
    return events


@router.get("/following/feed")
async def api_following_feed(user_id: str):
    """Get activity feed from followed users (last 30 days)."""
    from datetime import datetime, timedelta, timezone

    from peerpedia_core.storage.db import get_following

    session = get_db_session()
    try:
        following = get_following(session, user_id)
        followed_ids = [f.followed_id for f in following]

        if not followed_ids:
            return {"user_id": user_id, "events": []}

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        events = []
        for fid in followed_ids:
            events.extend(_collect_user_events(session, fid, cutoff))  # type: ignore[arg-type]

        events.sort(key=lambda e: e["time"], reverse=True)
        return {"user_id": user_id, "events": events[:50]}
    finally:
        session.close()
