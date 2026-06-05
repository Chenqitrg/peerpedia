"""Bookmark API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_core.storage.db.crud_bookmark import (
    add_bookmark, remove_bookmark, is_bookmarked, get_bookmarks_for_user,
)
from peerpedia_core.storage.db.crud_article import get_article
from peerpedia_core.storage.db.models import User

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.get("")
def list_bookmarks(current_user: User = Depends(deps.require_user),
                   db: Session = Depends(deps.get_db)):
    articles = get_bookmarks_for_user(db, current_user.id)
    return {
        "bookmarks": [
            {"article_id": a.id, "title": a.title or "",
             "authors": a.authors, "status": a.status,
             "created_at": a.created_at.isoformat()}
            for a in articles
        ]
    }


@router.post("", status_code=201)
def bookmark(article_id: str, current_user: User = Depends(deps.require_user),
             db: Session = Depends(deps.get_db)):
    if get_article(db, article_id) is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if not is_bookmarked(db, current_user.id, article_id):
        add_bookmark(db, current_user.id, article_id)
    return {"bookmarked": True}


@router.delete("/{article_id}")
def unbookmark(article_id: str, current_user: User = Depends(deps.require_user),
               db: Session = Depends(deps.get_db)):
    remove_bookmark(db, current_user.id, article_id)
    return {"bookmarked": False}
