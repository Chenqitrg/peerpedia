"""Review API schemas."""
from datetime import datetime
from enum import Enum

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


class ReviewCreate(BaseModel):
    article_id: str
    commit_hash: str
    reviewer_id: str
    scope: ReviewScope
    scores: dict  # FiveDimScores as dict, validated below

    @model_validator(mode="after")
    def validate_five_dims(self):
        missing = FIVE_DIMS - set(self.scores.keys())
        if missing:
            raise ValueError(f"Missing score dimensions: {missing}")
        for dim in FIVE_DIMS:
            v = self.scores[dim]
            if not isinstance(v, (int, float)) or v < 0 or v > 5:
                raise ValueError(f"{dim} must be 0-5, got {v}")
        return self


class ReviewOut(BaseModel):
    id: str
    article_id: str
    commit_hash: str
    reviewer_id: str
    scope: str
    scores: dict
    thread: list[dict]
    reviewer_name: str  # 池内匿名名 or 实名
    is_self_review: bool = False
    created_at: datetime
    updated_at: datetime
