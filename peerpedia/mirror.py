"""ArXiv article mirroring.

Users can import articles from arXiv into PeerPedia. The original author
gets a "suspended founder" placeholder account. The importing user gets
mirror credit (+5 points).

Flow:
    1. Query arXiv API for metadata
    2. Create placeholder author accounts (arxiv:<slug>)
    3. Create Article record (source_arxiv_id, mirror_by)
    4. Award mirror points to importer
    5. Article directly published (no review needed for arXiv imports)
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    create_article,
    get_article,
    Article,
)
from peerpedia_core.storage.git_backend import (
    init_article_repo,
    commit_article,
)


ARXIV_API_URL = "https://export.arxiv.org/api/query"


@dataclass
class ArxivMetadata:
    """Parsed arXiv metadata."""
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    published_date: str
    pdf_url: str


@dataclass
class MirrorResult:
    """Result of mirroring an arXiv article."""
    success: bool
    article_id: str = ""
    arxiv_id: str = ""
    title: str = ""
    authors: list[str] = None  # type: ignore
    mirror_points: int = 0
    error: str = ""

    def __post_init__(self):
        if self.authors is None:
            self.authors = []


# ── arXiv API client ──────────────────────────────────────────────────────────

def fetch_arxiv_metadata(arxiv_id: str) -> Optional[ArxivMetadata]:
    """Fetch article metadata from arXiv API.

    Args:
        arxiv_id: arXiv identifier, e.g. "2301.00001" or "2301.00001v1"

    Returns:
        ArxivMetadata or None if not found / API error.
    """
    # Strip version suffix
    clean_id = re.sub(r'v\d+$', '', arxiv_id)

    url = f"{ARXIV_API_URL}?id_list={clean_id}&max_results=1"
    try:
        req = Request(url, headers={"User-Agent": "PeerPedia/0.1 (mailto:peerpedia@localhost)"})
        with urlopen(req, timeout=15) as response:
            xml_data = response.read().decode("utf-8")
    except URLError as e:
        reason = getattr(e, 'reason', str(e))
        code = getattr(e, 'code', None)
        return None  # caller uses generic error; detailed logging would go here

    return _parse_arxiv_xml(xml_data)


def _parse_arxiv_xml(xml_data: str) -> Optional[ArxivMetadata]:
    """Parse arXiv API XML response into ArxivMetadata."""
    # Remove namespace prefixes for easier parsing
    xml_clean = re.sub(r'<(\w+):(\w+)', r'<\1_\2', xml_data)
    xml_clean = re.sub(r'</(\w+):(\w+)', r'</\1_\2', xml_clean)

    # Safe: xml.etree.ElementTree does not resolve external entities or DTDs by default
    try:
        root = ET.fromstring(xml_clean)
    except ET.ParseError:
        return None

    # Namespace
    ns = "{http://www.w3.org/2005/Atom}"
    arxiv_ns = "{http://arxiv.org/schemas/atom}"

    entry = root.find(f"{ns}entry")
    if entry is None:
        return None

    # ID
    id_elem = entry.find(f"{ns}id")
    arxiv_id = id_elem.text.strip().split("/")[-1] if id_elem is not None and id_elem.text else ""
    arxiv_id = re.sub(r'v\d+$', '', arxiv_id)

    # Title
    title_elem = entry.find(f"{ns}title")
    title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else "Untitled"

    # Abstract
    summary_elem = entry.find(f"{ns}summary")
    abstract = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else ""

    # Authors
    authors = []
    for author_elem in entry.findall(f"{ns}author"):
        name_elem = author_elem.find(f"{ns}name")
        if name_elem is not None and name_elem.text:
            authors.append(name_elem.text.strip())

    # Categories
    categories = []
    for cat_elem in entry.findall(f"{ns}category"):
        term = cat_elem.attrib.get("term", "")
        if term:
            categories.append(term)

    # Published date
    published_elem = entry.find(f"{ns}published")
    published_date = published_elem.text.strip() if published_elem is not None and published_elem.text else ""

    # PDF URL
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

    return ArxivMetadata(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors,
        categories=categories,
        published_date=published_date,
        pdf_url=pdf_url,
    )


# ── Author slug generation ────────────────────────────────────────────────────

def _author_slug(name: str) -> str:
    """Generate a suspended founder ID from an author name.

    Example: "Albert Einstein" -> "arxiv:einstein-albert"
    """
    parts = name.lower().split()
    if len(parts) >= 2:
        slug = f"{parts[-1]}-{'-'.join(parts[:-1])}"
    else:
        slug = name.lower()
    # Remove non-alphanumeric except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    return f"arxiv:{slug}"


# ── Mirror orchestrator ───────────────────────────────────────────────────────

def mirror_arxiv(
    arxiv_id: str,
    mirror_user_id: str,
    *,
    database_url: str,
    articles_dir: Path,
) -> MirrorResult:
    """Mirror an arXiv article into PeerPedia.

    Args:
        arxiv_id: arXiv identifier, e.g. "2301.00001"
        mirror_user_id: The user performing the mirror
        database_url: SQLAlchemy database URL
        articles_dir: Directory for article git repos

    Returns:
        MirrorResult with article_id and points awarded.
    """
    # 1. Check for duplicate
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)
    try:
        existing = session.query(Article).filter(
            Article.source_arxiv_id == arxiv_id
        ).first()
        if existing:
            return MirrorResult(
                success=False,
                arxiv_id=arxiv_id,
                error=f"arXiv:{arxiv_id} 已经被搬运过了 (article: {existing.id})",
            )
    finally:
        session.close()

    # 2. Fetch metadata
    meta = fetch_arxiv_metadata(arxiv_id)
    if meta is None:
        return MirrorResult(
            success=False,
            arxiv_id=arxiv_id,
            error=f"无法获取 arXiv:{arxiv_id} 的元数据（API 错误或文章不存在）",
        )

    # 3. Create suspended founder accounts (just use the slug as author name)
    suspended_authors = [_author_slug(a) for a in meta.authors]

    # 4. Initialize git repo + create article
    try:
        repo_path = init_article_repo(arxiv_id, base_dir=articles_dir)

        # Write a minimal source file with metadata
        source_file = repo_path / f"{arxiv_id}.md"
        source_content = f"""---
