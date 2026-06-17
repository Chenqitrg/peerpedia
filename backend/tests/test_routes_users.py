# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Integration tests for user API routes."""

import pytest
from fastapi.testclient import TestClient
from peerpedia_core.storage.db.engine import get_session


@pytest.fixture
def client(db_engine):
    from peerpedia_api import deps
    from peerpedia_api.main import app

    def override_db():
        session = get_session(db_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestUserCRUD:
    def test_create_user(self, client):
        resp = client.post(
            "/api/v1/users",
            json={
                "username": "testuser",
                "password": "666666",
                "email": "test@test.com",
                "name": "测试用户",
                "affiliation": "清华",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "测试用户"
        assert data["anonymous_name"] != ""

    def test_get_user(self, client):
        resp = client.post(
            "/api/v1/users", json={"username": "zhangsan", "password": "666666", "email": "z@t.com", "name": "张三"}
        )
        uid = resp.json()["id"]
        resp2 = client.get(f"/api/v1/users/{uid}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "张三"
        assert "followers_count" in resp2.json()

    def test_get_nonexistent(self, client):
        resp = client.get("/api/v1/users/nonexistent")
        assert resp.status_code == 404

    def test_list_users(self, client):
        client.post("/api/v1/users", json={"username": "userA", "password": "666666", "email": "a@t.com", "name": "A"})
        client.post("/api/v1/users", json={"username": "userB", "password": "666666", "email": "b@t.com", "name": "B"})
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2


class TestFollow:
    def test_follow_unfollow(self, client, auth_header):
        a = client.post("/api/v1/users", json={"username": "folA", "password": "666666", "email": "a@t.com", "name": "A"}).json()
        b = client.post("/api/v1/users", json={"username": "folB", "password": "666666", "email": "b@t.com", "name": "B"}).json()

        headers_a = auth_header(a["id"])

        # follow: user A follows user B
        resp = client.post(f"/api/v1/users/{b['id']}/follow", headers=headers_a)
        assert resp.status_code == 201
        assert resp.json()["following"] is True

        # unfollow
        resp = client.delete(f"/api/v1/users/{b['id']}/follow", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["following"] is False

    def test_followers_list(self, client, auth_header):
        a = client.post("/api/v1/users", json={"username": "folA", "password": "666666", "email": "a@t.com", "name": "A"}).json()
        b = client.post("/api/v1/users", json={"username": "folB", "password": "666666", "email": "b@t.com", "name": "B"}).json()

        headers_b = auth_header(b["id"])

        # user B follows user A
        client.post(f"/api/v1/users/{a['id']}/follow", headers=headers_b)

        resp = client.get(f"/api/v1/users/{a['id']}/followers")
        assert resp.status_code == 200
        followers = resp.json()
        assert len(followers) == 1
        assert followers[0]["id"] == b["id"]
        assert followers[0]["article_count"] >= 0, "followers should include article_count"
        assert isinstance(followers[0]["reputation"], dict), "followers should include reputation dict"

    def test_following_list_includes_reputation_and_article_count(self, client, auth_header):
        a = client.post("/api/v1/users", json={"username": "folC", "password": "666666", "email": "c@t.com", "name": "C"}).json()
        b = client.post("/api/v1/users", json={"username": "folD", "password": "666666", "email": "d@t.com", "name": "D"}).json()

        headers_a = auth_header(a["id"])
        client.post(f"/api/v1/users/{b['id']}/follow", headers=headers_a)

        resp = client.get(f"/api/v1/users/{a['id']}/following")
        assert resp.status_code == 200
        following = resp.json()
        assert len(following) == 1
        assert following[0]["id"] == b["id"]
        assert "article_count" in following[0], "following list should include article_count"
        assert "reputation" in following[0], "following list should include reputation"

    def test_follow_nonexistent_user_returns_404(self, client, auth_header):
        """Following a non-existent user returns 404."""
        a = client.post(
            "/api/v1/users",
            json={
                "username": "fol_404",
                "password": "666666",
                "email": "f@t.com",
                "name": "Follower",
            },
        ).json()
        headers = auth_header(a["id"])
        resp = client.post("/api/v1/users/nonexistent-id/follow", headers=headers)
        assert resp.status_code == 404

    def test_create_user_with_optional_fields(self, client):
        """Creating a user with expertise, avatar_url, and contact."""
        resp = client.post(
            "/api/v1/users",
            json={
                "username": "full_user",
                "password": "pass123",
                "email": "full@test.com",
                "name": "Full User",
                "affiliation": "MIT",
                "expertise": ["physics", "math"],
                "avatar_url": "https://example.com/avatar.png",
                "contact": "@full_user",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["expertise"] == ["physics", "math"]
        assert data["avatar_url"] == "https://example.com/avatar.png"
        assert data["contact"] == "@full_user"

    def test_update_own_profile(self, client, auth_header):
        """A user can update their own profile fields."""
        a = client.post(
            "/api/v1/users",
            json={
                "username": "self_edit",
                "password": "pass123",
                "email": "s@t.com",
                "name": "Self Editor",
            },
        ).json()
        headers = auth_header(a["id"])
        resp = client.put(
            f"/api/v1/users/{a['id']}",
            headers=headers,
            json={"affiliation": "New University", "expertise": ["cs"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["affiliation"] == "New University"
        assert data["expertise"] == ["cs"]

    def test_update_other_user_profile_returns_403(self, client, auth_header):
        """A user cannot update another user's profile."""
        a = client.post(
            "/api/v1/users",
            json={
                "username": "victim",
                "password": "pass123",
                "email": "v@t.com",
                "name": "Victim",
            },
        ).json()
        b = client.post(
            "/api/v1/users",
            json={
                "username": "attacker",
                "password": "pass123",
                "email": "at@t.com",
                "name": "Attacker",
            },
        ).json()
        headers_b = auth_header(b["id"])
        resp = client.put(
            f"/api/v1/users/{a['id']}",
            headers=headers_b,
            json={"affiliation": "Hacked"},
        )
        assert resp.status_code == 403

    def test_update_anonymous_name(self, client, auth_header):
        """A user can update their anonymous_name."""
        a = client.post(
            "/api/v1/users",
            json={
                "username": "anon_edit",
                "password": "pass123",
                "email": "ae@t.com",
                "name": "Anon Editor",
            },
        ).json()
        headers = auth_header(a["id"])
        resp = client.put(
            f"/api/v1/users/{a['id']}",
            headers=headers,
            json={"anonymous_name": "量子探索者"},
        )
        assert resp.status_code == 200
        assert resp.json()["anonymous_name"] == "量子探索者"

    def test_update_avatar_url(self, client, auth_header):
        """A user can update their avatar_url."""
        a = client.post(
            "/api/v1/users",
            json={
                "username": "avatar_edit",
                "password": "pass123",
                "email": "av@t.com",
                "name": "Avatar Editor",
            },
        ).json()
        headers = auth_header(a["id"])
        resp = client.put(
            f"/api/v1/users/{a['id']}",
            headers=headers,
            json={"avatar_url": "https://example.com/pic.png"},
        )
        assert resp.status_code == 200
        assert resp.json()["avatar_url"] == "https://example.com/pic.png"

    def test_update_contact(self, client, auth_header):
        """A user can update their contact."""
        a = client.post(
            "/api/v1/users",
            json={
                "username": "contact_edit",
                "password": "pass123",
                "email": "ce@t.com",
                "name": "Contact Editor",
            },
        ).json()
        headers = auth_header(a["id"])
        resp = client.put(
            f"/api/v1/users/{a['id']}",
            headers=headers,
            json={"contact": "@contact_editor"},
        )
        assert resp.status_code == 200
        assert resp.json()["contact"] == "@contact_editor"
