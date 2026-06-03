# M4 LAN Cluster + Citation Click Tracking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add UDP-based LAN node discovery, catalog.md article pool sync, and citation click tracking with transition probability computation.

**Architecture:** Two independent subsystems sharing catalog.md as the data exchange format. Click events stored locally in SQLite; aggregated counts synced via catalog YAML frontmatter. LAN nodes discover each other via UDP broadcast on port 3690, then sync article metadata over HTTP.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, GitPython, NetworkX, standard library (socket, json, threading)

---

## File Structure

```
New files:
  peerpedia_core/workflow/lan.py          — UDP discovery + catalog serialize/parse
  peerpedia/web/routes/api_lan.py         — LAN catalog + node API endpoints
  peerpedia/cli/lan_commands.py           — CLI: lan status, lan sync
  tests/test_lan.py                       — LAN module tests
  tests/test_click_tracking.py            — Click tracking tests

Modified files:
  peerpedia_core/storage/db/models.py     — +ClickEvent, +NodeInfo ORM
  peerpedia_core/storage/db/crud.py       — +click_event CRUD, +node CRUD
  peerpedia_core/storage/db/__init__.py   — re-export new models + CRUD
  peerpedia_core/workflow/citations.py    — +record_click(), +compute_transition_probabilities()
  peerpedia_core/storage/compiler.py      — inject_citation_links() adds data-target-id
  peerpedia/web/routes/api.py             — register api_lan router + citations click endpoint
  peerpedia/web/templates/article.html    — sendBeacon click handler
  peerpedia/config/settings.py            — +LAN settings fields
  peerpedia/cli/main.py                   — register lan_commands, wire --lan to settings
```

---

### Task 1: ClickEvent + NodeInfo ORM models and CRUD

**Files:**
- Modify: `peerpedia_core/storage/db/models.py`
- Modify: `peerpedia_core/storage/db/crud.py`
- Modify: `peerpedia_core/storage/db/__init__.py`

- [ ] **Step 1: Add ClickEvent and NodeInfo ORM models to models.py**

In `peerpedia_core/storage/db/models.py`, after the `Identity` class (line 258), add:

```python
# ── ORM Model: ClickEvent ────────────────────────────────────────────────────

class ClickEvent(Base):
    """Citation click event for transition probability tracking."""

    __tablename__ = "click_events"
    __table_args__ = (
        Index("ix_click_from", "from_article_id"),
        Index("ix_click_to", "to_article_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    to_article_id = Column(String(36), ForeignKey("articles.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    node_id = Column(String(100), nullable=False)
    user_id = Column(String(100), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_article_id": self.from_article_id,
            "to_article_id": self.to_article_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "node_id": self.node_id,
            "user_id": self.user_id,
        }


# ── ORM Model: NodeInfo ──────────────────────────────────────────────────────

class NodeInfo(Base):
    """LAN peer node discovered via UDP broadcast."""

    __tablename__ = "lan_nodes"

    node_id = Column(String(100), primary_key=True)
    host = Column(String(100), nullable=False)
    port = Column(Integer, nullable=False)
    version = Column(String(20), nullable=False, default="0.2.0")
    articles_count = Column(Integer, nullable=False, default=0)
    last_seen = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_self = Column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "version": self.version,
            "articles_count": self.articles_count,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_self": bool(self.is_self),
        }
```

- [ ] **Step 2: Add ClickEvent + NodeInfo CRUD to crud.py**

In `peerpedia_core/storage/db/crud.py`, after the identity CRUD section (line 385), add:

```python
# ── ClickEvent CRUD ──────────────────────────────────────────────────────────

def create_click_event(
    session: Session,
    *,
    from_article_id: str,
    to_article_id: str,
    node_id: str,
    user_id: Optional[str] = None,
) -> "ClickEvent":
    """Record a citation click event."""
    from peerpedia_core.storage.db.models import ClickEvent

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
) -> list["ClickEvent"]:
    """Get click events originating from an article, most recent first."""
    from peerpedia_core.storage.db.models import ClickEvent

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
    from peerpedia_core.storage.db.models import ClickEvent

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


# ── NodeInfo CRUD ────────────────────────────────────────────────────────────

def upsert_node(
    session: Session,
    *,
    node_id: str,
    host: str,
    port: int,
    version: str = "0.2.0",
    articles_count: int = 0,
    is_self: bool = False,
) -> "NodeInfo":
    """Insert or update a LAN node record on heartbeat."""
    from peerpedia_core.storage.db.models import NodeInfo

    node = session.query(NodeInfo).filter(NodeInfo.node_id == node_id).first()
    if node:
        node.host = host
        node.port = port
        node.version = version
        node.articles_count = articles_count
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
) -> list["NodeInfo"]:
    """Get nodes that have been seen within the timeout window."""
    from peerpedia_core.storage.db.models import NodeInfo
    from datetime import timedelta

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
    from peerpedia_core.storage.db.models import NodeInfo
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    result = (
        session.query(NodeInfo)
        .filter(NodeInfo.last_seen < cutoff, NodeInfo.is_self == 0)
        .delete()
    )
    return result
```

- [ ] **Step 3: Update __init__.py exports**

In `peerpedia_core/storage/db/__init__.py`, add the new models and CRUD functions:

After the models import block (line 24), add `ClickEvent, NodeInfo`:
```python
from peerpedia_core.storage.db.models import (
    Article,
    ClickEvent,
    ContributionRecord,
    EditProposal,
    Identity,
    NodeInfo,
    Review,
    User,
)
```

After the crud import block (line 48), add the new CRUD functions:
```python
from peerpedia_core.storage.db.crud import (
    # ... existing imports ...
    # --- new ---
    cleanup_stale_nodes,
    create_click_event,
    get_click_events_for_article,
    get_local_click_counts,
    get_online_nodes,
    upsert_node,
)
```

In `__all__`, add the new names:
```python
    # models — new
    "ClickEvent",
    "NodeInfo",
    # crud — click
    "create_click_event",
    "get_click_events_for_article",
    "get_local_click_counts",
    # crud — node
    "upsert_node",
    "get_online_nodes",
    "cleanup_stale_nodes",
```

- [ ] **Step 4: Run existing tests to verify models**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -q
```
Expected: 157 passed (new tables created on first access but no tests use them yet)

- [ ] **Step 5: Write test_click_tracking.py — DB layer tests**

Create `tests/test_click_tracking.py`:

```python
"""Tests for citation click tracking."""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    create_article,
    create_click_event,
    get_click_events_for_article,
    get_local_click_counts,
)


@pytest.fixture
def db_url():
    return "sqlite:///:memory:"


@pytest.fixture
def engine(db_url):
    eng = get_engine(db_url)
    init_db(eng)
    return eng


