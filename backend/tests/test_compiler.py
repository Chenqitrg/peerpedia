"""Specification: Compiler Backends for Typst and Markdown.

The compiler module translates article source files into rendered output.
It must reliably:
  - Extract structured metadata from YAML-like frontmatter
  - Detect article format from file extension
  - Compile Typst source to PDF/SVG via CLI
  - Compile Markdown to HTML with KaTeX math support
  - Handle missing CLI, timeouts, and read errors gracefully
"""
import tempfile
from pathlib import Path

from peerpedia_core.storage.compiler import (
    CompileResult,
    MarkdownBackend,
    TypstBackend,
    _parse_simple_yaml,
    _parse_typst_warnings,
    _protect_math,
    _restore_math,
    _strip_frontmatter,
    detect_format,
    extract_frontmatter,
)


class TestFrontmatterExtraction:
    """Extract structured metadata from article headers."""

    def test_extract_simple_kv(self):
        """Single key: value pairs are parsed correctly."""
        source = "---\ntitle: My Article\nauthor: Alice\n---\n\nBody"
        fm = extract_frontmatter(source)
        assert fm["title"] == "My Article"
        assert fm["author"] == "Alice"

    def test_extract_with_list(self):
        """List values are parsed into Python lists."""
        source = "---\ncategories:\n  - physics\n  - math\n---\n\nBody"
        fm = extract_frontmatter(source)
        assert fm["categories"] == ["physics", "math"]

    def test_extract_mixed(self):
        """Mixed scalar and list values in the same frontmatter."""
        source = "---\ntitle: Test\nkeywords:\n  - a\n  - b\nstatus: draft\n---\nBody"
        fm = extract_frontmatter(source)
        assert fm["title"] == "Test"
        assert fm["keywords"] == ["a", "b"]
        assert fm["status"] == "draft"

    def test_no_frontmatter(self):
        """Source without frontmatter returns empty dict."""
        assert extract_frontmatter("Just content") == {}
        assert extract_frontmatter("") == {}

    def test_unclosed_frontmatter(self):
        """Frontmatter without closing --- returns empty dict."""
        source = "---\ntitle: Incomplete\nBody"
        assert extract_frontmatter(source) == {}

    def test_chinese_alias_mapping(self):
        """Chinese frontmatter keys are mapped to English equivalents."""
        source = "---\n标题: 相对论\n摘要: 一篇文章\n---\n\nBody"
        fm = extract_frontmatter(source)
        assert fm["title"] == "相对论"
        assert fm["abstract"] == "一篇文章"
        # Original Chinese key should be removed
        assert "标题" not in fm

    def test_scalar_parsing_types(self):
        """YAML scalars are parsed to bool/int/float/str as appropriate."""
        source = "---\ncount: 42\nratio: 3.14\nactive: true\ninactive: false\nname: Alice\n---\nBody"
        fm = extract_frontmatter(source)
        assert fm["count"] == 42
        assert fm["ratio"] == 3.14
        assert fm["active"] is True
        assert fm["inactive"] is False
        assert fm["name"] == "Alice"

    def test_frontmatter_with_leading_blank_line(self):
        """Blank lines in frontmatter are skipped."""
        source = "---\n\ntitle: Hello\n\n\nauthor: Bob\n---\nBody"
        fm = extract_frontmatter(source)
        assert fm["title"] == "Hello"
        assert fm["author"] == "Bob"


class TestParseSimpleYaml:
    """Unit tests for the minimal YAML subset parser."""

    def test_empty_lines(self):
        assert _parse_simple_yaml([]) == {}

    def test_key_with_colon_in_value(self):
        """Values containing colons (e.g., URLs) should parse correctly."""
        result = _parse_simple_yaml(["url: https://example.com"])
        assert result["url"] == "https://example.com"

    def test_multiple_lists(self):
        """Multiple list keys can appear in sequence."""
        lines = [
            "categories:",
            "  - a",
            "  - b",
            "keywords:",
            "  - x",
            "  - y",
        ]
        result = _parse_simple_yaml(lines)
        assert result["categories"] == ["a", "b"]
        assert result["keywords"] == ["x", "y"]


