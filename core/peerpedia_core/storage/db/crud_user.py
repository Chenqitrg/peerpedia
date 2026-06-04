"""User CRUD operations."""
import secrets

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import User, Follow


def _generate_anonymous_name() -> str:
    """Generate a random fixed anonymous name for a user."""
    adjectives = ["星云", "极光", "天狼", "猎户", "仙女", "北斗", "南十字", "麒麟",
                  "凤凰", "天龙", "白矮", "超新", "脉冲", "量子", "光子", "引力",
                  "暗物质", "反物质", "时空", "维度", "弦论", "拓扑"]
    nouns = ["观察者", "评审员", "学者", "旅人", "探索者", "记录者", "测量员", "解码者"]
    return f"{secrets.choice(adjectives)}{secrets.choice(nouns)}"


def create_user(
    session: Session,
    name: str,
    affiliation: str = "",
    anonymous_name: str | None = None,
) -> User:
    u = User(
        name=name,
        affiliation=affiliation,
        anonymous_name=anonymous_name or _generate_anonymous_name(),
    )
    session.add(u)
    session.commit()
    return u


def get_user(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)


def list_users(session: Session) -> list[User]:
    return session.query(User).order_by(User.created_at.desc()).all()


def update_user_reputation(session: Session, user_id: str, reputation: dict) -> User:
    u = session.get(User, user_id)
    if u is None:
        raise ValueError(f"User {user_id} not found")
    u.reputation = reputation
    session.commit()
    return u


# ── Follow ───────────────────────────────────────────────────────────────

def follow_user(session: Session, follower_id: str, followed_id: str) -> Follow:
    if follower_id == followed_id:
        raise ValueError("A user cannot follow themselves")
    f = Follow(follower_id=follower_id, followed_id=followed_id)
    session.add(f)
    session.commit()
    return f


def unfollow_user(session: Session, follower_id: str, followed_id: str) -> None:
    f = (
        session.query(Follow)
        .filter(Follow.follower_id == follower_id, Follow.followed_id == followed_id)
        .first()
    )
    if f:
        session.delete(f)
        session.commit()


def is_following(session: Session, follower_id: str, followed_id: str) -> bool:
    return (
        session.query(Follow)
        .filter(Follow.follower_id == follower_id, Follow.followed_id == followed_id)
        .first()
        is not None
    )


def get_followers(session: Session, user_id: str) -> list[User]:
    follower_ids = (
        session.query(Follow.follower_id)
        .filter(Follow.followed_id == user_id)
        .all()
    )
    ids = [row[0] for row in follower_ids]
    return session.query(User).filter(User.id.in_(ids)).all() if ids else []


def get_following(session: Session, user_id: str) -> list[User]:
    followed_ids = (
        session.query(Follow.followed_id)
        .filter(Follow.follower_id == user_id)
        .all()
    )
    ids = [row[0] for row in followed_ids]
    return session.query(User).filter(User.id.in_(ids)).all() if ids else []


def get_follower_count(session: Session, user_id: str) -> int:
    return (
        session.query(Follow)
        .filter(Follow.followed_id == user_id)
        .count()
    )


def get_following_count(session: Session, user_id: str) -> int:
    return (
        session.query(Follow)
        .filter(Follow.follower_id == user_id)
        .count()
    )
