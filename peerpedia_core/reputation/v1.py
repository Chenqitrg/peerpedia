"""Layer 1: Reputation algorithm v1.

This algorithm can be upgraded via PIP. The abstract base class defines
the interface; concrete versions implement the algorithm.

Current v1:
- 4 dimensions: academic, review, collaboration, education
- Time decay: 90 days inactivity → 0.1% decay per day
- Identity weights boost initial reputation
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func

from peerpedia_core.protocol import IdentityType, ReputationVector
from peerpedia_core.storage.db import (
    Article,
    ContributionRecord,
    Review,
    get_identities_for_user,
    get_user,
    update_user_last_active,
)

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

        update_user_last_active(session, user_id)

        activity = self._aggregate_activity(session, user_id)
        identity_multiplier = self._compute_identity_multiplier(session, user_id,
                                                                get_identities_for_user)
        user = get_user(session, user_id)
        decay = self._compute_decay(user)

        academic = min(100.0, (activity["article_count"] * 10.0
                       + activity["contrib_weight_total"] / 100.0)
                       * identity_multiplier * decay)
        review = min(100.0, (activity["review_count"] * 15.0
                     + activity["review_points"] / 10.0)
                     * identity_multiplier * decay)
        collaboration = min(100.0, (activity["collab_count"] * 20.0)
                            * identity_multiplier * decay)
        education = min(100.0, (activity["outreach"] * 5.0)
                        * identity_multiplier * decay)

        return ReputationVector(
            user_id=user_id,
            academic_contribution=round(academic, 1),
            review_quality=round(review, 1),
            collaboration_spirit=round(collaboration, 1),
            education_outreach=round(education, 1),
            total_points=activity["review_points"],
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _aggregate_activity(self, session, user_id: str) -> dict:
        """Query the database for all user activity metrics."""
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
        ).filter(ContributionRecord.user_id == user_id).scalar() or 0

        articles = session.query(Article).filter(
            Article.founding_authors.contains(user_id)
        ).all()

        collab_count = sum(1 for a in articles if len(a.founding_authors) > 1)
        outreach = sum(a.pinned_by for a in articles)

        return {
            "article_count": article_count,
            "review_count": review_count,
            "review_points": review_points,
            "contrib_weight_total": contrib_weight_total,
            "collab_count": collab_count,
            "outreach": outreach,
        }

    def _compute_identity_multiplier(self, session, user_id: str,
                                     get_identities_for_user) -> float:
        """Compute multiplier from verified identity trust weights."""
        identities = get_identities_for_user(session, user_id)
        multiplier = 1.0
        for ident in identities:
            if ident.verified:
                multiplier += (ident.trust_weight / 100.0) * 0.1
        return multiplier

    def _compute_decay(self, user) -> float:
        """Compute time-decay factor based on user's last_active timestamp."""
        if user is None or user.last_active is None:
            return 1.0

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        last_active = user.last_active
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)

        days_inactive = (now - last_active).days
        if days_inactive <= self.params.decay_grace_days:
            return 1.0

        decay_days = days_inactive - self.params.decay_grace_days
        return max(0.5, (1.0 - self.params.decay_rate_per_day) ** decay_days)

    def apply_decay(self, vector: ReputationVector, last_active: datetime) -> ReputationVector:
        """Decay reputation for inactive users."""
        now = datetime.now(timezone.utc)
        # Normalize: SQLite may return naive datetimes
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        days_inactive = (now - last_active).days
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