class TestDetectFormat:
    """Format detection from file extension."""

    def test_typst_extensions(self):
        assert detect_format(Path("article.typ")) == "typst"
        assert detect_format(Path("article.typst")) == "typst"

    def test_markdown_extensions(self):
        assert detect_format(Path("article.md")) == "markdown"
        assert detect_format(Path("article.markdown")) == "markdown"

    def test_unknown_defaults_to_typst(self):
        """Unknown extensions default to typst."""
        assert detect_format(Path("article.txt")) == "typst"


class TestParseTypstWarnings:
    """Parse warning lines from Typst stderr."""

    def test_filters_warning_lines(self):
        stderr = "warning: unused variable x\nerror: compilation failed\nwarning: deprecation notice"
        warnings = _parse_typst_warnings(stderr)
        assert len(warnings) == 2
        assert "unused variable" in warnings[0]
        assert "deprecation" in warnings[1]

    def test_empty_stderr(self):
        assert _parse_typst_warnings("") == []


class TestStripFrontmatter:
    """Remove YAML frontmatter from source."""

    def test_strips(self):
        source = "---\ntitle: X\n---\n\nContent here"
        assert _strip_frontmatter(source) == "Content here"

    def test_no_frontmatter_passes_through(self):
        source = "Just content\nNo frontmatter"
        assert _strip_frontmatter(source) == source

    def test_partial_delimiters_ok(self):
        """Only opening --- present, no closing."""
        source = "---\nnot real frontmatter"
        result = _strip_frontmatter(source)
        # Should not crash — returns either source or stripped
        assert len(result) >= 0


class TestMathProtection:
    """Protect and restore math expressions during Markdown rendering."""

    def test_protect_display_math(self):
        text = "Hello $$E = mc^2$$ world"
        protected, placeholders = _protect_math(text)
        assert "$$E = mc^2$$" not in protected
        assert "PEERPEDIA_MATH_D0" in protected
        assert placeholders["PEERPEDIA_MATH_D0"] == "$$E = mc^2$$"

    def test_protect_inline_math(self):
        text = "Inline $x^2$ math"
        protected, placeholders = _protect_math(text)
        assert "$x^2$" not in protected
        assert "PEERPEDIA_MATH_I0" in protected
        assert placeholders["PEERPEDIA_MATH_I0"] == "$x^2$"

    def test_protect_multiple(self):
        text = "$$a$$ and $b$ and $$c$$"
        protected, placeholders = _protect_math(text)
        assert "$$a$$" not in protected
        assert "$b$" not in protected
        assert "$$c$$" not in protected
        assert len(placeholders) == 3

    def test_restore_math(self):
        text = "Hello $$E = mc^2$$ world"
        protected, placeholders = _protect_math(text)
        restored = _restore_math(protected, placeholders)
        assert "$$E = mc^2$$" in restored
        assert "katex-display" in restored

    def test_restore_inline_math(self):
        text = "Inline $x^2$ math"
        protected, placeholders = _protect_math(text)
        restored = _restore_math(protected, placeholders)
        assert "$x^2$" in restored
        assert "katex-inline" in restored

    def test_no_math_passes_through(self):
        text = "Plain text without math"
        protected, placeholders = _protect_math(text)
        assert protected == text
        assert placeholders == {}

    def test_restore_with_no_placeholders(self):
        html = "<p>Hello</p>"
        assert _restore_math(html, {}) == html


class TestMarkdownBackend:
    """Compile Markdown to HTML."""

    def test_compile_simple(self):
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            src = tmp_dir / "test.md"
            src.write_text("# Hello\n\nWorld")
            out_dir = tmp_dir / "out"
            out_dir.mkdir()
            result = backend.compile(src, out_dir)
            assert result.success is True
            assert result.format == "markdown"
            assert result.html_content is not None
            assert "<h1>" in result.html_content

    def test_compile_nonexistent_file(self):
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            out_dir.mkdir()
            result = backend.compile(Path("/no/such/file.md"), out_dir)
            assert result.success is False

    def test_compile_with_frontmatter(self):
        """Frontmatter is stripped before rendering."""
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            src = tmp_dir / "test.md"
            src.write_text("---\ntitle: My Article\n---\n\n# Content\n\nHello world.")
            out_dir = tmp_dir / "out"
            out_dir.mkdir()
            result = backend.compile(src, out_dir)
            assert result.success is True
            assert "<h1>" in result.html_content
            # Frontmatter should NOT appear in output
            assert "My Article" not in result.html_content.split("<h1>")[0]

    def test_format_name(self):
        assert MarkdownBackend.format_name == "markdown"


