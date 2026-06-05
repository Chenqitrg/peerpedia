"""Authentication API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_api.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from peerpedia_api.schemas.user import UserProfile
from peerpedia_api.deps import (
    get_db, get_current_user, hash_password, verify_password, create_token,
)
from peerpedia_core.storage.db.models import User
from peerpedia_core.storage.db.crud_user import create_user, get_user_by_username, get_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_profile(u: User) -> UserProfile:
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
    return AuthResponse(user=_user_to_profile(u), token=token)


@router.post("/login", response_model=AuthResponse)
def api_login(body: LoginRequest, db: Session = Depends(get_db)):
    """Log in with username and password."""
    u = get_user_by_username(db, body.username)
    if u is None or not verify_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(u.id)
    return AuthResponse(user=_user_to_profile(u), token=token)


@router.get("/me", response_model=AuthResponse)
def api_me(user: User = Depends(get_current_user)):
    """Get current user profile from token. Returns 401 if not authenticated."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return AuthResponse(user=_user_to_profile(user), token="")
