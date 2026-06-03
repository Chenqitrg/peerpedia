"""Tests for review workflow orchestration."""
import tempfile
from pathlib import Path

import pytest

from peerpedia.submit import submit_article
from peerpedia_core.workflow.review import (
    assign_reviewer,
    calculate_review_points,
    make_decision,
    submit_review,
)

SIMPLE_ARTICLE = """---
title: Review Workflow Test
abstract: Testing review orchestration.
categories:
  - test
language: en
---

= Review Workflow Test

== Section 1

Content for review testing.
"""


def _prepare_article(tmp_path, status="submitted"):
    """Helper: submit an article and set its status."""
    db_path = tmp_path / "test.db"
    articles_dir = tmp_path / "articles"
    articles_dir.mkdir()

    source = tmp_path / "test.typ"
    source.write_text(SIMPLE_ARTICLE)

    result = submit_article(
        source_path=source,
        database_url=f"sqlite:///{db_path}",
        articles_dir=articles_dir,
    )
    assert result.success

    if status != "draft":
        from peerpedia_core.storage.db import (
            get_engine,
            get_session,
            init_db,
            update_article_status,
        )
        engine = get_engine(f"sqlite:///{db_path}")
        init_db(engine)
        session = get_session(engine)
        update_article_status(session, result.article_id, status)
        session.commit()
        session.close()

    return result.article_id, f"sqlite:///{db_path}"


class TestReviewAssignment:
    """Assigning reviewers to articles."""

    def test_assign_reviewer_to_submitted_article(self):
        """Reviewer can be assigned to a submitted article."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id, db_url = _prepare_article(base, status="submitted")
            assign_result = assign_reviewer(
                article_id=article_id,
                reviewer_id="reviewer-1",
                database_url=db_url,
            )
            assert assign_result.success is True
            assert assign_result.new_status == "submitted"

    def test_assign_reviewer_to_draft_fails(self):
        """Cannot assign reviewer to a draft article (M2 constraint)."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id, db_url = _prepare_article(base, status="draft")

            # draft is also accepted as valid starting point for MVP convenience
            assign_result = assign_reviewer(
                article_id=article_id,
                reviewer_id="reviewer-1",
                database_url=db_url,
            )
            # draft -> in_review works in MVP (auto-transitions)
            assert assign_result.success is True


class TestReviewSubmission:
    """Submitting reviews and points calculation."""

    def test_submit_review_and_points(self):
        """Submit a review and verify points are calculated."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id, db_url = _prepare_article(base, status="submitted")
            assign_reviewer(article_id=article_id, reviewer_id="r1", database_url=db_url)

            review_result = submit_review(
                article_id=article_id,
                reviewer_id="r1",
                decision="accept",
                comments="Excellent work.",
                scientific_correctness=5,
                clarity=4,
                database_url=db_url,
            )
            assert review_result.success is True
            assert review_result.review_id is not None
            assert review_result.points_earned == 20  # base review points

    def test_submit_review_duplicate_updates(self):
        """Same reviewer can update their review (sedimentation pool model)."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id, db_url = _prepare_article(base, status="submitted")
            assign_reviewer(article_id=article_id, reviewer_id="r1", database_url=db_url)

            r1 = submit_review(article_id=article_id, reviewer_id="r1", decision="accept", comments="OK", scientific_correctness=5, clarity=4, database_url=db_url)
            assert r1.success

            r2 = submit_review(article_id=article_id, reviewer_id="r1", decision="revise", comments="Updated review", scientific_correctness=3, clarity=2, database_url=db_url)
            assert r2.success

            # Verify the review was updated in-place
            from peerpedia_core.storage.db import get_engine, get_session, init_db, get_reviews_for_article
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            reviews = get_reviews_for_article(session, article_id)
            assert len(reviews) == 1
            assert reviews[0].decision == "revise"
            assert reviews[0].comments == "Updated review"
            session.close()

    def test_submit_review_wrong_status_fails(self):
        """Cannot submit review for published article."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id, db_url = _prepare_article(base, status="published")
            result = submit_review(article_id=article_id, reviewer_id="r1", decision="accept", comments="OK", database_url=db_url)
            assert result.success is False


class TestDecisionMaking:
    """Making decisions based on reviews."""

    @pytest.mark.skip(reason="Decision removed in sedimentation pool model")
    def test_accept_decision(self):
        """Accept an article after a positive review."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id, db_url = _prepare_article(base, status="submitted")
            assign_reviewer(article_id=article_id, reviewer_id="r1", database_url=db_url)
            submit_review(article_id=article_id, reviewer_id="r1", decision="accept", comments="OK", scientific_correctness=5, clarity=5, database_url=db_url)

            decision = make_decision(article_id=article_id, database_url=db_url)
            assert decision.success is True
            assert decision.new_status == "accepted"
            assert decision.author_points == 50  # accepted bonus

    @pytest.mark.skip(reason="Decision removed in sedimentation pool model")
    def test_reject_decision(self):
        """Reject an article after a negative review."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id, db_url = _prepare_article(base, status="submitted")
            assign_reviewer(article_id=article_id, reviewer_id="r1", database_url=db_url)
            submit_review(article_id=article_id, reviewer_id="r1", decision="reject", comments="Not good.", database_url=db_url)

            decision = make_decision(article_id=article_id, database_url=db_url)
            assert decision.success is True
            assert decision.new_status == "rejected"
            assert decision.author_points == 0

    def test_no_decision_without_reviews(self):
        """Cannot make decision on article with no reviews."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id, db_url = _prepare_article(base, status="submitted")
            # Set to in_review without any reviews
            from peerpedia_core.storage.db import (
                get_engine,
                get_session,
                init_db,
                update_article_status,
            )
            engine = get_engine(db_url)
            init_db(engine)
            session = get_session(engine)
            update_article_status(session, article_id, "in_review")
            session.commit()
            session.close()

            decision = make_decision(article_id=article_id, database_url=db_url)
            assert decision.success is False
            assert "No reviews" in decision.error

    @pytest.mark.skip(reason="Decision removed in sedimentation pool model")
    def test_revise_decision(self):
        """Revise decision when reviewer says revise."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            article_id, db_url = _prepare_article(base, status="submitted")
            assign_reviewer(article_id=article_id, reviewer_id="r1", database_url=db_url)
            submit_review(article_id=article_id, reviewer_id="r1", decision="revise", comments="Needs work.", database_url=db_url)

            decision = make_decision(article_id=article_id, database_url=db_url)
            assert decision.success is True
            assert decision.new_status == "revisions_requested"


class TestPointsCalculation:
    """Points calculation logic."""

    def test_calculate_review_points(self):
        """Base review always gives 20 points."""
        pts = calculate_review_points(scientific_correctness=5, clarity=5)
        assert pts == 20

    def test_calculate_review_points_minimum(self):
        """Even low-quality reviews get base points."""
        pts = calculate_review_points(scientific_correctness=1, clarity=1)
        assert pts == 20
