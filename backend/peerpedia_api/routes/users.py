"""User API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.schemas.user import UserProfile, UserSummary, UserCreate, UserUpdate
from peerpedia_api.deps import get_current_user, require_user, hash_password
from peerpedia_core.storage.db.crud_user import (
    create_user, get_user, list_users,
    follow_user, unfollow_user, is_following,
    get_followers, get_following, get_follower_count, get_following_count,
)
from peerpedia_core.storage.db.crud_article import list_articles
from peerpedia_core.storage.db.models import User

router = APIRouter(prefix="/users", tags=["users"])

# ── Users ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[UserSummary])
def api_list_users(db: Session = Depends(deps.get_db)):
    from peerpedia_core.storage.db.models import Article
    users = list_users(db)
    out = []
    for u in users:
        article_count = db.query(Article).filter(
            Article.authors.contains([u.id])
        ).count()
        out.append(UserSummary(
            id=u.id, name=u.name, anonymous_name=u.anonymous_name,
            affiliation=u.affiliation, expertise=u.expertise,
            avatar_url=u.avatar_url,
            article_count=article_count,
            reputation=u.reputation or {},
        ))
    return out


@router.post("", status_code=201, response_model=UserProfile)
def api_create_user(body: UserCreate, db: Session = Depends(deps.get_db)):
    u = create_user(db, name=body.name, affiliation=body.affiliation,
                    username=body.username,
                    password_hash=hash_password(body.password),
                    email=body.email)
    if body.expertise:
        u.expertise = body.expertise
    if body.avatar_url:
        u.avatar_url = body.avatar_url
    if body.contact:
        u.contact = body.contact
    if body.expertise or body.avatar_url or body.contact:
        db.commit()
    return UserProfile(id=u.id, username=u.username or "", name=u.name,
                       anonymous_name=u.anonymous_name or "",
                       affiliation=u.affiliation or "",
                       expertise=u.expertise or [],
                       avatar_url=u.avatar_url, contact=u.contact,
                       reputation=u.reputation or {},
                       followers_count=0, following_count=0, article_count=0,
                       created_at=u.created_at)


@router.get("/{user_id}", response_model=UserProfile)
def api_get_user(user_id: str, db: Session = Depends(deps.get_db)):
    u = get_user(db, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found")
    articles = [a for a in list_articles(db) if user_id in a.authors]
    return UserProfile(
        id=u.id, username=u.username or "", name=u.name,
        anonymous_name=u.anonymous_name or "",
        affiliation=u.affiliation or "",
        expertise=u.expertise or [],
        avatar_url=u.avatar_url, contact=u.contact,
        reputation=u.reputation or {},
        followers_count=get_follower_count(db, user_id),
        following_count=get_following_count(db, user_id),
        article_count=len(articles),
        created_at=u.created_at,
    )


@router.put("/{user_id}", response_model=UserProfile)
def api_update_user(user_id: str, body: UserUpdate,
                    db: Session = Depends(deps.get_db),
                    current_user: User = Depends(require_user)):
    """Update user profile. Only self-editable. Name is immutable."""
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Cannot edit another user's profile")
    u = get_user(db, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found")
    changed = False
    if body.anonymous_name is not None:
        u.anonymous_name = body.anonymous_name
        changed = True
    if body.affiliation is not None:
        u.affiliation = body.affiliation
        changed = True
    if body.expertise is not None:
        u.expertise = body.expertise
        changed = True
    if body.avatar_url is not None:
        u.avatar_url = body.avatar_url
        changed = True
    if body.contact is not None:
        u.contact = body.contact
        changed = True
    if changed:
        db.commit()
    return api_get_user(user_id, db=db)


# ── Follow ───────────────────────────────────────────────────────────────

@router.get("/{user_id}/followers", response_model=list[UserSummary])
def api_get_followers(user_id: str, db: Session = Depends(deps.get_db)):
    from peerpedia_core.storage.db.models import Article
    users = get_followers(db, user_id)
    out = []
    for u in users:
        article_count = db.query(Article).filter(
            Article.authors.contains([u.id])
        ).count()
        out.append(UserSummary(
            id=u.id, name=u.name, affiliation=u.affiliation,
            expertise=u.expertise,
            article_count=article_count, reputation=u.reputation or {},
        ))
    return out


@router.get("/{user_id}/following", response_model=list[UserSummary])
def api_get_following(user_id: str, db: Session = Depends(deps.get_db)):
    from peerpedia_core.storage.db.models import Article
    users = get_following(db, user_id)
    out = []
    for u in users:
        article_count = db.query(Article).filter(
            Article.authors.contains([u.id])
        ).count()
        out.append(UserSummary(
            id=u.id, name=u.name, affiliation=u.affiliation,
            expertise=u.expertise,
            article_count=article_count, reputation=u.reputation or {},
        ))
    return out


@router.post("/{user_id}/follow", status_code=201)
def api_follow(user_id: str, current_user: User = Depends(require_user),
               db: Session = Depends(deps.get_db)):
    if get_user(db, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not is_following(db, current_user.id, user_id):
        follow_user(db, current_user.id, user_id)
    return {"status": "ok", "following": True}


@router.delete("/{user_id}/follow")
def api_unfollow(user_id: str, current_user: User = Depends(require_user),
                 db: Session = Depends(deps.get_db)):
    unfollow_user(db, current_user.id, user_id)
    return {"status": "ok", "following": False}
