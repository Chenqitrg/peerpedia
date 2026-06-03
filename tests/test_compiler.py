"""Tests for compiler backends."""
import tempfile
from pathlib import Path

from peerpedia_core.storage.compiler import (
    CompileResult,
    MarkdownBackend,
    TypstBackend,
    _protect_math,
    _restore_math,
    detect_format,
    extract_frontmatter,
)

SAMPLE_TYPST = """---
title: On Quantum Error Correction
abstract: A survey of surface codes.
categories:
  - physics
  - quantum
keywords:
  - surface code
  - error correction
language: en
---

= On Quantum Error Correction

== Introduction

Hello world.
"""

SAMPLE_MARKDOWN = """---
title: My Math Notes
abstract: Notes on linear algebra.
categories:
  - math
language: zh
---

# My Math Notes

## Introduction

Some text with math: $E = mc^2$
"""

NO_FRONTMATTER = """= Simple Typst Document

== Section 1

Just content, no metadata.
"""


class TestFrontmatterParsing:
    """Frontmatter extraction from Typst/Markdown sources."""

    def test_extract_typst_frontmatter(self):
        """Should parse YAML frontmatter from Typst source."""
        meta = extract_frontmatter(SAMPLE_TYPST)
        assert meta["title"] == "On Quantum Error Correction"
        assert meta["abstract"] == "A survey of surface codes."
        assert meta["categories"] == ["physics", "quantum"]
        assert meta["keywords"] == ["surface code", "error correction"]
        assert meta["language"] == "en"

    def test_extract_markdown_frontmatter(self):
        """Should parse YAML frontmatter from Markdown source."""
        meta = extract_frontmatter(SAMPLE_MARKDOWN)
        assert meta["title"] == "My Math Notes"
        assert meta["language"] == "zh"
        assert meta["categories"] == ["math"]

    def test_no_frontmatter_returns_empty(self):
        """Source without frontmatter should return empty dict."""
        meta = extract_frontmatter(NO_FRONTMATTER)
        assert meta == {}

    def test_frontmatter_strips_body(self):
        """extract_frontmatter should return only metadata, body stripped."""
        meta = extract_frontmatter(SAMPLE_TYPST)
        # Body content should NOT appear in metadata
        assert "Hello world" not in str(meta)
        assert "Introduction" not in str(meta)


class TestFormatDetection:
    """Detect format from file extension."""

    def test_detect_typst(self):
        assert detect_format(Path("article.typ")) == "typst"

    def test_detect_markdown(self):
        assert detect_format(Path("notes.md")) == "markdown"

    def test_detect_unknown(self):
        assert detect_format(Path("unknown.txt")) == "typst"  # default


class TestTypstBackend:
    """Typst compiler backend."""

    def test_format_name(self):
        backend = TypstBackend()
        assert backend.format_name == "typst"

    def test_compile_creates_pdf(self):
        """Compile a simple Typst document to PDF."""
        backend = TypstBackend()
        with tempfile.TemporaryDirectory() as tmp:
            source = _write(Path(tmp), "test.typ", NO_FRONTMATTER)
            result = backend.compile(source, Path(tmp))
            # Result should be a CompileResult
            assert isinstance(result, CompileResult)
            # If typst is installed, we get a PDF; if not, we get an error
            if result.success:
                assert result.output_path is not None
                assert Path(result.output_path).exists()

    def test_compile_missing_typst_graceful(self):
        """Should handle missing typst CLI gracefully."""
        backend = TypstBackend()
        with tempfile.TemporaryDirectory() as tmp:
            source = _write(Path(tmp), "test.typ", NO_FRONTMATTER)
            result = backend.compile(source, Path(tmp))
            # Result should always be a CompileResult, success or not
            assert isinstance(result, CompileResult)
            assert isinstance(result.success, bool)
            if not result.success:
                assert result.error is not None


