"""Web — Route handlers for HTML pages."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from peerpedia.config.settings import settings
from peerpedia_core.storage.db import (
    get_engine, get_session, init_db, list_articles, get_article,
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

        # Try to load compiled HTML content for display
        content_html = ""
        if article_dict["git_repo_path"]:
            repo = Path(article_dict["git_repo_path"])
            if article_dict["format"] == "markdown":
                html_candidates = list(repo.glob("*.html"))
                if html_candidates:
                    content_html = html_candidates[0].read_text()
            else:
                # For Typst, show source as plain text
                source_files = list(repo.glob("*.typ"))
                if source_files:
                    content_html = f"<pre>{source_files[0].read_text()}</pre>"

        article_dict["content"] = content_html

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
