"""Integration tests for user API routes."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User


@pytest.fixture
def client(db_engine):
    from peerpedia_api.main import app
    from peerpedia_api import deps

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
        resp = client.post("/api/v1/users", json={"username": "testuser", "password": "666666", "email": "test@test.com", "name": "测试用户", "affiliation": "清华"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "测试用户"
        assert data["anonymous_name"] != ""

    def test_get_user(self, client):
        resp = client.post("/api/v1/users", json={"username": "zhangsan", "password": "666666", "email": "z@t.com", "name": "张三"})
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
    def test_follow_unfollow(self, client):
        a = client.post("/api/v1/users", json={"username": "folA", "password": "666666", "email": "a@t.com", "name": "A"}).json()
        b = client.post("/api/v1/users", json={"username": "folB", "password": "666666", "email": "b@t.com", "name": "B"}).json()

        # follow
        resp = client.post(f"/api/v1/users/{b['id']}/follow?follower_id={a['id']}")
        assert resp.status_code == 201
        assert resp.json()["following"] is True

        # unfollow
        resp = client.delete(f"/api/v1/users/{b['id']}/follow?follower_id={a['id']}")
        assert resp.status_code == 200
        assert resp.json()["following"] is False

    def test_followers_list(self, client):
        a = client.post("/api/v1/users", json={"username": "folA", "password": "666666", "email": "a@t.com", "name": "A"}).json()
        b = client.post("/api/v1/users", json={"username": "folB", "password": "666666", "email": "b@t.com", "name": "B"}).json()
        client.post(f"/api/v1/users/{a['id']}/follow?follower_id={b['id']}")

        resp = client.get(f"/api/v1/users/{a['id']}/followers")
        assert resp.status_code == 200
        followers = resp.json()
        assert len(followers) == 1
        assert followers[0]["id"] == b["id"]