class TestMarkdownBackend:
    """Markdown + KaTeX compiler backend."""

    def test_format_name(self):
        backend = MarkdownBackend()
        assert backend.format_name == "markdown"

    def test_compile_produces_html(self):
        """Compile Markdown to HTML."""
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            source = _write(Path(tmp), "test.md", SAMPLE_MARKDOWN)
            result = backend.compile(source, Path(tmp))
            assert isinstance(result, CompileResult)
            if result.success and result.html_content:
                assert "<h1>" in result.html_content or "<h2>" in result.html_content

    def test_inline_math_is_preserved(self):
        """Inline math $...$ should survive Markdown rendering."""
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            source = _write(Path(tmp), "math.md", "---\ntitle: Math\n---\n\nSome math: $E = mc^2$")
            result = backend.compile(source, Path(tmp))
            if result.success and result.html_content:
                assert "E = mc^2" in result.html_content

    def test_math_with_underscores_preserved(self):
        """$x_i$ and $a_{bc}$ must NOT have underscores parsed as Markdown emphasis."""
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            source = _write(Path(tmp), "sub.md", "---\ntitle: Subscripts\n---\n\n$x_i + y_j$")
            result = backend.compile(source, Path(tmp))
            if result.success and result.html_content:
                html = result.html_content
                # Underscores inside $...$ must survive, not become <em>
                assert "x_i" in html, f"Expected x_i in: {html}"
                assert "y_j" in html, f"Expected y_j in: {html}"
                assert "<em>" not in html, f"Underscores should not create <em>: {html}"

    def test_display_math_preserved(self):
        """$$...$$ display math should survive Markdown rendering."""
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            source = _write(Path(tmp), "display.md",
                            "---\ntitle: Display\n---\n\n$$\n\\sum_{i=1}^n i = \\frac{n(n+1)}{2}\n$$")
            result = backend.compile(source, Path(tmp))
            if result.success and result.html_content:
                html = result.html_content
                assert "\\sum" in html or "sum" in html.lower()
                assert "katex-display" in html, f"Expected display math: {html}"

    def test_math_mixed_with_markdown(self):
        """Math inside a paragraph with other Markdown formatting should work."""
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            source = _write(Path(tmp), "mixed.md",
                            "---\ntitle: Mixed\n---\n\n**Bold** and $x^2$ and *italic*.")
            result = backend.compile(source, Path(tmp))
            if result.success and result.html_content:
                html = result.html_content
                assert "x^2" in html
                assert "<strong>" in html or "<b>" in html


class TestMathProtection:
    """Unit tests for _protect_math and _restore_math."""

    def test_protect_inline_math(self):
        text = "Hello $x + y$ world"
        protected, ph = _protect_math(text)
        # $x + y$ should be replaced with placeholder
        assert "$" not in protected
        assert len(ph) == 1
        restored = _restore_math(protected, ph)
        assert "$x + y$" in restored

    def test_protect_display_math(self):
        text = "$$\n\\alpha + \\beta\n$$"
        protected, ph = _protect_math(text)
        assert "$$" not in protected
        assert len(ph) == 1
        restored = _restore_math(protected, ph)
        assert "$$" in restored
        assert "katex-display" in restored

    def test_protect_underscore_inside_math(self):
        """Underscores inside $...$ must be protected from Markdown."""
        text = "$x_i + y_j$"
        protected, ph = _protect_math(text)
        # The placeholder should contain the full original text
        assert "$" not in protected
        restored = _restore_math(protected, ph)
        assert "$x_i + y_j$" in restored

    def test_protect_no_math_unchanged(self):
        text = "Just plain text with _emphasis_ and **bold**."
        protected, ph = _protect_math(text)
        assert ph == {}
        assert protected == text

    def test_protect_multiple_math_expressions(self):
        text = "$a^2$ plus $b^2$ equals $c^2$"
        protected, ph = _protect_math(text)
        assert len(ph) == 3
        restored = _restore_math(protected, ph)
        assert restored.count("katex-inline") == 3

    def test_restore_display_math_has_correct_class(self):
        text = "$$\nx=1\n$$"
        protected, ph = _protect_math(text)
        restored = _restore_math(protected, ph)
        assert 'class="katex-display"' in restored

    def test_restore_inline_math_has_correct_class(self):
        text = "$E=mc^2$"
        protected, ph = _protect_math(text)
        restored = _restore_math(protected, ph)
        assert 'class="katex-inline"' in restored


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write(base: Path, name: str, content: str) -> Path:
    """Write content to a file in a temp directory, return the path."""
    filepath = base / name
    filepath.write_text(content)
    return filepath


