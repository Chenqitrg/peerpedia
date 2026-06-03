"""Tests for user follow system."""
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from sqlalchemy.exc import IntegrityError

from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    create_user,
    follow_user,
    unfollow_user,
    is_following,
    get_following,
    get_followers,
    get_following_count,
    get_follower_count,
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
def users(engine):
    session = get_session(engine)
    create_user(session, id="alice", name="Alice", email="alice@test.com")
    create_user(session, id="bob", name="Bob", email="bob@test.com")
    create_user(session, id="charlie", name="Charlie", email="charlie@test.com")
    session.commit()
    session.close()


class TestFollowCRUD:

    def test_follow_user(self, engine, users):
        session = get_session(engine)
        follow = follow_user(session, follower_id="alice", followed_id="bob")
        session.commit()
        assert follow.follower_id == "alice"
        assert follow.followed_id == "bob"
        session.close()

    def test_unfollow_user(self, engine, users):
        session = get_session(engine)
        follow_user(session, follower_id="alice", followed_id="bob")
        session.commit()

        result = unfollow_user(session, follower_id="alice", followed_id="bob")
        session.commit()
        assert result is True
        assert not is_following(session, "alice", "bob")
        session.close()

    def test_unfollow_nonexistent(self, engine, users):
        session = get_session(engine)
        result = unfollow_user(session, follower_id="alice", followed_id="bob")
        session.commit()
        assert result is False
        session.close()

    def test_duplicate_follow_raises(self, engine, users):
        session = get_session(engine)
        follow_user(session, follower_id="alice", followed_id="bob")
        session.commit()
        with pytest.raises(IntegrityError):
            follow_user(session, follower_id="alice", followed_id="bob")
            session.flush()
        session.rollback()
        session.close()

    def test_is_following(self, engine, users):
        session = get_session(engine)
        assert not is_following(session, "alice", "bob")
        follow_user(session, follower_id="alice", followed_id="bob")
        session.commit()
        assert is_following(session, "alice", "bob")
        session.close()

    def test_get_following(self, engine, users):
        session = get_session(engine)
        follow_user(session, follower_id="alice", followed_id="bob")
        follow_user(session, follower_id="alice", followed_id="charlie")
        session.commit()

        following = get_following(session, "alice")
        assert len(following) == 2
        followed_ids = {f.followed_id for f in following}
        assert followed_ids == {"bob", "charlie"}
        session.close()

    def test_get_followers(self, engine, users):
        session = get_session(engine)
        follow_user(session, follower_id="alice", followed_id="charlie")
        follow_user(session, follower_id="bob", followed_id="charlie")
        session.commit()

        followers = get_followers(session, "charlie")
        assert len(followers) == 2
        follower_ids = {f.follower_id for f in followers}
        assert follower_ids == {"alice", "bob"}
        session.close()

    def test_counts(self, engine, users):
        session = get_session(engine)
        follow_user(session, follower_id="alice", followed_id="bob")
        follow_user(session, follower_id="alice", followed_id="charlie")
        follow_user(session, follower_id="bob", followed_id="alice")
        session.commit()

        assert get_following_count(session, "alice") == 2
        assert get_follower_count(session, "alice") == 1
        assert get_following_count(session, "charlie") == 0
        assert get_follower_count(session, "charlie") == 1
        session.close()


from fastapi.testclient import TestClient

from peerpedia_core.storage.db import get_engine, get_session, init_db


def _setup_test_db(tmp_path):
    """Create a test database and return the database URL."""
    db_path = tmp_path / "test.db"
    engine = get_engine(f"sqlite:///{db_path}")
    init_db(engine)
    session = get_session(engine)
    session.close()
    return f"sqlite:///{db_path}"


def _create_users(db_url):
    """Create test users via API."""
    from peerpedia.web.app import app
    with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
        client = TestClient(app)
        for uid, name in [("alice", "Alice"), ("bob", "Bob"), ("charlie", "Charlie")]:
            client.post("/api/v1/users", json={
                "id": uid, "name": name, "email": f"{uid}@test.com"
            })


