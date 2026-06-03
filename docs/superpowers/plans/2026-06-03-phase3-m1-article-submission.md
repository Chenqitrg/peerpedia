# Phase 3 M1: Article Submission Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `peerpedia submit` work end-to-end: user submits Typst/Markdown article → git repo init + commit → SQLite metadata stored → Web shows real articles.

**Architecture:** Three new modules — `peerpedia_core/storage/db.py` (SQLAlchemy models + CRUD), `peerpedia_core/storage/compiler.py` (abstract compiler + Typst/Markdown backends), and `peerpedia/submit.py` (submission orchestrator). Existing CLI and Web routes are modified to wire real data through. TDD throughout: write failing tests first, then implement.

**Tech Stack:** Python 3.14, SQLAlchemy 2.0, SQLite, GitPython, Pydantic v2, Click, FastAPI, Jinja2, pytest

---

## File Map

```
NEW:
  peerpedia_core/storage/db.py          # SQLAlchemy models + engine + CRUD
  peerpedia_core/storage/compiler.py    # CompilerBackend ABC + TypstBackend + MarkdownBackend
  peerpedia/submit.py                   # Submission orchestrator (tying DB + git + compiler)
  tests/test_db.py                      # Database model + CRUD tests
  tests/test_compiler.py                # Compiler backend tests
  tests/test_submit.py                  # Submission orchestrator tests

MODIFY:
  peerpedia_core/storage/__init__.py    # Export new db + compiler symbols
  peerpedia/cli/main.py                 # Wire init (create tables) + submit (real impl)
  peerpedia/web/routes/api.py           # Real article list + article detail from DB
  peerpedia/web/routes/pages.py         # Pass real articles to templates
  peerpedia/config/settings.py          # Add DB URL config
```

---

### Task 1: Database Models + Engine

**Files:**
- Create: `peerpedia_core/storage/db.py`
- Create: `tests/test_db.py`
- Modify: `peerpedia_core/storage/__init__.py`

**What:** SQLAlchemy ORM models mirroring Pydantic protocol models, plus engine/session factory and CRUD functions. The `Article` model maps to a `articles` table in SQLite. JSON columns for list/dict fields.

- [ ] **Step 1: Write the failing DB model test**

Create `tests/test_db.py`:

```python
"""Tests for SQLAlchemy database layer."""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from peerpedia_core.storage.db import (
    Article,
    Base,
    get_engine,
    get_session,
    init_db,
    create_article,
    get_article,
    list_articles,
    ArticleStatus,
)


class TestArticleModel:
    """SQLAlchemy Article model must store and retrieve fields."""

    def test_article_table_creation(self):
        """init_db should create the articles table."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            # Verify table exists by querying the schema
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            assert "articles" in tables

    def test_create_and_get_article(self):
        """Create an article and retrieve it by ID."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            article = create_article(
                session,
                title="Test Article",
                founding_authors=["user-1"],
                abstract="A test abstract.",
                categories=["physics", "math"],
                keywords=["test"],
                language="en",
                format="typst",
                git_repo_path="/tmp/articles/test-1",
            )
            session.commit()

            assert article.id is not None
            assert article.title == "Test Article"
            assert article.status == ArticleStatus.DRAFT

            # Retrieve
            retrieved = get_article(session, article.id)
            assert retrieved is not None
            assert retrieved.title == "Test Article"
            assert retrieved.founding_authors == ["user-1"]
            assert retrieved.categories == ["physics", "math"]

    def test_list_articles(self):
        """list_articles should return all articles ordered by created_at desc."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            a1 = create_article(
                session, title="First", founding_authors=["u1"],
                abstract="First article.", git_repo_path="/tmp/a1",
            )
            a2 = create_article(
                session, title="Second", founding_authors=["u2"],
                abstract="Second article.", git_repo_path="/tmp/a2",
            )
            session.commit()

            articles = list_articles(session)
            assert len(articles) == 2
            # Most recent first
            assert articles[0].title == "Second"
            assert articles[1].title == "First"

    def test_list_articles_empty(self):
        """list_articles on empty DB returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            articles = list_articles(session)
            assert articles == []

    def test_article_defaults(self):
        """Article model should have correct defaults."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)

            article = create_article(
                session,
                title="Defaults Test",
                founding_authors=["u1"],
                abstract="Testing defaults.",
                git_repo_path="/tmp/defaults",
            )
            session.commit()

            assert article.status == ArticleStatus.DRAFT
            assert article.version == "v0.1"
            assert article.language == "en"
            assert article.format == "typst"
            assert article.categories == []
            assert article.keywords == []
            assert article.cid is None
            assert article.pinned_by == 0
            assert isinstance(article.created_at, datetime)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_db.py -v`
Expected: FAIL — module `peerpedia_core.storage.db` not found / import errors

- [ ] **Step 3: Write the database module**

Create `peerpedia_core/storage/db.py`:

