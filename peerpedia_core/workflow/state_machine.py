"""Layer 1: ArticleStatus state machine.

Defines valid transitions and provides transition validation + execution.
The state machine is versioned — transition rules can be modified via PIP.

MVP transitions (M2):
    draft → submitted
    submitted → in_review
    in_review → accepted
    in_review → rejected
    in_review → revisions_requested
    accepted → published
    revisions_requested → submitted
    rejected → submitted
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Status constants (mirrors protocol enum) ───────────────────────────────────

class ArticleStatus:
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    REVISIONS_REQUESTED = "revisions_requested"
    ACCEPTED = "accepted"
    PUBLISHED = "published"
    REJECTED = "rejected"


# ── Valid transitions ──────────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[str, set[str]] = {
    ArticleStatus.DRAFT: {ArticleStatus.SUBMITTED},
    ArticleStatus.SUBMITTED: {ArticleStatus.IN_REVIEW},
    ArticleStatus.IN_REVIEW: {
        ArticleStatus.ACCEPTED,
        ArticleStatus.REJECTED,
        ArticleStatus.REVISIONS_REQUESTED,
    },
    ArticleStatus.REVISIONS_REQUESTED: {ArticleStatus.SUBMITTED},
    ArticleStatus.REJECTED: {ArticleStatus.SUBMITTED},
    ArticleStatus.ACCEPTED: {ArticleStatus.PUBLISHED},
    ArticleStatus.PUBLISHED: set(),  # terminal state for M2
}


# ── Functions ──────────────────────────────────────────────────────────────────

def can_transition(current: str, target: str) -> bool:
    """Check if a transition from current to target status is valid."""
    allowed = VALID_TRANSITIONS.get(current, set())
    return target in allowed


def transition(current: str, target: str) -> str:
    """Execute a status transition. Returns new status.

    Raises ValueError if the transition is invalid.
    """
    if not can_transition(current, target):
        raise ValueError(
            f"Invalid transition: {current} → {target}. "
            f"Allowed: {VALID_TRANSITIONS.get(current, set())}"
        )
    return target


# ── State machine class ────────────────────────────────────────────────────────

@dataclass
class StateMachine:
    """Tracks an article's status transitions with history."""

    article_id: str
    current_status: str = ArticleStatus.DRAFT
    history: list[tuple[str, str]] = field(default_factory=list)

    def can_apply(self, target: str) -> bool:
        """Check if target transition is valid from current status."""
        return can_transition(self.current_status, target)

    def apply(self, target: str) -> str:
        """Apply a transition, recording it in history."""
        old = self.current_status
        self.current_status = transition(old, target)
        self.history.append((old, target))
        return self.current_status
