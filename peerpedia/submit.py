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
    8. Store metadata in SQLite
    9. Compute CID
    10. Return SubmissionResult
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from peerpedia_core.protocol.addressing import compute_article_cid
from peerpedia_core.storage.compiler import (
    detect_format,
    extract_frontmatter,
)
from peerpedia_core.storage.db import (
    create_article,
    get_article,
    get_engine,
    get_session,
    init_db,
)
from peerpedia_core.storage.git_backend import (
    commit_article,
    init_article_repo,
)
from peerpedia_core.workflow.citations import extract_references


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


def _setup_repo_and_commit(
    source_path: Path,
    article_id: str,
    articles_dir: Path,
    title: str,
    author_name: str,
    author_email: str,
) -> tuple[Path, str] | SubmissionResult:
    """Initialize git repo, copy source files, and make initial commit.

    Returns (repo_path, commit_hash) on success, or SubmissionResult on failure.
    """
    try:
        repo_path = init_article_repo(article_id, base_dir=articles_dir)
    except Exception as e:
        return SubmissionResult(success=False, error=f"Git init failed: {e}")

    try:
        dest_file = repo_path / source_path.name
        shutil.copy2(source_path, dest_file)
        for sibling in source_path.parent.iterdir():
            if sibling == source_path:
                continue
            if sibling.is_file():
                dest_sibling = repo_path / sibling.name
                if not dest_sibling.exists():
                    shutil.copy2(sibling, dest_sibling)
    except Exception as e:
        shutil.rmtree(repo_path, ignore_errors=True)
        return SubmissionResult(success=False, error=f"文件复制失败: {e}")

    try:
        commit_hash = commit_article(
            repo_path,
            message=f"Submit: {title}",
            author_name=author_name,
            author_email=author_email,
        )
    except Exception as e:
        shutil.rmtree(repo_path, ignore_errors=True)
        return SubmissionResult(success=False, error=f"Git 提交失败: {e}")

    return repo_path, commit_hash


def _store_and_scan_references(
    session,
    article,
    source_path: Path,
) -> None:
    """Auto-populate article.references from citations found in source."""
    try:
        source_text = source_path.read_text()
        ref_ids = extract_references(source_text)
        if ref_ids:
            ref_dicts = []
            for rid in ref_ids:
                target = get_article(session, rid)
                ref_dicts.append({
                    "article_id": rid,
                    "title": target.title if target else rid[:8] + "...",
                })
            article.references = ref_dicts
    except Exception:
        pass  # Reference scanning is best-effort


def submit_article(
    source_path: Path,
    *,
    database_url: str,
    articles_dir: Path,
    author_name: str = "peerpedia",
    author_email: str = "peerpedia@localhost",
) -> SubmissionResult:
    """Submit an article from a Typst or Markdown source file."""
    # 1. Read source
    try:
        source_content = source_path.read_text()
    except Exception as e:
        return SubmissionResult(success=False, error=f"Cannot read file: {e}")

    # 2. Detect format + extract metadata
    fmt = detect_format(source_path)
    frontmatter = extract_frontmatter(source_content)

    title = frontmatter.get("title", source_path.stem)
    abstract = frontmatter.get("abstract", "")
    abstract_zh = frontmatter.get("abstract_zh")
    categories = frontmatter.get("categories", [])
    keywords = frontmatter.get("keywords", [])
    language = frontmatter.get("language", "en")
    about_person = frontmatter.get("about_person")
    article_id = str(uuid.uuid4())

    # 3. Git: init repo, copy files, commit
    result = _setup_repo_and_commit(
        source_path, article_id, articles_dir, title,
        author_name, author_email,
    )
    if isinstance(result, SubmissionResult):
        return result
    repo_path, commit_hash = result

    # 4. Store in DB + scan references
    session = None
    try:
        engine = get_engine(database_url)
        init_db(engine)
        session = get_session(engine)
        article = create_article(
            session, id=article_id, title=title,
            founding_authors=[author_name], abstract=abstract,
            abstract_zh=abstract_zh, categories=categories,
            keywords=keywords, language=language, format=fmt,
            about_person=about_person, git_repo_path=str(repo_path),
        )
        _store_and_scan_references(session, article, source_path)
        session.commit()
    except Exception as e:
        return SubmissionResult(success=False, error=f"Database error: {e}")
    finally:
        if session is not None:
            session.close()

    # 5. Compute CID (best-effort)
    try:
        dest_file = repo_path / source_path.name
        cid = compute_article_cid(
            typst_source=dest_file.read_text(),
            metadata={"title": title, "id": article_id, "version": "v0.1"},
            git_commit_hash=commit_hash,
        )
    except Exception:
        cid = None

    return SubmissionResult(
        success=True, article_id=article_id, title=title,
        abstract=abstract, categories=categories, format=fmt,
        git_repo_path=str(repo_path), git_commit_hash=commit_hash,
        cid=cid,
    )
