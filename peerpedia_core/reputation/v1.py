"""Layer 1: Reputation algorithm v1.

This algorithm can be upgraded via PIP. The abstract base class defines
the interface; concrete versions implement the algorithm.

Current v1:
- 4 dimensions: academic, review, collaboration, education
- Time decay: 90 days inactivity → 0.1% decay per day
- Identity weights boost initial reputation
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

from peerpedia_core.protocol import IdentityType, ReputationVector


# ── Layer 2: Configurable parameters ─────────────────────────────────────────

class ReputationParams:
    """Parameters that can be tuned without protocol upgrade."""

    # Time decay
    decay_grace_days: int = 90
    decay_rate_per_day: float = 0.001  # 0.1%

    # Identity trust weights
    identity_weights: dict[IdentityType, float] = {
        IdentityType.ORCID: 1.0,
        IdentityType.INST_EMAIL: 0.8,
        IdentityType.ARXIV: 0.6,
        IdentityType.GOOGLE_SCHOLAR: 0.5,
        IdentityType.GITHUB: 0.3,
    }

    # Base reputation from verified identities
    base_reputation_per_identity: float = 5.0  # points per verified identity

    # Contribution weight multipliers (Layer 2 — community adjustable)
    change_type_weights: dict[str, float] = {
        "new_theorem": 5.0,
        "proof_fix": 4.0,
        "content": 2.0,
        "prose": 1.0,
        "format": 0.3,
    }

    # Point values
    points_submit: int = 10
    points_accepted: int = 50
    points_review: int = 20
    points_per_citation: int = 2
    points_high_quality_review: int = 5  # base, multiplied by author score
    points_report_spam: int = 5
    points_pin_per_day: int = 1


# ── Abstract base (Layer 1 interface) ────────────────────────────────────────

class BaseReputation(ABC):
    """Abstract reputation algorithm — versioned via PIP."""

    def __init__(self, params: Optional[ReputationParams] = None):
        self.params = params or ReputationParams()

    @abstractmethod
    def compute(self, user_id: str) -> ReputationVector:
        """Compute the current reputation vector for a user."""
        ...

    @abstractmethod
    def apply_decay(self, vector: ReputationVector, last_active: datetime) -> ReputationVector:
        """Apply time-based decay to a reputation vector."""
        ...

    @abstractmethod
    def merge_identities(self, vector: ReputationVector, verified_count: int) -> ReputationVector:
        """Apply identity verification bonus to initial reputation."""
        ...


# ── v1 Implementation ────────────────────────────────────────────────────────

class ReputationV1(BaseReputation):
    """Reputation algorithm v1.

    Four-dimensional radar:
    - academic_contribution: article output × citation impact
    - review_quality: review helpfulness rated by authors
    - collaboration_spirit: co-authored articles + partner ratings
    - education_outreach: reader engagement (pins, shares)
    """

    def compute(self, user_id: str, session=None) -> ReputationVector:
        """Compute reputation from stored article, review, and identity records.

        Args:
            user_id: The user slug to compute for.
            session: SQLAlchemy Session for database access. If None, returns
                     an empty vector (backward compatible).

        Returns:
            ReputationVector with 4D scores (0-100) and total_points.
        """
        if session is None:
            return ReputationVector(user_id=user_id)

        from peerpedia_core.storage.db import (
            Article, Review, ContributionRecord, Identity,
            get_user, get_identities_for_user, update_user_last_active,
        )
        from sqlalchemy import func
        from datetime import datetime, timezone

        # ── Update last_active ──
        update_user_last_active(session, user_id)

        # ── 1. Aggregate activity data ──
        article_count = session.query(func.count(Article.id)).filter(
            Article.founding_authors.contains(user_id)
        ).scalar() or 0

        review_count = session.query(func.count(Review.id)).filter(
            Review.reviewer_id == user_id
        ).scalar() or 0

        review_points = session.query(func.sum(Review.points_earned)).filter(
            Review.reviewer_id == user_id
        ).scalar() or 0

        contrib_weight_total = session.query(
            func.sum(ContributionRecord.contribution_weight)
        ).filter(
            ContributionRecord.user_id == user_id
        ).scalar() or 0

        # Count collaborations (articles where user co-authors with others)
        collab_count = 0
        articles = session.query(Article).filter(
            Article.founding_authors.contains(user_id)
        ).all()
        for a in articles:
            if len(a.founding_authors) > 1:
                collab_count += 1

        # Education outreach: pinned_by on user's articles
        outreach = sum(a.pinned_by for a in articles)

        # ── 2. Identity multiplier ──
        identities = get_identities_for_user(session, user_id)
        identity_multiplier = 1.0
        for ident in identities:
            if ident.verified:
                identity_multiplier += (ident.trust_weight / 100.0) * 0.1

        # ── 3. Time decay ──
        user = get_user(session, user_id)
        decay = 1.0
        if user is not None and user.last_active is not None:
            now = datetime.now(timezone.utc)
            last_active = user.last_active
            # SQLite may or may not preserve timezone info on readback; normalize
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            days_inactive = (now - last_active).days
            if days_inactive > self.params.decay_grace_days:
                decay_days = days_inactive - self.params.decay_grace_days
                decay = max(0.5, (1.0 - self.params.decay_rate_per_day) ** decay_days)

        # ── 4. Compute four dimensions ──
        academic = min(100.0, (article_count * 10.0 + contrib_weight_total / 100.0)
                       * identity_multiplier * decay)
        review = min(100.0, (review_count * 15.0 + review_points / 10.0)
                     * identity_multiplier * decay)
        collaboration = min(100.0, (collab_count * 20.0)
                            * identity_multiplier * decay)
        education = min(100.0, (outreach * 5.0)
                        * identity_multiplier * decay)

        return ReputationVector(
            user_id=user_id,
            academic_contribution=round(academic, 1),
            review_quality=round(review, 1),
            collaboration_spirit=round(collaboration, 1),
            education_outreach=round(education, 1),
            total_points=review_points,
        )

    def apply_decay(self, vector: ReputationVector, last_active: datetime) -> ReputationVector:
        """Decay reputation for inactive users."""
        days_inactive = (datetime.utcnow() - last_active).days
        if days_inactive <= self.params.decay_grace_days:
            return vector

        decay_days = days_inactive - self.params.decay_grace_days
        decay_factor = (1 - self.params.decay_rate_per_day) ** decay_days

        vector.academic_contribution *= decay_factor
        vector.review_quality *= decay_factor
        vector.collaboration_spirit *= decay_factor
        vector.education_outreach *= decay_factor

        return vector

    def merge_identities(self, vector: ReputationVector, verified_count: int) -> ReputationVector:
        """Add base reputation from verified identities."""
        bonus = self.params.base_reputation_per_identity * verified_count
        vector.academic_contribution = min(100, vector.academic_contribution + bonus)
        return vector


# ── Registry ─────────────────────────────────────────────────────────────────

REPUTATION_VERSIONS = {
    "v1": ReputationV1,
}


def get_reputation(version: str = "v1") -> BaseReputation:
    """Get the current reputation algorithm."""
    cls = REPUTATION_VERSIONS.get(version)
    if cls is None:
        raise ValueError(f"Unknown reputation version: {version}")
    return cls()
