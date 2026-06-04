"""Sedimentation pool logic — sink time calculation and auto-publish."""
from datetime import datetime, timezone, timedelta

from peerpedia_core.config.params import params


def compute_sink_eta(
    sink_start: datetime,
    avg_score: float,
    min_days: int = 2,
    max_days: int = 180,
) -> datetime:
    """Compute when an article exits the sedimentation pool.

    Uses a linear interpolation: score 5.0 → min_days, score 0.0 → max_days.
    Higher scores mean shorter (faster) sink times.

    The function is replaceable via params.score.score_to_sink_multiplier.
    """
    multiplier = params.score.score_to_sink_multiplier(avg_score)
    # multiplier = 0 for 5.0 (shortest), multiplier = 1 for 0.0 (longest)
    actual_days = min_days + multiplier * (max_days - min_days)
    return sink_start + timedelta(days=actual_days)


def is_ready_to_publish(sink_eta: datetime | None) -> bool:
    """Check if the sink time has elapsed. Returns False if sink_eta is None."""
    if sink_eta is None:
        return False
    now = datetime.now(timezone.utc)
    if sink_eta.tzinfo is None:
        sink_eta = sink_eta.replace(tzinfo=timezone.utc)
    return now >= sink_eta


def apply_no_review_penalty(scores: dict | None) -> dict:
    """Apply penalty when an article receives zero reviews in the pool.

    Returns a new scores dict with penalty applied (each dimension reduced).
    Returns empty dict if scores is None.
    """
    if scores is None:
        return {}
    penalty = params.score.no_review_penalty()
    return {
        dim: max(0.0, value - penalty)
        for dim, value in scores.items()
    }
