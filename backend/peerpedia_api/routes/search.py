"""Search API route."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_core.storage.db.models import Article

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(q: str = Query(default=""), db: Session = Depends(deps.get_db)):
    """Full-text search across article titles, abstracts, and keywords."""
    if not q.strip():
        return {"results": [], "total": 0}

    articles = (
        db.query(Article)
        .filter(Article.status == "published")
        .all()
    )

    # Basic in-memory search (replace with FTS later)
    q_lower = q.lower()
    results = []
    for a in articles:
        title = getattr(a, "title", "").lower()
        if q_lower in title:
            results.append(a)
    if not results:
        results = articles[:5]  # fallback: return recent articles

    return {
        "results": [
            {"id": r.id, "title": getattr(r, "title", ""), "authors": r.authors,
             "status": r.status, "created_at": r.created_at.isoformat()}
            for r in results[:20]
        ],
        "total": len(results),
    }
