"""Layer 1: Citation scanner and graph builder.

Extracts peerpedia intra-site references from Typst/Markdown source,
builds a NetworkX citation Directed Acyclic Graph, and provides
cites/cited_by query functions.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import networkx as nx

# Regex: match peerpedia:<UUID> in text, or inside #cite("peerpedia:<UUID>")
_CITE_RE = re.compile(
    r'(?:#cite\s*\(\s*"peerpedia:)?'
    r'peerpedia:'
    r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
    r'(?:"\s*\))?'
)


def extract_references(source: str) -> list[str]:
    """Scan source text for peerpedia article references.

    Supports two formats:
    - Typst:    #cite("peerpedia:<article-id>")
    - Inline:   peerpedia:<article-id>  (anywhere in text)

    Returns deduplicated list of article IDs, in order of first appearance.
    """
    seen = set()
    result = []
    for m in _CITE_RE.finditer(source):
        aid = m.group(1)
        if aid not in seen:
            seen.add(aid)
            result.append(aid)
    return result


def inject_citation_links(html: str) -> str:
    """Replace peerpedia:<id> references with clickable HTML links."""
    def replacement(match):
        aid = match.group(1)
        return (
            f'<a href="/article/{aid}" class="citation-link" '
            f'data-target-id="{aid}">引用文章</a>'
        )

    return re.sub(
        r'peerpedia:([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})',
        replacement,
        html,
    )


def build_citation_graph(session) -> "nx.DiGraph":
    """Build a NetworkX DiGraph from all articles' references.

    Nodes: article IDs (with title attribute)
    Edges: A -> B means "A cites B"
    """
    import networkx as nx

    from peerpedia_core.storage.db import Article

    G = nx.DiGraph()
    articles = session.query(Article).all()
    for a in articles:
        G.add_node(a.id, title=a.title)
        for ref in (a.references or []):
            target_id = ref.get("article_id") if isinstance(ref, dict) else ref
            if target_id:
                G.add_edge(a.id, target_id)
    return G


def get_citation_info(
    session, article_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Get citation information for an article.

    Returns:
        {"cites": [{"id": ..., "title": ...}, ...],
         "cited_by": [{"id": ..., "title": ...}, ...]}
    """
    from peerpedia_core.storage.db import Article

    article = session.query(Article).filter(Article.id == article_id).first()

    # What this article cites
    cites = []
    if article and article.references:
        for ref in article.references:
            target_id = ref.get("article_id") if isinstance(ref, dict) else ref
            if target_id:
                target = session.query(Article).filter(
                    Article.id == target_id
                ).first()
                cites.append({
                    "id": target_id,
                    "title": target.title if target else target_id[:8] + "...",
                })

    # Who cites this article (reverse lookup)
    cited_by = []
    all_articles = session.query(Article).all()
    for a in all_articles:
        if not a.references:
            continue
        for ref in a.references:
            target_id = ref.get("article_id") if isinstance(ref, dict) else ref
            if target_id == article_id:
                cited_by.append({"id": a.id, "title": a.title})
                break

    return {"cites": cites, "cited_by": cited_by}


# ── Click tracking ───────────────────────────────────────────────────────────────

def record_click(
    session,
    from_article_id: str,
    to_article_id: str,
    *,
    node_id: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Record a citation click event in the local database.

    Returns the created event as a dict.
    """
    from peerpedia_core.storage.db.crud import create_click_event

    event = create_click_event(
        session,
        from_article_id=from_article_id,
        to_article_id=to_article_id,
        node_id=node_id,
        user_id=user_id,
    )
    return event.to_dict()


def compute_transition_probabilities(
    session,
    from_article_id: str,
    *,
    other_nodes_clicks: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Compute click-based transition probabilities from an article.

    Merges local SQLite click events with aggregated click counts from
    other LAN nodes (via catalog.md sync).

    Args:
        session: SQLAlchemy session.
        from_article_id: Source article ID.
        other_nodes_clicks: Dict of to_article_id -> click count from other nodes.

    Returns:
        {"article_id": str, "total_clicks": int,
         "transitions": [{"to_article_id": str, "title": str,
                           "clicks": int, "probability": float}, ...]}
        Sorted by probability descending.
    """
    from peerpedia_core.storage.db import (
        get_article,
        get_local_click_counts,
    )

    # Local counts from SQLite (precise, per-event)
    local_counts = get_local_click_counts(session, from_article_id)

    # Merge with other nodes' aggregated counts (sum — disjoint readers)
    merged: dict[str, int] = defaultdict(int)
    for to_id, n in local_counts.items():
        merged[to_id] += n
    if other_nodes_clicks:
        for to_id, n in other_nodes_clicks.items():
            merged[to_id] += n

    total = sum(merged.values())
    if total == 0:
        return {
            "article_id": from_article_id,
            "total_clicks": 0,
            "transitions": [],
        }

    transitions = []
    for to_id, clicks in sorted(merged.items(), key=lambda x: -x[1]):
        target = get_article(session, to_id)
        title = target.title if target else (to_id[:8] + "...")
        transitions.append({
            "to_article_id": to_id,
            "title": title,
            "clicks": clicks,
            "probability": round(clicks / total, 4),
        })

    return {
        "article_id": from_article_id,
        "total_clicks": total,
        "transitions": transitions,
    }
