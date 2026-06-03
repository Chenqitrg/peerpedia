"""PeerPedia Core Protocol — Layer 0: Message Formats.

These schemas define the immutable wire protocol. Changes to these schemas
constitute a protocol fork. See design/brainstorm.md Section 10 for details.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# ── Enums ────────────────────────────────────────────────────────────────────

class ArticleStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    REVISIONS_REQUESTED = "revisions_requested"
    ACCEPTED = "accepted"
    PUBLISHED = "published"
    EDIT_PROPOSED = "edit_proposed"
    REJECTED = "rejected"


class Decision(str, Enum):
    ACCEPT = "accept"
    REVISE = "revise"
    REJECT = "reject"


class ChangeType(str, Enum):
    NEW_THEOREM = "new_theorem"   # ×5.0 weight
    PROOF_FIX = "proof_fix"        # ×4.0 weight
    CONTENT = "content"            # ×2.0 weight
    PROSE = "prose"                # ×1.0 weight
    FORMAT = "format"              # ×0.3 weight


class EditType(str, Enum):
    MINOR = "minor"     # <20 lines, auto-approve after 1 day
    MEDIUM = "medium"   # Original author review, 7 days
    MAJOR = "major"     # Community review, points stake required


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


class IdentityType(str, Enum):
    ORCID = "orcid"              # weight 1.0
    INST_EMAIL = "inst_email"   # weight 0.8
    ARXIV = "arxiv"              # weight 0.6
    GOOGLE_SCHOLAR = "scholar"   # weight 0.5
    GITHUB = "github"            # weight 0.3


# ── Core Messages ────────────────────────────────────────────────────────────

class Identity(BaseModel):
    """A verified identity binding."""
    type: IdentityType
    value: str
    verified: bool = False
    trust_weight: float = 0.1  # default for unverified


class UserProfile(BaseModel):
    """User profile — the base identity in the protocol."""
    id: str
    name: str
    email: str
    affiliation: Optional[str] = None
    expertise: list[str] = Field(default_factory=list)
    identities: list[Identity] = Field(default_factory=list)
    public_key: str = ""
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContributorShare(BaseModel):
    """Contribution share at a point in time."""
    user_id: str
    percentage: float
    lines_owned: int
    role: str  # "founding" | "co-author" | "contributor" | "editor"


class ContributionSnapshot(BaseModel):
    """A snapshot of contribution breakdown at a version."""
    version: str
    timestamp: datetime
    git_commit: str
    contributions: list[ContributorShare]
    total_lines: int


class AuthorContrib(BaseModel):
    """Contribution record from a single commit."""
    user_id: str
    timestamp: datetime
    commit_hash: str
    commit_message: str
    lines_added: int
    lines_deleted: int
    files_changed: list[str]
    change_type: ChangeType
    contribution_weight: float


class ArticleRef(BaseModel):
    """Lightweight reference to another article."""
    article_id: str
    title: str
    cid: Optional[str] = None


class OriginalWork(BaseModel):
    """Reference to a historical/original work (can be authored by deceased persons)."""
    title: str
    original_authors: list[str]  # Name strings, not user_ids (can be deceased)
    year: int
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    url: Optional[str] = None


class ArticleMeta(BaseModel):
    """Article metadata (header fields)."""
    id: str
    title: str
    founding_authors: list[str]  # user_ids — never changes (living users who write the article)
    about_person: Optional[str] = None  # If this article is about a person (e.g., "Albert Einstein", can be deceased)
    original_works: list[OriginalWork] = Field(default_factory=list)  # Historical works being transcribed/referenced
    abstract: str
    abstract_zh: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    language: str = "en"  # "zh" | "en" | "bilingual"
    status: ArticleStatus = ArticleStatus.DRAFT
    version: str = "v0.1"
    format: str = "typst"  # "typst" | "markdown"
    references: list[ArticleRef] = Field(default_factory=list)
    cited_by: list[str] = Field(default_factory=list)
    cid: Optional[str] = None
    pinned_by: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewMessage(BaseModel):
    """Peer review submitted by a reviewer."""
    id: str
    article_id: str
    reviewer_id: str
    decision: Decision
    comments: str  # Markdown
    scientific_correctness: int = 0  # 1-5
    clarity: int = 0  # 1-5
    collaboration_request: bool = False
    collaboration_message: str = ""
    points_earned: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EditProposal(BaseModel):
    """Post-publication edit proposal."""
    id: str
    article_id: str
    proposer_id: str
    proposal_type: EditType
    description: str
    git_branch: str
    diff_stat: str = ""
    status: ProposalStatus = ProposalStatus.PENDING
    points_stake: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None


class ReputationVector(BaseModel):
    """Multi-dimensional reputation."""
    user_id: str
    academic_contribution: float = 0.0   # 0-100
    review_quality: float = 0.0          # 0-100
    collaboration_spirit: float = 0.0    # 0-100
    education_outreach: float = 0.0      # 0-100
    total_points: int = 0


class PIPProposal(BaseModel):
    """PeerPedia Improvement Proposal."""
    id: str
    title: str
    author_id: str
    layer: int  # 1 = versioned module, 2 = configurable parameter
    summary: str
    specification: str
    status: str = "draft"  # draft | discussion | voting | accepted | rejected
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
