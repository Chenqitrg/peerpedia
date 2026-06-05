"""Review API schemas."""
from datetime import datetime
from enum import Enum

from typing import Optional

from pydantic import BaseModel, Field, model_validator


FIVE_DIMS = {"originality", "rigor", "completeness", "pedagogy", "impact"}


class ReviewScope(str, Enum):
    pool = "pool"
    published = "published"


class ThreadMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=300)


class ThreadMessageOut(BaseModel):
    author_id: str
    content: str
    created_at: datetime

    model_config = {"extra": "allow"}


class ReviewCreate(BaseModel):
    article_id: str
    commit_hash: str
    scope: ReviewScope
    scores: dict  # FiveDimScores as dict, validated below
    contributions: Optional[dict[str, dict[str, float]]] = None  # author_id → 5-dim ratios

    @model_validator(mode="after")
    def validate_five_dims(self):
        missing = FIVE_DIMS - set(self.scores.keys())
        if missing:
            raise ValueError(f"Missing score dimensions: {missing}")
        for dim in FIVE_DIMS:
            v = self.scores[dim]
            if not isinstance(v, (int, float)) or v < 0 or v > 5:
                raise ValueError(f"{dim} must be 0-5, got {v}")
        # Validate contributions if provided
        if self.contributions:
            for author_id, contrib in self.contributions.items():
                c_missing = FIVE_DIMS - set(contrib.keys())
                if c_missing:
                    raise ValueError(
                        f"Contributions for {author_id} missing dimensions: {c_missing}"
                    )
                for dim in FIVE_DIMS:
                    v = contrib[dim]
                    if not isinstance(v, (int, float)) or v < 0 or v > 1:
                        raise ValueError(
                            f"Contribution {dim} for {author_id} must be 0-1, got {v}"
                        )
        return self


class ReviewOut(BaseModel):
    id: str
    article_id: str
    commit_hash: str
    reviewer_id: str
    scope: ReviewScope
    scores: dict  # FiveDimScores: {originality, rigor, completeness, pedagogy, impact} each 0-5
    contributions: Optional[dict[str, dict[str, float]]] = None  # author_id → 5-dim ratios
    thread: list[ThreadMessageOut] = []
    reviewer_name: str
    is_self_review: bool = False
    created_at: datetime
    updated_at: datetime
