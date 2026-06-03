"""CRUD operations for User, Identity, and Follow models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Follow, Identity, User


# ── User CRUD ───────────────────────────────────────────────────────────────────

def create_user(
    session: Session,
    *,
    id: str,
    name: str,
    email: str,
    affiliation: Optional[str] = None,
    expertise: Optional[list[str]] = None,
    bio: Optional[str] = None,
    public_key: Optional[str] = None,
) -> User:
    """Create a new user record."""
    user = User(
        id=id,
        name=name,
        email=email,
        affiliation=affiliation,
        expertise=expertise or [],
        bio=bio,
        public_key=public_key,
    )
    session.add(user)
    return user


def get_user(session: Session, user_id: str) -> Optional[User]:
    """Get a user by ID, or None."""
    return session.query(User).filter(User.id == user_id).first()


def update_user_last_active(session: Session, user_id: str) -> Optional[User]:
    """Update a user's last_active timestamp to now."""
    user = get_user(session, user_id)
    if user:
        user.last_active = datetime.now(timezone.utc)
    return user


# ── Identity CRUD ───────────────────────────────────────────────────────────────

def create_identity(
    session: Session,
    *,
    user_id: str,
    type: str,
    value: str,
    verified: bool = False,
    trust_weight: int = 10,
) -> Identity:
    """Create an identity binding for a user.

    trust_weight is scaled ×100 (e.g., 100 for ORCID = 1.0 weight).
    """
    identity = Identity(
        id=str(uuid.uuid4()),
        user_id=user_id,
        type=type,
        value=value,
        verified=1 if verified else 0,
        trust_weight=trust_weight,
    )
    session.add(identity)
    return identity


def get_identities_for_user(session: Session, user_id: str) -> list[Identity]:
    """Get all identity bindings for a user."""
    return session.query(Identity).filter(Identity.user_id == user_id).all()


# ── Follow CRUD ─────────────────────────────────────────────────────────────────

def follow_user(
    session: Session,
    *,
    follower_id: str,
    followed_id: str,
) -> Follow:
    """Create a follow relationship. Raises IntegrityError on duplicate."""
    follow = Follow(
        follower_id=follower_id,
        followed_id=followed_id,
    )
    session.add(follow)
    session.flush()  # Trigger IntegrityError immediately
    return follow


def unfollow_user(
    session: Session,
    *,
    follower_id: str,
    followed_id: str,
) -> bool:
    """Remove a follow relationship. Returns True if a row was deleted."""
    result = (
        session.query(Follow)
        .filter(
            Follow.follower_id == follower_id,
            Follow.followed_id == followed_id,
        )
        .delete()
    )
    return result > 0


def is_following(
    session: Session,
    follower_id: str,
    followed_id: str,
) -> bool:
    """Check if follower_id follows followed_id."""
    return (
        session.query(Follow)
        .filter(
            Follow.follower_id == follower_id,
            Follow.followed_id == followed_id,
        )
        .first()
        is not None
    )


def get_following(
    session: Session,
    user_id: str,
) -> list[Follow]:
    """Get users that user_id follows, newest first."""
    return (
        session.query(Follow)
        .filter(Follow.follower_id == user_id)
        .order_by(Follow.created_at.desc())
        .all()
    )


def get_followers(
    session: Session,
    user_id: str,
) -> list[Follow]:
    """Get users that follow user_id, newest first."""
    return (
        session.query(Follow)
        .filter(Follow.followed_id == user_id)
        .order_by(Follow.created_at.desc())
        .all()
    )


def get_following_count(session: Session, user_id: str) -> int:
    """Count how many users user_id follows."""
    return (
        session.query(Follow)
        .filter(Follow.follower_id == user_id)
        .count()
    )


def get_follower_count(session: Session, user_id: str) -> int:
    """Count how many users follow user_id."""
    return (
        session.query(Follow)
        .filter(Follow.followed_id == user_id)
        .count()
    )
