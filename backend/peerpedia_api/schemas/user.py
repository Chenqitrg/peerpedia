"""User API schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReputationScoresOut(BaseModel):
    professionalism: float = 0.0
    objectivity: float = 0.0
    collaboration: float = 0.0
    pedagogy: float = 0.0


class UserSummary(BaseModel):
    id: str
    name: str
    anonymous_name: str = ""
    affiliation: str = ""
    expertise: list[str] = []
    avatar_url: Optional[str] = None


class UserProfile(BaseModel):
    id: str
    username: str = ""
    name: str
    anonymous_name: str = ""
    affiliation: str = ""
    expertise: list[str] = []
    avatar_url: Optional[str] = None
    contact: Optional[str] = None
    reputation: dict = {}
    followers_count: int = 0
    following_count: int = 0
    article_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(BaseModel):
    username: str
    password: str
    email: str = ""
    name: str
    affiliation: str = ""
    expertise: list[str] = []
    avatar_url: Optional[str] = None
    contact: Optional[str] = None


class UserUpdate(BaseModel):
    """Fields the user can edit about themselves. Name is immutable."""
    anonymous_name: Optional[str] = None
    affiliation: Optional[str] = None
    expertise: Optional[list[str]] = None
    avatar_url: Optional[str] = None
    contact: Optional[str] = None