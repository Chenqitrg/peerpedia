"""CRUD operations for ClickEvent and NodeInfo models."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import ClickEvent, NodeInfo


# ── ClickEvent CRUD ─────────────────────────────────────────────────────────────

def create_click_event(
    session: Session,
    *,
    from_article_id: str,
    to_article_id: str,
    node_id: str,
    user_id: Optional[str] = None,
) -> ClickEvent:
    """Record a citation click event."""
    event = ClickEvent(
        id=str(uuid.uuid4()),
        from_article_id=from_article_id,
        to_article_id=to_article_id,
        node_id=node_id,
        user_id=user_id,
    )
    session.add(event)
    return event


def get_click_events_for_article(
    session: Session,
    article_id: str,
    *,
    limit: int = 1000,
) -> list[ClickEvent]:
    """Get click events originating from an article, most recent first."""
    return (
        session.query(ClickEvent)
        .filter(ClickEvent.from_article_id == article_id)
        .order_by(ClickEvent.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_local_click_counts(
    session: Session,
    from_article_id: str,
) -> dict[str, int]:
    """Get local click counts per target article from a given source article.

    Returns dict mapping to_article_id -> click count.
    """
    rows = (
        session.query(
            ClickEvent.to_article_id,
            func.count(ClickEvent.id).label("cnt"),
        )
        .filter(ClickEvent.from_article_id == from_article_id)
        .group_by(ClickEvent.to_article_id)
        .all()
    )
    return {row.to_article_id: row.cnt for row in rows}


# ── NodeInfo CRUD ───────────────────────────────────────────────────────────────

def upsert_node(
    session: Session,
    *,
    node_id: str,
    host: str,
    port: int,
    version: str = "0.2.0",
    articles_count: int = 0,
    is_self: bool = False,
) -> NodeInfo:
    """Insert or update a LAN node record on heartbeat."""
    node = session.query(NodeInfo).filter(NodeInfo.node_id == node_id).first()
    if node:
        node.host = host
        node.port = port
        node.version = version
        node.articles_count = articles_count
        node.is_self = 1 if is_self else 0
        node.last_seen = datetime.now(timezone.utc)
    else:
        node = NodeInfo(
            node_id=node_id,
            host=host,
            port=port,
            version=version,
            articles_count=articles_count,
            is_self=1 if is_self else 0,
        )
        session.add(node)
    return node


def get_online_nodes(
    session: Session,
    *,
    timeout_seconds: float = 30.0,
) -> list[NodeInfo]:
    """Get nodes that have been seen within the timeout window."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
    return (
        session.query(NodeInfo)
        .filter(NodeInfo.last_seen >= cutoff)
        .order_by(NodeInfo.last_seen.desc())
        .all()
    )


def cleanup_stale_nodes(
    session: Session,
    *,
    max_age_seconds: float = 3600.0,
) -> int:
    """Remove nodes not seen for over an hour. Returns count of removed nodes."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    result = (
        session.query(NodeInfo)
        .filter(NodeInfo.last_seen < cutoff, NodeInfo.is_self == 0)
        .delete()
    )
    return result