```python
"""Layer 0: SQLAlchemy database layer for PeerPedia metadata.

All article metadata, user profiles, reviews, and reputation vectors
are stored in SQLite. The git repos themselves live on the filesystem
under ~/.peerpedia/articles/.

This module provides:
- SQLAlchemy ORM models (mirroring Pydantic protocol models)
- Engine/session factory
- CRUD operations for articles
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    Engine,
)
from sqlalchemy.orm import Session, DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator


# ── JSON column type for list/dict fields ──────────────────────────────────────

class JSONList(TypeDecorator):
    """Store Python list as JSON string in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


class JSONDict(TypeDecorator):
    """Store Python dict as JSON string in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


# ── ArticleStatus (mirrors protocol enum) ──────────────────────────────────────

class ArticleStatus:
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    REVISIONS_REQUESTED = "revisions_requested"
    ACCEPTED = "accepted"
    PUBLISHED = "published"
    REJECTED = "rejected"


# ── Base + Engine ──────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


def get_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine. Uses SQLite with WAL mode for concurrency."""
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        echo=False,
    )
    # Enable WAL mode for better concurrent reads
    if "sqlite" in database_url:
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def init_db(engine: Engine) -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_session(engine: Engine) -> Session:
    """Create a new session bound to the given engine."""
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


# ── ORM Model: Article ────────────────────────────────────────────────────────

class Article(Base):
    """SQLAlchemy model for article metadata. Mirrors protocol ArticleMeta."""

    __tablename__ = "articles"

    # Primary
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    founding_authors = Column(JSONList, nullable=False, default=list)

    # Metadata
    about_person = Column(String(300), nullable=True)
    original_works = Column(JSONList, nullable=False, default=list)
    abstract = Column(Text, nullable=False, default="")
    abstract_zh = Column(Text, nullable=True)
    categories = Column(JSONList, nullable=False, default=list)
    keywords = Column(JSONList, nullable=False, default=list)
    language = Column(String(20), nullable=False, default="en")
    status = Column(String(30), nullable=False, default=ArticleStatus.DRAFT)
    version = Column(String(20), nullable=False, default="v0.1")
    format = Column(String(20), nullable=False, default="typst")

    # References
    references = Column(JSONList, nullable=False, default=list)
    cited_by = Column(JSONList, nullable=False, default=list)

    # Content addressing
    cid = Column(String(128), nullable=True)
    pinned_by = Column(Integer, nullable=False, default=0)

    # Git
    git_repo_path = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to a dict suitable for JSON serialization / template rendering."""
        return {
            "id": self.id,
            "title": self.title,
            "founding_authors": self.founding_authors,
            "about_person": self.about_person,
            "original_works": self.original_works,
            "abstract": self.abstract,
            "abstract_zh": self.abstract_zh,
            "categories": self.categories,
            "keywords": self.keywords,
            "language": self.language,
            "status": self.status,
            "version": self.version,
            "format": self.format,
            "references": self.references,
            "cited_by": self.cited_by,
            "cid": self.cid,
            "pinned_by": self.pinned_by,
            "git_repo_path": self.git_repo_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ── CRUD Operations ────────────────────────────────────────────────────────────

def create_article(
    session: Session,
    *,
    title: str,
    founding_authors: list[str],
    abstract: str,
    git_repo_path: str,
    about_person: Optional[str] = None,
    original_works: Optional[list[dict]] = None,
    abstract_zh: Optional[str] = None,
    categories: Optional[list[str]] = None,
    keywords: Optional[list[str]] = None,
    language: str = "en",
    format: str = "typst",
) -> Article:
    """Create a new article record in the database."""
    article = Article(
        id=str(uuid.uuid4()),
        title=title,
        founding_authors=founding_authors,
        about_person=about_person,
        original_works=original_works or [],
        abstract=abstract,
        abstract_zh=abstract_zh,
        categories=categories or [],
        keywords=keywords or [],
        language=language,
        status=ArticleStatus.DRAFT,
        version="v0.1",
        format=format,
        git_repo_path=git_repo_path,
    )
    session.add(article)
    return article


def get_article(session: Session, article_id: str) -> Optional[Article]:
    """Get an article by ID, or None."""
    return session.query(Article).filter(Article.id == article_id).first()


def list_articles(
    session: Session,
    *,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Article]:
    """List articles, most recent first. Optionally filter by status."""
    q = session.query(Article).order_by(Article.created_at.desc())
    if status:
        q = q.filter(Article.status == status)
    return q.offset(offset).limit(limit).all()


def update_article_status(
    session: Session, article_id: str, new_status: str
) -> Optional[Article]:
    """Update an article's status."""
    article = get_article(session, article_id)
    if article:
        article.status = new_status
        article.updated_at = datetime.now(timezone.utc)
    return article


def update_article_cid(
    session: Session, article_id: str, cid: str
) -> Optional[Article]:
    """Update an article's CID after publishing."""
    article = get_article(session, article_id)
    if article:
        article.cid = cid
        article.updated_at = datetime.now(timezone.utc)
    return article
```

- [ ] **Step 4: Update storage __init__.py to export db symbols**

Read the file first, then edit `peerpedia_core/storage/__init__.py` to add:

```python
from peerpedia_core.storage.db import (
    Article,
    ArticleStatus,
    Base,
    create_article,
    get_article,
    get_engine,
    get_session,
    init_db,
    list_articles,
    update_article_cid,
    update_article_status,
)

__all__ = [
    # git_backend
    "DEFAULT_ARTICLES_DIR",
    "commit_article",
    "get_blame",
    "get_commit_history",
    "init_article_repo",
    # db
    "Article",
    "ArticleStatus",
    "Base",
    "create_article",
    "get_article",
    "get_engine",
    "get_session",
    "init_db",
    "list_articles",
    "update_article_cid",
    "update_article_status",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_db.py -v`
Expected: 5 PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add peerpedia_core/storage/db.py peerpedia_core/storage/__init__.py tests/test_db.py
git commit -m "feat: add SQLAlchemy database layer with Article model and CRUD

- Article ORM model with JSON column types for SQLite
- Engine/session factory with WAL mode + foreign keys
- CRUD: create_article, get_article, list_articles, update_status, update_cid
- 5 tests for table creation, CRUD, defaults, and edge cases

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Compiler Backends (Typst + Markdown)

**Files:**
- Create: `peerpedia_core/storage/compiler.py`
- Create: `tests/test_compiler.py`
- Modify: `peerpedia_core/storage/__init__.py`

**What:** Abstract `CompilerBackend` base class with `compile()` and `extract_metadata()`. Two implementations: `TypstBackend` (subprocess `typst compile`) and `MarkdownBackend` (markdown-it-py for HTML rendering + KaTeX for math). For MVP, `extract_metadata` parses frontmatter (YAML-like block at top of source).

- [ ] **Step 1: Write the failing compiler test**

Create `tests/test_compiler.py`:

