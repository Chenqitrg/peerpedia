# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Direct tests for article policy functions."""

import pytest
from peerpedia_core.exceptions import NotAuthorizedError, NotFoundError
from peerpedia_core.policies.articles import (
    assert_can_bookmark_article,
    assert_can_delete_article,
    assert_can_download_content,
    assert_can_edit_article,
    assert_can_extend_sink,
    assert_can_fork_article,
    assert_can_publish_article,
    assert_can_read_article,
    assert_can_rollback_article,
    assert_can_self_review,
    assert_can_sync_article,
    get_article_or_raise,
    visible_statuses_for_user,
)
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, ArticleAuthor, User


def _setup(s, uid, aid, status="draft"):
    """Create user + article + authorship link, flushed in order."""
    u = User(id=uid, username=uid, password_hash="", name=uid, anonymous_name="a")
    a = Article(id=aid, status=status, fork_count=0)
    s.add_all([u, a])
    s.flush()
    s.add(ArticleAuthor(article_id=aid, author_id=uid, position=0))
    s.commit()
    return u, a


def _user(s, uid):
    u = User(id=uid, username=uid, password_hash="", name=uid, anonymous_name="a")
    s.add(u)
    s.commit()
    return u


def _article(s, aid, status="draft"):
    a = Article(id=aid, status=status, fork_count=0)
    s.add(a)
    s.commit()
    return a


# ── visible_statuses_for_user ────────────────────────────────────────────

class TestVisibleStatuses:
    def test_anon_sees_public(self):
        assert visible_statuses_for_user(None) == {"sedimentation", "published"}

    def test_auth_sees_all(self):
        u = User(id="ux", username="x", password_hash="", name="X", anonymous_name="a")
        assert visible_statuses_for_user(u) == {"draft", "sedimentation", "published"}


# ── get_article_or_raise ─────────────────────────────────────────────────

class TestGetArticleOrRaise:
    def test_raises_not_found(self, db_engine):
        s = get_session(db_engine)
        with pytest.raises(NotFoundError):
            get_article_or_raise(s, "nonexistent")
        s.close()

    def test_returns_article(self, db_engine):
        s = get_session(db_engine)
        a = Article(id="a-gor", status="draft", fork_count=0)
        s.add(a); s.commit()
        result = get_article_or_raise(s, a.id)
        assert result.id == "a-gor"
        s.close()


# ── assert_can_bookmark_article ──────────────────────────────────────────

class TestBookmarkPolicy:
    def test_raises_not_found_for_missing_article(self, db_engine):
        s = get_session(db_engine)
        u = _user(s, "ub0")
        with pytest.raises(NotFoundError):
            assert_can_bookmark_article(s, "nonexistent", u)
        s.close()

    def test_author_raises(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "ub1", "ab1", "published")
        with pytest.raises(NotAuthorizedError, match="own article"):
            assert_can_bookmark_article(s, a.id, u)
        s.close()

    def test_non_author_ok(self, db_engine):
        s = get_session(db_engine)
        _setup(s, "ub2a", "ab2", "published")
        u2 = _user(s, "ub2b")
        assert_can_bookmark_article(s, "ab2", u2)  # does not raise
        s.close()


# ── assert_can_self_review ───────────────────────────────────────────────

class TestSelfReviewPolicy:
    def test_author_draft_ok(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "us1", "as1", "draft")
        r = assert_can_self_review(s, a.id, u)
        assert r.id == a.id
        s.close()

    def test_author_sedimentation_ok(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "us2", "as2", "sedimentation")
        r = assert_can_self_review(s, a.id, u)
        assert r.id == a.id
        s.close()

    def test_author_published_raises(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "us3", "as3", "published")
        with pytest.raises(NotAuthorizedError, match="self-review"):
            assert_can_self_review(s, a.id, u)
        s.close()

    def test_non_author_raises(self, db_engine):
        s = get_session(db_engine)
        _setup(s, "us4a", "as4", "sedimentation")
        u2 = _user(s, "us4b")
        with pytest.raises(NotAuthorizedError, match="authors"):
            assert_can_self_review(s, "as4", u2)
        s.close()