title: {meta.title}
abstract: {meta.abstract}
categories:
{chr(10).join(f'  - {c}' for c in meta.categories)}
language: en
source: arxiv:{arxiv_id}
mirror_by: {mirror_user_id}
original_authors:
{chr(10).join(f'  - {a}' for a in meta.authors)}
---

# {meta.title}

**原文作者**: {', '.join(meta.authors)}

**来源**: [arXiv:{arxiv_id}]({meta.pdf_url})

**搬运者**: {mirror_user_id}

---

{meta.abstract}

---

> 本文由 {mirror_user_id} 从 arXiv 搬运。原作者为 {'、'.join(meta.authors)}。
> 原文地址: {meta.pdf_url}
"""
        source_file.write_text(source_content)

        commit_article(
            repo_path,
            message=f"Mirror: {meta.title} (arXiv:{arxiv_id})",
            author_name=mirror_user_id,
            author_email=f"{mirror_user_id}@peerpedia.local",
        )
    except Exception as e:
        return MirrorResult(success=False, arxiv_id=arxiv_id, error=f"Git 操作失败: {e}")

    # 5. Store in database
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)
    try:
        article = create_article(
            session,
            title=meta.title,
            founding_authors=suspended_authors,
            abstract=meta.abstract,
            categories=meta.categories,
            keywords=[],
            language="en",
            format="markdown",
            git_repo_path=str(repo_path),
        )
        # Set mirror-specific fields
        article.source_arxiv_id = arxiv_id
        article.mirror_by = mirror_user_id
        article.status = "published"  # arXiv imports are pre-published
        session.commit()

        article_id = article.id
    except Exception as e:
        session.rollback()
        return MirrorResult(success=False, arxiv_id=arxiv_id, error=f"数据库错误: {e}")
    finally:
        session.close()

    return MirrorResult(
        success=True,
        article_id=article_id,
        arxiv_id=arxiv_id,
        title=meta.title,
        authors=meta.authors,
        mirror_points=5,  # mirror credit
    )
