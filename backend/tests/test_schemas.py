# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for API request/response schemas (Pydantic models)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


class TestFiveDimScoresSchema:
    def test_valid_scores(self):
        from peerpedia_api.schemas.article import FiveDimScoresOut

        s = FiveDimScoresOut(originality=4.0, rigor=3.5, completeness=5.0, pedagogy=2.0, impact=4.5)
        assert s.model_dump()["originality"] == 4.0

    def test_clamps_out_of_range(self):
        from peerpedia_api.schemas.article import FiveDimScoresOut

        s = FiveDimScoresOut(originality=6.0, rigor=-1.0, completeness=5.0, pedagogy=0.0, impact=7.0)
        assert s.originality == 5.0
        assert s.rigor == 0.0
        assert s.impact == 5.0


class TestArticleSummary:
    def test_valid_article_summary(self):
        from peerpedia_api.schemas.article import ArticleSummary, AuthorInfo

        a = ArticleSummary(
            id="abc123",
            status="published",
            authors=[AuthorInfo(id="u1", name="Alice", anonymous_name="anon_alice")],
            fork_count=5,
            created_at=datetime.now(timezone.utc),
        )
        d = a.model_dump()
        assert d["id"] == "abc123"
        assert d["fork_count"] == 5

    def test_rejects_invalid_status(self):
        from peerpedia_api.schemas.article import ArticleSummary

        with pytest.raises(ValidationError):
            from peerpedia_api.schemas.article import AuthorInfo

            ArticleSummary(
                id="x",
                status="invalid",
                authors=[AuthorInfo(id="u1", name="A")],
                fork_count=0,
                created_at=datetime.now(timezone.utc),
            )


class TestArticleDetail:
    def test_detail_includes_all_fields(self):
        from peerpedia_api.schemas.article import ArticleDetail, AuthorInfo

        now = datetime.now(timezone.utc)
        a = ArticleDetail(
            id="a1",
            status="published",
            authors=[AuthorInfo(id="u1", name="Alice", anonymous_name="anon_alice")],
            fork_count=0,
            created_at=now,
            updated_at=now,
            compiled_format="html",
            compiled_output="<h1>Hi</h1>",
            compiled_pages=None,
            score={"originality": 4.0, "rigor": 3.0, "completeness": 4.0, "pedagogy": 3.0, "impact": 3.5},
            sink_eta=None,
            days_remaining=None,
            forked_from=None,
            review_count=2,
        )
        d = a.model_dump()
        assert d["review_count"] == 2
        assert d["compiled_format"] == "html"


