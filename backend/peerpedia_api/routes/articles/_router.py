"""Shared router for article sub-modules."""
from fastapi import APIRouter

router = APIRouter(prefix="/articles", tags=["articles"])
