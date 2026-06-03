"""Layer 0: Git storage backend.

Every article is an independent git repository stored under
~/.peerpedia/articles/<article-id>/.

This is the immutable storage format — the git object format IS the protocol.
"""

from pathlib import Path
from typing import Optional


DEFAULT_ARTICLES_DIR = Path.home() / ".peerpedia" / "articles"


def init_article_repo(
    article_id: str,
    base_dir: Optional[Path] = None,
) -> Path:
    """Initialize a new git repository for an article.

    Returns the path to the repo.
    """
    import git

    base = base_dir or DEFAULT_ARTICLES_DIR
    repo_path = base / article_id
    repo_path.mkdir(parents=True, exist_ok=True)

    repo = git.Repo.init(repo_path)
    return repo_path


def commit_article(
    repo_path: Path,
    message: str,
    author_name: str,
    author_email: str,
) -> str:
    """Stage all changes and commit. Returns the commit hash."""
    import git

    repo = git.Repo(repo_path)
    repo.git.add(A=True)

    # Only commit if there are changes
    if not repo.is_dirty(untracked_files=True):
        return repo.head.commit.hexsha  # type: ignore[union-attr]

    commit = repo.index.commit(
        message,
        author=git.Actor(author_name, author_email),
        committer=git.Actor(author_name, author_email),
    )
    return commit.hexsha


def get_commit_history(
    repo_path: Path,
    max_count: int = 50,
) -> list[dict]:
    """Get commit history for an article."""
    import git

    repo = git.Repo(repo_path)
    commits = []
    for c in repo.iter_commits(max_count=max_count):
        commits.append({
            "hash": c.hexsha,
            "message": c.message.strip(),
            "author": str(c.author),
            "timestamp": c.committed_datetime.isoformat(),
            "stats": {
                "total": c.stats.total,
                "files": list(c.stats.files.keys()),
            } if c.stats.total else {},
        })
    return commits


def get_blame(repo_path: Path, file_path: str) -> list[dict]:
    """Get git blame for a file — maps lines to authors."""
    import git  # type: ignore[import-untyped]

    repo = git.Repo(repo_path)
    blames: list[dict] = []
    for entry in repo.blame_incremental("HEAD", file_path):  # type: ignore[attr-defined]
        blames.append({
            "commit": entry.commit.hexsha[:8],  # type: ignore[attr-defined]
            "author": str(entry.commit.author),  # type: ignore[attr-defined]
            "lines": list(range(entry.linenos_start, entry.linenos_start + entry.linenos_count)),  # type: ignore[attr-defined]
        })
    return blames
