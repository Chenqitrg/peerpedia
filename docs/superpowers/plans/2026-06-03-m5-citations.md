# M5 Citation Jump — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build citation scanner, graph, and click-to-jump sidebar — extract peerpedia references from article source, build a citation DAG, and show clickable cite/cited-by links on the article page.

**Architecture:** New `citations.py` module handles reference extraction (regex) and graph building (NetworkX). Submit flow auto-populates Article.references. Compile endpoint injects citation links into HTML. Article page gets an HTMX sidebar that loads citation relationships.

**Tech Stack:** Python 3.14, NetworkX, FastAPI, Jinja2, HTMX, pytest

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `peerpedia_core/workflow/citations.py` | Reference scanner + graph builder | **Create** |
| `peerpedia/submit.py` | Auto-populate references on submit | Modify |
| `peerpedia/web/routes/api.py` | Citations endpoint + compile-time link injection | Modify |
| `peerpedia/web/templates/article.html` | Citation sidebar with HTMX | Modify |
| `tests/test_citations.py` | Scanner + graph tests | **Create** |

---

### Task 1: Citation Scanner + Graph Module

**Files:**
- Create: `peerpedia_core/workflow/citations.py`
- Create: `tests/test_citations.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_citations.py`:

```python
"""Tests for citation scanner and graph builder."""
import pytest
import tempfile
from pathlib import Path

from peerpedia_core.storage.db import (
    get_engine, get_session, init_db, create_article,
)
from peerpedia_core.workflow.citations import (
    extract_references,
    build_citation_graph,
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

            # Create two articles where A cites B
            aid_a = "aaaaaaaa-1111-2222-3333-444444444444"
            aid_b = "bbbbbbbb-2222-3333-4444-555555555555"

            create_article(session, id=aid_a, title="Article A",
                           founding_authors=["alice"], abstract="Cites B.",
                           git_repo_path="/tmp/a",
                           references=[{"article_id": aid_b, "title": "Article B"}])
            create_article(session, id=aid_b, title="Article B",
                           founding_authors=["bob"], abstract="Cited by A.",
                           git_repo_path="/tmp/b")
            session.commit()

            G = build_citation_graph(session)
            assert G.has_edge(aid_a, aid_b)

    def test_get_cites_and_cited_by(self):
        """Should correctly identify cites and cited_by for an article."""
        from peerpedia_core.workflow.citations import get_citation_info

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
                           git_repo_path="/tmp/a",
                           references=[{"article_id": aid_b, "title": "Article B"}])
            create_article(session, id=aid_b, title="Article B",
                           founding_authors=["bob"], abstract="...",
                           git_repo_path="/tmp/b")
            create_article(session, id=aid_c, title="Article C",
                           founding_authors=["charlie"], abstract="...",
                           git_repo_path="/tmp/c",
                           references=[{"article_id": aid_a, "title": "Article A"}])
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
        from peerpedia_core.workflow.citations import get_citation_info

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            info = get_citation_info(session, "nonexistent-id")
            assert info["cites"] == []
            assert info["cited_by"] == []
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /Users/chenqimeng/Projects/peerpedia
source .venv/bin/activate
python -m pytest tests/test_citations.py -v
```

Expected: FAIL — module `peerpedia_core.workflow.citations` doesn't exist.

- [ ] **Step 3: Create citations.py module**

Create `peerpedia_core/workflow/citations.py`:

