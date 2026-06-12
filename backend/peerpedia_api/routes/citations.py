"""Citation API routes."""
from fastapi import APIRouter, Depends, HTTPException
from peerpedia_core.storage.db.crud_article import get_article
from peerpedia_core.storage.db.crud_citation import (
    create_or_update_citation,
    get_cited_by,
    get_cites,
)
from peerpedia_core.storage.db.models import Article
from pydantic import BaseModel
from sqlalchemy.orm import Session

from peerpedia_api import deps

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

    # Batch-load all referenced articles
    ids = {c.to_article_id for c in cites} | {c.from_article_id for c in cited_by}
    article_map = {}
    if ids:
        articles = db.query(Article).filter(Article.id.in_(ids)).all()
        article_map = {a.id: a for a in articles}

    def _edge(article, direction: str) -> dict:
        aid = article.to_article_id if direction == "forward" else article.from_article_id
        a = article_map.get(aid)
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
