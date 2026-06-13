"""Article API schemas — request/response Pydantic models."""
from datetime import datetime, timezone
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


# ── Shared score / author types ────────────────────────────────────────────

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
    """Five-dimension scores input (0.0-5.0 each)."""
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


class AuthorInfo(BaseModel):
    """Resolved author information for API responses."""
    id: str
    name: str
    anonymous_name: str = ""
    affiliation: str = ""
    expertise: list[str] = []


# ── Output schemas ───────────────────────────────────────────────────────

class ArticleSummary(BaseModel):
    id: str
    title: str = ""
    status: ArticleStatus
    authors: list[AuthorInfo] = []
    abstract: Optional[str] = None
    content_preview: str = ""
    commit_hash: str = ""
    fork_count: int = 0
    forked_from: Optional[str] = None
    commit_count: int = 1
    score: Optional[dict] = None
    sink_eta: Optional[datetime] = None
    days_remaining: Optional[int] = None
    sink_duration_days: Optional[int] = None
    is_bookmarked: bool = False
    is_own_article: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ArticleDetail(BaseModel):
    id: str
    title: str = ""
    status: ArticleStatus
    authors: list[AuthorInfo] = []
    commit_hash: str = ""
    fork_count: int = 0
    forked_from: Optional[str] = None
    commit_count: int = 1
    compiled_format: Optional[str] = None
    compiled_output: Optional[str] = None
    compiled_pages: Optional[list[str]] = None
    score: Optional[dict] = None
    sink_eta: Optional[datetime] = None
    days_remaining: Optional[int] = None
    sink_duration_days: Optional[int] = None
    review_count: int = 0
    is_bookmarked: bool = False
    is_own_article: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Input schemas ────────────────────────────────────────────────────────

class ArticleCreate(BaseModel):
    title: str = ""
    abstract: str = ""
    keywords: list[str] = []
    categories: list[str] = []
    authors: list[str] = []  # optional: defaults to [current_user] in route handler
    content: str = ""               # article body (markdown or typst)
    format: str = "markdown"        # "markdown" | "typst"
    commit_message: str = ""        # git commit message (required for submit)
    self_review: FiveDimScoresIn
    contributions: Optional[dict[str, FiveDimScoresIn]] = None
    forked_from: Optional[str] = None


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    content: Optional[str] = None
    commit_message: Optional[str] = None  # git commit message
    self_review: Optional[FiveDimScoresIn] = None
    contributions: Optional[dict[str, FiveDimScoresIn]] = None
    publish: bool = False  # True = publish to pool, False = save as draft


class SinkExtensionRequest(BaseModel):
    extra_days: int = Field(ge=1, le=180)


# ── Source / download ────────────────────────────────────────────────────

class ArticleSourceResponse(BaseModel):
    content: str
    format: str  # "markdown" | "typst"
