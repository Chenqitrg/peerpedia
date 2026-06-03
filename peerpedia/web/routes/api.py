"""Web — API endpoints (REST)."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
import tempfile

from peerpedia.config.settings import settings
from peerpedia_core.storage.db import (
    get_engine, get_session, init_db, list_articles, get_article,
)
from peerpedia.submit import submit_article

router = APIRouter(prefix="/api/v1")


def _get_db_session():
    """Get a database session, ensuring tables exist."""
    engine = get_engine(settings.database_url)
    init_db(engine)
    return get_session(engine)


@router.get("/articles")
async def api_list_articles():
    """List all articles (most recent first)."""
    session = _get_db_session()
    try:
        articles = list_articles(session)
        return {
            "articles": [a.to_dict() for a in articles],
            "total": len(articles),
        }
    finally:
        session.close()


@router.get("/articles/{article_id}")
async def api_get_article(article_id: str):
    """Get article metadata by ID."""
    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        return article.to_dict()
    finally:
        session.close()


@router.post("/articles")
async def api_create_article(
    title: str = Form(...),
    abstract: str = Form(""),
    format: str = Form("typst"),
    categories: str = Form(""),
    keywords: str = Form(""),
    language: str = Form("en"),
    article_file: UploadFile = File(...),
):
    """Submit a new article via file upload (multipart form)."""
    # Validate format
    if format not in ("typst", "markdown"):
        raise HTTPException(status_code=400, detail="Format must be 'typst' or 'markdown'")

    # Save uploaded file to temp location
    suffix = ".typ" if format == "typst" else ".md"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        content = await article_file.read()
        # If the file doesn't have frontmatter, prepend from form fields
        text = content.decode("utf-8")
        if not text.startswith("---"):
            cats = [c.strip() for c in categories.split(",") if c.strip()]
            kws = [k.strip() for k in keywords.split(",") if k.strip()]
            cats_yaml = "\n".join(f"  - {c}" for c in cats) if cats else ""
            kws_yaml = "\n".join(f"  - {k}" for k in kws) if kws else ""
            fm = f"---\ntitle: {title}\nabstract: {abstract}\nlanguage: {language}\n"
            if cats_yaml:
                fm += f"categories:\n{cats_yaml}\n"
            if kws_yaml:
                fm += f"keywords:\n{kws_yaml}\n"
            fm += "---\n\n"
            text = fm + text
        tmp.write(text)
        tmp_path = Path(tmp.name)

    try:
        settings.ensure_dirs()
        result = submit_article(
            source_path=tmp_path,
            database_url=settings.database_url,
            articles_dir=settings.articles_dir,
        )

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)

        return {
            "article_id": result.article_id,
            "title": result.title,
            "commit": result.git_commit_hash,
            "status": "submitted",
        }
    finally:
        # Cleanup temp file
        if tmp_path.exists():
            tmp_path.unlink()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
