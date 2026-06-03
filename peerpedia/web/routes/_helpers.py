"""Shared route helpers — reduce boilerplate in API handlers."""

from fastapi import HTTPException

from peerpedia_core.storage.db import get_article


def get_article_or_404(session, article_id: str):
    """Get an article by ID, or raise HTTP 404.

    Usage:
        article = get_article_or_404(session, article_id)
    """
    article = get_article(session, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
