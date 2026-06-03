"""API routes for articles, reviews, compilation, and citations."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
import tempfile

from peerpedia.config.settings import settings
from peerpedia.web.db_session import get_db_session
from peerpedia_core.storage.db import (
    list_articles, get_article, get_reviews_for_article,
)
from peerpedia_core.workflow.citations import get_citation_info, inject_citation_links
from peerpedia.submit import submit_article

router = APIRouter()


@router.get("/articles")
async def api_list_articles():
    """List all articles (most recent first)."""
    session = get_db_session()
    try:
        articles = list_articles(session)
        return {"articles": [a.to_dict() for a in articles], "total": len(articles)}
    finally:
        session.close()


@router.get("/articles/{article_id}")
async def api_get_article(article_id: str):
    """Get article metadata by ID."""
    session = get_db_session()
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
    if format not in ("typst", "markdown"):
        raise HTTPException(status_code=400, detail="Format must be 'typst' or 'markdown'")

    suffix = ".typ" if format == "typst" else ".md"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        content = await article_file.read()
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
        if tmp_path.exists():
            tmp_path.unlink()


@router.get("/articles/{article_id}/reviews")
async def api_get_reviews(article_id: str):
    """Get all reviews for an article."""
    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        reviews = get_reviews_for_article(session, article_id)
        return {
            "article_id": article_id,
            "reviews": [r.to_dict() for r in reviews],
            "total": len(reviews),
        }
    finally:
        session.close()


@router.post("/articles/{article_id}/reviews")
async def api_submit_review(
    article_id: str,
    reviewer_id: str = Form(...),
    decision: str = Form(...),
    comments: str = Form(""),
    scientific_correctness: int = Form(0),
    clarity: int = Form(0),
):
    """Submit a review for an article."""
    from peerpedia_core.workflow.review import assign_reviewer, submit_review

    assign_result = assign_reviewer(
        article_id=article_id,
        reviewer_id=reviewer_id,
        database_url=settings.database_url,
    )
    if not assign_result.success and "must be" not in assign_result.error:
        raise HTTPException(status_code=400, detail=assign_result.error)

    result = submit_review(
        article_id=article_id,
        reviewer_id=reviewer_id,
        decision=decision,
        comments=comments,
        scientific_correctness=scientific_correctness,
        clarity=clarity,
        database_url=settings.database_url,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "review_id": result.review_id,
        "points_earned": result.points_earned,
        "status": "submitted",
    }


@router.post("/articles/{article_id}/decide")
async def api_decide_article(article_id: str):
    """Make a decision on an article based on accumulated reviews."""
    from peerpedia_core.workflow.review import make_decision

    result = make_decision(article_id=article_id, database_url=settings.database_url)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "article_id": article_id,
        "new_status": result.new_status,
        "author_points": result.author_points,
    }


@router.get("/articles/{article_id}/compile")
async def api_compile_article(article_id: str, fmt: str = "html"):
    """Compile an article on demand. fmt: 'html' (default) or 'pdf'."""
    from pathlib import Path
    from peerpedia_core.storage.compiler import TypstBackend, MarkdownBackend
    from fastapi.responses import HTMLResponse

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            return HTMLResponse(
                content='<div class="compile-error"><p>⚠️ 文章未找到。</p></div>',
                status_code=404,
            )

        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo is None or not repo.exists():
            return HTMLResponse(
                content=f'<div class="compile-error"><p>⚠️ 源文件目录不存在。</p><p>路径: {article.git_repo_path}</p><p>文章摘要: {article.abstract}</p></div>',
            )

        if article.format == "typst":
            source_files = list(repo.glob("*.typ"))
            backend = TypstBackend()
        else:
            source_files = list(repo.glob("*.md"))
            backend = MarkdownBackend()

        if not source_files:
            return HTMLResponse(
                content=f'<div class="compile-error"><p>⚠️ 源文件未找到。</p><p>目录: {repo}</p><p>格式: {article.format}</p><hr><h3>摘要</h3><p>{article.abstract}</p></div>',
            )

        result = backend.compile(source_files[0], repo)
        if not result.success:
            return HTMLResponse(
                content=f'<div class="compile-error"><p>⚠️ 编译失败: {result.error}</p><hr><h3>摘要</h3><p>{article.abstract}</p></div>',
            )

        if fmt == "pdf" and result.output_path:
            from fastapi.responses import FileResponse
            return FileResponse(
                result.output_path,
                media_type="application/pdf",
                filename=f"{article.title}.pdf",
            )
        elif result.html_content:
            linked_html = inject_citation_links(result.html_content)
            return HTMLResponse(content=linked_html)
        elif result.output_path:
            output = Path(result.output_path)
            return {"content": output.read_text(), "format": article.format}
        else:
            return HTMLResponse(
                content='<div class="compile-error"><p>⚠️ 编译未产生输出。</p></div>',
            )
    finally:
        session.close()


@router.get("/articles/{article_id}/citations")
async def api_get_citations(article_id: str):
    """Get citation graph info (cites + cited_by) for an article."""
    session = get_db_session()
    try:
        info = get_citation_info(session, article_id)
        return info
    finally:
        session.close()


@router.get("/articles/{article_id}/contributions")
async def api_get_contribution_timeline(article_id: str):
    """Get contribution timeline and breakdown for an article."""
    from peerpedia_core.storage.db import get_contribution_records
    from peerpedia_core.workflow.contribution import (
        compute_contribution_breakdown,
        compute_contribution_timeline,
    )

    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        records = get_contribution_records(session, article_id)
        timeline = compute_contribution_timeline([r.to_dict() for r in records])
        breakdown = compute_contribution_breakdown([r.to_dict() for r in records])

        return {
            "article_id": article_id,
            "timeline": timeline,
            "breakdown": breakdown,
            "total_records": len(records),
        }
    finally:
        session.close()