```python
"""Tests for compiler backends."""
import pytest
import tempfile
from pathlib import Path

from peerpedia_core.storage.compiler import (
    CompilerBackend,
    CompileResult,
    TypstBackend,
    MarkdownBackend,
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
            source = tmpdir_write(Path(tmp), "test.typ", NO_FRONTMATTER)
            result = backend.compile(source, Path(tmp))
            # Result should be a CompileResult
            assert isinstance(result, CompileResult)
            # If typst is installed, we get a PDF; if not, we get an error
            if result.success:
                assert result.output_path is not None
                assert Path(result.output_path).exists()

    def test_compile_missing_typst_graceful(self):
        """Should handle missing typst CLI gracefully."""
        # We test the compile method — it should not crash even if typst is absent
        backend = TypstBackend()
        with tempfile.TemporaryDirectory() as tmp:
            source = tmpdir_write(Path(tmp), "test.typ", NO_FRONTMATTER)
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
            source = tmpdir_write(Path(tmp), "test.md", SAMPLE_MARKDOWN)
            result = backend.compile(source, Path(tmp))
            assert isinstance(result, CompileResult)
            if result.success and result.html_content:
                assert "<h1>" in result.html_content or "<h2>" in result.html_content

    def test_inline_math_is_preserved(self):
        """Inline math $...$ should be converted to KaTeX HTML spans."""
        backend = MarkdownBackend()
        with tempfile.TemporaryDirectory() as tmp:
            source = tmpdir_write(Path(tmp), "math.md", "---\ntitle: Math\n---\n\nSome math: $E = mc^2$")
            result = backend.compile(source, Path(tmp))
            if result.success and result.html_content:
                # Should contain KaTeX class or at least the math expression
                assert "E = mc^2" in result.html_content or "katex" in result.html_content.lower()


# ── Helpers ────────────────────────────────────────────────────────────────────

def tmpdir_write(base: Path, name: str, content: str) -> Path:
    """Write content to a file in a temp directory, return the path."""
    filepath = base / name
    filepath.write_text(content)
    return filepath
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_compiler.py -v`
Expected: FAIL — module `peerpedia_core.storage.compiler` not found

- [ ] **Step 3: Write the compiler module**

Create `peerpedia_core/storage/compiler.py`:

```python
"""Layer 1: Compiler backends for Typst and Markdown.

This is a versioned module — new backends can be added via PIP without
changing the core protocol.

Abstract interface:
    CompilerBackend.compile(source_path, output_dir) -> CompileResult
    CompilerBackend.extract_metadata(source_content) -> dict
"""

from __future__ import annotations

import re
import subprocess
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class CompileResult:
    """Result of a compilation."""
    success: bool
    format: str
    output_path: Optional[str] = None      # Path to compiled file (PDF, HTML)
    html_content: Optional[str] = None     # Inline HTML (for Markdown rendering)
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


# ── Frontmatter parsing ────────────────────────────────────────────────────────

def extract_frontmatter(source: str) -> dict:
    """Extract YAML-like frontmatter from Typst or Markdown source.

    Frontmatter is delimited by --- on its own lines at the start of the file.
    Only simple key: value pairs and list items (with - prefix) are supported
    for MVP. No PyYAML dependency required.

    Example:
        ---
        title: My Article
        abstract: A summary.
        categories:
          - physics
          - math
        ---

        = Actual content starts here
    """
    lines = source.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}

    fm_lines = lines[1:end_idx]
    return _parse_simple_yaml(fm_lines)


def _parse_simple_yaml(lines: list[str]) -> dict:
    """Parse a minimal YAML subset: scalar keys and list values.

    Supports:
        key: value
        key:
          - item1
          - item2

    No nested dicts, no quotes, no anchors. Just enough for article metadata.
    """
    result = {}
    current_key = None
    current_list = []

    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue

        # List item
        if line.strip().startswith("- "):
            item = line.strip()[2:].strip()
            if current_key is not None:
                current_list.append(item)
            continue

        # Key: value — flush any pending list
        if ":" in line:
            if current_key is not None and current_list:
                result[current_key] = current_list
                current_list = []

            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            if value:
                # Scalar value: key: value
                result[key] = _parse_scalar(value)
                current_key = None
            else:
                # List follows: key:
                current_key = key

    # Flush final list
    if current_key is not None and current_list:
        result[current_key] = current_list

    return result


def _parse_scalar(value: str) -> str | bool | int | float:
    """Parse a scalar YAML value."""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


# ── Format detection ───────────────────────────────────────────────────────────

def detect_format(file_path: Path) -> str:
    """Detect article format from file extension."""
    suffix = file_path.suffix.lower()
    if suffix in (".typ", ".typst"):
        return "typst"
    elif suffix in (".md", ".markdown"):
        return "markdown"
    return "typst"  # default


# ── Abstract compiler ──────────────────────────────────────────────────────────

class CompilerBackend(ABC):
    """Abstract compiler backend — versioned via PIP."""

    @abstractmethod
    def compile(self, source_path: Path, output_dir: Path) -> CompileResult:
        """Compile source to output format (PDF for Typst, HTML for Markdown)."""
        ...

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Return the format name: 'typst' or 'markdown'."""
        ...


# ── Typst backend ──────────────────────────────────────────────────────────────

class TypstBackend(CompilerBackend):
    """Compile Typst source via subprocess `typst compile`."""

    format_name = "typst"

    def compile(self, source_path: Path, output_dir: Path) -> CompileResult:
        """Run `typst compile <source> <output.pdf>`."""
        typst_bin = shutil.which("typst")
        if typst_bin is None:
            return CompileResult(
                success=False,
                format="typst",
                error="typst CLI not found. Install from https://github.com/typst/typst",
            )

        output_pdf = output_dir / f"{source_path.stem}.pdf"
        try:
            result = subprocess.run(
                [typst_bin, "compile", str(source_path), str(output_pdf)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return CompileResult(
                    success=True,
                    format="typst",
                    output_path=str(output_pdf),
                    warnings=_parse_typst_warnings(result.stderr),
                )
            else:
                return CompileResult(
                    success=False,
                    format="typst",
                    error=result.stderr.strip() or "Unknown typst error",
                )
        except subprocess.TimeoutExpired:
            return CompileResult(
                success=False,
                format="typst",
                error="typst compilation timed out (30s)",
            )
        except Exception as e:
            return CompileResult(
                success=False,
                format="typst",
                error=str(e),
            )


def _parse_typst_warnings(stderr: str) -> list[str]:
    """Parse warning lines from typst stderr output."""
    warnings = []
    for line in stderr.split("\n"):
        line = line.strip()
        if line.startswith("warning:"):
            warnings.append(line)
    return warnings


# ── Markdown backend ───────────────────────────────────────────────────────────

class MarkdownBackend(CompilerBackend):
    """Compile Markdown to HTML with KaTeX math rendering.

    Uses Python's markdown library for parsing. KaTeX is rendered
    client-side via CDN — the backend wraps $...$ in KaTeX-compatible
    HTML spans.
    """

    format_name = "markdown"

    def compile(self, source_path: Path, output_dir: Path) -> CompileResult:
        """Compile Markdown to HTML with KaTeX math support."""
        try:
            source = source_path.read_text()
        except Exception as e:
            return CompileResult(success=False, format="markdown", error=str(e))

        try:
            # Strip frontmatter for rendering
            body = _strip_frontmatter(source)
            html_body = _render_markdown(body)
            html_body = _wrap_math(html_body)

            full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
</head>
<body>
{html_body}
<script>
  renderMathInElement(document.body, {{
    delimiters: [
      {{left: '$$', right: '$$', display: true}},
      {{left: '$', right: '$', display: false}},
    ]
  }});
</script>
</body>
</html>"""

            output_path = output_dir / f"{source_path.stem}.html"
            output_path.write_text(full_html)

            return CompileResult(
                success=True,
                format="markdown",
                output_path=str(output_path),
                html_content=full_html,
            )
        except Exception as e:
            return CompileResult(success=False, format="markdown", error=str(e))


def _strip_frontmatter(source: str) -> str:
    """Remove YAML frontmatter from source, return body only."""
    if not source.startswith("---"):
        return source
    parts = source.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return source


def _render_markdown(md_text: str) -> str:
    """Render Markdown text to HTML.

    Uses built-in markdown parsing. Falls back to plain text with
    <br> line breaks if the markdown library is unavailable.
    """
    try:
        import markdown
        return markdown.markdown(
            md_text,
            extensions=["fenced_code", "tables", "codehilite"],
        )
    except ImportError:
        # Fallback: basic HTML wrapping
        escaped = md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        paragraphs = escaped.split("\n\n")
        return "\n".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip())


def _wrap_math(html: str) -> str:
    """Wrap $...$ and $$...$$ math expressions in KaTeX-compatible spans.

    $$...$$ → display math (block)
    $...$   → inline math
    """
    # Display math $$...$$ — must be handled first to not conflict with inline $
    html = re.sub(
        r'\$\$(.+?)\$\$',
        r'<span class="katex-display">$$\1$$</span>',
        html,
        flags=re.DOTALL,
    )
    # Inline math $...$ (single $, not $$)
    html = re.sub(
        r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)',
        r'<span class="katex-inline">$\1$</span>',
        html,
    )
    return html
```

