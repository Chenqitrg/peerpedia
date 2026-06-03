"""Tests for arXiv mirror functionality."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from peerpedia.mirror import (
    ArxivMetadata,
    MirrorResult,
    _author_slug,
    _parse_arxiv_xml,
    mirror_arxiv,
)


SAMPLE_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <title>On Quantum Test Theory</title>
    <summary>  This is a test abstract for a quantum theory paper.
</summary>
    <author>
      <name>John Smith</name>
    </author>
    <author>
      <name>Jane Doe</name>
    </author>
    <category term="quant-ph"/>
    <category term="hep-th"/>
    <published>2023-01-01T00:00:00Z</published>
  </entry>
</feed>"""


class TestAuthorSlug:
    """Suspended founder ID generation."""

    def test_two_word_name(self):
        assert _author_slug("Albert Einstein") == "arxiv:einstein-albert"

    def test_three_word_name(self):
        slug = _author_slug("John Von Neumann")
        assert slug.startswith("arxiv:")

    def test_single_name(self):
        assert _author_slug("Plato") == "arxiv:plato"


class TestArxivXMLParsing:
    """Parse arXiv API XML responses."""

    def test_parse_metadata(self):
        meta = _parse_arxiv_xml(SAMPLE_ARXIV_XML)
        assert meta is not None
        assert meta.arxiv_id == "2301.00001"
        assert meta.title == "On Quantum Test Theory"
        assert meta.authors == ["John Smith", "Jane Doe"]
        assert "quant-ph" in meta.categories
        assert "hep-th" in meta.categories

    def test_parse_empty_xml(self):
        result = _parse_arxiv_xml("<feed></feed>")
        assert result is None

    def test_parse_bad_xml(self):
        result = _parse_arxiv_xml("not xml at all")
        assert result is None


class TestMirrorDeduplication:
    """Same arXiv article cannot be mirrored twice."""

    def test_duplicate_mirror_fails(self):
        """Mirroring the same arXiv ID twice should fail."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()
            db_url = f"sqlite:///{db_path}"

            # Mock the arXiv API to avoid network calls
            with patch("peerpedia.mirror.fetch_arxiv_metadata") as mock_fetch:
                mock_fetch.return_value = ArxivMetadata(
                    arxiv_id="2301.00001",
                    title="Test Paper",
                    abstract="Test abstract.",
                    authors=["John Smith"],
                    categories=["quant-ph"],
                    published_date="2023-01-01",
                    pdf_url="https://arxiv.org/pdf/2301.00001",
                )

                # First mirror
                r1 = mirror_arxiv(
                    arxiv_id="2301.00001",
                    mirror_user_id="user-zhang",
                    database_url=db_url,
                    articles_dir=articles_dir,
                )
                assert r1.success is True
                assert r1.mirror_points == 5

                # Second mirror (should fail)
                r2 = mirror_arxiv(
                    arxiv_id="2301.00001",
                    mirror_user_id="user-li",
                    database_url=db_url,
                    articles_dir=articles_dir,
                )
                assert r2.success is False
                assert "已经" in r2.error

    def test_mirror_creates_article(self):
        """Mirrored article should be stored in DB as published."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()
            db_url = f"sqlite:///{db_path}"

            with patch("peerpedia.mirror.fetch_arxiv_metadata") as mock_fetch:
                mock_fetch.return_value = ArxivMetadata(
                    arxiv_id="2301.00001",
                    title="Test Paper",
                    abstract="Test abstract.",
                    authors=["John Smith"],
                    categories=["quant-ph"],
                    published_date="2023-01-01",
                    pdf_url="https://arxiv.org/pdf/2301.00001",
                )

                result = mirror_arxiv(
                    arxiv_id="2301.00001",
                    mirror_user_id="user-zhang",
                    database_url=db_url,
                    articles_dir=articles_dir,
                )

                assert result.success is True
                assert result.article_id != ""

                # Verify in DB
                from peerpedia_core.storage.db import get_engine, init_db, get_session, get_article
                engine = get_engine(db_url)
                init_db(engine)
                session = get_session(engine)
                article = get_article(session, result.article_id)
                assert article is not None
                assert article.title == "Test Paper"
                assert article.source_arxiv_id == "2301.00001"
                assert article.mirror_by == "user-zhang"
                assert article.status == "published"
                # Founding authors should be suspended accounts
                assert len(article.founding_authors) == 1
                assert article.founding_authors[0].startswith("arxiv:")
                session.close()
