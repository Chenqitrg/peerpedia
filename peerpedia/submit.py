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

from peerpedia_core.storage.compiler import (
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
    try:
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
    except Exception as e:
        # Clean up repo if file copy fails
        shutil.rmtree(repo_path, ignore_errors=True)
        return SubmissionResult(success=False, error=f"文件复制失败: {e}")

    # 7. Git commit
    try:
        commit_hash = commit_article(
            repo_path,
            message=f"Submit: {title}",
            author_name=author_name,
            author_email=author_email,
        )
    except Exception as e:
        # Clean up repo if commit fails
        shutil.rmtree(repo_path, ignore_errors=True)
        return SubmissionResult(success=False, error=f"Git 提交失败: {e}")

    # 8. Store metadata in SQLite
    session = None
    try:
        engine = get_engine(database_url)
        init_db(engine)
        session = get_session(engine)

        article = create_article(
            session,
            id=article_id,
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
        if session is not None:
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
        compile_output=None,
        cid=cid,
    )