class TestFollowAPI:

    def test_follow_user(self):
        """POST /api/v1/users/{id}/follow creates follow relationship."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})
                assert resp.status_code == 200
                assert "已关注" in resp.text

    def test_unfollow_user(self):
        """DELETE /api/v1/users/{id}/follow removes follow."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})
                resp = client.request("DELETE", "/api/v1/users/bob/follow", data={"follower_id": "alice"})
                assert resp.status_code == 200
                assert "关注" in resp.text

    def test_follow_nonexistent_user(self):
        """Follow nonexistent user returns 404."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post("/api/v1/users/nobody/follow", data={"follower_id": "alice"})
                assert resp.status_code == 404

    def test_duplicate_follow_returns_409(self):
        """Duplicate follow returns 409."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})
                resp = client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})
                assert resp.status_code == 409

    def test_get_following(self):
        """GET /api/v1/users/{id}/following returns list."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})
                resp = client.get("/api/v1/users/alice/following")
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] >= 1

    def test_get_followers(self):
        """GET /api/v1/users/{id}/followers returns list."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})
                resp = client.get("/api/v1/users/bob/followers")
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] >= 1

    def test_feed(self):
        """GET /api/v1/following/feed returns events."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/following/feed?user_id=alice")
                assert resp.status_code == 200
                data = resp.json()
                assert "events" in data
                assert isinstance(data["events"], list)

    def test_feed_with_no_follows_returns_empty(self):
        """Feed for user with no follows returns empty events, no error."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                # alice follows nobody — feed should be empty, not error
                resp = client.get("/api/v1/following/feed?user_id=alice")
                assert resp.status_code == 200
                data = resp.json()
                assert data["events"] == []
                assert data["user_id"] == "alice"

    def test_feed_missing_user_id(self):
        """Feed without user_id should return empty events, not 500."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/following/feed")
                # Should handle gracefully, not crash
                assert resp.status_code in (200, 400, 422)

    def test_feed_structure_has_required_fields(self):
        """Feed events should have required fields when articles exist."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                # Make alice follow bob
                client = TestClient(app)
                client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})

                resp = client.get("/api/v1/following/feed?user_id=alice")
                assert resp.status_code == 200
                data = resp.json()
                assert "user_id" in data
                assert "events" in data
                # Each event, if present, should have required fields
                for event in data["events"]:
                    assert "type" in event
                    assert event["type"] in ("new_article", "new_version")
                    assert "user_id" in event
                    assert "time" in event

    def test_cannot_self_follow(self):
        """POST /api/v1/users/{id}/follow with same follower_id returns 400."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.post("/api/v1/users/alice/follow", data={"follower_id": "alice"})
                assert resp.status_code == 400

    def test_followers_html_list_shows_correct_names(self):
        """GET /users/{id}/followers?format=html returns follower names (not followed_id)."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                # bob and charlie follow alice
                client.post("/api/v1/users/alice/follow", data={"follower_id": "bob"})
                client.post("/api/v1/users/alice/follow", data={"follower_id": "charlie"})

                resp = client.get("/api/v1/users/alice/followers?format=html&viewer=alice")
                assert resp.status_code == 200
                html = resp.text
                assert "bob" in html, f"Expected bob in followers list: {html}"
                assert "charlie" in html, f"Expected charlie in followers list: {html}"
                assert '<ul class="follow-list">' in html

    def test_following_html_list_shows_correct_names(self):
        """GET /users/{id}/following?format=html returns followed names."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                client.post("/api/v1/users/bob/follow", data={"follower_id": "alice"})
                client.post("/api/v1/users/charlie/follow", data={"follower_id": "alice"})

                resp = client.get("/api/v1/users/alice/following?format=html&viewer=alice")
                assert resp.status_code == 200
                html = resp.text
                assert "bob" in html, f"Expected bob in following: {html}"
                assert "charlie" in html, f"Expected charlie in following: {html}"

    def test_followers_html_empty_returns_placeholder(self):
        """GET /users/{id}/followers?format=html with no followers returns placeholder."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url = _setup_test_db(Path(tmp))
            _create_users(db_url)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/users/alice/followers?format=html")
                assert resp.status_code == 200
                assert "暂无" in resp.text or "follow-empty" in resp.text