- [ ] **Step 4: Update storage __init__.py to export compiler symbols**

Edit `peerpedia_core/storage/__init__.py` — append to existing imports:

```python
from peerpedia_core.storage.compiler import (
    CompileResult,
    CompilerBackend,
    MarkdownBackend,
    TypstBackend,
    detect_format,
    extract_frontmatter,
)
```

And append to `__all__`:

```python
    # compiler
    "CompileResult",
    "CompilerBackend",
    "MarkdownBackend",
    "TypstBackend",
    "detect_format",
    "extract_frontmatter",
```

- [ ] **Step 5: Run tests to verify**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_compiler.py -v`
Expected: Some tests pass (format detection, frontmatter parsing), Typst tests may skip gracefully if typst not installed

- [ ] **Step 6: Commit**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add peerpedia_core/storage/compiler.py peerpedia_core/storage/__init__.py tests/test_compiler.py
git commit -m "feat: add compiler backends (Typst + Markdown)

- CompilerBackend abstract interface with compile() method
- TypstBackend: subprocess typst compile to PDF
- MarkdownBackend: markdown-it-py to HTML with KaTeX math
- Frontmatter parsing (minimal YAML subset, no PyYAML dependency)
- Format detection from file extension
- 9 tests for frontmatter, format detection, and compilation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Submission Orchestrator

**Files:**
- Create: `peerpedia/submit.py`
- Create: `tests/test_submit.py`
- Modify: `peerpedia/config/settings.py`

**What:** The `submit_article()` function ties everything together: detect format → extract metadata → init git repo → commit source → compile → store in DB → compute CID. This is the core business logic that CLI and API will both call.

- [ ] **Step 1: Update settings to add DB URL**

Read and edit `peerpedia/config/settings.py`, add `database_url`:

```python
    # Database
    database_url: str = ""

    def __post_init__(self):
        if not self.database_url:
            self.database_url = f"sqlite:///{self.db_path}"
```

- [ ] **Step 2: Write the failing submission test**

Create `tests/test_submit.py`:

```python
"""Tests for article submission orchestrator."""
import pytest
import tempfile
from pathlib import Path

from peerpedia.submit import (
    submit_article,
    SubmissionResult,
)


SIMPLE_TYPST = """---
title: A Simple Test Article
abstract: Just testing the submission pipeline.
categories:
  - test
  - physics
keywords:
  - submission
  - test
language: en
---

= A Simple Test Article

== Introduction

This is a test article for the submission pipeline.

== Main Result

We find that $E = mc^2$ is correct.
"""


