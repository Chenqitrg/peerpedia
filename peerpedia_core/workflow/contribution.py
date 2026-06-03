"""Layer 1: Contribution tracking engine.

Computes contribution weights from git history using git blame and
commit metadata. Versioned via PIP — weight formulas can be upgraded.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from peerpedia_core.reputation.v1 import ReputationParams

# ── Change type weight computation ─────────────────────────────────────────────

def compute_change_type_weight(change_type: str) -> int:
    """Compute contribution weight for a change type.

    Returns integer weight (scaled by 100 to avoid floating point in DB).
    """
    params = ReputationParams()
    weight_float = params.change_type_weights.get(change_type, 2.0)
    return int(weight_float * 100)


# ── Contribution breakdown ─────────────────────────────────────────────────────

def compute_contribution_breakdown(
    records: list[dict],
) -> dict[str, float]:
    """Compute contribution percentages from weighted records.

    Args:
        records: List of dicts with at least {'user_id': str, 'contribution_weight': int}

    Returns:
        Dict mapping user_id -> percentage (0-100), summing to 100.
    """
    if not records:
        return {}

    user_weights: dict[str, int] = {}
    for r in records:
        uid = r["user_id"]
        w = r.get("contribution_weight", 0)
        user_weights[uid] = user_weights.get(uid, 0) + w

    total = sum(user_weights.values())
    if total == 0:
        return {uid: 0.0 for uid in user_weights}

    return {
        uid: round((w / total) * 100, 2)
        for uid, w in user_weights.items()
    }


# ── Contribution timeline ──────────────────────────────────────────────────────

def compute_contribution_timeline(
    records: list[dict],
) -> list[dict]:
    """Build a contribution timeline sorted by timestamp (oldest first).

    Args:
        records: List of dicts with timestamp, user_id, contribution_weight, etc.

    Returns:
        Sorted list of contribution entries.
    """
    def sort_key(r: dict) -> str:
        ts = r.get("timestamp")
        if isinstance(ts, datetime):
            return ts.isoformat()
        return str(ts)

    return sorted(records, key=sort_key)


# ── Git blame -> Contribution records ───────────────────────────────────────────

def build_contribution_records_from_git(
    repo_path: Path,
    article_id: str,
    change_type: str = "content",
) -> list[dict]:
    """Build contribution records from a git repository's commit history.

    Uses git log to extract per-commit contribution data.

    Args:
        repo_path: Path to the git repository.
        article_id: The article UUID.
        change_type: Default change type for all commits.

    Returns:
        List of contribution record dicts ready for DB insertion.
    """
    import git

    repo = git.Repo(repo_path)
    records = []

    for commit in repo.iter_commits(reverse=True):
        author_name = str(commit.author)

        try:
            if commit.parents:
                diff = commit.parents[0].diff(commit, create_patch=True)
            else:
                # Initial commit — diff against the null tree
                diff = commit.diff(git.NULL_TREE, create_patch=True)
        except Exception:
            diff = []

        lines_added = 0
        lines_deleted = 0
        files_changed = []

        for d in diff:
            if d.a_path:
                files_changed.append(d.a_path)
            if d.diff:
                diff_text = d.diff.decode("utf-8", errors="replace") if isinstance(d.diff, bytes) else str(d.diff)
                for line in diff_text.split("\n"):
                    if line.startswith("+") and not line.startswith("+++"):
                        lines_added += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        lines_deleted += 1

        weight = compute_change_type_weight(change_type)

        records.append({
            "article_id": article_id,
            "user_id": author_name,
            "timestamp": commit.committed_datetime.replace(tzinfo=timezone.utc),
            "commit_hash": commit.hexsha,
            "commit_message": commit.message.strip(),
            "lines_added": lines_added,
            "lines_deleted": lines_deleted,
            "files_changed": files_changed,
            "change_type": change_type,
            "contribution_weight": weight,
        })

    return records