# ── Write gates — _WRITABLE_STATUSES = {draft, published} ────────────────

class TestWriteGate:
    def test_edit_blocked_sedimentation(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "uw1", "aw1", "sedimentation")
        with pytest.raises(NotAuthorizedError, match="edit"):
            assert_can_edit_article(s, a.id, u)
        s.close()

    def test_delete_blocked_sedimentation(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "uw2", "aw2", "sedimentation")
        with pytest.raises(NotAuthorizedError, match="delete"):
            assert_can_delete_article(s, a.id, u)
        s.close()

    def test_rollback_blocked_sedimentation(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "uw3", "aw3", "sedimentation")
        with pytest.raises(NotAuthorizedError, match="rollback"):
            assert_can_rollback_article(s, a.id, u)
        s.close()

    def test_publish_blocked_sedimentation(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "uw4", "aw4", "sedimentation")
        with pytest.raises(NotAuthorizedError, match="publish"):
            assert_can_publish_article(s, a.id, u)
        s.close()

    def test_sync_blocked_sedimentation(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "uw5", "aw5", "sedimentation")
        with pytest.raises(NotAuthorizedError, match="sync"):
            assert_can_sync_article(s, a.id, u)
        s.close()

    def test_extend_sink_ok(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "uw6", "aw6", "sedimentation")
        r = assert_can_extend_sink(s, a.id, u)
        assert r.id == a.id
        s.close()

    def test_extend_sink_blocked_draft(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "uw7", "aw7", "draft")
        with pytest.raises(NotAuthorizedError):
            assert_can_extend_sink(s, a.id, u)
        s.close()

    def test_non_author_cannot_write(self, db_engine):
        s = get_session(db_engine)
        _setup(s, "uw8a", "aw8", "draft")
        u2 = _user(s, "uw8b")
        with pytest.raises(NotAuthorizedError, match="authors"):
            assert_can_edit_article(s, "aw8", u2)
        s.close()


# ── Fork ─────────────────────────────────────────────────────────────────

class TestForkPolicy:
    def test_ok_published(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "uf1", "af1", "published")
        r = assert_can_fork_article(s, a.id, u)
        assert r.id == a.id
        s.close()

    def test_blocked_draft(self, db_engine):
        s = get_session(db_engine)
        u = _user(s, "uf2")
        _article(s, "af2", "draft")
        with pytest.raises(NotAuthorizedError, match="published"):
            assert_can_fork_article(s, "af2", u)
        s.close()

    def test_blocked_sedimentation(self, db_engine):
        s = get_session(db_engine)
        u = _user(s, "uf3")
        _article(s, "af3", "sedimentation")
        with pytest.raises(NotAuthorizedError, match="published"):
            assert_can_fork_article(s, "af3", u)
        s.close()


# ── Read / Download ──────────────────────────────────────────────────────

class TestReadDownload:
    def test_anon_can_read_published(self, db_engine):
        s = get_session(db_engine)
        _article(s, "ar1", "published")
        assert assert_can_read_article(s, "ar1", None).id == "ar1"
        s.close()

    def test_anon_cannot_read_draft(self, db_engine):
        s = get_session(db_engine)
        _article(s, "ar2", "draft")
        with pytest.raises(NotAuthorizedError):
            assert_can_read_article(s, "ar2", None)
        s.close()

    def test_author_can_read_own_draft(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "ur3", "ar3", "draft")
        assert assert_can_read_article(s, a.id, u).id == a.id
        s.close()

    def test_anon_can_download_published(self, db_engine):
        s = get_session(db_engine)
        _article(s, "ar4", "published")
        assert assert_can_download_content(s, "ar4", None).id == "ar4"
        s.close()

    def test_anon_cannot_download_sedimentation(self, db_engine):
        s = get_session(db_engine)
        _article(s, "ar5", "sedimentation")
        with pytest.raises(NotAuthorizedError):
            assert_can_download_content(s, "ar5", None)
        s.close()

    def test_author_can_download_own_draft(self, db_engine):
        s = get_session(db_engine)
        u, a = _setup(s, "ur6", "ar6", "draft")
        assert assert_can_download_content(s, a.id, u).id == a.id
        s.close()