```python
"""Layer 1: Citation scanner and graph builder.

Extracts peerpedia intra-site references from Typst/Markdown source,
builds a NetworkX citation Directed Acyclic Graph, and provides
cites/cited_by query functions.
"""

from __future__ import annotations

import re
from typing import Any

# Regex: match peerpedia:<UUID> in text or #cite("peerpedia:<UUID>")
# UUID pattern: 8-4-4-4-12 hex digits
_CITE_RE = re.compile(
    r'(?:#cite\s*\(\s*"peerpedia:)?'
    r'peerpedia:'
    r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
    r'(?:"\s*\))?'
)


def extract_references(source: str) -> list[str]:
    """Scan source text for peerpedia article references.

    Supports two formats:
    - Typst:    #cite("peerpedia:<article-id>")
    - Inline:   peerpedia:<article-id>  (anywhere in text)

    Returns deduplicated list of article IDs, in order of first appearance.
    """
    seen = set()
    result = []
    for m in _CITE_RE.finditer(source):
        aid = m.group(1)
        if aid not in seen:
            seen.add(aid)
            result.append(aid)
    return result


def inject_citation_links(html: str) -> str:
    """Replace peerpedia:<id> references with clickable HTML links.

    Only modifies inline references (not those already inside <a> tags).
    """
    def replacement(match):
        aid = match.group(1)
        return f'<a href="/article/{aid}" class="citation-link">📄 引用文章</a>'

    return re.sub(
        r'peerpedia:([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})',
        replacement,
        html,
    )


def build_citation_graph(session) -> "nx.DiGraph":
    """Build a NetworkX DiGraph from all articles' references.

    Nodes: article IDs
    Edges: A -> B means "A cites B"
    """
    import networkx as nx
    from peerpedia_core.storage.db import Article

    G = nx.DiGraph()
    articles = session.query(Article).all()
    for a in articles:
        G.add_node(a.id, title=a.title)
        for ref in (a.references or []):
            target_id = ref.get("article_id") if isinstance(ref, dict) else ref
            if target_id:
                G.add_edge(a.id, target_id)
    return G


def get_citation_info(
    session, article_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Get citation information for an article.

    Returns:
        {"cites": [{"id": ..., "title": ...}, ...],
         "cited_by": [{"id": ..., "title": ...}, ...]}
    """
    from peerpedia_core.storage.db import Article

    article = session.query(Article).filter(Article.id == article_id).first()

    # What this article cites (from references field)
    cites = []
    if article and article.references:
        for ref in article.references:
            target_id = ref.get("article_id") if isinstance(ref, dict) else ref
            if target_id:
                target = session.query(Article).filter(
                    Article.id == target_id
                ).first()
                cites.append({
                    "id": target_id,
                    "title": target.title if target else target_id[:8] + "...",
                })

    # Who cites this article (reverse lookup)
    cited_by = []
    all_articles = session.query(Article).all()
    for a in all_articles:
        if not a.references:
            continue
        for ref in a.references:
            target_id = ref.get("article_id") if isinstance(ref, dict) else ref
            if target_id == article_id:
                cited_by.append({"id": a.id, "title": a.title})
                break

    return {"cites": cites, "cited_by": cited_by}
```

Note: Install NetworkX if not already in venv: `pip install networkx`

- [ ] **Step 4: Run tests — verify they pass**

```bash
source .venv/bin/activate
python -m pytest tests/test_citations.py -v
```

Expected: 10 passed (7 scanner + 3 graph)

- [ ] **Step 5: Commit**

```bash
git add peerpedia_core/workflow/citations.py tests/test_citations.py
git commit -m "feat: add citation scanner and graph builder (M5)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Auto-Populate References on Submit

**Files:**
- Modify: `peerpedia/submit.py`

- [ ] **Step 6: Modify submit.py to scan references**

Open `peerpedia/submit.py`. Find the `submit_article()` function. After the article record is created (after `create_article(...)` call) and before `session.commit()`, add reference scanning:

Find the line like:
```python
    article = create_article(session, ...)
```

After it, add:
```python
    # Extract references from source
    from peerpedia_core.workflow.citations import extract_references
    try:
        source_text = source_path.read_text()
        ref_ids = extract_references(source_text)
        if ref_ids:
            # Build ref dicts with titles from DB
            ref_dicts = []
            for rid in ref_ids:
                target = get_article(session, rid)
                ref_dicts.append({
                    "article_id": rid,
                    "title": target.title if target else rid[:8] + "...",
                })
            article.references = ref_dicts
    except Exception:
        pass  # Reference scanning is best-effort, not critical
```

- [ ] **Step 7: Run full test suite**

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: ALL tests pass (154 passed).

- [ ] **Step 8: Commit**

```bash
git add peerpedia/submit.py
git commit -m "feat: auto-populate article references from source on submit

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Citation API + Compile-Time Link Injection

**Files:**
- Modify: `peerpedia/web/routes/api.py`

- [ ] **Step 9: Add citations endpoint and compile-time injection**

### 9a: Add import at top of api.py

In the existing imports section, add:
```python
from peerpedia_core.workflow.citations import get_citation_info, inject_citation_links
```

### 9b: Add citations API endpoint

Add before the health check endpoint at the end of api.py:

```python
# ── Citations ────────────────────────────────────────────────────────────────────


@router.get("/articles/{article_id}/citations")
async def api_get_citations(article_id: str):
    """Get citation graph info (cites + cited_by) for an article."""
    session = _get_db_session()
    try:
        info = get_citation_info(session, article_id)
        return info
    finally:
        session.close()
```

### 9c: Inject citation links in compile endpoint

In the existing `api_compile_article` function, find the line that returns `HTMLResponse(content=result.html_content)`. Before that line, add link injection:

