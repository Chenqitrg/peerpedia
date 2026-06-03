"""Tests for LAN node discovery and catalog sync."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from peerpedia_core.storage.db import (
    cleanup_stale_nodes,
    get_engine,
    get_online_nodes,
    get_session,
    init_db,
    upsert_node,
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

    def test_get_online_nodes_empty(self, engine):
        """No nodes returns empty list."""
        session = get_session(engine)
        online = get_online_nodes(session)
        assert online == []
        session.close()

    def test_cleanup_stale_nodes_nothing_stale(self, engine):
        """No stale nodes returns 0."""
        session = get_session(engine)
        upsert_node(session, node_id="fresh", host="192.168.1.10", port=8080)
        session.commit()
        removed = cleanup_stale_nodes(session, max_age_seconds=3600.0)
        session.commit()
        assert removed == 0
        session.close()

    def test_to_dict(self, engine):
        """NodeInfo.to_dict() returns correct fields."""
        session = get_session(engine)
        node = upsert_node(session, node_id="n1", host="10.0.0.1", port=8080, articles_count=3)
        session.commit()
        d = node.to_dict()
        assert d["node_id"] == "n1"
        assert d["host"] == "10.0.0.1"
        assert d["articles_count"] == 3
        assert "last_seen" in d
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


from peerpedia_core.workflow.lan import (
    CATALOG_YAML_DELIMITER,
    catalog_to_yaml_string,
    parse_catalog_yaml,
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
        # Count: exactly two delimiters
        assert yaml_str.count(CATALOG_YAML_DELIMITER + "\n") >= 2

    def test_parse_multiline_string(self):
        """Abstract with newlines survives roundtrip."""
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

    def test_parse_empty_input(self):
        """Empty or invalid input returns default dict."""
        result = parse_catalog_yaml("")
        assert result["node_id"] == "unknown"
        assert result["articles"] == []

    def test_parse_no_delimiters(self):
        """Content without YAML delimiters returns default."""
        result = parse_catalog_yaml("# Just a markdown file\n\n| Table | Here |")
        assert result["node_id"] == "unknown"
        assert result["articles"] == []


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


from unittest import mock

from fastapi.testclient import TestClient

from peerpedia.web.app import app


class TestLanAPI:
    """Tests for LAN API endpoints."""

    def _setup_test_db(self, tmp_path):
        """Create a test database and return the database URL."""
        db_path = tmp_path / "test_lan_api.db"
        engine = get_engine(f"sqlite:///{db_path}")
        init_db(engine)
        session = get_session(engine)
        session.close()
        return f"sqlite:///{db_path}"

    def _seed_article(self, db_url, article_id, title):
        """Insert a minimal article into the test DB."""
        from peerpedia_core.storage.db.models import Article

        engine = get_engine(db_url)
        init_db(engine)
        session = get_session(engine)
        from datetime import datetime, timezone
        art = Article(
            id=article_id,
            title=title,
            version="v1.1",
            status="accepted",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(art)
        session.commit()
        session.close()

    def _seed_node(self, db_url, node_id, host="127.0.0.1", port=8080):
        """Insert a node into the test DB."""
        from datetime import datetime, timezone

        from peerpedia_core.storage.db.models import NodeInfo

        engine = get_engine(db_url)
        init_db(engine)
        session = get_session(engine)
        node = NodeInfo(
            node_id=node_id,
            host=host,
            port=port,
            last_seen=datetime.now(timezone.utc),
        )
        session.add(node)
        session.commit()
        session.close()

    def test_get_catalog(self):
        """GET /api/v1/lan/catalog returns catalog.md content."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db_url = self._setup_test_db(Path(tmp))
            self._seed_article(db_url, "art1", "Test Article 1")

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                client = TestClient(app)
                response = client.get("/api/v1/lan/catalog")
                assert response.status_code == 200
                content = response.text
                assert "---" in content
                assert "node_id" in content

    def test_get_nodes(self):
        """GET /api/v1/lan/nodes returns node list."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db_url = self._setup_test_db(Path(tmp))
            self._seed_node(db_url, "node-test-1")

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                client = TestClient(app)
                response = client.get("/api/v1/lan/nodes")
                assert response.status_code == 200
                data = response.json()
                assert "nodes" in data
                assert "total" in data

    def test_get_status(self):
        """GET /api/v1/lan/status returns status summary."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db_url = self._setup_test_db(Path(tmp))
            self._seed_node(db_url, "node-test-1")

            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                client = TestClient(app)
                response = client.get("/api/v1/lan/status")
                assert response.status_code == 200
                data = response.json()
                assert "online_nodes" in data
                assert "total_nodes_seen" in data
