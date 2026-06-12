"""Specification: Sedimentation Pool Auto-Publish.

The sedimentation pool is a time-boxed review period. When articles' sink time
elapses, they auto-publish. The `publish_ready_articles` function scans all
sedimentation articles and publishes those whose sink ETA has passed.

Contract:
  SP1 — Articles in "sedimentation" with elapsed sink time are published.
  SP2 — Articles without a sink_start are skipped (defensive guard).
  SP3 — Articles with null tzinfo on sink_start are treated as UTC.
  SP4 — No-review penalty is applied when an article has zero community reviews.
  SP5 — Author reputations are recalculated after publish.
  SP6 — Returns count of articles published in this call.
"""
from datetime import datetime, timedelta, timezone

import pytest

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, ArticleAuthor, Review, User
from peerpedia_core.workflow.sedimentation import (
    compute_sink_eta,
    is_ready_to_publish,
    publish_ready_articles,
)


def _make_user(session, name):
    u = User(
        username=f"sp_{name}",
        password_hash="",
        name=name,
        anonymous_name=f"anon_{name}",
    )
    session.add(u)
    session.commit()
    return u


def _make_article(session, authors, **kw):
    a = Article(**kw)
    session.add(a)
    session.flush()
    for pos, aid in enumerate(authors):
        session.add(ArticleAuthor(article_id=a.id, author_id=aid, position=pos))
    session.commit()
    return a


def _make_review(session, article_id, commit_hash, reviewer_id, scope, scores):
    r = Review(
        article_id=article_id,
        commit_hash=commit_hash,
        reviewer_id=reviewer_id,
        scope=scope,
        scores=scores,
    )
    session.add(r)
    session.commit()
    return r


class TestIsReadyToPublish:
    """SP3 — is_ready_to_publish handles timezone-naive and aware datetimes."""

    def test_past_returns_true(self):
        past = datetime.now(timezone.utc) - timedelta(days=10)
        assert is_ready_to_publish(past) is True

    def test_future_returns_false(self):
        future = datetime.now(timezone.utc) + timedelta(days=10)
        assert is_ready_to_publish(future) is False

    def test_none_returns_false(self):
        assert is_ready_to_publish(None) is False

    def test_naive_datetime_treated_as_utc(self):
        """SP3 — A timezone-naive datetime is treated as UTC."""
        # Create a naive datetime in the past
        past = datetime.utcnow() - timedelta(days=10)  # naive
        # Should not crash, and should correctly determine it's in the past
        result = is_ready_to_publish(past)
        assert result is True


class TestComputeSinkEta:
    """Sink ETA calculation with different scores."""

    def test_max_score_min_time(self):
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        eta = compute_sink_eta(start, avg_score=5.0, min_days=2, max_days=180)
        assert eta == start + timedelta(days=2)

    def test_min_score_max_time(self):
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        eta = compute_sink_eta(start, avg_score=0.0, min_days=2, max_days=180)
        assert eta == start + timedelta(days=180)


def _build_score(orig=3, rig=3, comp=3, ped=3, imp=3):
    return {"originality": orig, "rigor": rig, "completeness": comp,
            "pedagogy": ped, "impact": imp}


class TestPublishReadyArticles:
    """SP1-SP6 — Full auto-publish lifecycle."""

    @pytest.fixture
    def session(self, engine):
        s = get_session(engine)
        yield s
        s.close()

    def test_no_sedimentation_articles_returns_zero(self, session):
        """SP6 — When no articles are in sedimentation, returns 0."""
        count = publish_ready_articles(session)
        assert count == 0

    def test_skips_articles_without_sink_start(self, session):
        """SP2 — Articles without sink_start are skipped."""
        author = _make_user(session, "no_sink")
        _make_article(session, [author.id], status="sedimentation")
        # Article has status=sedimentation but no sink_start — should be skipped
        count = publish_ready_articles(session)
        assert count == 0

    def test_publishes_article_with_elapsed_sink(self, session):
        """SP1 — An article whose sink time has elapsed gets published,
        even without a git repo directory (uses article.score fallback)."""
        author = _make_user(session, "elapsed")
        past_start = datetime.now(timezone.utc) - timedelta(days=200)
        _make_article(
            session, [author.id],
            status="sedimentation",
            sink_start=past_start,
            sink_duration_days=7,
            score=_build_score(3, 3, 3, 3, 3),
        )
        count = publish_ready_articles(session)
        assert count == 1
        # Verify status change
        session.expire_all()
        published = session.query(Article).filter(Article.status == "published").all()
        assert len(published) == 1

    def test_publishes_article_with_git_repo(self, session):
        """SP1 — When .git directory exists, uses commit_hash for score."""
        import tempfile
        from pathlib import Path

        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        author = _make_user(session, "has_git")
        past_start = datetime.now(timezone.utc) - timedelta(days=200)

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article = _make_article(
                session, [author.id],
                status="sedimentation",
                sink_start=past_start,
                sink_duration_days=7,
            )
            article_id = article.id

            # Monkey-patch DEFAULT_ARTICLES_DIR to point to our temp dir
            import peerpedia_core.storage.git_backend as gb_mod
            orig_dir = gb_mod.DEFAULT_ARTICLES_DIR
            try:
                gb_mod.DEFAULT_ARTICLES_DIR = base
                rp = init_article_repo(article_id, base_dir=base)
                (rp / "article.md").write_text("# Test")
                commit_article(rp, "init", "A", "a@b.com", allow_empty=True)

                count = publish_ready_articles(session)
                assert count == 1
            finally:
                gb_mod.DEFAULT_ARTICLES_DIR = orig_dir

    def test_skips_article_with_future_sink_eta(self, session):
        """Articles whose sink time has not elapsed are not published."""
        author = _make_user(session, "future_sink")
        future_start = datetime.now(timezone.utc) - timedelta(days=5)
        _make_article(
            session, [author.id],
            status="sedimentation",
            sink_start=future_start,
            sink_duration_days=180,
        )
        count = publish_ready_articles(session)
        assert count == 0

    def test_publishes_with_community_reviews(self, session):
        """Article with community reviews publishes normally."""
        author = _make_user(session, "comm_rv")
        reviewer = _make_user(session, "rv_comm")
        past_start = datetime.now(timezone.utc) - timedelta(days=200)
        article = _make_article(
            session, [author.id],
            status="sedimentation",
            sink_start=past_start,
            sink_duration_days=7,
        )
        # Add a community review
        _make_review(
            session, article.id, "hash1", reviewer.id, "pool",
            _build_score(4, 4, 4, 4, 4),
        )
        count = publish_ready_articles(session)
        assert count == 1

    def test_multiple_ready_articles(self, session):
        """When multiple articles are ready, all are published."""
        author = _make_user(session, "multi")
        past_start = datetime.now(timezone.utc) - timedelta(days=200)

        for i in range(3):
            _make_article(
                session, [author.id],
                status="sedimentation",
                sink_start=past_start,
                sink_duration_days=7,
            )

        count = publish_ready_articles(session)
        assert count == 3