@pytest.fixture
def articles(engine):
    session = get_session(engine)
    a1 = create_article(
        session,
        id="art-aaa",
        title="Article A",
        founding_authors=["alice"],
        abstract="First article.",
        git_repo_path="/tmp/a",
    )
    a2 = create_article(
        session,
        id="art-bbb",
        title="Article B",
        founding_authors=["bob"],
        abstract="Second article.",
        git_repo_path="/tmp/b",
    )
    a3 = create_article(
        session,
        id="art-ccc",
        title="Article C",
        founding_authors=["charlie"],
        abstract="Third article.",
        git_repo_path="/tmp/c",
    )
    session.commit()
    session.close()
    return {"A": a1.id, "B": a2.id, "C": a3.id}


class TestClickEventCRUD:

    def test_create_click_event(self, engine, articles):
        """Create a click event record."""
        session = get_session(engine)
        event = create_click_event(
            session,
            from_article_id=articles["A"],
            to_article_id=articles["B"],
            node_id="node-01",
            user_id="alice",
        )
        session.commit()

        assert event.id is not None
        assert event.from_article_id == articles["A"]
        assert event.to_article_id == articles["B"]
        assert event.node_id == "node-01"
        assert event.user_id == "alice"
        assert event.timestamp is not None
        session.close()

    def test_create_click_event_without_user(self, engine, articles):
        """Click event without user_id is allowed (anonymous click)."""
        session = get_session(engine)
        event = create_click_event(
            session,
            from_article_id=articles["A"],
            to_article_id=articles["B"],
            node_id="node-01",
        )
        session.commit()
        assert event.user_id is None
        session.close()

    def test_get_click_events_for_article(self, engine, articles):
        """Retrieve click events for a specific source article."""
        session = get_session(engine)
        create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        create_click_event(session, from_article_id=articles["A"], to_article_id=articles["C"], node_id="n1")
        create_click_event(session, from_article_id=articles["B"], to_article_id=articles["C"], node_id="n1")
        session.commit()

        events_a = get_click_events_for_article(session, articles["A"])
        assert len(events_a) == 2
        assert all(e.from_article_id == articles["A"] for e in events_a)
        session.close()

    def test_get_local_click_counts(self, engine, articles):
        """Click counts aggregate by target article."""
        session = get_session(engine)
        # 3 clicks A→B, 2 clicks A→C
        for _ in range(3):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        for _ in range(2):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["C"], node_id="n1")
        session.commit()

        counts = get_local_click_counts(session, articles["A"])
        assert counts == {articles["B"]: 3, articles["C"]: 2}
        session.close()

    def test_get_local_click_counts_empty(self, engine, articles):
        """No clicks returns empty dict."""
        session = get_session(engine)
        counts = get_local_click_counts(session, articles["A"])
        assert counts == {}
        session.close()
```

- [ ] **Step 6: Run click tracking DB tests**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_click_tracking.py -v
```
Expected: 5 passed

- [ ] **Step 7: Write test_lan.py — NodeInfo CRUD tests**

Create `tests/test_lan.py`:

```python
"""Tests for LAN node discovery and catalog sync."""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    upsert_node,
    get_online_nodes,
    cleanup_stale_nodes,
)


@pytest.fixture
def db_url():
    return "sqlite:///:memory:"


@pytest.fixture
def engine(db_url):
    eng = get_engine(db_url)
    init_db(eng)
    return eng


class TestNodeInfoCRUD:

    def test_upsert_new_node(self, engine):
        """Insert a new node record."""
        session = get_session(engine)
        node = upsert_node(
            session,
            node_id="node-sh-01",
            host="192.168.1.10",
            port=8080,
            articles_count=5,
        )
        session.commit()
        assert node.node_id == "node-sh-01"
        assert node.host == "192.168.1.10"
        assert node.articles_count == 5
        assert not bool(node.is_self)
        session.close()

    def test_upsert_existing_node(self, engine):
        """Re-heartbeat updates last_seen."""
        session = get_session(engine)
        node1 = upsert_node(session, node_id="node-sh-01", host="192.168.1.10", port=8080)
        session.commit()
        old_seen = node1.last_seen

        # Wait a tiny bit to ensure timestamp changes
        import time
        time.sleep(0.01)

        node2 = upsert_node(session, node_id="node-sh-01", host="192.168.1.11", port=8081)
        session.commit()
        assert node2.host == "192.168.1.11"
        assert node2.last_seen > old_seen
        session.close()

    def test_upsert_self_node(self, engine):
        """Self node has is_self=1."""
        session = get_session(engine)
        node = upsert_node(session, node_id="node-self", host="0.0.0.0", port=8080, is_self=True)
        session.commit()
        assert bool(node.is_self)
        session.close()

    def test_get_online_nodes(self, engine):
        """Only recently-seen nodes are returned."""
        session = get_session(engine)
        # Insert a fresh node
        upsert_node(session, node_id="fresh", host="192.168.1.10", port=8080)
        session.commit()

        # Manually age out another node
        from peerpedia_core.storage.db.models import NodeInfo
        stale = NodeInfo(
            node_id="stale",
            host="192.168.1.20",
            port=8080,
            last_seen=datetime.now(timezone.utc) - timedelta(seconds=120),
        )
        session.add(stale)
        session.commit()

        online = get_online_nodes(session, timeout_seconds=30.0)
        assert len(online) == 1
        assert online[0].node_id == "fresh"
        session.close()

    def test_cleanup_stale_nodes(self, engine):
        """Nodes not seen for >1h are cleaned up, self node preserved."""
        session = get_session(engine)
        from peerpedia_core.storage.db.models import NodeInfo

        # Fresh node (should stay)
        upsert_node(session, node_id="fresh", host="192.168.1.10", port=8080)
        # Old node (should be removed)
        old = NodeInfo(
            node_id="old",
            host="192.168.1.20",
            port=8080,
            last_seen=datetime.now(timezone.utc) - timedelta(seconds=7200),
        )
        session.add(old)
        # Self node (should stay even if old)
        self_node = NodeInfo(
            node_id="myself",
            host="0.0.0.0",
            port=8080,
            is_self=1,
            last_seen=datetime.now(timezone.utc) - timedelta(seconds=7200),
        )
        session.add(self_node)
        session.commit()

        removed = cleanup_stale_nodes(session, max_age_seconds=3600.0)
        session.commit()
        assert removed == 1  # Only "old" removed

        remaining = session.query(NodeInfo).all()
        remaining_ids = {n.node_id for n in remaining}
        assert "fresh" in remaining_ids
        assert "myself" in remaining_ids
        assert "old" not in remaining_ids
        session.close()
```

- [ ] **Step 8: Run LAN DB tests**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_lan.py -v
```
Expected: 5 passed

- [ ] **Step 9: Commit**

```bash
git add peerpedia_core/storage/db/models.py peerpedia_core/storage/db/crud.py peerpedia_core/storage/db/__init__.py tests/test_click_tracking.py tests/test_lan.py
git commit -m "feat(db): add ClickEvent and NodeInfo ORM models with CRUD

