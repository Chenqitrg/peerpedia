"""Tests for sedimentation pool workflow and scoring aggregation."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest import mock


class TestComputeArticleScore:
    """Score aggregation: weighted average of reviews, with self-review weighting."""

    def test_no_reviews_returns_none(self):
        from peerpedia_core.workflow.scoring import compute_article_score
        assert compute_article_score([]) is None

    def test_single_review_equals_that_review(self):
        from peerpedia_core.workflow.scoring import compute_article_score
        reviews = [{"scores": {"originality": 4, "rigor": 3, "completeness": 5,
                                "pedagogy": 4, "impact": 4}, "is_self": False}]
        result = compute_article_score(reviews)
        assert result["originality"] == 4.0
        assert result["completeness"] == 5.0

    def test_self_review_weighted_lower(self):
        """Self-review has smaller weight than community reviews."""
        from peerpedia_core.workflow.scoring import compute_article_score
        reviews = [
            {"scores": {"originality": 5, "rigor": 5, "completeness": 5,
                         "pedagogy": 5, "impact": 5}, "is_self": True},
            {"scores": {"originality": 3, "rigor": 3, "completeness": 3,
                         "pedagogy": 3, "impact": 3}, "is_self": False},
        ]
        result = compute_article_score(reviews)
        # Self-review (5) weighted 0.15, community (3) weighted 0.85
        # expected ≈ 5*0.15 + 3*0.85 = 0.75 + 2.55 = 3.3
        assert result["originality"] == pytest.approx(3.3, abs=0.1)

    def test_multiple_community_reviews_averaged(self):
        from peerpedia_core.workflow.scoring import compute_article_score
        reviews = [
            {"scores": {"originality": 4, "rigor": 4, "completeness": 4,
                         "pedagogy": 4, "impact": 4}, "is_self": False},
            {"scores": {"originality": 2, "rigor": 2, "completeness": 2,
                         "pedagogy": 2, "impact": 2}, "is_self": False},
        ]
        result = compute_article_score(reviews)
        assert result["originality"] == 3.0


class TestSedimentation:
    """Sink time calculation and auto-publish logic."""

    def test_compute_sink_eta_max_score(self):
        from peerpedia_core.workflow.sedimentation import compute_sink_eta
        from datetime import datetime, timezone
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        eta = compute_sink_eta(start, avg_score=5.0,
                               min_days=2, max_days=180)
        # Max score → min time (~2 days)
        expected = start + timedelta(days=2)
        assert eta == expected

    def test_compute_sink_eta_min_score(self):
        from peerpedia_core.workflow.sedimentation import compute_sink_eta
        from datetime import datetime, timezone
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        eta = compute_sink_eta(start, avg_score=0.0,
                               min_days=2, max_days=180)
        # Min score → max time (180 days)
        expected = start + timedelta(days=180)
        assert eta == expected

    def test_compute_sink_eta_mid_score(self):
        from peerpedia_core.workflow.sedimentation import compute_sink_eta
        from datetime import datetime, timezone
        start = datetime(2026, 6, 1, tzinfo=timezone.utc)
        eta_max = compute_sink_eta(start, 0.0, 2, 180)
        eta_mid = compute_sink_eta(start, 2.5, 2, 180)
        eta_min = compute_sink_eta(start, 5.0, 2, 180)
        # Monotonically decreasing: higher score → earlier eta
        assert eta_min < eta_mid < eta_max

    def test_is_ready_to_publish(self):
        from peerpedia_core.workflow.sedimentation import is_ready_to_publish
        from datetime import datetime, timezone
        past = datetime.now(timezone.utc) - timedelta(days=10)
        future = datetime.now(timezone.utc) + timedelta(days=10)
        assert is_ready_to_publish(past) is True
        assert is_ready_to_publish(future) is False

    def test_is_ready_to_publish_none(self):
        """Bug 4: is_ready_to_publish crashes on None."""
        from peerpedia_core.workflow.sedimentation import is_ready_to_publish
        assert is_ready_to_publish(None) is False

    def test_apply_no_review_penalty(self):
        """No reviews → score penalty applied."""
        from peerpedia_core.workflow.sedimentation import apply_no_review_penalty
        scores = {"originality": 3, "rigor": 3, "completeness": 3,
                  "pedagogy": 3, "impact": 3}
        penalized = apply_no_review_penalty(scores)
        # Penalty reduces each dimension by at least 0.5
        assert penalized["originality"] < scores["originality"]
        assert penalized["originality"] >= 0

    def test_apply_no_review_penalty_none(self):
        """Bug 5: apply_no_review_penalty crashes on None."""
        from peerpedia_core.workflow.sedimentation import apply_no_review_penalty
        result = apply_no_review_penalty(None)
        assert result == {}
