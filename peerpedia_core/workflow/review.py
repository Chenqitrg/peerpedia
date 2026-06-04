"""Layer 1: Review workflow orchestration.

Coordinates the full review lifecycle:
    assign reviewer -> submit review -> make decision -> award points

This is a versioned module -- review rules (quorum size, point values)
can be upgraded via PIP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from peerpedia_core.reputation.v1 import ReputationParams
from peerpedia_core.storage.db import (
    create_review,
    get_article,
    get_reviews_for_article,
    update_article_status,
)
from peerpedia_core.storage.db.session_utils import db_session_scope
from peerpedia_core.workflow.state_machine import ArticleStatus

# -- Result types -----------------------------------------------------------------

@dataclass
class AssignResult:
    """Result of assigning a reviewer."""
    success: bool
    article_id: str = ""
    reviewer_id: str = ""
    new_status: str = ""
    error: str = ""


@dataclass
class ReviewResult:
    """Result of submitting a review."""
    success: bool
    review_id: Optional[str] = None
    article_id: str = ""
    reviewer_id: str = ""
    points_earned: int = 0
    error: str = ""


@dataclass
class DecisionResult:
    """Result of making a decision on an article."""
    success: bool
    article_id: str = ""
    new_status: str = ""
    author_points: int = 0
    error: str = ""


# -- Points calculation -----------------------------------------------------------

def calculate_review_points(
    scientific_correctness: int = 0,
    clarity: int = 0,
) -> int:
    """Calculate points earned for a review.

    MVP: flat 20 points per review. The scientific_correctness and clarity
    parameters are accepted so callers can pass them, but the current (v1)
    algorithm awards a flat 20 points regardless of score. A future upgrade
    (via PIP) will make points proportional to review quality.
    """
    _ = (scientific_correctness, clarity)  # accepted for future v2 algorithm
    params = ReputationParams()
    return params.points_review


# -- Review assignment ------------------------------------------------------------

def assign_reviewer(
    article_id: str,
    reviewer_id: str,
    *,
    database_url: str,
) -> AssignResult:
    """Verify article is in a valid state for rating (sedimentation pool model).

    No status transition needed — articles stay in 'submitted' until auto-published.
    """
    try:
        with db_session_scope(database_url) as session:
            article = get_article(session, article_id)
            if article is None:
                return AssignResult(success=False, article_id=article_id, error="Article not found")

            if article.status not in (ArticleStatus.SUBMITTED, ArticleStatus.IN_REVIEW, ArticleStatus.DRAFT, ArticleStatus.PUBLISHED):
                return AssignResult(
                    success=False,
                    article_id=article_id,
                    error=f"Cannot rate: article status is '{article.status}', must be 'submitted' or 'published'",
                )

            return AssignResult(
                success=True,
                article_id=article_id,
                reviewer_id=reviewer_id,
                new_status=article.status,
            )
    except Exception as e:
        return AssignResult(success=False, article_id=article_id, error=str(e))


# -- Review submission ------------------------------------------------------------

def submit_review(
    article_id: str,
    reviewer_id: str,
    decision: str,
    comments: str,
    *,
    database_url: str,
    scientific_correctness: int = 0,
    clarity: int = 0,
    collaboration_request: bool = False,
    collaboration_message: str = "",
    review_originality: int = 0,
    review_rigor: int = 0,
    review_completeness: int = 0,
    review_pedagogy: int = 0,
    review_impact: int = 0,
    review_version: str = "v0.1",
) -> ReviewResult:
    """Submit a review for an article.

    One review per reviewer per version. Old-version reviews are frozen.
    """
    try:
        with db_session_scope(database_url) as session:
            article = get_article(session, article_id)
            if article is None:
                return ReviewResult(success=False, article_id=article_id, error="Article not found")

            # Accept submitted, in_review, or published for sedimentation pool + post-publish comments
            if article.status not in (ArticleStatus.SUBMITTED, ArticleStatus.IN_REVIEW, ArticleStatus.PUBLISHED):
                return ReviewResult(
                    success=False,
                    article_id=article_id,
                    error=f"Cannot submit review: article status is '{article.status}', must be 'submitted', 'in_review', or 'published'",
                )

            # Authors cannot rate their own articles (comment-only)
            is_author = reviewer_id in (article.founding_authors or [])
            if is_author:
                review_originality = review_rigor = review_completeness = 0
                review_pedagogy = review_impact = 0

            # Same reviewer + same version → update; different version → new review
            existing = get_reviews_for_article(session, article_id)
            existing_review = None
            for r in existing:
                if r.reviewer_id == reviewer_id and r.review_version == review_version:
                    existing_review = r
                    break

            if existing_review:
                # Update existing review for this version
                has_new_ratings = any(v > 0 for v in [
                    review_originality, review_rigor, review_completeness,
                    review_pedagogy, review_impact,
                ])
                existing_review.decision = decision
                if comments.strip():
                    existing_review.comments = comments
                if has_new_ratings:
                    existing_review.review_originality = review_originality
                    existing_review.review_rigor = review_rigor
                    existing_review.review_completeness = review_completeness
                    existing_review.review_pedagogy = review_pedagogy
                    existing_review.review_impact = review_impact
                existing_review.collaboration_request = 1 if collaboration_request else 0
                if collaboration_message:
                    existing_review.collaboration_message = collaboration_message

                return ReviewResult(
                    success=True,
                    review_id=existing_review.id,
                    article_id=article_id,
                    reviewer_id=reviewer_id,
                    points_earned=existing_review.points_earned,
                )

            # Calculate points
            points = calculate_review_points(scientific_correctness, clarity)

            # Create review record
            review = create_review(
                session,
                article_id=article_id,
                reviewer_id=reviewer_id,
                decision=decision,
                comments=comments,
                scientific_correctness=scientific_correctness,
                clarity=clarity,
                collaboration_request=collaboration_request,
                collaboration_message=collaboration_message,
                points_earned=points,
                review_originality=review_originality,
                review_rigor=review_rigor,
                review_completeness=review_completeness,
                review_pedagogy=review_pedagogy,
                review_impact=review_impact,
                review_version=review_version,
            )

            return ReviewResult(
                success=True,
                review_id=review.id,
                article_id=article_id,
                reviewer_id=reviewer_id,
                points_earned=points,
            )
    except Exception as e:
        return ReviewResult(success=False, article_id=article_id, error=str(e))


# -- Decision ---------------------------------------------------------------------

def make_decision(
    article_id: str,
    *,
    database_url: str,
) -> DecisionResult:
    """Make a decision on an article based on accumulated reviews.

    MVP rule: if any review says 'accept', accept. If any say 'revise'
    (and none accept), revise. If all reject, reject.
    """
    try:
        with db_session_scope(database_url) as session:
            article = get_article(session, article_id)
            if article is None:
                return DecisionResult(success=False, article_id=article_id, error="Article not found")

            if article.status != ArticleStatus.IN_REVIEW:
                return DecisionResult(
                    success=False,
                    article_id=article_id,
                    error=f"Cannot decide: article status is '{article.status}', must be 'in_review'",
                )

            reviews = get_reviews_for_article(session, article_id)
            if not reviews:
                return DecisionResult(
                    success=False,
                    article_id=article_id,
                    error="No reviews available for decision",
                )

            # Count decisions
            accepts = sum(1 for r in reviews if r.decision == "accept")
            revises = sum(1 for r in reviews if r.decision == "revise")
            rejects = sum(1 for r in reviews if r.decision == "reject")

            # MVP logic: accept if any accept, else revise if any revise, else reject
            if accepts > 0:
                new_status = ArticleStatus.ACCEPTED
                author_points = ReputationParams().points_accepted
            elif revises > 0:
                new_status = ArticleStatus.REVISIONS_REQUESTED
                author_points = 0
            else:
                new_status = ArticleStatus.REJECTED
                author_points = 0

            update_article_status(session, article_id, new_status)

            return DecisionResult(
                success=True,
                article_id=article_id,
                new_status=new_status,
                author_points=author_points,
            )
    except Exception as e:
        return DecisionResult(success=False, article_id=article_id, error=str(e))