class TestSubmitArticle:
    """End-to-end article submission tests."""

    def test_submit_typst_article(self):
        """Submit a Typst article — creates git repo + DB entry."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source_file = base / "test.typ"
            source_file.write_text(SIMPLE_TYPST)

            result = submit_article(
                source_path=source_file,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            assert isinstance(result, SubmissionResult)
            assert result.success is True
            assert result.article_id is not None
            assert result.title == "A Simple Test Article"
            assert result.git_commit_hash is not None

            # Git repo should exist
            repo_path = articles_dir / result.article_id
            assert repo_path.exists()
            assert (repo_path / ".git").is_dir()

            # Source file should be in repo
            assert (repo_path / "test.typ").exists()

    def test_submit_article_stores_db_metadata(self):
        """After submission, metadata should be retrievable from DB."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source_file = base / "article.typ"
            source_file.write_text(SIMPLE_TYPST)

            result = submit_article(
                source_path=source_file,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            # Read from DB
            from peerpedia_core.storage.db import (
                get_engine, init_db, get_session, get_article,
            )
            engine = get_engine(f"sqlite:///{db_path}")
            init_db(engine)
            session = get_session(engine)
            article = get_article(session, result.article_id)
            assert article is not None
            assert article.title == "A Simple Test Article"
            assert article.categories == ["test", "physics"]
            assert article.keywords == ["submission", "test"]
            assert article.format == "typst"

    def test_submit_article_extracts_frontmatter(self):
        """Metadata from frontmatter should be stored."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source_file = base / "test.typ"
            source_file.write_text(SIMPLE_TYPST)

            result = submit_article(
                source_path=source_file,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            assert result.title == "A Simple Test Article"
            assert result.abstract == "Just testing the submission pipeline."
            assert result.categories == ["test", "physics"]

    def test_submit_without_frontmatter_prompts(self):
        """Article without frontmatter should still submit (use filename as title)."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            source_file = base / "notes.typ"
            source_file.write_text("= My Notes\n\nSome content without metadata.")

            result = submit_article(
                source_path=source_file,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            assert result.success is True
            assert result.article_id is not None
            # Falls back to filename
            assert result.title == "notes"

    def test_submit_markdown_article(self):
        """Submit a Markdown article."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "test.db"
            articles_dir = base / "articles"
            articles_dir.mkdir()

            md_content = """---
title: Markdown Test
abstract: Testing markdown submission.
language: en
---

# Markdown Test

Some math: $E = mc^2$
"""
            source_file = base / "notes.md"
            source_file.write_text(md_content)

            result = submit_article(
                source_path=source_file,
                database_url=f"sqlite:///{db_path}",
                articles_dir=articles_dir,
            )

            assert result.success is True
            assert result.format == "markdown"
            assert result.title == "Markdown Test"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_submit.py -v`
Expected: FAIL — module `peerpedia.submit` not found

- [ ] **Step 4: Write the submission orchestrator**

Create `peerpedia/submit.py`:

```python
"""Article submission orchestrator.

Ties together compiler, git backend, and database layers to implement
the full article submission flow:

    1. Read source file
    2. Detect format (typst/markdown)
    3. Extract frontmatter metadata
    4. Generate article UUID
    5. Initialize git repo for the article
    6. Copy source + assets into repo
    7. Git commit
    8. Compile (Typst -> PDF, Markdown -> HTML)
    9. Store metadata in SQLite
    10. Compute CID
    11. Return SubmissionResult
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from peerpedia_core.storage.compiler import (
    TypstBackend,
    MarkdownBackend,
    detect_format,
    extract_frontmatter,
)
from peerpedia_core.storage.git_backend import (
    init_article_repo,
    commit_article,
)
from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    create_article,
)
from peerpedia_core.protocol.addressing import compute_article_cid


@dataclass
class SubmissionResult:
    """Result of an article submission."""
    success: bool
    article_id: Optional[str] = None
    title: str = ""
    abstract: str = ""
    categories: list[str] = field(default_factory=list)
    format: str = "typst"
    git_repo_path: Optional[str] = None
    git_commit_hash: Optional[str] = None
    compile_output: Optional[str] = None   # Path to compiled PDF/HTML
    cid: Optional[str] = None
    error: Optional[str] = None


def submit_article(
    source_path: Path,
    *,
    database_url: str,
    articles_dir: Path,
    author_name: str = "peerpedia",
    author_email: str = "peerpedia@localhost",
) -> SubmissionResult:
    """Submit an article from a Typst or Markdown source file.

    Args:
        source_path: Path to the .typ or .md source file.
        database_url: SQLAlchemy database URL (e.g. sqlite:///path/to/db).
        articles_dir: Directory where article git repos are stored.
        author_name: Git author name.
        author_email: Git author email.

    Returns:
        SubmissionResult with article_id, git commit hash, and metadata.
    """
    # 1. Read source
    try:
        source_content = source_path.read_text()
    except Exception as e:
        return SubmissionResult(success=False, error=f"Cannot read file: {e}")

    # 2. Detect format
    fmt = detect_format(source_path)

    # 3. Extract frontmatter
    frontmatter = extract_frontmatter(source_content)

    title = frontmatter.get("title", source_path.stem)
    abstract = frontmatter.get("abstract", "")
    abstract_zh = frontmatter.get("abstract_zh")
    categories = frontmatter.get("categories", [])
    keywords = frontmatter.get("keywords", [])
    language = frontmatter.get("language", "en")
    about_person = frontmatter.get("about_person")

    # 4. Generate article ID
    article_id = str(uuid.uuid4())

    # 5. Initialize git repo
    try:
        repo_path = init_article_repo(article_id, base_dir=articles_dir)
    except Exception as e:
        return SubmissionResult(success=False, error=f"Git init failed: {e}")

    # 6. Copy source file into repo
    dest_file = repo_path / source_path.name
    shutil.copy2(source_path, dest_file)

    # Also copy any supporting files from the same directory
    for sibling in source_path.parent.iterdir():
        if sibling == source_path:
            continue
        if sibling.is_file():
            dest_sibling = repo_path / sibling.name
            if not dest_sibling.exists():
                shutil.copy2(sibling, dest_sibling)

    # 7. Git commit
    try:
        commit_hash = commit_article(
            repo_path,
            message=f"Submit: {title}",
            author_name=author_name,
            author_email=author_email,
        )
    except Exception as e:
        return SubmissionResult(success=False, error=f"Git commit failed: {e}")

    # 8. Compile
    if fmt == "typst":
        backend = TypstBackend()
    else:
        backend = MarkdownBackend()

    compile_result = backend.compile(dest_file, repo_path)

    # 9. Store metadata in SQLite
    try:
        engine = get_engine(database_url)
        init_db(engine)
        session = get_session(engine)

        article = create_article(
            session,
            title=title,
            founding_authors=[author_name],
            abstract=abstract,
            abstract_zh=abstract_zh,
            categories=categories,
            keywords=keywords,
            language=language,
            format=fmt,
            about_person=about_person,
            git_repo_path=str(repo_path),
        )
        session.commit()
    except Exception as e:
        return SubmissionResult(success=False, error=f"Database error: {e}")
    finally:
        session.close()

    # 10. Compute CID
    try:
        source_for_cid = dest_file.read_text()
        cid = compute_article_cid(
            typst_source=source_for_cid,
            metadata={"title": title, "id": article_id, "version": "v0.1"},
            git_commit_hash=commit_hash,
        )
    except Exception:
        cid = None

    return SubmissionResult(
        success=True,
        article_id=article_id,
        title=title,
        abstract=abstract,
        categories=categories,
        format=fmt,
        git_repo_path=str(repo_path),
        git_commit_hash=commit_hash,
        compile_output=compile_result.output_path,
        cid=cid,
    )
```

- [ ] **Step 5: Run tests to verify**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_submit.py -v`
Expected: 5 PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add peerpedia/submit.py peerpedia/config/settings.py tests/test_submit.py
git commit -m "feat: add article submission orchestrator

- submit_article() ties compiler + git + DB layers together
- Flow: read source → detect format → extract frontmatter → init git →
  commit → compile → store DB metadata → compute CID
- Handles Typst and Markdown formats
- Falls back gracefully on missing frontmatter (uses filename as title)
- 5 tests for end-to-end submission, DB storage, format detection

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Wire CLI Commands (init + submit)

**Files:**
- Modify: `peerpedia/cli/main.py`
- Modify: `peerpedia/config/settings.py`

**What:** Update `peerpedia init` to also create database tables. Rewrite `peerpedia submit` to call `submit_article()` instead of printing a placeholder.

- [ ] **Step 1: Run existing tests to get baseline**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: 19 passed (existing tests)

- [ ] **Step 2: Update `peerpedia init` to create DB tables**

Edit `peerpedia/cli/main.py` — replace the `init()` function:

```python
@cli.command()
def init():
    """Initialize PeerPedia in the current directory.

    Creates ~/.peerpedia/ with default configuration, empty database,
    and required directory structure.
    """
    from pathlib import Path
    from peerpedia_core.storage import DEFAULT_ARTICLES_DIR
    from peerpedia_core.storage.db import get_engine, init_db
    from peerpedia.config.settings import settings

    base = Path.home() / ".peerpedia"
    dirs = [
        base,
        DEFAULT_ARTICLES_DIR,
        base / "profiles",
        base / "db",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Initialize database tables
    engine = get_engine(settings.database_url)
    init_db(engine)

    click.echo(f"PeerPedia initialized at {base}")
    click.echo(f"  Articles repo dir: {DEFAULT_ARTICLES_DIR}")
    click.echo(f"  Database: {settings.db_path}")
    click.echo(f"  Next: peerpedia serve")
```

- [ ] **Step 3: Rewrite `peerpedia submit` to call submission orchestrator**

Edit `peerpedia/cli/main.py` — replace the `submit()` function:

```python
@cli.command()
@click.argument("article_path", type=click.Path(exists=True))
@click.option("--author", default=None, help="Your name for git commits")
@click.option("--email", default=None, help="Your email for git commits")
def submit(article_path: str, author: str | None, email: str | None):
    """Submit a Typst or Markdown article for peer review.

    ARTICLE_PATH: Path to the main .typ or .md file.
    """
    from pathlib import Path
    from peerpedia.config.settings import settings
    from peerpedia.submit import submit_article

    path = Path(article_path).resolve()

    author_name = author or "peerpedia"
    author_email = email or "peerpedia@localhost"

    click.echo(f"Submitting article: {path.name}")
    click.echo(f"  Format: {'Typst' if path.suffix in ('.typ', '.typst') else 'Markdown'}")

    # Ensure database is initialized
    from peerpedia_core.storage.db import get_engine, init_db
    engine = get_engine(settings.database_url)
    init_db(engine)

    settings.ensure_dirs()

    result = submit_article(
        source_path=path,
        database_url=settings.database_url,
        articles_dir=settings.articles_dir,
        author_name=author_name,
        author_email=author_email,
    )

    if result.success:
        click.echo()
        click.echo(f"✓ Article submitted successfully!")
        click.echo(f"  ID:     {result.article_id}")
        click.echo(f"  Title:  {result.title}")
        click.echo(f"  Commit: {result.git_commit_hash[:8]}")
        if result.cid:
            click.echo(f"  CID:    {result.cid[:16]}...")
        if result.compile_output:
            click.echo(f"  Output: {result.compile_output}")
        click.echo()
        click.echo(f"  View: peerpedia serve → http://localhost:{settings.port}")
    else:
        click.echo(f"✗ Submission failed: {result.error}", err=True)
        raise SystemExit(1)
```

- [ ] **Step 4: Add `python-multipart` dependency for file uploads**

Edit `pyproject.toml` — add to dependencies:

```toml
    "python-multipart>=0.0.6",
```

(Needed for FastAPI file upload via multipart form in Task 5)

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && pip install python-multipart`

- [ ] **Step 5: Run all tests to verify nothing is broken**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All tests pass (19 original + 5 db + 9 compiler + 5 submit = 38 passed)

- [ ] **Step 6: Manual smoke test of CLI**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && peerpedia init`
Expected: "PeerPedia initialized at ..." with DB path

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && echo '---\ntitle: Smoke Test\nabstract: Testing CLI.\n---\n\n= Smoke Test\n\nHello.' > /tmp/smoke.typ && peerpedia submit /tmp/smoke.typ`
Expected: "✓ Article submitted successfully!" with ID, title, commit hash

- [ ] **Step 7: Commit**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add peerpedia/cli/main.py pyproject.toml
git commit -m "feat: wire CLI init (creates DB) + submit (real submission)

- peerpedia init now initializes SQLite database tables
- peerpedia submit calls submission orchestrator for real article creation
- Added --author/--email options to submit command
- Added python-multipart dependency for upcoming file upload support

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Wire Web Routes (API + Pages)

**Files:**
- Modify: `peerpedia/web/routes/api.py`
- Modify: `peerpedia/web/routes/pages.py`
- Modify: `peerpedia/web/templates/index.html`

**What:** API returns real article data from SQLite. Homepage shows real articles. Article detail page shows rendered content. Submission form (POST) creates a real article.

- [ ] **Step 1: Update API routes to use real database**

Rewrite `peerpedia/web/routes/api.py`:

```python
"""Web — API endpoints (REST)."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
import tempfile
import shutil

from peerpedia.config.settings import settings
from peerpedia_core.storage.db import (
    get_engine, get_session, init_db, list_articles, get_article,
)
from peerpedia.submit import submit_article

router = APIRouter(prefix="/api/v1")


def _get_db_session():
    """Get a database session, ensuring tables exist."""
    engine = get_engine(settings.database_url)
    init_db(engine)
    return get_session(engine)


@router.get("/articles")
async def api_list_articles():
    """List all articles (most recent first)."""
    session = _get_db_session()
    try:
        articles = list_articles(session)
        return {
            "articles": [a.to_dict() for a in articles],
            "total": len(articles),
        }
    finally:
        session.close()


@router.get("/articles/{article_id}")
async def api_get_article(article_id: str):
    """Get article metadata by ID."""
    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        return article.to_dict()
    finally:
        session.close()


@router.post("/articles")
async def api_create_article(
    title: str = Form(...),
    abstract: str = Form(""),
    format: str = Form("typst"),
    categories: str = Form(""),
    keywords: str = Form(""),
    language: str = Form("en"),
    article_file: UploadFile = File(...),
):
    """Submit a new article via file upload (multipart form)."""
    # Validate format
    if format not in ("typst", "markdown"):
        raise HTTPException(status_code=400, detail="Format must be 'typst' or 'markdown'")

    # Save uploaded file to temp location
    suffix = ".typ" if format == "typst" else ".md"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        content = await article_file.read()
        # If the file doesn't have frontmatter, prepend from form fields
        text = content.decode("utf-8")
        if not text.startswith("---"):
            cats = [c.strip() for c in categories.split(",") if c.strip()]
            kws = [k.strip() for k in keywords.split(",") if k.strip()]
            cats_yaml = "\n".join(f"  - {c}" for c in cats) if cats else ""
            kws_yaml = "\n".join(f"  - {k}" for k in kws) if kws else ""
            fm = f"---\ntitle: {title}\nabstract: {abstract}\nlanguage: {language}\n"
            if cats_yaml:
                fm += f"categories:\n{cats_yaml}\n"
            if kws_yaml:
                fm += f"keywords:\n{kws_yaml}\n"
            fm += "---\n\n"
            text = fm + text
        tmp.write(text)
        tmp_path = Path(tmp.name)

    try:
        settings.ensure_dirs()
        result = submit_article(
            source_path=tmp_path,
            database_url=settings.database_url,
            articles_dir=settings.articles_dir,
        )

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)

        return {
            "article_id": result.article_id,
            "title": result.title,
            "commit": result.git_commit_hash,
            "status": "submitted",
        }
    finally:
        # Cleanup temp file
        if tmp_path.exists():
            tmp_path.unlink()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 2: Update page routes to use real database**

Rewrite `peerpedia/web/routes/pages.py`:

```python
"""Web — Route handlers for HTML pages."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from peerpedia.config.settings import settings
from peerpedia_core.storage.db import (
    get_engine, get_session, init_db, list_articles, get_article,
)

router = APIRouter()

templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _get_db_session():
    """Get a database session, ensuring tables exist."""
    engine = get_engine(settings.database_url)
    init_db(engine)
    return get_session(engine)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page — article listing from database."""
    session = _get_db_session()
    try:
        articles = list_articles(session)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "title": "PeerPedia",
                "articles": [a.to_dict() for a in articles],
            },
        )
    finally:
        session.close()


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def view_article(request: Request, article_id: str):
    """View a single article with rendered content."""
    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            return templates.TemplateResponse(
                "article.html",
                {"request": request, "title": "Not Found", "article": None},
                status_code=404,
            )

        article_dict = article.to_dict()

        # Try to load compiled HTML content for display
        content_html = ""
        if article_dict["git_repo_path"]:
            repo = Path(article_dict["git_repo_path"])
            # Look for compiled output
            if article_dict["format"] == "markdown":
                html_file = repo / f"{article_id}.html"
            else:
                # For Typst, try to read the source and render it as plain text
                source_files = list(repo.glob("*.typ"))
                if source_files:
                    content_html = f"<pre>{source_files[0].read_text()}</pre>"

            if article_dict["format"] == "markdown":
                html_candidates = list(repo.glob("*.html"))
                if html_candidates:
                    content_html = html_candidates[0].read_text()

        article_dict["content"] = content_html

        return templates.TemplateResponse(
            "article.html",
            {
                "request": request,
                "title": article_dict["title"],
                "article": article_dict,
            },
        )
    finally:
        session.close()


@router.get("/submit", response_class=HTMLResponse)
async def submit_page(request: Request):
    """Article submission page."""
    return templates.TemplateResponse(
        "submit.html",
        {"request": request, "title": "Submit Article"},
    )


@router.get("/review", response_class=HTMLResponse)
async def review_queue(request: Request):
    """Review queue — list articles pending review."""
    session = _get_db_session()
    try:
        articles = list_articles(session, status="submitted")
        return templates.TemplateResponse(
            "review.html",
            {
                "request": request,
                "title": "Review Queue",
                "articles": [a.to_dict() for a in articles],
            },
        )
    finally:
        session.close()
```

- [ ] **Step 3: Update homepage template to show real article metadata**

Edit `peerpedia/web/templates/index.html` — update the article card to show more fields:

Replace this block:
```html
                <article class="article-card">
                    <h3><a href="/article/{{ article.id }}">{{ article.title }}</a></h3>
                    <p class="meta">
                        {{ article.authors | join(", ") }} · {{ article.created_at }}
                    </p>
                </article>
```

With:
```html
                <article class="article-card">
                    <h3><a href="/article/{{ article.id }}">{{ article.title }}</a></h3>
                    <p class="meta">
                        {{ article.founding_authors | join(", ") if article.founding_authors else "Unknown" }}
                        · {{ article.format }}
                        · <span class="status {{ article.status }}">{{ article.status }}</span>
                        · {{ article.created_at[:10] if article.created_at else "" }}
                    </p>
                    {% if article.abstract %}
                    <p class="abstract">{{ article.abstract[:200] }}{% if article.abstract | length > 200 %}...{% endif %}</p>
                    {% endif %}
                </article>
```

- [ ] **Step 4: Add a minimal CSS file for status badges**

Create `peerpedia/web/static/style.css`:

```css
/* PeerPedia — Minimal Styles */

:root {
    --bg: #fafafa;
    --text: #1a1a1a;
    --muted: #666;
    --accent: #2563eb;
    --border: #e5e5e5;
    --card-bg: #fff;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    max-width: 800px;
    margin: 0 auto;
    padding: 1rem;
}

header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.75rem;
    margin-bottom: 2rem;
}

header h1 { font-size: 1.5rem; }

nav a {
    margin-left: 1rem;
    color: var(--accent);
    text-decoration: none;
}

nav a:hover { text-decoration: underline; }

.article-list h2 { margin-bottom: 1rem; }

.article-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem;
    margin-bottom: 0.75rem;
}

.article-card h3 { margin-bottom: 0.25rem; }
.article-card h3 a { color: var(--text); text-decoration: none; }
.article-card h3 a:hover { color: var(--accent); }

.meta {
    font-size: 0.85rem;
    color: var(--muted);
    margin-bottom: 0.5rem;
}

.abstract {
    font-size: 0.9rem;
    color: var(--muted);
}

.status {
    display: inline-block;
    padding: 0.1em 0.4em;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
}

.status.draft { background: #fef3c7; color: #92400e; }
.status.submitted { background: #dbeafe; color: #1e40af; }
.status.published { background: #d1fae5; color: #065f46; }
.status.rejected { background: #fee2e2; color: #991b1b; }

form {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.5rem;
}

label {
    display: block;
    margin-bottom: 0.75rem;
    font-size: 0.9rem;
}

label input, label select, label textarea {
    display: block;
    width: 100%;
    margin-top: 0.25rem;
    padding: 0.4rem 0.5rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    font-size: 0.95rem;
}

button {
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 0.5rem 1.25rem;
    border-radius: 4px;
    font-size: 0.95rem;
    cursor: pointer;
}

button:hover { opacity: 0.9; }

.empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--muted);
}

.article-view h1 { margin-bottom: 1rem; }

.article-meta {
    display: flex;
    gap: 1rem;
    font-size: 0.85rem;
    color: var(--muted);
    margin-bottom: 1.5rem;
}

.article-abstract {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem;
    margin-bottom: 1.5rem;
}

.article-content {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.5rem;
}

footer {
    text-align: center;
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    font-size: 0.85rem;
    color: var(--muted);
}
```

- [ ] **Step 5: Run all tests**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All 38 tests pass

- [ ] **Step 6: Verify web server boots and shows articles**

Run a quick server check:
```bash
cd /Users/chenqimeng/Projects/peerpedia
source .venv/bin/activate
# Submit a test article first
echo '---
title: Web Test Article
abstract: Testing the web interface.
categories:
  - test
  - web
---

= Web Test Article

== Section 1

This article was submitted via CLI and should appear on the web homepage.
' > /tmp/web_test.typ
peerpedia submit /tmp/web_test.typ
```

Verify the article was stored:
```bash
python -c "
from peerpedia.config.settings import settings
from peerpedia_core.storage.db import get_engine, init_db, get_session, list_articles
engine = get_engine(settings.database_url)
init_db(engine)
session = get_session(engine)
articles = list_articles(session)
print(f'Articles in DB: {len(articles)}')
for a in articles:
    print(f'  - {a.id[:8]}... {a.title} [{a.status}]')
"
```
Expected: At least 1 article listed

- [ ] **Step 7: Commit**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add peerpedia/web/routes/api.py peerpedia/web/routes/pages.py peerpedia/web/templates/index.html peerpedia/web/static/style.css
git commit -m "feat: wire web routes to real database

- API /api/v1/articles returns real articles from SQLite
- API /api/v1/articles/{id} returns article detail
- API POST /api/v1/articles handles file upload with real submission
- Homepage shows articles from database with status badges
- Article detail page loads rendered content
- Review queue shows articles with 'submitted' status
- Added minimal CSS stylesheet with status badges

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: End-to-End Verification

**Files:** None (verification only)

**What:** Run the full test suite, verify CLI works, verify web server starts.

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: 38 passed (13 protocol + 6 reputation + 5 db + 9 compiler + 5 submit)

- [ ] **Step 2: End-to-end CLI workflow test**

```bash
cd /Users/chenqimeng/Projects/peerpedia
source .venv/bin/activate

# Reset test DB
rm -f ~/.peerpedia/db/peerpedia.db

# Init
peerpedia init

# Submit a Typst article
cat > /tmp/e2e_test.typ << 'TYPST'
---
title: End-to-End Test Article
abstract: Verifying the complete submission pipeline works.
categories:
  - physics
  - test
keywords:
  - e2e
  - verification
language: en
---

= End-to-End Test Article

== Introduction

This article tests the complete PeerPedia submission pipeline.

== Results

The pipeline should handle:
- Frontmatter parsing
- Git repository initialization
- Database storage
- CID computation
- Web display

All systems nominal.
TYPST

peerpedia submit /tmp/e2e_test.typ --author "Test User" --email "test@peerpedia.local"

# Verify via Python
python -c "
from peerpedia.config.settings import settings
from peerpedia_core.storage.db import get_engine, init_db, get_session, list_articles
engine = get_engine(settings.database_url)
init_db(engine)
session = get_session(engine)
articles = list_articles(session)
print(f'\\n✓ {len(articles)} article(s) in database:')
for a in articles:
    print(f'  ID: {a.id}')
    print(f'  Title: {a.title}')
    print(f'  Status: {a.status}')
    print(f'  Categories: {a.categories}')
    print(f'  Format: {a.format}')
    print(f'  Git repo: {a.git_repo_path}')
    print(f'  CID: {a.cid}')
    print()
"
```

Expected: Article appears in DB with all metadata

- [ ] **Step 3: Verify git repo was created**

```bash
# Check the git repo for the submitted article
ARTICLES_DIR=~/.peerpedia/articles
ls -la $ARTICLES_DIR/
# Should show a directory with the article ID
ARTICLE_DIR=$(ls -dt $ARTICLES_DIR/*/ | head -1)
echo "Article repo: $ARTICLE_DIR"
cd "$ARTICLE_DIR" && git log --oneline
# Should show at least one commit
```

- [ ] **Step 4: Verify all tests still pass**

Run: `cd /Users/chenqimeng/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All 38 tests pass

- [ ] **Step 5: Final commit for Phase 3 M1**

```bash
cd /Users/chenqimeng/Projects/peerpedia
git add -A
git commit -m "feat: Phase 3 M1 complete — article submission loop

End-to-end article submission pipeline:
- SQLAlchemy models + CRUD for article metadata (SQLite)
- Compiler backends: Typst (subprocess) + Markdown (HTML/KaTeX)
- Frontmatter parsing (minimal YAML subset)
- submit_article() orchestrator: parse → git init → commit → compile → DB store → CID
- CLI: peerpedia init creates DB tables, peerpedia submit does real submission
- Web: real article listing, detail pages, file upload submission
- 38 tests, 0 failures

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Summary

| Task | What | Files | Tests |
|---|---|---|---|
| 1 | SQLAlchemy DB layer | `db.py` (new) | 5 |
| 2 | Compiler backends | `compiler.py` (new) | 9 |
| 3 | Submission orchestrator | `submit.py` (new) | 5 |
| 4 | Wire CLI commands | `main.py` (edit) | — |
| 5 | Wire Web routes | `api.py`, `pages.py`, templates (edit) | — |
| 6 | End-to-end verification | — | — |

**After M1:** `peerpedia init` + `peerpedia submit` + `peerpedia serve` form a working pipeline:
1. Submit Typst/Markdown from CLI → git repo created, metadata in SQLite
2. Submit from Web UI → file upload with form metadata
3. Homepage shows real articles from database
4. Article detail page shows metadata and content
