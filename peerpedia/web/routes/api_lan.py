"""Web -- LAN catalog and node discovery API endpoints."""

from fastapi import APIRouter

from peerpedia.web.db_session import get_db_session
from peerpedia_core.storage.db import (
    get_online_nodes,
    list_articles,
    get_local_click_counts,
)

router = APIRouter()


@router.get("/lan/catalog")
async def get_catalog():
    """Return this node's catalog.md content (YAML + Markdown).

    Response is plain text (text/plain) since catalog.md is a markdown file.
    """
    from peerpedia_core.workflow.lan import catalog_to_yaml_string
    from datetime import datetime, timezone
    from fastapi.responses import PlainTextResponse

    session = get_db_session()
    try:
        articles = list_articles(session, limit=10000)
        article_data = []
        for a in articles:
            d = a.to_dict()
            refs = []
            for ref in (a.references or []):
                target_id = ref.get("article_id") if isinstance(ref, dict) else ref
                if target_id:
                    clicks = get_local_click_counts(session, a.id).get(target_id, 0)
                    refs.append({
                        "target": target_id,
                        "title": ref.get("title", "") if isinstance(ref, dict) else "",
                        "clicks_local": clicks,
                    })
            article_data.append({
                "id": d["id"],
                "title": d["title"],
                "authors": d["founding_authors"],
                "version": d["version"],
                "cid": d.get("cid"),
                "references": refs,
            })

        catalog_data = {
            "node_id": "local",
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "articles": article_data,
        }
        return PlainTextResponse(content=catalog_to_yaml_string(catalog_data))
    finally:
        session.close()


@router.get("/lan/nodes")
async def get_nodes():
    """Return list of currently online LAN nodes."""
    session = get_db_session()
    try:
        nodes = get_online_nodes(session, timeout_seconds=30.0)
        return {
            "nodes": [n.to_dict() for n in nodes],
            "total": len(nodes),
        }
    finally:
        session.close()


@router.get("/lan/status")
async def get_lan_status():
    """Overall LAN status summary."""
    session = get_db_session()
    try:
        from peerpedia_core.storage.db.models import NodeInfo
        online = get_online_nodes(session, timeout_seconds=30.0)
        all_nodes = session.query(NodeInfo).all()
        return {
            "online_nodes": len(online),
            "total_nodes_seen": len(all_nodes),
            "nodes": [n.to_dict() for n in online],
        }
    finally:
        session.close()
