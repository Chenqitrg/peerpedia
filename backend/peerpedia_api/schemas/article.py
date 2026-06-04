"""Article API schemas — request/response Pydantic models."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ArticleStatus(str, Enum):
    draft = "draft"
    sedimentation = "sedimentation"
    published = "published"


class CompileFormat(str, Enum):
    html = "html"
    svg = "svg"


def _clamp(v: float) -> float:
    return max(0.0, min(5.0, v))


class FiveDimScoresOut(BaseModel):
    originality: float = 0.0
    rigor: float = 0.0
    completeness: float = 0.0
    pedagogy: float = 0.0
    impact: float = 0.0

    @model_validator(mode="after")
    def clamp(self):
        for field in ("originality", "rigor", "completeness", "pedagogy", "impact"):
            setattr(self, field, _clamp(getattr(self, field)))
        return self


class FiveDimScoresIn(BaseModel):
    """Five-dimension scores input (1.0-5.0 each)."""
    originality: float
    rigor: float
    completeness: float
    pedagogy: float
    impact: float

    @model_validator(mode="after")
    def validate_all_present(self):
        for field in ("originality", "rigor", "completeness", "pedagogy", "impact"):
            v = getattr(self, field)
            if not (0.0 <= v <= 5.0):
                raise ValueError(f"{field} must be between 0 and 5, got {v}")
        return self


# ── Output schemas ───────────────────────────────────────────────────────

class ArticleSummary(BaseModel):
    id: str
    title: str = ""
    status: ArticleStatus
    authors: list[str] = []
    fork_count: int = 0
    created_at: datetime
    score: Optional[dict] = None


class ArticleDetail(BaseModel):
    id: str
    title: str = ""
    status: ArticleStatus
    authors: list[str] = []
    fork_count: int = 0
    forked_from: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    compiled_format: Optional[str] = None
    compiled_output: Optional[str] = None
    compiled_pages: Optional[list[str]] = None
    score: Optional[dict] = None
    sink_eta: Optional[datetime] = None
    days_remaining: Optional[int] = None
    review_count: int = 0


# ── Input schemas ────────────────────────────────────────────────────────

class ArticleCreate(BaseModel):
    title: str = ""
    abstract: str = ""
    keywords: list[str] = []
    categories: list[str] = []
    authors: list[str]
    content: str = ""               # article body (markdown or typst)
    format: str = "markdown"        # "markdown" | "typst"
    self_review: FiveDimScoresIn
    forked_from: Optional[str] = None


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    content: Optional[str] = None
    self_review: Optional[FiveDimScoresIn] = None


class SinkExtensionRequest(BaseModel):
    extra_days: int = Field(ge=1, le=180)
