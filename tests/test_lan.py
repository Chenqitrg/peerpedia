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
        upsert_node(session, node_id="fresh", host="192.168.1.10", port=8080)
        session.commit()

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

        upsert_node(session, node_id="fresh", host="192.168.1.10", port=8080)
        old = NodeInfo(
            node_id="old",
            host="192.168.1.20",
            port=8080,
            last_seen=datetime.now(timezone.utc) - timedelta(seconds=7200),
        )
        session.add(old)
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
        assert removed == 1

        remaining = session.query(NodeInfo).all()
        remaining_ids = {n.node_id for n in remaining}
        assert "fresh" in remaining_ids
        assert "myself" in remaining_ids
        assert "old" not in remaining_ids
        session.close()
