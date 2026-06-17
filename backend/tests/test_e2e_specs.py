# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Locked specification tests — define product behavior.

SPECIFICATION STATUS = LOCKED
"""

import pytest
from fastapi.testclient import TestClient
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, ArticleAuthor, User
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    commit_article,
    init_article_repo,
)


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


def _create_article_with_user(db_engine, username="spec_user"):
    s = get_session(db_engine)
    u = User(username=username, password_hash="", name="Spec Tester")
    s.add(u)
    s.commit()

    a = Article(status="draft")
    s.add(a)
    s.flush()
    s.add(ArticleAuthor(article_id=a.id, author_id=u.id, position=0))
    s.commit()
    aid, uid = a.id, u.id
    s.close()

    rp = init_article_repo(aid, DEFAULT_ARTICLES_DIR)
    (rp / "article.md").write_text("# Spec\n\nContent")
    commit_article(rp, "Initial", username, f"{username}@test.com")
    return aid, uid


class TestSpec3ForkUserValidation:
    def test_fork_works_with_server_user(self, client, db_engine):
        aid, uid = _create_article_with_user(db_engine, "fork_user_1")
        s = get_session(db_engine)
        user = s.query(User).filter(User.id == uid).first()
        s.close()

        from peerpedia_api import deps as api_deps
        from peerpedia_api.main import app

        app.dependency_overrides[api_deps.require_user] = lambda: user

        resp = client.post(f"/api/v1/articles/{aid}/fork")
        assert resp.status_code == 201, f"Fork failed: {resp.text}"
        data = resp.json()
        assert "id" in data
        assert data["forked_from"] == aid

    def test_fork_returns_404_for_nonexistent_article(self, client, db_engine):
        _, uid = _create_article_with_user(db_engine, "fork_user_2")
        s = get_session(db_engine)
        user = s.query(User).filter(User.id == uid).first()
        s.close()

        from peerpedia_api import deps as api_deps
        from peerpedia_api.main import app

        app.dependency_overrides[api_deps.require_user] = lambda: user

        resp = client.post("/api/v1/articles/nonexistent-id/fork")
        assert resp.status_code == 404
