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


def get_diff(repo_path: Path, commit_hash: str) -> dict:
    """Get the diff for a specific commit.

    Returns a dict with:
        - commit_hash: the commit's full hash
        - message: commit message
        - author: author name
        - timestamp: ISO datetime
        - files: list of file paths changed
        - diff_text: unified diff text (for diff2html rendering)
        - parent_hash: parent commit hash (or None for initial commit)
    """
    import git

    repo = git.Repo(repo_path)
    commit = repo.commit(commit_hash)

    parent_hash = commit.parents[0].hexsha if commit.parents else None

    # Get diff between parent and this commit
    if commit.parents:
        diff_index = commit.parents[0].diff(commit, create_patch=True)
    else:
        # Initial commit: diff against empty tree
        diff_index = commit.diff(git.NULL_TREE, create_patch=True)

    files_changed = []
    diff_parts = []

    for d in diff_index:
        if d.a_path:
            files_changed.append(d.a_path)
        if d.diff:
            diff_text = d.diff.decode("utf-8", errors="replace") if isinstance(d.diff, bytes) else str(d.diff)
            diff_parts.append(diff_text)

    unified_diff = "\n".join(diff_parts)

    return {
        "commit_hash": commit.hexsha,
        "message": commit.message.strip(),
        "author": str(commit.author),
        "timestamp": commit.committed_datetime.isoformat(),
        "files": files_changed,
        "diff_text": unified_diff,
        "parent_hash": parent_hash,
        "stats": {
            "total": commit.stats.total.get("lines", 0) if commit.stats.total else 0,
            "files": list(commit.stats.files.keys()) if commit.stats.total else [],
        } if commit.stats.total else {},
    }


def get_diff_between(
    repo_path: Path, hash1: str, hash2: str
) -> dict:
    """Get the diff between two arbitrary commits.

    hash1 is the "old" commit, hash2 is the "new" commit.
    Returns the same shape as get_diff().
    """
    import git

    repo = git.Repo(repo_path)
    c1 = repo.commit(hash1)
    c2 = repo.commit(hash2)

    diff_index = c1.diff(c2, create_patch=True)

    files_changed = []
    diff_parts = []

    for d in diff_index:
        if d.a_path:
            files_changed.append(d.a_path)
        if d.diff:
            diff_text = d.diff.decode("utf-8", errors="replace") if isinstance(d.diff, bytes) else str(d.diff)
            diff_parts.append(diff_text)

    unified_diff = "\n".join(diff_parts)

    return {
        "commit_hash": c2.hexsha,
        "message": c2.message.strip(),
        "author": str(c2.author),
        "timestamp": c2.committed_datetime.isoformat(),
        "files": files_changed,
        "diff_text": unified_diff,
        "parent_hash": c1.hexsha,
        "stats": {},
    }
