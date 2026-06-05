"""Citation API routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from peerpedia_api import deps
from peerpedia_core.storage.db.crud_citation import (
    create_or_update_citation, get_cites, get_cited_by,
)
from peerpedia_core.storage.db.crud_article import get_article

router = APIRouter(tags=["citations"])


class ClickRequest(BaseModel):
    from_article_id: str
    to_article_id: str


@router.get("/articles/{article_id}/citations")
def api_get_citations(article_id: str, db: Session = Depends(deps.get_db)):
    if get_article(db, article_id) is None:
        raise HTTPException(status_code=404, detail="Article not found")
    cites = get_cites(db, article_id)
    cited_by = get_cited_by(db, article_id)

    def _edge(article, direction: str) -> dict:
        aid = article.to_article_id if direction == "forward" else article.from_article_id
        a = get_article(db, aid)
        return {
            "article_id": aid,
            "title": a.title if a else "Unknown",
            "forward_prob": article.forward_prob,
            "backward_prob": article.backward_prob,
        }

    return {
        "cites": [_edge(c, "forward") for c in cites],
        "cited_by": [_edge(c, "backward") for c in cited_by],
    }


@router.post("/citations/click", status_code=201)
def api_record_click(body: ClickRequest, db: Session = Depends(deps.get_db)):
    create_or_update_citation(db, body.from_article_id, body.to_article_id,
                              forward=0.5, backward=0.0)
    return {"status": "ok"}
