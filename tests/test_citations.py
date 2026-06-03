"""Tests for citation scanner and graph builder."""
import pytest
import tempfile
from pathlib import Path

from peerpedia_core.storage.db import (
    get_engine, get_session, init_db, create_article, Article,
)
from peerpedia_core.workflow.citations import (
    extract_references,
    build_citation_graph,
    get_citation_info,
    inject_citation_links,
)


class TestExtractReferences:

    def test_extract_typst_cite_format(self):
        """Should find #cite("peerpedia:<id>") patterns."""
        source = '''
        #cite("peerpedia:12345678-1234-1234-1234-123456789abc")
        Some text.
        #cite("peerpedia:abcdef01-5678-5678-5678-abcdef012345")
        '''
        refs = extract_references(source)
        assert len(refs) == 2
        assert "12345678-1234-1234-1234-123456789abc" in refs
        assert "abcdef01-5678-5678-5678-abcdef012345" in refs

    def test_extract_inline_format(self):
        """Should find peerpedia:<uuid> inline patterns."""
        source = "See also peerpedia:aaaaaaaa-1111-2222-3333-444444444444 for details."
        refs = extract_references(source)
        assert refs == ["aaaaaaaa-1111-2222-3333-444444444444"]

    def test_extract_no_references(self):
        """Should return empty list when no references found."""
        source = "Just a normal article with no citations."
        refs = extract_references(source)
        assert refs == []

    def test_extract_deduplicates(self):
        """Should not return duplicate references."""
        source = '''
        #cite("peerpedia:aaaaaaaa-1111-2222-3333-444444444444")
        And again peerpedia:aaaaaaaa-1111-2222-3333-444444444444
        '''
        refs = extract_references(source)
        assert refs == ["aaaaaaaa-1111-2222-3333-444444444444"]

    def test_extract_handles_whitespace(self):
        """Should handle whitespace variations in #cite format."""
        source = '#cite( "peerpedia:aaaaaaaa-1111-2222-3333-444444444444" )'
        refs = extract_references(source)
        assert "aaaaaaaa-1111-2222-3333-444444444444" in refs

    def test_extract_ignores_non_peerpedia_cites(self):
        """Should not match non-peerpedia citations."""
        source = '#cite("arxiv:2301.00001") and #cite("doi:10.1234/foo")'
        refs = extract_references(source)
        assert refs == []

    def test_extract_markdown(self):
        """Should find references in Markdown text."""
        source = '''
        # My Paper

        ## References
        - peerpedia:aaaaaaaa-1111-2222-3333-444444444444
        - See peerpedia:bbbbbbbb-2222-3333-4444-555555555555
        '''
        refs = extract_references(source)
        assert len(refs) == 2

    def test_inject_citation_links(self):
        """Should replace peerpedia:<id> with clickable HTML links."""
        html = '<p>See peerpedia:aaaaaaaa-1111-2222-3333-444444444444</p>'
        result = inject_citation_links(html)
        assert '<a href="/article/aaaaaaaa-1111-2222-3333-444444444444"' in result
        assert 'peerpedia:aaaaaaaa' not in result

    def test_inject_citation_links_no_refs(self):
        """Should not modify HTML without references."""
        html = '<p>No references here.</p>'
        result = inject_citation_links(html)
        assert result == html


class TestCitationGraph:

    def test_build_empty_graph(self):
        """Should return an empty DiGraph when no articles exist."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            G = build_citation_graph(session)
            assert len(G.nodes) == 0

    def test_build_graph_with_references(self):
        """Graph should contain edges for article references."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            aid_a = "aaaaaaaa-1111-2222-3333-444444444444"
            aid_b = "bbbbbbbb-2222-3333-4444-555555555555"

            create_article(session, id=aid_a, title="Article A",
                           founding_authors=["alice"], abstract="Cites B.",
                           git_repo_path="/tmp/a")
            create_article(session, id=aid_b, title="Article B",
                           founding_authors=["bob"], abstract="Cited by A.",
                           git_repo_path="/tmp/b")
            # Set references after creation
            a = session.query(Article).filter(Article.id == aid_a).first()
            a.references = [{"article_id": aid_b, "title": "Article B"}]
            session.commit()

            G = build_citation_graph(session)
            assert G.has_edge(aid_a, aid_b)
            assert G.nodes[aid_a]["title"] == "Article A"

    def test_get_cites_and_cited_by(self):
        """Should correctly identify cites and cited_by for an article."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            aid_a = "aaaaaaaa-1111-2222-3333-444444444444"
            aid_b = "bbbbbbbb-2222-3333-4444-555555555555"
            aid_c = "cccccccc-3333-4444-5555-666666666666"

            # A cites B, C cites A
            create_article(session, id=aid_a, title="Article A",
                           founding_authors=["alice"], abstract="...",
                           git_repo_path="/tmp/a")
            create_article(session, id=aid_b, title="Article B",
                           founding_authors=["bob"], abstract="...",
                           git_repo_path="/tmp/b")
            create_article(session, id=aid_c, title="Article C",
                           founding_authors=["charlie"], abstract="...",
                           git_repo_path="/tmp/c")
            # Set references after creation
            a = session.query(Article).filter(Article.id == aid_a).first()
            a.references = [{"article_id": aid_b, "title": "Article B"}]
            c = session.query(Article).filter(Article.id == aid_c).first()
            c.references = [{"article_id": aid_a, "title": "Article A"}]
            session.commit()

            # For A: cites = [B], cited_by = [C]
            info = get_citation_info(session, aid_a)
            assert len(info["cites"]) == 1
            assert info["cites"][0]["id"] == aid_b
            assert len(info["cited_by"]) == 1
            assert info["cited_by"][0]["id"] == aid_c

            # For B: cites = [], cited_by = [A]
            info_b = get_citation_info(session, aid_b)
            assert len(info_b["cites"]) == 0
            assert len(info_b["cited_by"]) == 1

    def test_citation_info_nonexistent_article(self):
        """Should return empty lists for nonexistent article."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            info = get_citation_info(session, "nonexistent-id")
            assert info["cites"] == []
            assert info["cited_by"] == []
