"""API routes for article compilation (Typst → PDF, Markdown → HTML)."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from peerpedia.web.routes._helpers import get_article_or_404
from peerpedia.web.db_session import get_db_session
from peerpedia_core.storage.db import get_article
from peerpedia_core.storage.compiler import MarkdownBackend, TypstBackend
from peerpedia_core.workflow.citations import inject_citation_links

router = APIRouter()


def _compile_error(message: str, status: int = 200):
    """Return an HTML error response for compile failures."""
    return HTMLResponse(
        content=f'<div class="compile-error"><p>⚠️ {message}</p></div>',
        status_code=status,
    )


def _resolve_compile_backend(repo, article_format: str, article_title: str = ""):
    """Resolve the compiler backend and find the best source file.

    Returns (backend, source_path) or raises HTTPException on failure.
    When multiple source files exist, picks the one whose frontmatter title
    best matches the article title stored in the DB.
    """
    ext = "*.typ" if article_format == "typst" else "*.md"
    source_files = list(repo.glob(ext))
    if not source_files:
        raise HTTPException(
            status_code=400,
            detail=f"源文件未找到 (格式: {article_format})",
        )

    if len(source_files) == 1:
        picked = source_files[0]
    else:
        # Prefer the file whose frontmatter title matches the DB title
        from peerpedia_core.storage.compiler import extract_frontmatter
        picked = source_files[0]  # fallback
        for f in source_files:
            try:
                fm = extract_frontmatter(f.read_text())
                if fm.get("title") == article_title:
                    picked = f
                    break
            except Exception:
                continue

    backend = TypstBackend() if article_format == "typst" else MarkdownBackend()
    return backend, picked


@router.get("/articles/{article_id}/compile")
async def api_compile_article(article_id: str, fmt: str = "html"):
    """Compile an article on demand. fmt: 'html' (default) or 'pdf'."""
    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            return _compile_error("文章未找到。", status=404)

        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo is None or not repo.exists():
            return _compile_error(f"源文件目录不存在。路径: {article.git_repo_path}")

        try:
            backend, source_file = _resolve_compile_backend(
                repo, article.format, article_title=article.title,  # type: ignore[arg-type]
            )
        except HTTPException as e:
            return _compile_error(str(e.detail))

        result = backend.compile(source_file, repo)
        if not result.success:
            return _compile_error(f"编译失败: {result.error}")

        if fmt == "pdf" and result.output_path:
            return FileResponse(
                result.output_path, media_type="application/pdf",
                filename=f"{article.title}.pdf",
            )
        elif result.html_content:
            return HTMLResponse(content=inject_citation_links(result.html_content))
        elif result.output_path and article.format == "typst":
            # Typst compiles to PDF only; show a preview card with download link
            pdf_url = f"/api/v1/articles/{article_id}/compile?fmt=pdf"
            viewer_html = (
                '<div style="text-align:center;padding:40px 20px;'
                'background:#f8f9fa;border-radius:8px;border:2px dashed #ddd;">'
                '<p style="font-size:3em;margin:0 0 16px 0;">📄</p>'
                '<p style="font-size:1.1em;margin:0 0 8px 0;color:#333;">'
                'Typst 文章已编译为 PDF</p>'
                '<p style="font-size:0.9em;color:#888;margin:0 0 20px 0;">'
                '点击下方按钮查看或下载</p>'
                f'<a href="{pdf_url}" target="_blank" '
                'style="display:inline-block;padding:10px 24px;background:#2563eb;'
                'color:white;border-radius:6px;text-decoration:none;margin:4px;">'
                '在新标签页中查看</a>'
                f'<a href="{pdf_url}" download '
                'style="display:inline-block;padding:10px 24px;background:#16a34a;'
                'color:white;border-radius:6px;text-decoration:none;margin:4px;">'
                '下载 PDF</a>'
                '</div>'
            )
            return HTMLResponse(content=viewer_html)
        elif result.output_path:
            output = Path(result.output_path)
            return {"content": output.read_text(), "format": article.format}
        else:
            return _compile_error("编译未产生输出。")
    finally:
        session.close()
