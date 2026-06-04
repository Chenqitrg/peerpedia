"""Score aggregation — weighted average of reviews."""
from peerpedia_core.config.params import params
from peerpedia_core.types.scores import FiveDimScores

DIMS = ["originality", "rigor", "completeness", "pedagogy", "impact"]


def compute_article_score(
    reviews: list[dict],
    reviewer_weights: dict[str, float] | None = None,
) -> dict | None:
    """Compute weighted average score from a list of reviews.

    Each review is a dict with:
        - scores: {originality, rigor, completeness, pedagogy, impact}
        - is_self: bool (reviewer is article author)
        - reviewer_id: str (required when *reviewer_weights* is provided)

    Self-reviews are weighted by params.score.self_review_weight.
    Community reviews are weighted by params.score.community_weight.

    When *reviewer_weights* is given, each review's contribution is additionally
    multiplied by ``reviewer_weights.get(review.reviewer_id, 1.0)``, allowing
    reputation-weighted scoring.
    """
    if not reviews:
        return None

    self_reviews = [r for r in reviews if r.get("is_self")]
    community_reviews = [r for r in reviews if not r.get("is_self")]

    self_weight = params.score.self_review_weight
    community_weight = params.score.community_weight

    def _reviewer_mult(review: dict) -> float:
        if reviewer_weights is None:
            return 1.0
        return reviewer_weights.get(review.get("reviewer_id", ""), 1.0)

    result = {}
    for dim in DIMS:
        total = 0.0
        count = 0.0

        for r in self_reviews:
            w = self_weight * _reviewer_mult(r)
            total += r["scores"][dim] * w
            count += w

        for r in community_reviews:
            w = community_weight * _reviewer_mult(r)
            total += r["scores"][dim] * w
            count += w

        result[dim] = round(total / count, 2) if count > 0 else 0.0

    return result