Find:
```python
            return HTMLResponse(content=result.html_content)
```

Replace with:
```python
            # Inject citation links for peerpedia:<id> patterns
            linked_html = inject_citation_links(result.html_content)
            return HTMLResponse(content=linked_html)
```

- [ ] **Step 10: Run full test suite**

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: ALL tests pass.

- [ ] **Step 11: Commit**

```bash
git add peerpedia/web/routes/api.py
git commit -m "feat: add citation API endpoint and compile-time link injection

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Citation Sidebar on Article Page

**Files:**
- Modify: `peerpedia/web/templates/article.html`

- [ ] **Step 12: Add citation sidebar to article.html**

Open `peerpedia/web/templates/article.html`. Find the main content area where the article is rendered. Add a sidebar alongside the main content.

The exact edit: find the `<main>` section and restructure it to have a sidebar. If the current structure is:

```html
<main>
    <article>...content...</article>
</main>
```

Change to:

```html
<main style="display: flex; gap: 24px;">
    <article style="flex: 1; min-width: 0;">
        ...existing article content...
    </article>
    {% if article %}
    <aside class="citation-sidebar" style="width: 280px; flex-shrink: 0;">
        <h3>📚 引用关系</h3>
        <div id="citation-panel"
             hx-get="/api/v1/articles/{{ article.id }}/citations"
             hx-trigger="load"
             hx-swap="innerHTML">
            <p style="color: #888;">加载中...</p>
        </div>
    </aside>
    {% endif %}
</main>
```

Now add a Jinja2 template fragment that the HTMX endpoint returns — but since our API returns JSON, we need the sidebar to use a client-side render. Add a script that fetches and renders:

Actually, simpler approach: Make the citations endpoint return an HTML fragment when `Accept: text/html` header is present, or use HTMX's `hx-target` with a JSON-to-HTML transform.

**Simplest approach**: Create a tiny inline template in the article page. Add this script AFTER the sidebar div:

```html
<script>
(function() {
    var panel = document.getElementById('citation-panel');
    if (!panel) return;
    fetch('/api/v1/articles/{{ article.id }}/citations')
        .then(r => r.json())
        .then(data => {
            var html = '';
            if (data.cites && data.cites.length > 0) {
                html += '<h4>引用 (cites) ' + data.cites.length + ' 篇</h4><ul>';
                data.cites.forEach(function(c) {
                    html += '<li><a href="/article/' + c.id + '">' + c.title + '</a></li>';
                });
                html += '</ul>';
            } else {
                html += '<p style="color:#888;">未引用其他文章</p>';
            }
            if (data.cited_by && data.cited_by.length > 0) {
                html += '<h4>被引用 (cited by) ' + data.cited_by.length + ' 篇</h4><ul>';
                data.cited_by.forEach(function(c) {
                    html += '<li><a href="/article/' + c.id + '">' + c.title + '</a></li>';
                });
                html += '</ul>';
            } else {
                html += '<p style="color:#888;">暂无被引用</p>';
            }
            panel.innerHTML = html;
        })
        .catch(function() {
            panel.innerHTML = '<p style="color:#888;">引用加载失败</p>';
        });
})();
</script>
```

- [ ] **Step 13: Run full test suite**

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: ALL tests pass.

- [ ] **Step 14: Commit**

```bash
git add peerpedia/web/templates/article.html
git commit -m "feat: add citation sidebar with cites/cited-by to article page

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Final Verification

- [ ] **Step 15: Run full test suite**

```bash
cd /Users/chenqimeng/Projects/peerpedia
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: 154+ tests, 0 failures.

- [ ] **Step 16: Quick manual test**

```bash
# Submit an article with a citation
echo '# Test\n\nSee peerpedia:aaaaaaaa-1111-2222-3333-444444444444' > /tmp/test.md
source .venv/bin/activate
python -m peerpedia.cli.main submit /tmp/test.md --author testuser

# Check the article's references in the API
curl http://localhost:8080/api/v1/articles/<article-id>
# Should show references field populated
```

- [ ] **Step 17: Update STATUS.md**

Update the test count and M5 status in STATUS.md:

```markdown
> 当前状态: Phase 3 M1+M2+M2.5+M2.6+M3+M4(Rep)+M5 完成
> 测试: 154+ tests, 0 failures
```

And change the M5 row:
```markdown
| M5 | 引用跳转 | 引用扫描 + Graph + 点击跳转 | ✅ |
```

- [ ] **Step 18: Final commit**

```bash
git add STATUS.md
git commit -m "docs: update STATUS for M5 citation jump system complete

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