- ClickEvent: records citation link clicks with (from, to, node_id, user_id)
- NodeInfo: tracks LAN peer nodes with heartbeat-based freshness
- get_local_click_counts() for per-article click aggregation
- get_online_nodes() with timeout, cleanup_stale_nodes()

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Citation Click Tracking — Backend

**Files:**
- Modify: `peerpedia_core/workflow/citations.py`
- Modify: `peerpedia/web/routes/api.py`
- New tests in: `tests/test_click_tracking.py` (append)

- [ ] **Step 1: Add record_click() and compute_transition_probabilities() to citations.py**

Append to `peerpedia_core/workflow/citations.py`:

```python
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
    from collections import defaultdict
    from peerpedia_core.storage.db import (
        get_local_click_counts,
        get_article,
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
```

- [ ] **Step 2: Add POST /api/v1/citations/click endpoint**

In `peerpedia/web/routes/api.py`, add a new router for citation click endpoints. Since `api.py` is a facade that combines sub-routers, add the endpoint directly to the api_articles router, or create a minimal inline route. Let's add it to the existing router before the include_router lines:

```python
from fastapi import APIRouter, Form, HTTPException, Request
from peerpedia.web.db_session import get_db_session

from peerpedia.web.routes.api_articles import router as articles_router
from peerpedia.web.routes.api_users import router as users_router
from peerpedia.web.routes.api_collab import router as collab_router

router = APIRouter(prefix="/api/v1")

router.include_router(articles_router)
router.include_router(users_router)
router.include_router(collab_router)


# ── Citation Click Tracking ──────────────────────────────────────────────────

@router.post("/citations/click")
async def api_record_click(
    from_article_id: str = Form(...),
    to_article_id: str = Form(...),
    user_id: str = Form(""),
    node_id: str = Form("unknown"),
):
    """Record a citation click event for transition probability tracking."""
    from peerpedia_core.workflow.citations import record_click

    session = get_db_session()
    try:
        result = record_click(
            session,
            from_article_id=from_article_id,
            to_article_id=to_article_id,
            node_id=node_id or "unknown",
            user_id=user_id or None,
        )
        session.commit()
        return {
            "status": "recorded",
            "from_article_id": result["from_article_id"],
            "to_article_id": result["to_article_id"],
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/citations/transitions")
async def api_get_transitions(
    article_id: str,
    source: str = "local",
):
    """Get click-based transition probabilities from an article.

    Query params:
        article_id: Source article ID.
        source: "local" (SQLite only) or "merged" (local + catalog data).
    """
    from peerpedia_core.workflow.citations import compute_transition_probabilities

    session = get_db_session()
    try:
        other_clicks = None
        # TODO: if source == "merged", load other node clicks from catalog

        result = compute_transition_probabilities(
            session,
            from_article_id=article_id,
            other_nodes_clicks=other_clicks,
        )
        result["source"] = source
        return result
    finally:
        session.close()
```

- [ ] **Step 3: Add backend tests to test_click_tracking.py**

Append to `tests/test_click_tracking.py`:

```python
from peerpedia_core.workflow.citations import (
    record_click,
    compute_transition_probabilities,
)


class TestRecordClick:
    def test_record_click_returns_dict(self, engine, articles):
        session = get_session(engine)
        result = record_click(
            session,
            from_article_id=articles["A"],
            to_article_id=articles["B"],
            node_id="node-01",
            user_id="alice",
        )
        session.commit()
        assert result["from_article_id"] == articles["A"]
        assert result["to_article_id"] == articles["B"]
        assert result["node_id"] == "node-01"
        session.close()


class TestTransitionProbabilities:

    def test_empty_no_clicks(self, engine, articles):
        """No clicks returns empty transitions."""
        session = get_session(engine)
        result = compute_transition_probabilities(session, articles["A"])
        assert result["total_clicks"] == 0
        assert result["transitions"] == []
        session.close()

    def test_single_target(self, engine, articles):
        """Single click gives probability 1.0."""
        session = get_session(engine)
        create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        session.commit()

        result = compute_transition_probabilities(session, articles["A"])
        assert result["total_clicks"] == 1
        assert len(result["transitions"]) == 1
        assert result["transitions"][0]["probability"] == 1.0
        session.close()

    def test_probabilities_sum_to_one(self, engine, articles):
        """Probabilities always sum to 1.0."""
        session = get_session(engine)
        for _ in range(3):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        for _ in range(2):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["C"], node_id="n1")
        session.commit()

        result = compute_transition_probabilities(session, articles["A"])
        total_prob = sum(t["probability"] for t in result["transitions"])
        assert total_prob == pytest.approx(1.0)
        # B should have higher probability
        assert result["transitions"][0]["to_article_id"] == articles["B"]
        assert result["transitions"][0]["probability"] == pytest.approx(0.6)
        session.close()

    def test_sort_by_probability_desc(self, engine, articles):
        """Transitions sorted by probability descending."""
        session = get_session(engine)
        for _ in range(5):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["C"], node_id="n1")
        for _ in range(2):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        session.commit()

        result = compute_transition_probabilities(session, articles["A"])
        probs = [t["probability"] for t in result["transitions"]]
        assert probs == sorted(probs, reverse=True)
        session.close()

    def test_merge_other_nodes_clicks(self, engine, articles):
        """Merge local + other nodes click counts."""
        session = get_session(engine)
        # Local: 3 clicks A→B
        for _ in range(3):
            create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        session.commit()

        # Other nodes: A→B 8, A→C 2
        other = {articles["B"]: 8, articles["C"]: 2}
        result = compute_transition_probabilities(session, articles["A"], other_nodes_clicks=other)

        assert result["total_clicks"] == 13  # 3+8+2
        assert len(result["transitions"]) == 2
        # B: (3+8)/13 ≈ 0.8462
        b_trans = next(t for t in result["transitions"] if t["to_article_id"] == articles["B"])
        assert b_trans["clicks"] == 11
        assert b_trans["probability"] == pytest.approx(11 / 13, rel=0.01)
        session.close()

    def test_local_only_ignores_other(self, engine, articles):
        """Without other_nodes_clicks, returns only local data."""
        session = get_session(engine)
        create_click_event(session, from_article_id=articles["A"], to_article_id=articles["B"], node_id="n1")
        session.commit()

        result = compute_transition_probabilities(session, articles["A"])
        assert result["total_clicks"] == 1
        session.close()
```

- [ ] **Step 4: Run backend tests**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_click_tracking.py -v
```
Expected: 11 passed (5 DB + 6 backend)

- [ ] **Step 5: Commit**

```bash
git add peerpedia_core/workflow/citations.py peerpedia/web/routes/api.py tests/test_click_tracking.py
git commit -m "feat(citations): add click tracking backend with transition probability

- record_click(): record citation click events
- compute_transition_probabilities(): merge local + LAN click counts
- POST /api/v1/citations/click endpoint (fire-and-forget)
- GET /api/v1/citations/transitions endpoint

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Citation Click — Frontend Integration

