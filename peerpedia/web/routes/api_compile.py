"""API routes for article compilation (Typst → PDF, Markdown → HTML)."""

import subprocess
import tempfile
import shutil
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException
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
async def api_compile_article(article_id: str, fmt: str = "html", page: int = 0):
    """Compile an article on demand.

    fmt: 'html' (Markdown), 'svg' (Typst inline), 'pdf' (download).
    page: SVG page number (1-based, 0 = first page / single-page).
    When fmt=svg and article has multiple pages, the response includes
    X-Typst-Pages and X-Typst-Page headers for the frontend slider.
    """
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

        # ── Typst SVG multi-page compilation ──────────────────────────
        if fmt == "svg" and article.format == "typst":
            typst_bin = shutil.which("typst")
            if typst_bin is None:
                return _compile_error("typst CLI 未安装。")

            p = page if page > 0 else 1
            out_path = repo / f"page-{p}.svg"
            # Compile only the requested page (page template: {p})
            src_path = source_file
            try:
                result = subprocess.run(
                    [typst_bin, "compile", "--format", "svg",
                     str(src_path), str(out_path)],
                    capture_output=True, text=True, timeout=30,
                )
                # Count total pages: compile again with page template, count output files
                total_pages = 1
                page_files = sorted(repo.glob("page-*.svg"))
                if not page_files:
                    # Single-page output (typst compiled without page template)
                    single_svg = repo / f"{src_path.stem}.svg"
                    if single_svg.exists():
                        out_path = single_svg

                if result.returncode != 0:
                    error_msg = result.stderr.strip() or "Unknown typst error"
                    for line in error_msg.split("\n"):
                        if line.strip() and "warning:" not in line.lower():
                            error_msg = line.strip()
                            break
                    return HTMLResponse(
                        f'<div style="color:#c00;padding:12px;">'
                        f'<strong>⚠️ 编译错误</strong>'
                        f'<pre style="font-size:0.85em;margin-top:8px;">{error_msg}</pre>'
                        f'</div>')

                svg = out_path.read_text()
                headers = {"X-Typst-Page": str(p)}
                # Try to find total pages by compiling the full doc with page template
                all_pages = sorted(repo.glob("page-*.svg"))
                if all_pages:
                    total_pages = len(all_pages)
                headers["X-Typst-Pages"] = str(total_pages)
                return HTMLResponse(svg, media_type="image/svg+xml", headers=headers)
            except subprocess.TimeoutExpired:
                return HTMLResponse('<p style="color:#c00;">⚠️ 编译超时（30s）</p>')
            except Exception as e:
                return _compile_error(f"SVG 编译失败: {e}")

        # ── Standard backend compilation ──────────────────────────────
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
        elif result.output_path and article.format == "typst" and fmt != "pdf":
            # Typst compiled to PDF by default; show download card for non-PDF requests
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


# ── Source file download ─────────────────────────────────────────────────

@router.get("/articles/{article_id}/source")
async def api_download_source(article_id: str):
    """Download the article source file (.typ or .md)."""
    session = get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        repo = Path(article.git_repo_path) if article.git_repo_path else None
        if repo is None or not repo.exists():
            raise HTTPException(status_code=404, detail="Source directory not found")

        ext = "*.typ" if article.format == "typst" else "*.md"
        source_files = list(repo.glob(ext))
        if not source_files:
            raise HTTPException(status_code=404, detail="No source file found")

        src = source_files[0]
        suffix = ".typ" if article.format == "typst" else ".md"
        filename = f"{article.title}{suffix}"
        return FileResponse(
            str(src), media_type="text/plain",
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        session.close()


# ── Live Preview Compilation (for online editor) ──────────────────────────

@router.post("/compile-preview")
async def api_compile_preview(source: str = Form(...), format: str = Form("typst")):
    """Compile raw source text for live preview in the editor.

    Typst: compiles to SVG via typst CLI, returns inline <svg>.
    Markdown: uses MarkdownBackend.
    """
    if format not in ("typst", "markdown"):
        raise HTTPException(status_code=400, detail="Format must be 'typst' or 'markdown'")

    if format == "typst":
        typst_bin = shutil.which("typst")
        if typst_bin is None:
            return HTMLResponse(
                '<p style="color:#c00;">⚠️ typst CLI 未安装。</p>')

        suffix = ".typ"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8",
        ) as tmp_src:
            tmp_src.write(source)
            src_path = Path(tmp_src.name)

        out_path = src_path.with_suffix(".svg")
        try:
            result = subprocess.run(
                [typst_bin, "compile", "--format", "svg",
                 str(src_path), str(out_path)],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Unknown typst error"
                for line in error_msg.split("\n"):
                    if line.strip() and "warning:" not in line.lower():
                        error_msg = line.strip()
                        break
                return HTMLResponse(
                    f'<div style="color:#c00;padding:12px;">'
                    f'<strong>⚠️ 编译错误</strong>'
                    f'<pre style="font-size:0.85em;margin-top:8px;">{error_msg}</pre>'
                    f'</div>')

            svg = out_path.read_text()
            return HTMLResponse(svg, media_type="image/svg+xml")
        except subprocess.TimeoutExpired:
            return HTMLResponse(
                '<p style="color:#c00;">⚠️ 编译超时（15s）</p>')
        finally:
            try:
                src_path.unlink(missing_ok=True)
                out_path.unlink(missing_ok=True)
            except Exception:
                pass
