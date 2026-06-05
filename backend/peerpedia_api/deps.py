"""FastAPI dependency injection."""
import os
import time
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.engine import get_engine, get_session
from peerpedia_core.storage.db.models import User

_engine = None
_JWT_SECRET = os.environ.get("JWT_SECRET", "peerpedia-dev-secret")
_JWT_EXPIRY = 86400  # 24 hours


def get_db():
    """Yield a database session. Engine is cached across requests."""
    global _engine
    if _engine is None:
        _engine = get_engine("sqlite:///peerpedia.db")
    session = get_session(_engine)
    try:
        yield session
    finally:
        session.close()


# ── Password hashing ───────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ── JWT token ──────────────────────────────────────────────────────────

def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "iat": int(time.time()), "exp": int(time.time()) + _JWT_EXPIRY}
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> Optional[str]:
    """Decode JWT token, return user_id or None if invalid/expired."""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ── Auth dependencies ──────────────────────────────────────────────────

def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Extract current user from Bearer token. Returns None if invalid/missing."""
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    user_id = decode_token(token)
    if user_id is None:
        return None
    return db.get(User, user_id)


def require_user(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """Raise 401 if not authenticated."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
