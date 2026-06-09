"""Compile API route."""
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(tags=["compile"])


class CompileRequest(BaseModel):
    content: str
    format: str  # "markdown" | "typst"


# ── Shared compilation helpers ────────────────────────────────────────────

def _compile_markdown(content: str) -> str:
    """Compile Markdown content to HTML string."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / "article.md"
        src.write_text(content)
        out_dir = tmp_dir / "out"
        out_dir.mkdir()
        from peerpedia_core.storage.compiler import MarkdownBackend
        backend = MarkdownBackend()
        result = backend.compile(src, out_dir)
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        html = result.html_content or ""
        if result.output_path:
            html = Path(result.output_path).read_text()
        return html


def _compile_typst_svg(content: str) -> str:
    """Compile Typst content to SVG string (for preview)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / "article.typ"
        src.write_text(content)
        out_dir = tmp_dir / "out"
        out_dir.mkdir()
        from peerpedia_core.storage.compiler import TypstBackend
        backend = TypstBackend()
        result = backend.compile(src, out_dir, fmt="svg")
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        svg = result.html_content or ""
        if not svg and result.output_path:
            svg = Path(result.output_path).read_text()
        return svg


def _compile_typst_pdf(content: str) -> bytes:
    """Compile Typst content to PDF bytes (for download)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / "article.typ"
        src.write_text(content)
        out_dir = tmp_dir / "out"
        out_dir.mkdir()
        from peerpedia_core.storage.compiler import TypstBackend
        backend = TypstBackend()
        result = backend.compile(src, out_dir, fmt="pdf")
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        pdf_path = result.output_path
        if not pdf_path or not Path(pdf_path).exists():
            raise HTTPException(status_code=500, detail="PDF output not found")
        return Path(pdf_path).read_bytes()


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/compile-preview")
def compile_preview(body: CompileRequest):
    """Compile raw content and return rendered output."""
    format_lower = body.format.lower()
    try:
        if format_lower == "markdown":
            html = _compile_markdown(body.content)
            return {"format": "html", "output": html, "pages": None}
        elif format_lower == "typst":
            svg = _compile_typst_svg(body.content)
            return {"format": "svg", "output": svg, "pages": None}
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {body.format}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compile-download")
def compile_download(body: CompileRequest):
    """Compile raw content and return as downloadable file.

    Markdown → HTML file download, Typst → PDF file download.
    """
    format_lower = body.format.lower()
    try:
        if format_lower == "markdown":
            html = _compile_markdown(body.content)
            return Response(
                content=html.encode("utf-8"),
                media_type="text/html",
                headers={"Content-Disposition": "attachment; filename=article.html"},
            )
        elif format_lower == "typst":
            pdf_bytes = _compile_typst_pdf(body.content)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=article.pdf"},
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {body.format}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