class TestReviewOut:
    def test_review_output(self):
        from peerpedia_api.schemas.review import ReviewOut

        now = datetime.now(timezone.utc)
        r = ReviewOut(
            id="r1",
            article_id="a1",
            commit_hash="abc",
            reviewer_id="u1",
            scope="pool",
            scores={"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
            thread=[],
            created_at=now,
            updated_at=now,
            reviewer_name="星云观察者",
        )
        assert r.reviewer_name == "星云观察者"


class TestReviewCreate:
    def test_valid_create_request(self):
        from peerpedia_api.schemas.review import ReviewCreate

        r = ReviewCreate(
            article_id="a1",
            commit_hash="abc",
            reviewer_id="u1",
            scope="pool",
            scores={"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
        )
        assert r.scope == "pool"

    def test_rejects_invalid_scope(self):
        from peerpedia_api.schemas.review import ReviewCreate

        with pytest.raises(ValidationError):
            ReviewCreate(
                article_id="a1",
                commit_hash="abc",
                reviewer_id="u1",
                scope="invalid",
                scores={"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
            )

    def test_rejects_missing_dimension(self):
        from peerpedia_api.schemas.review import ReviewCreate

        with pytest.raises(ValidationError):
            ReviewCreate(
                article_id="a1", commit_hash="abc", reviewer_id="u1", scope="pool", scores={"originality": 4, "rigor": 3}
            )  # missing 3 dims


class TestThreadMessageSchema:
    def test_message_create(self):
        from peerpedia_api.schemas.review import ThreadMessageCreate

        m = ThreadMessageCreate(content="需要补充推导。")
        assert m.content == "需要补充推导。"

    def test_rejects_empty(self):
        from peerpedia_api.schemas.review import ThreadMessageCreate

        with pytest.raises(ValidationError):
            ThreadMessageCreate(content="")

    def test_rejects_too_long(self):
        from peerpedia_api.schemas.review import ThreadMessageCreate

        with pytest.raises(ValidationError):
            ThreadMessageCreate(content="x" * 301)


class TestUserProfile:
    def test_user_profile(self):
        from peerpedia_api.schemas.user import UserProfile

        now = datetime.now(timezone.utc)
        u = UserProfile(
            id="u1",
            name="张三",
            anonymous_name="星云评审员",
            affiliation="清华大学",
            expertise=["物理", "数学"],
            reputation={"professionalism": 4.0, "objectivity": 3.5, "collaboration": 4.0, "pedagogy": 4.5},
            followers_count=10,
            following_count=5,
            article_count=3,
            created_at=now,
        )
        assert u.reputation["pedagogy"] == 4.5
        assert u.followers_count == 10


class TestArticleCreate:
    def test_minimal_create(self):
        from peerpedia_api.schemas.article import ArticleCreate

        a = ArticleCreate(
            authors=["u1"],
            self_review={"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
        )
        assert a.authors == ["u1"]

    def test_optional_fields(self):
        from peerpedia_api.schemas.article import ArticleCreate

        a = ArticleCreate(
            authors=["u1"],
            title="相对论讲义",
            abstract="一篇关于相对论的文章",
            keywords=["相对论", "物理"],
            categories=["理论物理"],
            self_review={"originality": 5, "rigor": 4, "completeness": 5, "pedagogy": 4, "impact": 5},
        )
        assert a.title == "相对论讲义"
        assert a.categories == ["理论物理"]


# ═══════════════════════════════════════════════════════════════════════════════
# Schema edge case tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleDetailEdgeCases:
    """ArticleDetail with null optional fields."""

    def test_detail_with_null_sink_eta_and_days(self):
        from peerpedia_api.schemas.article import ArticleDetail

        now = datetime.now(timezone.utc)
        a = ArticleDetail(
            id="a1",
            status="published",
            authors=[],
            fork_count=0,
            created_at=now,
            updated_at=now,
            sink_eta=None,
            days_remaining=None,
            forked_from=None,
            score=None,
            review_count=0,
        )
        d = a.model_dump()
        assert d["sink_eta"] is None
        assert d["days_remaining"] is None
        assert d["score"] is None

    def test_detail_with_zero_counts(self):
        from peerpedia_api.schemas.article import ArticleDetail

        now = datetime.now(timezone.utc)
        a = ArticleDetail(
            id="a_min",
            status="draft",
            authors=[],
            fork_count=0,
            created_at=now,
            updated_at=now,
            review_count=0,
        )
        assert a.review_count == 0
        assert a.fork_count == 0
        assert a.is_bookmarked is False
        assert a.is_own_article is False


class TestUserProfileEdgeCases:
    """UserProfile with empty/null optional fields."""

    def test_user_profile_with_empty_expertise(self):
        from peerpedia_api.schemas.user import UserProfile

        now = datetime.now(timezone.utc)
        u = UserProfile(
            id="u1",
            name="测试",
            affiliation="",
            expertise=[],
            avatar_url=None,
            contact=None,
            reputation={},
            followers_count=0,
            following_count=0,
            article_count=0,
            created_at=now,
        )
        assert u.expertise == []
        assert u.affiliation == ""
        assert u.avatar_url is None
        assert u.reputation == {}

    def test_user_profile_with_full_reputation(self):
        from peerpedia_api.schemas.user import UserProfile

        now = datetime.now(timezone.utc)
        u = UserProfile(
            id="u2",
            name="专家",
            expertise=["物理", "数学"],
            reputation={"professionalism": 5.0, "objectivity": 4.5, "collaboration": 3.0, "pedagogy": 4.0},
            followers_count=100,
            following_count=50,
            article_count=12,
            created_at=now,
        )
        assert u.reputation["professionalism"] == 5.0
        assert u.followers_count == 100


class TestRegisterRequestValidation:
    """RegisterRequest: username, password, email, name validators."""

    def test_username_too_long(self):
        from peerpedia_api.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError, match="32"):
            RegisterRequest(
                username="a" * 33,
                password="valid123",
                email="valid@test.com",
                name="Valid Name",
            )

    def test_username_special_chars(self):
        from peerpedia_api.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError, match="only letters"):
            RegisterRequest(
                username="bad user!",
                password="valid123",
                email="valid@test.com",
                name="Valid Name",
            )

    def test_password_too_short(self):
        from peerpedia_api.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError, match="6"):
            RegisterRequest(
                username="valid_user",
                password="12345",
                email="valid@test.com",
                name="Valid Name",
            )

    def test_name_whitespace_only(self):
        from peerpedia_api.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError, match="required"):
            RegisterRequest(
                username="valid_user",
                password="valid123",
                email="valid@test.com",
                name="   ",
            )

    def test_username_max_32_is_valid(self):
        from peerpedia_api.schemas.auth import RegisterRequest

        r = RegisterRequest(
            username="a" * 32,
            password="valid123",
            email="valid@test.com",
            name="Valid Name",
        )
        assert len(r.username) == 32