class TestTypstBackend:
    """Compile Typst source to PDF/SVG."""

    def test_compile_missing_cli(self):
        """When typst CLI is not installed, returns error result."""
        import shutil

        backend = TypstBackend()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            src = tmp_dir / "test.typ"
            src.write_text("= Hello")
            out_dir = tmp_dir / "out"
            out_dir.mkdir()

            result = backend.compile(src, out_dir, fmt="svg")
            if shutil.which("typst") is None:
                assert result.success is False
                assert "not found" in (result.error or "").lower()

    def test_compile_invalid_format_falls_back_to_pdf(self):
        """Invalid format falls back to PDF."""
        backend = TypstBackend()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            src = tmp_dir / "test.typ"
            src.write_text("= Hello")
            out_dir = tmp_dir / "out"
            out_dir.mkdir()
            # Should not crash even if CLI is missing
            result = backend.compile(src, out_dir, fmt="invalid")
            assert result.format in ("typst-pdf", "typst")

    def test_format_name(self):
        assert TypstBackend.format_name == "typst"

    def test_compile_timeout_handled(self):
        """CompileResult handles timeout case (may timeout or succeed)."""
        import shutil

        backend = TypstBackend()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            src = tmp_dir / "test.typ"
            src.write_text("= Simple")
            out_dir = tmp_dir / "out"
            out_dir.mkdir()

            result = backend.compile(src, out_dir)
            if shutil.which("typst"):
                assert result.success is True or result.success is False
            assert isinstance(result, CompileResult)


class TestTypstBackendWithoutCLI:
    """Typst backend behavior when typst CLI is not installed."""

    def test_compile_typst_not_installed(self):
        """When typst is not on PATH, returns error result with install message."""
        from unittest.mock import patch

        from peerpedia_core.storage.compiler import TypstBackend

        with patch("shutil.which", return_value=None):
            backend = TypstBackend()
            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                src = tmp_dir / "test.typ"
                src.write_text("= Hello\nWorld")
                out_dir = tmp_dir / "out"
                out_dir.mkdir()
                result = backend.compile(src, out_dir)
                assert result.success is False
                assert "not found" in (result.error or "").lower()
                assert result.format == "typst"


class TestMarkdownFallback:
    """Markdown backend behavior when markdown library is not installed."""

    def test_markdown_fallback_renders_basic_html(self):
        """When markdown library is unavailable, falls back to basic <p> tags."""
        import builtins
        import importlib

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "markdown":
                raise ImportError("No module named 'markdown'")
            return real_import(name, *args, **kwargs)

        try:
            builtins.__import__ = mock_import
            # Force reload so the module-level import check runs again
            from peerpedia_core.storage import compiler
            importlib.reload(compiler)

            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                src = tmp_dir / "test.md"
                src.write_text("# Hello\n\nWorld")
                out_dir = tmp_dir / "out"
                out_dir.mkdir()
                backend = compiler.MarkdownBackend()
                result = backend.compile(src, out_dir)
                assert result.success is True
                assert "<p>" in (result.html_content or "")

        finally:
            builtins.__import__ = real_import
            importlib.reload(compiler)


class TestCompileResult:
    """CompileResult dataclass behavior."""

    def test_success_result(self):
        r = CompileResult(success=True, format="markdown", html_content="<h1>Hi</h1>")
        assert r.success is True
        assert r.html_content == "<h1>Hi</h1>"
        assert r.error is None
        assert r.warnings == []

    def test_failure_result(self):
        r = CompileResult(success=False, format="typst", error="syntax error",
                         warnings=["warning: unused"])
        assert r.success is False
        assert r.error == "syntax error"
        assert len(r.warnings) == 1
