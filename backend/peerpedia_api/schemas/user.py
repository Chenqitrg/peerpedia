"""User API schemas."""
from datetime import datetime

from pydantic import BaseModel


class ReputationScoresOut(BaseModel):
    professionalism: float = 0.0
    objectivity: float = 0.0
    collaboration: float = 0.0
    pedagogy: float = 0.0


class UserSummary(BaseModel):
    id: str
    name: str
    affiliation: str = ""
    expertise: list[str] = []


class UserProfile(BaseModel):
    id: str
    name: str
    anonymous_name: str = ""
    affiliation: str = ""
    expertise: list[str] = []
    reputation: dict = {}
    followers_count: int = 0
    following_count: int = 0
    article_count: int = 0
    created_at: datetime


class UserCreate(BaseModel):
    name: str
    affiliation: str = ""
    expertise: list[str] = []
