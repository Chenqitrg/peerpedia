"""Bookmark API routes."""
from fastapi import APIRouter, Depends, HTTPException
from peerpedia_core.storage.db.crud_article import get_article, get_author_ids
from peerpedia_core.storage.db.crud_bookmark import (
    add_bookmark,
    get_bookmarks_for_user,
    is_bookmarked,
    remove_bookmark,
)
from peerpedia_core.storage.db.models import User
from sqlalchemy.orm import Session

from peerpedia_api import deps

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.get("")
def list_bookmarks(current_user: User = Depends(deps.require_user),
                   db: Session = Depends(deps.get_db)):
    articles = get_bookmarks_for_user(db, current_user.id)
    return {
        "bookmarks": [
            {"article_id": a.id, "title": a.title or "",
             "authors": get_author_ids(db, a.id), "status": a.status,
             "created_at": a.created_at.isoformat()}
            for a in articles
        ]
    }


@router.post("", status_code=201)
def bookmark(article_id: str, current_user: User = Depends(deps.require_user),
             db: Session = Depends(deps.get_db)):
    if get_article(db, article_id) is None:
        raise HTTPException(status_code=404, detail="Article not found")
    author_ids = get_author_ids(db, article_id)
    if current_user.id in author_ids:
        raise HTTPException(status_code=400, detail="Cannot bookmark your own article")
    if not is_bookmarked(db, current_user.id, article_id):
        add_bookmark(db, current_user.id, article_id)
    return {"bookmarked": True}


@router.delete("/{article_id}")
def unbookmark(article_id: str, current_user: User = Depends(deps.require_user),
               db: Session = Depends(deps.get_db)):
    author_ids = get_author_ids(db, article_id)
    if current_user.id in author_ids:
        raise HTTPException(status_code=400, detail="Cannot bookmark your own article")
    remove_bookmark(db, current_user.id, article_id)
    return {"bookmarked": False}