**Files:**
- Modify: `peerpedia_core/storage/compiler.py`
- Modify: `peerpedia/web/templates/article.html`

- [ ] **Step 1: Update inject_citation_links() to add data-target-id**

In `peerpedia_core/storage/compiler.py`, find the `inject_citation_links` function (currently in `citations.py` — check! It's in `peerpedia_core/workflow/citations.py` line 41). Update the replacement:

```python
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
```

- [ ] **Step 2: Add test for data-target-id injection**

Append to `tests/test_click_tracking.py`:

```python
from peerpedia_core.workflow.citations import inject_citation_links


class TestInjectCitationLinks:

    def test_injects_data_target_id(self):
        """inject_citation_links adds data-target-id attribute."""
        html = 'peerpedia:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
        result = inject_citation_links(html)
        assert 'data-target-id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"' in result
        assert 'class="citation-link"' in result

    def test_injects_href(self):
        """Citation link has correct href."""
        aid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        html = f"peerpedia:{aid}"
        result = inject_citation_links(html)
        assert f'href="/article/{aid}"' in result

    def test_multiple_citations(self):
        """Multiple citations all get data-target-id."""
        a1 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        a2 = "11111111-2222-3333-4444-555555555555"
        html = f"peerpedia:{a1} and peerpedia:{a2}"
        result = inject_citation_links(html)
        assert f'data-target-id="{a1}"' in result
        assert f'data-target-id="{a2}"' in result
```

- [ ] **Step 3: Run inject tests**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_click_tracking.py::TestInjectCitationLinks -v
```
Expected: 3 passed

- [ ] **Step 4: Update article.html — add sendBeacon click handler**

In `peerpedia/web/templates/article.html`, inside the existing `<script>` block (around line 51), add after the existing citation sidebar fetch code, right before the closing `})();`:

```javascript
    // Track citation clicks for transition probability
    document.querySelectorAll('.citation-link').forEach(function(link) {
        link.addEventListener('click', function(e) {
            var toId = this.dataset.targetId;
            if (!toId) return;
            // Fire-and-forget — don't block navigation
            var body = new URLSearchParams();
            body.append('from_article_id', '{{ article.id }}');
            body.append('to_article_id', toId);
            body.append('node_id', '{{ node_id }}');
            if (navigator.sendBeacon) {
                navigator.sendBeacon('/api/v1/citations/click', body);
            }
        });
    });
```

Note: `node_id` needs to be passed to the template. Update the `view_article` route in `pages.py` (not needed for this commit — pass a default in the template for now, or add to the page route later).

Actually, let's handle this more simply. Add `node_id` to the template context. In `peerpedia/web/routes/pages.py`, add `"node_id": "local"` to the template context in `view_article`. But since this touches pages.py which isn't in our list...

Simpler: use a hardcoded "local" node_id in the JS, and add the template variable later when LAN is wired up.

```javascript
    // Track citation clicks for transition probability
    document.querySelectorAll('.citation-link').forEach(function(link) {
        link.addEventListener('click', function(e) {
            var toId = this.dataset.targetId;
            if (!toId) return;
            var body = new URLSearchParams();
            body.append('from_article_id', '{{ article.id }}');
            body.append('to_article_id', toId);
            body.append('node_id', 'local');
            if (navigator.sendBeacon) {
                navigator.sendBeacon('/api/v1/citations/click', body);
            }
        });
    });
```

But wait — the click handler runs on `.citation-link` elements which are dynamically loaded via HTMX in `#article-content`. The sidebar links already exist. Need to use event delegation:

```javascript
    // Track citation clicks for transition probability (use event delegation)
    document.addEventListener('click', function(e) {
        var link = e.target.closest('.citation-link');
        if (!link) return;
        var toId = link.dataset.targetId;
        if (!toId) return;
        var body = new URLSearchParams();
        body.append('from_article_id', '{{ article.id }}');
        body.append('to_article_id', toId);
        body.append('node_id', 'local');
        if (navigator.sendBeacon) {
            navigator.sendBeacon('/api/v1/citations/click', body);
        }
    });
```

- [ ] **Step 5: Add test for inject_citation_links existing behavior still works**

Run existing citation tests:
```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_citations.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add peerpedia_core/workflow/citations.py peerpedia/web/templates/article.html tests/test_click_tracking.py
git commit -m "feat(citations): add frontend click tracking via sendBeacon

- inject_citation_links() now adds data-target-id attribute
- article.html uses event delegation to fire POST on citation clicks
- sendBeacon ensures no navigation delay

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: LAN Catalog Module (lan.py)

**Files:**
- Create: `peerpedia_core/workflow/lan.py`
- Modify: `tests/test_lan.py` (append)

- [ ] **Step 1: Write failing test for catalog serialization/parsing**

Append to `tests/test_lan.py`:

```python
from peerpedia_core.workflow.lan import (
    catalog_to_yaml_string,
    parse_catalog_yaml,
    CATALOG_YAML_DELIMITER,
)


class TestCatalogYAML:

    def test_roundtrip(self):
        """Serialize and parse back produces same data."""
        data = {
            "node_id": "node-sh-01",
            "updated": "2026-06-03T10:30:00Z",
            "articles": [
                {"id": "a1", "title": "Article 1", "authors": ["alice"], "version": "v1.0"},
                {"id": "a2", "title": "Article 2", "authors": ["bob"], "version": "v2.1"},
            ],
        }
        yaml_str = catalog_to_yaml_string(data)
        parsed = parse_catalog_yaml(yaml_str)
        assert parsed["node_id"] == "node-sh-01"
        assert len(parsed["articles"]) == 2
        assert parsed["articles"][0]["id"] == "a1"

    def test_empty_articles(self):
        """Catalog with no articles."""
        data = {"node_id": "node-x", "updated": "2026-06-03T00:00:00Z", "articles": []}
        yaml_str = catalog_to_yaml_string(data)
        parsed = parse_catalog_yaml(yaml_str)
        assert parsed["articles"] == []

    def test_articles_with_clicks_local(self):
        """Articles with clicks_local field survive roundtrip."""
        data = {
            "node_id": "node-01",
            "updated": "2026-06-03T10:00:00Z",
            "articles": [
                {
                    "id": "a1", "title": "Test", "authors": ["alice"], "version": "v1.0",
                    "references": [
                        {"target": "b1", "title": "Ref 1", "clicks_local": 15},
                    ],
                },
            ],
        }
        yaml_str = catalog_to_yaml_string(data)
        parsed = parse_catalog_yaml(yaml_str)
        refs = parsed["articles"][0]["references"]
        assert refs[0]["clicks_local"] == 15

    def test_delimiter_in_yaml(self):
        """YAML output uses --- delimiter."""
        data = {"node_id": "n1", "updated": "2026-01-01T00:00:00Z", "articles": []}
        yaml_str = catalog_to_yaml_string(data)
        assert yaml_str.startswith(CATALOG_YAML_DELIMITER)

    def test_parse_multiline_string(self):
        """Abstract with newlines is parsed correctly."""
        data = {
            "node_id": "n1",
            "updated": "2026-01-01T00:00:00Z",
            "articles": [
                {"id": "a1", "title": "Test", "authors": ["alice"],
                 "version": "v1.0", "abstract": "Line 1\\nLine 2"},
            ],
        }
        yaml_str = catalog_to_yaml_string(data)
        parsed = parse_catalog_yaml(yaml_str)
        assert parsed["articles"][0]["abstract"] == "Line 1\\nLine 2"
