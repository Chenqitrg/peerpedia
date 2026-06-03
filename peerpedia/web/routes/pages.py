"""Web — Route handlers for HTML pages."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from peerpedia.config.settings import settings
from peerpedia_core.storage.db import (
    get_engine, get_session, init_db, list_articles, get_article,
    Article,
)

router = APIRouter()

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _get_db_session():
    """Get a database session, ensuring tables exist."""
    engine = get_engine(settings.database_url)
    init_db(engine)
    return get_session(engine)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page — article listing from database."""
    session = _get_db_session()
    try:
        articles = list_articles(session)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "title": "PeerPedia",
                "articles": [a.to_dict() for a in articles],
            },
        )
    finally:
        session.close()


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def view_article(request: Request, article_id: str):
    """View a single article with rendered content."""
    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            return templates.TemplateResponse(
                "article.html",
                {"request": request, "title": "Not Found", "article": None},
                status_code=404,
            )

        article_dict = article.to_dict()

        article_dict["content"] = None  # Compiled on demand via HTMX

        return templates.TemplateResponse(
            "article.html",
            {
                "request": request,
                "title": article_dict["title"],
                "article": article_dict,
            },
        )
    finally:
        session.close()


@router.get("/submit", response_class=HTMLResponse)
async def submit_page(request: Request):
    """Article submission page."""
    return templates.TemplateResponse(
        "submit.html",
        {"request": request, "title": "Submit Article"},
    )


@router.get("/review/{article_id}", response_class=HTMLResponse)
async def review_article_page(request: Request, article_id: str):
    """Review form for a specific article."""
    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            return templates.TemplateResponse(
                "review.html",
                {"request": request, "title": "Not Found", "article": None, "reviews": []},
                status_code=404,
            )

        from peerpedia_core.storage.db import get_reviews_for_article
        reviews = get_reviews_for_article(session, article_id)

        return templates.TemplateResponse(
            "review.html",
            {
                "request": request,
                "title": f"Review: {article.title}",
                "article": article.to_dict(),
                "reviews": [r.to_dict() for r in reviews],
            },
        )
    finally:
        session.close()


@router.get("/review", response_class=HTMLResponse)
async def review_queue(request: Request):
    """Review queue — list articles pending review."""
    session = _get_db_session()
    try:
        articles = list_articles(session, status="submitted")
        return templates.TemplateResponse(
            "review.html",
            {
                "request": request,
                "title": "Review Queue",
                "articles": [a.to_dict() for a in articles],
            },
        )
    finally:
        session.close()


@router.get("/user/{user_id}", response_class=HTMLResponse)
async def user_profile(request: Request, user_id: str):
    """User profile page — personal arXiv and activity footprint."""
    session = _get_db_session()
    try:
        # Articles authored by this user
        authored = (
            session.query(Article)
            .filter(Article.founding_authors.contains(user_id))
            .order_by(Article.created_at.desc())
            .all()
        )

        # Articles mirrored by this user
        mirrored = (
            session.query(Article)
            .filter(Article.mirror_by == user_id)
            .order_by(Article.created_at.desc())
            .all()
        )

        # Reviews by this user
        from peerpedia_core.storage.db import Review
        reviews = (
            session.query(Review)
            .filter(Review.reviewer_id == user_id)
            .order_by(Review.created_at.desc())
            .all()
        )

        # Build activity timeline
        activities = []
        for a in authored:
            activities.append({
                "type": "submit",
                "label": "提交了文章",
                "title": a.title,
                "article_id": a.id,
                "time": a.created_at.isoformat() if a.created_at else "",
            })
        for m in mirrored:
            activities.append({
                "type": "mirror",
                "label": f"搬运了 arXiv:{m.source_arxiv_id or '?'}",
                "title": m.title,
                "article_id": m.id,
                "time": m.created_at.isoformat() if m.created_at else "",
            })
        for r in reviews:
            activities.append({
                "type": "review",
                "label": "审稿了",
                "title": r.article_id,
                "article_id": r.article_id,
                "decision": r.decision,
                "points": r.points_earned,
                "time": r.created_at.isoformat() if r.created_at else "",
            })

        # Sort by time descending
        activities.sort(key=lambda x: x["time"], reverse=True)

        # Compute reputation vector for radar chart
        from peerpedia_core.reputation import ReputationV1
        try:
            algo = ReputationV1()
            reputation = algo.compute(user_id, session=session).model_dump()
        except Exception:
            reputation = {}

        return templates.TemplateResponse(
            "user.html",
            {
                "request": request,
                "title": f"用户: {user_id}",
                "user_id": user_id,
                "authored": [a.to_dict() for a in authored],
                "mirrored": [m.to_dict() for m in mirrored],
                "reviews": [
                    {
                        "article_id": r.article_id,
                        "decision": r.decision,
                        "points_earned": r.points_earned,
                        "scientific_correctness": r.scientific_correctness,
                        "clarity": r.clarity,
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in reviews
                ],
                "activities": activities[:30],
                "total_articles": len(authored),
                "total_mirrors": len(mirrored),
                "total_reviews": len(reviews),
                "total_points": sum(r.points_earned for r in reviews),
                "reputation": reputation,
            },
        )
    finally:
        session.close()
