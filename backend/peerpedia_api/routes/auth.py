"""Authentication API routes."""
from fastapi import APIRouter, Depends, HTTPException
from peerpedia_core.storage.db.crud_article import count_articles
from peerpedia_core.storage.db.crud_user import (
    create_user,
    get_follower_count,
    get_following_count,
    get_user_by_username,
)
from peerpedia_core.storage.db.models import User
from sqlalchemy.orm import Session

from peerpedia_api.deps import (
    create_token,
    get_current_user,
    get_db,
    hash_password,
    verify_password,
)
from peerpedia_api.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from peerpedia_api.schemas.user import UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_profile(u: User, db: Session) -> UserProfile:
    return UserProfile(
        id=u.id,
        username=u.username or "",
        name=u.name,
        anonymous_name=u.anonymous_name or "",
        affiliation=u.affiliation or "",
        expertise=u.expertise or [],
        avatar_url=u.avatar_url,
        contact=u.contact,
        reputation=u.reputation or {},
        followers_count=get_follower_count(db, u.id),
        following_count=get_following_count(db, u.id),
        article_count=count_articles(db, author_id=u.id),
        created_at=u.created_at,
    )


@router.post("/register", status_code=201, response_model=AuthResponse)
def api_register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    # Check uniqueness
    if get_user_by_username(db, body.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    # Create user
    u = create_user(
        db,
        name=body.name,
        affiliation="",
        anonymous_name=None,
        username=body.username,
        password_hash=hash_password(body.password),
        email=body.email,
    )
    token = create_token(u.id)
    return AuthResponse(user=_user_to_profile(u, db), token=token)


@router.post("/login", response_model=AuthResponse)
def api_login(body: LoginRequest, db: Session = Depends(get_db)):
    """Log in with username and password."""
    u = get_user_by_username(db, body.username)
    if u is None or not verify_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(u.id)
    return AuthResponse(user=_user_to_profile(u, db), token=token)


@router.get("/me", response_model=AuthResponse)
def api_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user profile from token. Returns 401 if not authenticated."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return AuthResponse(user=_user_to_profile(user, db), token="")