class TestReviewCreateContributions:
    """ReviewCreate with optional contributions validation."""

    def test_valid_contributions(self):
        from peerpedia_api.schemas.review import ReviewCreate

        r = ReviewCreate(
            article_id="a1",
            commit_hash="abc",
            scope="pool",
            scores={"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
            contributions={"u1": {"originality": 0.5, "rigor": 0.3, "completeness": 0.2, "pedagogy": 0.0, "impact": 0.0}},
        )
        assert r.contributions is not None

    def test_contributions_missing_dimension(self):
        from peerpedia_api.schemas.review import ReviewCreate

        with pytest.raises(ValidationError):
            ReviewCreate(
                article_id="a1",
                commit_hash="abc",
                scope="pool",
                scores={"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
                contributions={"u1": {"originality": 0.5}},  # missing 4 dims
            )

    def test_contributions_out_of_range(self):
        from peerpedia_api.schemas.review import ReviewCreate

        with pytest.raises(ValidationError):
            ReviewCreate(
                article_id="a1",
                commit_hash="abc",
                scope="pool",
                scores={"originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
                contributions={"u1": {"originality": 1.5, "rigor": 0.3, "completeness": 0.2, "pedagogy": 0.0, "impact": 0.0}},
            )

    def test_scores_above_five(self):
        from peerpedia_api.schemas.review import ReviewCreate

        with pytest.raises(ValidationError):
            ReviewCreate(
                article_id="a1",
                commit_hash="abc",
                scope="pool",
                scores={"originality": 6, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 3},
            )


class TestValidationEdgeCases:
    """Validation of edge-case inputs."""

    def test_scores_at_boundaries(self):
        from peerpedia_api.schemas.article import FiveDimScoresOut

        # All zeros — valid
        s = FiveDimScoresOut(originality=0.0, rigor=0.0, completeness=0.0, pedagogy=0.0, impact=0.0)
        assert s.originality == 0.0

        # All fives — valid
        s2 = FiveDimScoresOut(originality=5.0, rigor=5.0, completeness=5.0, pedagogy=5.0, impact=5.0)
        assert s2.originality == 5.0

        # Clamping
        s3 = FiveDimScoresOut(originality=-10.0, rigor=99.0, completeness=5.0, pedagogy=2.5, impact=3.0)
        assert s3.originality == 0.0  # clamped to 0
        assert s3.rigor == 5.0  # clamped to 5