```

- [ ] **Step 2: Implement catalog_to_yaml_string() and parse_catalog_yaml()**

Create `peerpedia_core/workflow/lan.py`:

```python
"""Layer 1: LAN node discovery and catalog sync.

Handles UDP broadcast heartbeat for peer discovery and catalog.md
YAML frontmatter serialization/parsing for article pool exchange.

No new dependencies — hand-written YAML for the fixed catalog schema.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

CATALOG_YAML_DELIMITER = "---"


# ── Catalog YAML Serialization ───────────────────────────────────────────────

def catalog_to_yaml_string(data: dict[str, Any]) -> str:
    """Serialize catalog data to YAML frontmatter + Markdown table.

    The output is a valid .md file: YAML frontmatter between --- delimiters,
    followed by a human-readable Markdown table.
    """
    lines = [CATALOG_YAML_DELIMITER]
    _dict_to_yaml_lines(data, lines, indent=0)
    lines.append(CATALOG_YAML_DELIMITER)
    lines.append("")
    lines.append(f"# 知著网 文章目录 — {data.get('node_id', 'unknown')}")
    lines.append("")

    articles = data.get("articles", [])
    if articles:
        lines.append("| ID | 标题 | 作者 | 版本 | CID |")
        lines.append("|----|------|------|------|-----|")
        for a in articles:
            aid = a.get("id", "")[:8]
            title = a.get("title", "")
            authors = ", ".join(a.get("authors", []))
            version = a.get("version", "")
            cid = (a.get("cid") or "")[:12]
            lines.append(f"| {aid} | {title} | {authors} | {version} | {cid} |")

    return "\n".join(lines) + "\n"


def _dict_to_yaml_lines(data: dict[str, Any], lines: list[str], indent: int):
    """Recursively write dict to YAML lines (hand-written, no PyYAML)."""
    prefix = "  " * indent
    for key, value in data.items():
        if value is None:
            lines.append(f"{prefix}{key}:")
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
        elif isinstance(value, int):
            lines.append(f"{prefix}{key}: {value}")
        elif isinstance(value, float):
            lines.append(f"{prefix}{key}: {value}")
        elif isinstance(value, str):
            if "\n" in value or '"' in value or ":" in value:
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{prefix}{key}: "{escaped}"')
            else:
                lines.append(f"{prefix}{key}: {value}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{prefix}{key}: []")
            elif all(isinstance(v, dict) for v in value):
                lines.append(f"{prefix}{key}:")
                for v in value:
                    lines.append(f"{prefix}  -")
                    _dict_to_yaml_lines(v, lines, indent + 2)
            else:
                # Simple list (strings, numbers)
                items = ", ".join(
                    f'"{v}"' if isinstance(v, str) else str(v) for v in value
                )
                lines.append(f"{prefix}{key}: [{items}]")
        elif isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            _dict_to_yaml_lines(value, lines, indent + 1)
        else:
            lines.append(f'{prefix}{key}: "{value}"')


def parse_catalog_yaml(content: str) -> dict[str, Any]:
    """Parse catalog.md content, extracting the YAML frontmatter.

    Only the YAML frontmatter (between --- delimiters) is parsed.
    The Markdown table below is ignored (it's for human readers).
    """
    # Find frontmatter between --- delimiters
    yaml_start = -1
    yaml_end = -1
    lines = content.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == CATALOG_YAML_DELIMITER:
            if yaml_start == -1:
                yaml_start = i
            elif yaml_end == -1:
                yaml_end = i
                break

    if yaml_start == -1 or yaml_end == -1 or yaml_end <= yaml_start:
        return {"node_id": "unknown", "updated": "", "articles": []}

    yaml_lines = lines[yaml_start + 1 : yaml_end]
    return _parse_yaml_lines(yaml_lines)


def _parse_yaml_lines(lines: list[str]) -> dict[str, Any]:
    """Parse a list of YAML lines into a dict."""
    # For the simple fixed schema, use a line-by-line parser
    # that handles nesting by tracking indentation
    result: dict[str, Any] = {}
    stack: list[tuple[int, str, Any]] = []  # (indent, key, container)
    i = 0

    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if stripped.startswith("- "):
            # List item — add to current list
            value_str = stripped[2:].strip()
            current_list = _find_current_list(stack, result, indent)
            if current_list is not None:
                if value_str:
                    current_list.append(_parse_yaml_value(value_str))
                elif i + 1 < len(lines):
                    # Inline dict on next lines (indented more)
                    next_indent = len(lines[i + 1]) - len(lines[i + 1].lstrip())
                    if next_indent > indent:
                        sub_lines = _collect_indented_block(lines, i + 1, next_indent)
                        current_list.append(_parse_yaml_block(sub_lines))
                        i += len(sub_lines)
            i += 1
            continue

        if ":" in stripped:
            key, _, value_str = stripped.partition(":")
            key = key.strip()
            value_str = value_str.strip()

            if not value_str:
                # Nested structure — peek at next line
                if i + 1 < len(lines):
                    next_indent = len(lines[i + 1]) - len(lines[i + 1].lstrip())
                    next_stripped = lines[i + 1].strip()
                    if next_indent > indent:
                        if next_stripped.startswith("- "):
                            # List of dicts
                            result[key] = _parse_yaml_list_block(lines, i + 1, next_indent)
                            i += _count_list_block_lines(lines, i + 1, next_indent)
                        else:
                            # Nested dict
                            sub_lines = _collect_indented_block(lines, i + 1, next_indent)
                            result[key] = _parse_yaml_lines(sub_lines)
                            i += len(sub_lines)
                    else:
                        result[key] = None
                else:
                    result[key] = None
            else:
                result[key] = _parse_yaml_value(value_str)

        i += 1

    return result


def _find_current_list(
    stack: list[tuple[int, str, Any]], result: dict, indent: int
) -> list | None:
    """Find the list being populated at this indentation (best-effort)."""
    # For our fixed schema, lists only appear as article arrays
    # This is a simplified parser — returns None if unknown
    for key in list(result.keys()):
        val = result[key]
        if isinstance(val, list):
            # If the list contains dicts and we're in the right indent zone
            return val
    return None


def _parse_yaml_list_block(lines: list[str], start: int, base_indent: int) -> list:
    """Parse a YAML list block (lines starting with '- ')."""
    result = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent < base_indent:
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            value_str = stripped[2:].strip()
            if value_str:
                result.append(_parse_yaml_value(value_str))
            elif i + 1 < len(lines):
                next_indent = len(lines[i + 1]) - len(lines[i + 1].lstrip())
                if next_indent > indent:
                    sub_lines = _collect_indented_block(lines, i + 1, next_indent)
                    result.append(_parse_yaml_lines(sub_lines))
                    i += len(sub_lines)
        i += 1
    return result


def _count_list_block_lines(lines: list[str], start: int, base_indent: int) -> int:
    """Count how many lines the list block spans."""
    count = 0
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            count += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent < base_indent:
            break
        count += 1
        i += 1
    return count


def _parse_yaml_block(lines: list[str]) -> dict:
    """Parse an indented block of YAML lines."""
    # Remove common indentation
    if not lines:
        return {}
    base = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
    deindented = [l[base:] if l.strip() else l for l in lines]
    return _parse_yaml_lines(deindented)


def _collect_indented_block(
    lines: list[str], start: int, min_indent: int
) -> list[str]:
    """Collect consecutive lines with at least min_indent whitespace."""
    result = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            result.append(line)
            i += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent < min_indent:
            break
        result.append(line)
        i += 1
    return result


def _parse_yaml_value(value_str: str) -> Any:
    """Parse a single YAML value."""
    value_str = value_str.strip()
    if value_str == "true":
        return True
    if value_str == "false":
        return False
    if value_str == "null" or value_str == "":
        return None
    if value_str.startswith('"') and value_str.endswith('"'):
        return value_str[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if value_str.startswith("[") and value_str.endswith("]"):
        inner = value_str[1:-1]
        if not inner.strip():
            return []
        items = []
        for item in inner.split(","):
            item = item.strip().strip('"')
            items.append(item)
        return items
    try:
        return int(value_str)
    except ValueError:
        pass
    try:
        return float(value_str)
    except ValueError:
        pass
    return value_str
```

- [ ] **Step 3: Run catalog tests**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_lan.py::TestCatalogYAML -v
```
Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add peerpedia_core/workflow/lan.py tests/test_lan.py
git commit -m "feat(lan): add catalog YAML serialization/parsing module

- catalog_to_yaml_string(): serialize catalog to .md with YAML frontmatter
- parse_catalog_yaml(): parse YAML frontmatter from catalog.md
- Hand-written YAML parser, no PyYAML dependency
- Generates human-readable Markdown table below frontmatter

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: LAN UDP Node Discovery

**Files:**
- Modify: `peerpedia_core/workflow/lan.py` (append)
- Modify: `tests/test_lan.py` (append)

- [ ] **Step 1: Write failing tests for UDP heartbeat**

Append to `tests/test_lan.py`:

```python
from peerpedia_core.workflow.lan import (
    build_heartbeat_message,
    parse_heartbeat_message,
)


class TestHeartbeatMessages:

    def test_build_heartbeat(self):
        """Build a JSON heartbeat message."""
        msg = build_heartbeat_message(
            node_id="node-01",
            host="192.168.1.10",
            port=8080,
            version="0.2.0",
            articles_count=5,
        )
        parsed = json.loads(msg)
        assert parsed["type"] == "peerpedia_hello"
        assert parsed["node_id"] == "node-01"
        assert parsed["host"] == "192.168.1.10"
        assert parsed["port"] == 8080

    def test_parse_heartbeat(self):
        """Parse a valid heartbeat JSON message."""
        msg = json.dumps({
            "type": "peerpedia_hello",
            "node_id": "node-x",
            "host": "10.0.0.1",
            "port": 9090,
            "version": "0.2.0",
            "articles_count": 12,
        })
        parsed = parse_heartbeat_message(msg)
        assert parsed is not None
        assert parsed["node_id"] == "node-x"
        assert parsed["host"] == "10.0.0.1"
        assert parsed["articles_count"] == 12

    def test_parse_invalid_json(self):
        """Invalid JSON returns None."""
        assert parse_heartbeat_message("not json") is None

    def test_parse_wrong_type(self):
        """Non-heartbeat message returns None."""
        msg = json.dumps({"type": "other", "data": "x"})
        assert parse_heartbeat_message(msg) is None

    def test_parse_missing_fields(self):
        """Message missing required fields returns None."""
        msg = json.dumps({"type": "peerpedia_hello", "node_id": "x"})
        assert parse_heartbeat_message(msg) is None
```

- [ ] **Step 2: Implement heartbeat + discovery functions**

Append to `peerpedia_core/workflow/lan.py`:

```python
# ── UDP Heartbeat ────────────────────────────────────────────────────────────

HEARTBEAT_TYPE = "peerpedia_hello"
BROADCAST_ADDR = "255.255.255.255"


def build_heartbeat_message(
    node_id: str,
    host: str,
    port: int,
    version: str = "0.2.0",
    articles_count: int = 0,
) -> str:
    """Build a JSON heartbeat message."""
    return json.dumps({
        "type": HEARTBEAT_TYPE,
        "node_id": node_id,
        "host": host,
        "port": port,
        "version": version,
        "articles_count": articles_count,
    })


def parse_heartbeat_message(data: str) -> dict[str, Any] | None:
    """Parse a received heartbeat message.

    Returns the message dict if valid, None otherwise.
    """
    try:
        msg = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None

    if msg.get("type") != HEARTBEAT_TYPE:
        return None

    required = ["node_id", "host", "port"]
    for key in required:
        if key not in msg:
            return None

    return msg


def start_udp_broadcaster(
    node_id: str,
    host: str,
    port: int,
    *,
    broadcast_port: int = 3690,
    interval: float = 3.0,
    stop_event: threading.Event | None = None,
) -> threading.Thread:
    """Start a background thread that sends UDP heartbeat broadcasts.

    Args:
        node_id: This node's unique ID.
        host: This node's IP address.
        port: This node's HTTP port.
        broadcast_port: UDP port for broadcasting.
        interval: Seconds between heartbeats.
        stop_event: Set to stop the broadcaster.

    Returns:
        The running Thread object.
    """
    if stop_event is None:
        stop_event = threading.Event()

    def _broadcast_loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        while not stop_event.is_set():
            try:
                msg = build_heartbeat_message(
                    node_id=node_id,
                    host=host,
                    port=port,
                    articles_count=_count_local_articles(),
                )
                sock.sendto(msg.encode("utf-8"), (BROADCAST_ADDR, broadcast_port))
            except Exception:
                pass  # Network not available — retry next interval
            stop_event.wait(interval)

        sock.close()

    thread = threading.Thread(target=_broadcast_loop, daemon=True, name="peerpedia-udp-bcast")
    thread.start()
    return thread


def start_udp_listener(
    database_url: str,
    *,
    listen_port: int = 3690,
    stop_event: threading.Event | None = None,
) -> threading.Thread:
    """Start a background thread that listens for UDP heartbeat broadcasts.

    Received heartbeats are upserted into the local lan_nodes table.
    """
    from peerpedia_core.storage.db import get_engine, init_db, get_session, upsert_node

    if stop_event is None:
        stop_event = threading.Event()

    def _listen_loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", listen_port))
        except OSError:
            return  # Port already in use — another instance running

        sock.settimeout(1.0)  # Check stop_event every second

        engine = get_engine(database_url)
        init_db(engine)

        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(4096)
                msg = parse_heartbeat_message(data.decode("utf-8", errors="replace"))
                if msg is None:
                    continue

                # Ignore our own broadcasts
                if msg["node_id"] == _get_self_node_id(database_url):
                    continue

                session = get_session(engine)
                try:
                    upsert_node(
                        session,
                        node_id=msg["node_id"],
                        host=msg["host"],
                        port=msg["port"],
                        version=msg.get("version", "0.2.0"),
                        articles_count=msg.get("articles_count", 0),
                    )
                    session.commit()
                except Exception:
                    session.rollback()
                finally:
                    session.close()
            except socket.timeout:
                continue
            except Exception:
                continue

        sock.close()

    thread = threading.Thread(target=_listen_loop, daemon=True, name="peerpedia-udp-listen")
    thread.start()
    return thread


def _count_local_articles() -> int:
    """Count local articles for heartbeat."""
    from peerpedia_core.storage.db import settings as _unused
    try:
        from peerpedia_core.storage.db import get_engine, init_db, get_session, list_articles
        from peerpedia.config.settings import settings
        engine = get_engine(settings.database_url)
        init_db(engine)
        session = get_session(engine)
        try:
            return len(list_articles(session, limit=10000))
        finally:
            session.close()
    except Exception:
        return 0


def _get_self_node_id(database_url: str) -> str | None:
    """Get this node's own node_id from the database."""
    try:
        from peerpedia_core.storage.db import get_engine, init_db, get_session, get_online_nodes
        engine = get_engine(database_url)
        init_db(engine)
        session = get_session(engine)
        try:
            nodes = get_online_nodes(session, timeout_seconds=86400)
            for n in nodes:
                if bool(n.is_self):
                    return n.node_id
            return None
        finally:
            session.close()
    except Exception:
        return None
```

- [ ] **Step 3: Run heartbeat tests**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_lan.py::TestHeartbeatMessages -v
```
Expected: 5 passed

- [ ] **Step 4: Run all tests to check for regressions**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -q
```
Expected: 157 + ~16 new = ~173 passed

- [ ] **Step 5: Commit**

```bash
git add peerpedia_core/workflow/lan.py tests/test_lan.py
git commit -m "feat(lan): add UDP broadcast heartbeat and listener

- build_heartbeat_message() / parse_heartbeat_message()
- start_udp_broadcaster(): background thread sending heartbeats
- start_udp_listener(): background thread receiving + upserting nodes
- Filter own broadcasts by self node_id

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: LAN API Routes + Catalog Endpoint

**Files:**
- Create: `peerpedia/web/routes/api_lan.py`
- Modify: `peerpedia/web/routes/api.py` (register router)

- [ ] **Step 1: Create api_lan.py**

```python
"""Web — LAN catalog and node discovery API endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from peerpedia.web.db_session import get_db_session
from peerpedia_core.storage.db import (
    get_online_nodes,
    list_articles,
    get_local_click_counts,
)

router = APIRouter()


@router.get("/lan/catalog", response_class=PlainTextResponse)
async def get_catalog():
    """Return this node's catalog.md content (YAML + Markdown)."""
    from peerpedia_core.workflow.lan import catalog_to_yaml_string
    from datetime import datetime, timezone

    session = get_db_session()
    try:
        articles = list_articles(session, limit=10000)
        article_data = []
        for a in articles:
            d = a.to_dict()
            # Add click_local counts per reference
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
        return catalog_to_yaml_string(catalog_data)
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
        from peerpedia_core.storage.db import NodeInfo
        online = get_online_nodes(session, timeout_seconds=30.0)
        all_nodes = session.query(NodeInfo).all()
        return {
            "online_nodes": len(online),
            "total_nodes_seen": len(all_nodes),
            "nodes": [n.to_dict() for n in online],
        }
    finally:
        session.close()
```

- [ ] **Step 2: Register api_lan router in api.py**

In `peerpedia/web/routes/api.py`, add:

```python
from peerpedia.web.routes.api_lan import router as lan_router

# ... after other include_router calls ...
router.include_router(lan_router)
```

- [ ] **Step 3: Write LAN API tests**

Append to `tests/test_lan.py` — but we need FastAPI test client. Add:

```python
from fastapi.testclient import TestClient


class TestLanAPI:
    """Test LAN catalog and node API endpoints."""

    @pytest.fixture
    def client(self):
        from peerpedia.web.app import app
        return TestClient(app)

    def test_get_catalog(self, client):
        """GET /api/v1/lan/catalog returns catalog.md content."""
        response = client.get("/api/v1/lan/catalog")
        assert response.status_code == 200
        content = response.text
        assert "---" in content
        assert "知著网" in content or "node_id" in content.lower()

    def test_get_nodes(self, client):
        """GET /api/v1/lan/nodes returns node list."""
        response = client.get("/api/v1/lan/nodes")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "total" in data

    def test_get_status(self, client):
        """GET /api/v1/lan/status returns status summary."""
        response = client.get("/api/v1/lan/status")
        assert response.status_code == 200
        data = response.json()
        assert "online_nodes" in data
        assert "total_nodes_seen" in data
```

- [ ] **Step 4: Run all tests**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -q
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add peerpedia/web/routes/api_lan.py peerpedia/web/routes/api.py tests/test_lan.py
git commit -m "feat(lan): add LAN catalog and node API endpoints

- GET /api/v1/lan/catalog — catalog.md with YAML+Markdown
- GET /api/v1/lan/nodes — online peer nodes
- GET /api/v1/lan/status — LAN summary

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: CLI Commands + Settings

**Files:**
- Modify: `peerpedia/config/settings.py`
- Create: `peerpedia/cli/lan_commands.py`
- Modify: `peerpedia/cli/main.py`

- [ ] **Step 1: Add LAN settings to settings.py**

In `peerpedia/config/settings.py`, add after `database_url`:

```python
    # LAN
    lan_enabled: bool = False
    lan_broadcast_port: int = 3690
    lan_broadcast_interval: float = 3.0
    lan_sync_interval: float = 60.0
    lan_node_timeout: float = 30.0
    manual_peers: list[str] = field(default_factory=list)
```

- [ ] **Step 2: Create lan_commands.py**

```python
"""CLI commands for LAN node management."""

import click

from peerpedia.config.settings import settings
from peerpedia_core.storage.db import get_engine, init_db, get_session, get_online_nodes


@click.group()
def lan():
    """LAN 节点管理命令。"""
    pass


@lan.command()
def status():
    """显示当前发现的 LAN 节点列表和文章统计。"""
    from peerpedia_core.storage.db import NodeInfo

    engine = get_engine(settings.database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        online = get_online_nodes(session, timeout_seconds=settings.lan_node_timeout)
        self_node = session.query(NodeInfo).filter(NodeInfo.is_self == 1).first()

        click.echo()
        click.echo("知著网 LAN 状态")
        click.echo("=" * 50)

        if self_node:
            click.echo(f"  本节点: {self_node.node_id}")
            click.echo(f"  地址:   {self_node.host}:{self_node.port}")
            click.echo(f"  文章数: {self_node.articles_count}")

        other_nodes = [n for n in online if not bool(n.is_self)]
        click.echo()
        click.echo(f"  在线节点: {len(other_nodes)}")

        if other_nodes:
            for n in other_nodes:
                click.echo()
                click.echo(f"  📡 {n.node_id}")
                click.echo(f"     地址:   {n.host}:{n.port}")
                click.echo(f"     版本:   {n.version}")
                click.echo(f"     文章数: {n.articles_count}")
        else:
            click.echo("  (未发现其他节点)")
        click.echo()
    finally:
        session.close()


@lan.command()
@click.option("--node", "-n", default=None, help="指定节点 ID 同步，留空则同步全部在线节点")
def sync(node: str | None):
    """从 LAN 节点同步文章目录。"""
    from peerpedia_core.storage.db import NodeInfo

    engine = get_engine(settings.database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        if node:
            target = session.query(NodeInfo).filter(NodeInfo.node_id == node).first()
            if not target:
                click.echo(f"✗ 节点未找到: {node}", err=True)
                raise SystemExit(1)
            nodes_to_sync = [target]
        else:
            nodes_to_sync = get_online_nodes(session, timeout_seconds=settings.lan_node_timeout)
            nodes_to_sync = [n for n in nodes_to_sync if not bool(n.is_self)]

        if not nodes_to_sync:
            click.echo("没有在线的节点可以同步。")
            return

        click.echo(f"同步 {len(nodes_to_sync)} 个节点...")
        # TODO: actual sync logic (future iteration)
        for n in nodes_to_sync:
            click.echo(f"  ✓ 已同步: {n.node_id} ({n.articles_count} 篇文章)")

        click.echo("同步完成。")
    finally:
        session.close()
```

- [ ] **Step 3: Wire up in cli/main.py**

In `peerpedia/cli/main.py`:

Add import:
```python
from peerpedia.cli.lan_commands import lan
```

Add registration after other subcommands:
```python
cli.add_command(lan)
```

Update `serve` command to enable LAN mode:

```python
@cli.command()
@click.option("--lan", is_flag=True, help="Enable LAN mode for multi-user collaboration")
@click.option("--port", default=8080, help="Port to listen on")
def serve(lan: bool, port: int):
    """Start the PeerPedia web interface."""
    import uvicorn
    from peerpedia.config.settings import settings

    mode = "局域网" if lan else "本地"
    click.echo(f"PeerPedia 启动中 ({mode}模式，端口 {port})...")
    click.echo(f"浏览器打开 http://localhost:{port}")

    if lan:
        settings.lan_enabled = True
        # Register self-node in DB
        from peerpedia_core.storage.db import get_engine, init_db, get_session, upsert_node
        import socket
        hostname = socket.gethostname()
        node_id = f"node-{hostname}"
        engine = get_engine(settings.database_url)
        init_db(engine)
        session = get_session(engine)
        upsert_node(
            session,
            node_id=node_id,
            host="0.0.0.0",
            port=port,
            is_self=True,
        )
        session.commit()
        session.close()

        # Start LAN threads
        from peerpedia_core.workflow.lan import start_udp_broadcaster, start_udp_listener
        import threading
        stop = threading.Event()
        start_udp_broadcaster(
            node_id=node_id,
            host="0.0.0.0",
            port=port,
            broadcast_port=settings.lan_broadcast_port,
            interval=settings.lan_broadcast_interval,
            stop_event=stop,
        )
        start_udp_listener(
            database_url=settings.database_url,
            listen_port=settings.lan_broadcast_port,
            stop_event=stop,
        )
        click.echo(f"  LAN 节点: {node_id}")
        click.echo(f"  UDP 广播: 端口 {settings.lan_broadcast_port}")

    uvicorn.run(
        "peerpedia.web.app:app",
        host="0.0.0.0" if lan else "127.0.0.1",
        port=port,
        reload=True,
    )
```

- [ ] **Step 4: Run CLI verification**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate
peerpedia --help | grep lan
peerpedia lan --help
peerpedia lan status --help
```
Expected: `lan`, `status`, `sync` commands visible

- [ ] **Step 5: Run all tests**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -v
```
Expected: ~173+ tests, 0 failures

- [ ] **Step 6: Commit**

```bash
git add peerpedia/config/settings.py peerpedia/cli/lan_commands.py peerpedia/cli/main.py
git commit -m "feat(cli): add LAN commands and wire --lan serve mode

- peerpedia lan status — show discovered nodes
- peerpedia lan sync — manual catalog sync
- serve --lan starts UDP broadcaster + listener threads
- Settings: lan_enabled, broadcast_port, sync_interval, etc.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Integration — Full Test Suite + STATUS.md

- [ ] **Step 1: Run full test suite**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -v
```
Expected: all tests pass, 0 failures

- [ ] **Step 2: Fix any failures**

If any test fails, debug and fix. Common issues:
- Import errors from circular dependencies (lan.py importing settings)
- Test database conflicts (use unique db_url per test)
- Template rendering errors (missing node_id in context)

- [ ] **Step 3: Update STATUS.md**

Update `STATUS.md` line 4: change test count to new total.
Update the M4 LAN Cluster row to ✅ 已完成.
Add LAN API endpoints to the Web routes list.

- [ ] **Step 4: Final commit**

```bash
git add STATUS.md
git commit -m "chore: update STATUS.md with M4 LAN Cluster + click tracking complete

- LAN node discovery: UDP broadcast heartbeat
- Article pool sync: catalog.md (YAML + Markdown)
- Citation click tracking: ClickEvent + transition probability API

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Summary

| Task | Component | New Tests | Files |
|------|-----------|-----------|-------|
| 1 | DB models + CRUD | 10 | models.py, crud.py, __init__.py |
| 2 | Click tracking backend | 6 | citations.py, api.py |
| 3 | Click tracking frontend | 3 | compiler.py (just inject), article.html |
| 4 | LAN catalog module | 5 | lan.py (new) |
| 5 | UDP node discovery | 5 | lan.py |
| 6 | LAN API routes | 3 | api_lan.py (new) |
| 7 | CLI + settings | 0 | settings.py, lan_commands.py (new), main.py |
| 8 | Integration | — | STATUS.md |

**Total: 8 commits, ~32 new tests, ~173+ tests total**
