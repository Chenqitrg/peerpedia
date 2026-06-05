"""Compile API route."""
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["compile"])


class CompileRequest(BaseModel):
    content: str
    format: str  # "markdown" | "typst"


@router.post("/compile-preview")
def compile_preview(body: CompileRequest):
    """Compile raw content and return rendered output."""
    format_lower = body.format.lower()
    if format_lower == "markdown":
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            src = tmp_dir / "article.md"
            src.write_text(body.content)
            out_dir = tmp_dir / "out"
            out_dir.mkdir()
            try:
                from peerpedia_core.storage.compiler import MarkdownBackend
                backend = MarkdownBackend()
                result = backend.compile(src, out_dir)
                if not result.success:
                    raise HTTPException(status_code=500, detail=result.error)
                html = result.html_content or ""
                if result.output_path:
                    html = Path(result.output_path).read_text()
                return {"format": "html", "output": html, "pages": None}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    elif format_lower == "typst":
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            src = tmp_dir / "article.typ"
            src.write_text(body.content)
            out_dir = tmp_dir / "out"
            out_dir.mkdir()
            try:
                from peerpedia_core.storage.compiler import TypstBackend
                backend = TypstBackend()
                result = backend.compile(src, out_dir, fmt="svg")
                if not result.success:
                    raise HTTPException(status_code=500, detail=result.error)
                svg_content = result.html_content or ""
                if not svg_content and result.output_path:
                    svg_content = Path(result.output_path).read_text()
                return {"format": "svg", "output": svg_content, "pages": None}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {body.format}")