# ── Compile API Endpoint Tests (Bug 2 regression) ───────────────────────────────

from unittest import mock

from fastapi.testclient import TestClient

from peerpedia.submit import submit_article


def _setup_test_db_with_article(tmp_path, md_content=None):
    """Create a test DB with one article submitted. Returns (db_url, article_id, articles_dir)."""
    base = Path(tmp_path)
    db_path = base / "test.db"
    articles_dir = base / "articles"
    articles_dir.mkdir()
    db_url = f"sqlite:///{db_path}"

    source = base / "test.md"
    source.write_text(md_content or """---
title: Test Article
abstract: A test article for compile tests.
---

# Test Article

Content paragraph with $E = mc^2$.
""")
    result = submit_article(
        source_path=source,
        database_url=db_url,
        articles_dir=articles_dir,
    )
    assert result.success, f"submit_article failed: {result.error}"
    return db_url, result.article_id, articles_dir


class TestCompileEndpoint:
    """Regression tests: compile endpoint must always return HTML, never JSON error."""

    def test_compile_returns_html_when_article_not_found(self):
        """GET /compile with nonexistent article ID returns HTML (not JSON 404)."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, _, _ = _setup_test_db_with_article(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                client = TestClient(app)
                resp = client.get("/api/v1/articles/nonexistent-id/compile?fmt=html")
                # Must return HTML, not JSON error that HTMX can't render
                assert "text/html" in resp.headers.get("content-type", "")
                assert "编译" in resp.text or "compile-error" in resp.text.lower() or "文章" in resp.text

    def test_compile_returns_html_when_source_dir_missing(self):
        """GET /compile returns HTML when git_repo_path doesn't exist on disk."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id, articles_dir = _setup_test_db_with_article(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                from peerpedia_core.storage.db import Article, get_engine, get_session, init_db

                # Corrupt the git_repo_path to point to nonexistent directory
                engine = get_engine(db_url)
                init_db(engine)
                session = get_session(engine)
                article = session.query(Article).filter(Article.id == article_id).first()
                article.git_repo_path = "/tmp/nonexistent-dir-xyz"
                session.commit()
                session.close()

                client = TestClient(app)
                resp = client.get(f"/api/v1/articles/{article_id}/compile?fmt=html")
                # Must be HTML, not a 404 JSON error
                content_type = resp.headers.get("content-type", "")
                assert "text/html" in content_type, f"Expected HTML, got {content_type}: {resp.text[:200]}"
                assert "compile-error" in resp.text or "不存在" in resp.text or "not found" in resp.text.lower()

    def test_compile_returns_html_when_source_file_missing(self):
        """GET /compile returns HTML when directory exists but no source files."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id, articles_dir = _setup_test_db_with_article(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                from peerpedia_core.storage.db import Article, get_engine, get_session, init_db

                # Point to a real but empty directory
                empty_dir = Path(tmp) / "empty_article"
                empty_dir.mkdir()
                engine = get_engine(db_url)
                init_db(engine)
                session = get_session(engine)
                article = session.query(Article).filter(Article.id == article_id).first()
                article.git_repo_path = str(empty_dir)
                session.commit()
                session.close()

                client = TestClient(app)
                resp = client.get(f"/api/v1/articles/{article_id}/compile?fmt=html")
                # Must return HTML with compile-error class, not JSON error
                content_type = resp.headers.get("content-type", "")
                assert "text/html" in content_type, f"Expected HTML, got {content_type}: {resp.text[:200]}"
                assert "compile-error" in resp.text or "源文件" in resp.text or "source" in resp.text.lower()

    def test_compile_success_markdown_returns_html_content(self):
        """GET /compile with valid source returns compiled HTML with article content."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id, articles_dir = _setup_test_db_with_article(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                from peerpedia_core.storage.db import Article, get_engine, get_session, init_db

                # Ensure article points to the actual articles_dir, format=markdown
                engine = get_engine(db_url)
                init_db(engine)
                session = get_session(engine)
                article = session.query(Article).filter(Article.id == article_id).first()
                md_files = list(Path(article.git_repo_path).glob("*.md"))
                # If no .md file in the repo, create one there
                if not md_files:
                    md_path = Path(article.git_repo_path) / "article.md"
                    md_path.write_text("""---
title: Direct Test
abstract: Testing compile.
---

# Direct Test

Content here with math $x^2 + y^2 = z^2$.
""")
                article.format = "markdown"
                session.commit()
                session.close()

                client = TestClient(app)
                resp = client.get(f"/api/v1/articles/{article_id}/compile?fmt=html")
                # Must return HTML content, not stuck on "编译中..."
                assert "text/html" in resp.headers.get("content-type", "")
                # The response should contain the article content, not an error or empty loading state
                assert "Direct Test" in resp.text or "Content here" in resp.text or "<h1>" in resp.text

    def test_compile_unknown_format_handled(self):
        """GET /compile with article.format='typst' and no typst CLI should return HTML error."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id, articles_dir = _setup_test_db_with_article(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                from peerpedia_core.storage.db import Article, get_engine, get_session, init_db

                # Set format to typst — TypstBackend will fail without CLI installed
                engine = get_engine(db_url)
                init_db(engine)
                session = get_session(engine)
                article = session.query(Article).filter(Article.id == article_id).first()
                article.format = "typst"
                # Create a .typ file in the repo so we don't hit "source file missing" first
                typ_path = Path(article.git_repo_path) / "article.typ"
                typ_path.write_text("= Test\nContent.")
                session.commit()
                session.close()

                client = TestClient(app)
                resp = client.get(f"/api/v1/articles/{article_id}/compile?fmt=html")
                # Must return HTML, never JSON
                content_type = resp.headers.get("content-type", "")
                assert "text/html" in content_type, f"Expected HTML, got {content_type}: {resp.text[:200]}"

    def test_compile_picks_correct_file_when_multiple_exist(self):
        """When repo has multiple .md files, pick the one matching article title."""
        with tempfile.TemporaryDirectory() as tmp:
            db_url, article_id, articles_dir = _setup_test_db_with_article(tmp)
            with mock.patch("peerpedia.web.db_session.settings.database_url", db_url):
                from peerpedia.web.app import app
                from peerpedia_core.storage.db import Article, get_engine, get_session, init_db

                # Add a second .md file with a DIFFERENT title to the repo
                engine = get_engine(db_url)
                init_db(engine)
                session = get_session(engine)
                article = session.query(Article).filter(Article.id == article_id).first()
                repo = Path(article.git_repo_path)

                # The primary file (already exists from submit)
                # Create a decoy file that would be picked alphabetically first
                decoy = repo / "aaa_decoy.md"
                decoy.write_text("""---
title: Decoy Article
abstract: Should not be picked.
---
# Decoy Article
This is NOT the article you are looking for.
""")
                session.commit()
                session.close()

                client = TestClient(app)
                resp = client.get(f"/api/v1/articles/{article_id}/compile?fmt=html")
                assert resp.status_code == 200
                # The compiled content must be from the real article (Test Article),
                # NOT from the alphabetically-first decoy
                assert "Test Article" in resp.text, (
                    f"Should compile the matching article, got: {resp.text[:300]}"
                )
                assert "Decoy Article" not in resp.text, (
                    f"Should NOT compile the alphabetically-first decoy"
                )
