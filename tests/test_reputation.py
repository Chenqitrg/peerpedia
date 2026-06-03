"""Tests for reputation algorithm v1."""

import pytest
from datetime import datetime, timedelta
from peerpedia_core.protocol import ReputationVector, IdentityType
from peerpedia_core.reputation import ReputationV1, ReputationParams


class TestReputationV1:

    def test_no_decay_for_active_user(self):
        algo = ReputationV1()
        vec = ReputationVector(
            user_id="u1",
            academic_contribution=50.0,
            review_quality=50.0,
            collaboration_spirit=50.0,
            education_outreach=50.0,
        )
        yesterday = datetime.utcnow() - timedelta(days=1)
        result = algo.apply_decay(vec, yesterday)
        assert result.academic_contribution == 50.0

    def test_decay_after_grace_period(self):
        algo = ReputationV1()
        vec = ReputationVector(
            user_id="u1",
            academic_contribution=100.0,
            review_quality=100.0,
            collaboration_spirit=100.0,
            education_outreach=100.0,
        )
        # 100 days inactive: 10 days of decay
        inactive_since = datetime.utcnow() - timedelta(days=100)
        result = algo.apply_decay(vec, inactive_since)

        # After 10 days of 0.1% daily decay: 100 * 0.999^10 ≈ 99.0
        assert result.academic_contribution < 100.0
        assert result.academic_contribution > 98.0

    def test_identity_bonus(self):
        algo = ReputationV1()
        vec = ReputationVector(user_id="u1")
        result = algo.merge_identities(vec, verified_count=2)
        # 2 * 5.0 = 10.0 base reputation
        assert result.academic_contribution == 10.0

    def test_identity_bonus_capped_at_100(self):
        algo = ReputationV1()
        vec = ReputationVector(user_id="u1", academic_contribution=95.0)
        result = algo.merge_identities(vec, verified_count=3)
        assert result.academic_contribution == 100.0  # capped


class TestReputationParams:

    def test_default_params(self):
        params = ReputationParams()
        assert params.decay_grace_days == 90
        assert params.decay_rate_per_day == 0.001
        assert params.identity_weights[IdentityType.ORCID] == 1.0  # type: ignore
        assert params.identity_weights[IdentityType.GITHUB] == 0.3  # type: ignore

    def test_change_type_weights(self):
        params = ReputationParams()
        assert params.change_type_weights["new_theorem"] == 5.0
        assert params.change_type_weights["format"] == 0.3


class TestReputationComputeIntegration:
    """Integration tests for ReputationV1.compute() with real DB data."""

    def test_compute_from_articles_and_reviews(self):
        """compute() should aggregate articles, reviews, and contributions."""
        import tempfile
        from pathlib import Path
        from peerpedia_core.storage.db import (
            get_engine, get_session, init_db,
            create_user, create_article, create_review, create_contribution_record,
        )

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            create_user(session, id="alice", name="Alice", email="a@test.com")
            session.commit()

            article1 = create_article(session, title="Article 1",
                                      founding_authors=["alice"], abstract="...",
                                      git_repo_path="/tmp/a1")
            article2 = create_article(session, title="Article 2",
                                      founding_authors=["alice"], abstract="...",
                                      git_repo_path="/tmp/a2")
            article3 = create_article(session, title="Article 3",
                                      founding_authors=["alice"], abstract="...",
                                      git_repo_path="/tmp/a3")
            session.commit()

            # Review three different articles (avoids uq_article_reviewer)
            for art in [article1, article2, article3]:
                create_review(session, article_id=art.id, reviewer_id="alice",
                              decision="accept", comments="good",
                              scientific_correctness=4, clarity=4,
                              points_earned=20)
            session.commit()

            create_contribution_record(session, article_id=article1.id,
                                       user_id="alice", commit_hash="abc123",
                                       change_type="content",
                                       contribution_weight=200)
            session.commit()

            algo = ReputationV1()
            vec = algo.compute("alice", session=session)

            assert vec.academic_contribution > 0
            assert vec.review_quality > 0
            assert vec.total_points == 60  # 3 × 20

    def test_compute_with_identities(self):
        """Verified identities should boost reputation."""
        import tempfile
        from pathlib import Path
        from peerpedia_core.storage.db import (
            get_engine, get_session, init_db,
            create_user, create_article, create_identity,
        )

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            create_user(session, id="bob", name="Bob", email="b@test.com")
            session.flush()  # Ensure user row exists before creating FK-referencing identities
            create_identity(session, user_id="bob", type="orcid",
                            value="0000-0001-2345-6789", verified=True,
                            trust_weight=100)
            create_identity(session, user_id="bob", type="github",
                            value="bob-dev", verified=True, trust_weight=30)
            session.commit()

            create_article(session, title="Bob's Paper",
                           founding_authors=["bob"], abstract="...",
                           git_repo_path="/tmp/b1")
            session.commit()

            algo = ReputationV1()
            vec = algo.compute("bob", session=session)

            # Should have non-zero academic from 1 article + identity boost
            assert vec.academic_contribution > 0

    def test_compute_nonexistent_user(self):
        """compute() should return zero vector for unknown user."""
        import tempfile
        from pathlib import Path
        from peerpedia_core.storage.db import get_engine, get_session, init_db

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            algo = ReputationV1()
            vec = algo.compute("ghost", session=session)
            assert vec.academic_contribution == 0.0
            assert vec.review_quality == 0.0
            assert vec.collaboration_spirit == 0.0
            assert vec.education_outreach == 0.0
            assert vec.total_points == 0

    def test_compute_updates_last_active(self):
        """compute() should update user's last_active timestamp."""
        import tempfile
        from pathlib import Path
        from peerpedia_core.storage.db import (
            get_engine, get_session, init_db,
            create_user, get_user,
        )

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            create_user(session, id="eve", name="Eve", email="eve@test.com")
            session.commit()

            # Initially no last_active
            user = get_user(session, "eve")
            assert user.last_active is None

            algo = ReputationV1()
            algo.compute("eve", session=session)
            session.commit()

            user = get_user(session, "eve")
            assert user.last_active is not None
