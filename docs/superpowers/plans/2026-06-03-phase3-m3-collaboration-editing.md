# Phase 3 M3: 协作 + 开放编辑 + 贡献追踪 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现审稿期协作（Mode A — 审稿人→合作者）和出版后开放编辑（Mode B — EditProposal 流程），以及 git blame 驱动的贡献时间线追踪。

**Architecture:** 新增 `collaboration.py`（审稿期协作编排）、`edit_proposal.py`（开放编辑编排）、`contribution.py`（贡献度计算）三个工作流模块。扩展状态机（published → edit_proposed → published）和数据库（ContributionRecord + EditProposal ORM 模型）。实现 CLI 命令 `collaborate` 和 `propose-edit`，以及对应的 Web API。

**Tech Stack:** Python 3.14 + SQLAlchemy + GitPython + Pydantic v2 + FastAPI + Click

---

## File Structure

```
New files:
  peerpedia_core/workflow/collaboration.py   — 审稿期协作编排器 (Mode A)
  peerpedia_core/workflow/contribution.py    — 贡献度计算引擎 + ContributionRecord CRUD
  peerpedia_core/workflow/edit_proposal.py   — 开放编辑编排器 (Mode B)
  tests/test_collaboration.py                — 协作测试
  tests/test_edit_proposal.py                — 编辑提案测试
  tests/test_contribution.py                 — 贡献追踪测试

Modified files:
  peerpedia_core/workflow/state_machine.py   — 添加 edit_proposed 状态和转换
  peerpedia_core/storage/db.py               — 添加 ContributionRecord + EditProposal ORM + CRUD
  peerpedia_core/workflow/review.py          — 添加 accept_collaboration / reject_collaboration
  peerpedia/cli/main.py                      — 实现 collaborate + propose-edit 命令
  peerpedia/web/routes/api.py                — 添加协作 + 编辑提案 API 端点
  peerpedia/web/routes/pages.py              — 添加 EditProposal 列表页面
```

---

## 设计决策

### M3 范围内实现：
- ✅ 状态机扩展：published → edit_proposed → published（带审核后 merge）
- ✅ ContributionRecord ORM + CRUD（commit 元数据 + 权重计算）
- ✅ edit_proposal ORM + CRUD（提案创建/审核/合并生命周期）
- ✅ Mode A：审稿期协作（accept_collaboration 将审稿人转为 co-author，创建协作分支）
- ✅ Mode B：开放编辑提案（create/edit/review/merge 完整流程）
- ✅ CLI `collaborate`：接受协作申请
- ✅ CLI `propose-edit`：创建修改提案
- ✅ 贡献时间线计算（git blame → 贡献占比）
- ✅ Web API：协作接受 + EditProposal CRUD + 贡献时间线

### M3 范围外（M4/M5）：
- ❌ 作者拒绝协作（只实现 accept，reject 留到需要时）
- ❌ 社区投票机制（major 修改的投票逻辑留到 M4）
- ❌ 原作者一年不活跃的否决权降级
- ❌ 通知系统（邮件/应用内通知）
- ❌ 积分消耗（发起 major 提案消耗积分）

---

### Task 1: ContributionRecord + EditProposal 数据库模型

**Files:**
- Modify: `peerpedia_core/storage/db.py`
- Create: `tests/test_contribution.py` (部分)

- [ ] **Step 1: 在 db.py 中添加 ContributionRecord 和 EditProposal ORM 模型**

在 `peerpedia_core/storage/db.py` 中，在 Review 模型后面添加以下模型：

```python
# ── ORM Model: ContributionRecord ──────────────────────────────────────────────

class ContributionRecord(Base):
    """Per-commit contribution record for git blame timeline."""

    __tablename__ = "contribution_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    user_id = Column(String(100), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    commit_hash = Column(String(40), nullable=False)
    commit_message = Column(Text, nullable=False, default="")
    lines_added = Column(Integer, nullable=False, default=0)
    lines_deleted = Column(Integer, nullable=False, default=0)
    files_changed = Column(JSONList, nullable=False, default=list)
    change_type = Column(String(30), nullable=False, default="content")
    # "new_theorem" | "proof_fix" | "content" | "prose" | "format"
    contribution_weight = Column(Integer, nullable=False, default=0)
    # Scaled integer: weight * 100 to avoid floating point in DB

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "commit_hash": self.commit_hash,
            "commit_message": self.commit_message,
            "lines_added": self.lines_added,
            "lines_deleted": self.lines_deleted,
            "files_changed": self.files_changed,
            "change_type": self.change_type,
            "contribution_weight": self.contribution_weight,
        }


# ── ORM Model: EditProposal ───────────────────────────────────────────────────

class EditProposal(Base):
    """Post-publication edit proposal."""

    __tablename__ = "edit_proposals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    article_id = Column(String(36), ForeignKey("articles.id"), nullable=False, index=True)
    proposer_id = Column(String(100), nullable=False)
    proposal_type = Column(String(20), nullable=False)
    # "minor" | "medium" | "major"
    description = Column(Text, nullable=False, default="")
    git_branch = Column(String(200), nullable=False, default="")
    diff_stat = Column(Text, nullable=False, default="")
    # Human-readable diff summary
    status = Column(String(20), nullable=False, default="pending")
    # "pending" | "approved" | "rejected" | "auto_approved"
    reviewer_id = Column(String(100), nullable=True)
    # Who reviewed (original author or community member)
    review_comment = Column(Text, nullable=False, default="")
    points_stake = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "proposer_id": self.proposer_id,
            "proposal_type": self.proposal_type,
            "description": self.description,
            "git_branch": self.git_branch,
            "diff_stat": self.diff_stat,
            "status": self.status,
            "reviewer_id": self.reviewer_id,
            "review_comment": self.review_comment,
            "points_stake": self.points_stake,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
```

- [ ] **Step 2: 添加 ContributionRecord CRUD 函数**

在 db.py 末尾添加：

```python
# ── ContributionRecord CRUD ────────────────────────────────────────────────────

def create_contribution_record(
    session: Session,
    *,
    article_id: str,
    user_id: str,
    commit_hash: str,
    commit_message: str = "",
    lines_added: int = 0,
    lines_deleted: int = 0,
    files_changed: Optional[list[str]] = None,
    change_type: str = "content",
    contribution_weight: int = 0,
) -> ContributionRecord:
    """Create a contribution record."""
    record = ContributionRecord(
        id=str(uuid.uuid4()),
        article_id=article_id,
        user_id=user_id,
        commit_hash=commit_hash,
        commit_message=commit_message,
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        files_changed=files_changed or [],
        change_type=change_type,
        contribution_weight=contribution_weight,
    )
    session.add(record)
    return record


def get_contribution_records(
    session: Session,
    article_id: str,
) -> list[ContributionRecord]:
    """Get all contribution records for an article, oldest first."""
    return (
        session.query(ContributionRecord)
        .filter(ContributionRecord.article_id == article_id)
        .order_by(ContributionRecord.timestamp.asc())
        .all()
    )


def get_user_contribution_total(
    session: Session,
    article_id: str,
    user_id: str,
) -> int:
    """Get total contribution weight for a user on an article."""
    result = (
        session.query(ContributionRecord)
        .filter(
            ContributionRecord.article_id == article_id,
            ContributionRecord.user_id == user_id,
        )
        .all()
    )
    return sum(r.contribution_weight for r in result)
```

- [ ] **Step 3: 添加 EditProposal CRUD 函数**

在 db.py 末尾继续添加：

```python
# ── EditProposal CRUD ──────────────────────────────────────────────────────────

def create_edit_proposal(
    session: Session,
    *,
    article_id: str,
    proposer_id: str,
    proposal_type: str,
    description: str = "",
    git_branch: str = "",
    diff_stat: str = "",
    points_stake: int = 0,
) -> EditProposal:
    """Create an edit proposal record."""
    proposal = EditProposal(
        id=str(uuid.uuid4()),
        article_id=article_id,
        proposer_id=proposer_id,
        proposal_type=proposal_type,
        description=description,
        git_branch=git_branch,
        diff_stat=diff_stat,
        status="pending",
        points_stake=points_stake,
    )
    session.add(proposal)
    return proposal


def get_edit_proposal(session: Session, proposal_id: str) -> Optional[EditProposal]:
    """Get an edit proposal by ID."""
    return session.query(EditProposal).filter(EditProposal.id == proposal_id).first()


def get_edit_proposals_for_article(
    session: Session,
    article_id: str,
    *,
    status: Optional[str] = None,
) -> list[EditProposal]:
    """Get all edit proposals for an article, newest first."""
    q = (
        session.query(EditProposal)
        .filter(EditProposal.article_id == article_id)
        .order_by(EditProposal.created_at.desc())
    )
    if status:
        q = q.filter(EditProposal.status == status)
    return q.all()


def update_edit_proposal_status(
    session: Session,
    proposal_id: str,
    new_status: str,
    *,
    reviewer_id: Optional[str] = None,
    review_comment: str = "",
) -> Optional[EditProposal]:
    """Update an edit proposal's status."""
    proposal = get_edit_proposal(session, proposal_id)
    if proposal:
        proposal.status = new_status
        proposal.resolved_at = datetime.now(timezone.utc)
        if reviewer_id:
            proposal.reviewer_id = reviewer_id
        if review_comment:
            proposal.review_comment = review_comment
    return proposal


def update_article_founding_authors(
    session: Session,
    article_id: str,
    new_author_id: str,
) -> Optional[Article]:
    """Add a new author to the article's founding_authors list (co-author join)."""
    article = get_article(session, article_id)
    if article:
        authors = list(article.founding_authors)
        if new_author_id not in authors:
            authors.append(new_author_id)
            article.founding_authors = authors
            article.updated_at = datetime.now(timezone.utc)
    return article
```

- [ ] **Step 4: 添加 `update_article_version` 到 CRUD**

```python
def update_article_version(
    session: Session,
    article_id: str,
    new_version: str,
) -> Optional[Article]:
    """Increment an article's version string."""
    article = get_article(session, article_id)
    if article:
        article.version = new_version
        article.updated_at = datetime.now(timezone.utc)
    return article
```

- [ ] **Step 5: 确保 CRUD 函数在 `__init__.py` 中导出**

Read `peerpedia_core/storage/__init__.py` 确认导出。如果 `__init__.py` 只做 re-export，更新它包含新增函数。

- [ ] **Step 6: 运行现有测试确认未破坏任何功能**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -q
Expected: 87 passed (新表创建但不影响现有测试)
```

- [ ] **Step 7: Commit**

```bash
git add peerpedia_core/storage/db.py peerpedia_core/storage/__init__.py
git commit -m "feat(db): add ContributionRecord and EditProposal ORM models with CRUD"
```

---

### Task 2: 状态机扩展 — edit_proposed 状态

**Files:**
- Modify: `peerpedia_core/workflow/state_machine.py`
- Modify: `tests/test_state_machine.py`

- [ ] **Step 1: 更新 state_machine.py — 添加 edit_proposed 状态和转换**

在 `ArticleStatus` 类中添加：
```python
    EDIT_PROPOSED = "edit_proposed"
```

更新 `VALID_TRANSITIONS`：
```python
VALID_TRANSITIONS: dict[str, set[str]] = {
    ArticleStatus.DRAFT: {ArticleStatus.SUBMITTED, ArticleStatus.IN_REVIEW},
    ArticleStatus.SUBMITTED: {ArticleStatus.IN_REVIEW},
    ArticleStatus.IN_REVIEW: {
        ArticleStatus.ACCEPTED,
        ArticleStatus.REJECTED,
        ArticleStatus.REVISIONS_REQUESTED,
    },
    ArticleStatus.REVISIONS_REQUESTED: {ArticleStatus.SUBMITTED},
    ArticleStatus.REJECTED: {ArticleStatus.SUBMITTED},
    ArticleStatus.ACCEPTED: {ArticleStatus.PUBLISHED},
    ArticleStatus.PUBLISHED: {ArticleStatus.EDIT_PROPOSED},     # NEW
    ArticleStatus.EDIT_PROPOSED: {ArticleStatus.PUBLISHED},     # NEW — merge back
}
```

- [ ] **Step 2: 更新 test_state_machine.py — 添加 edit_proposed 转换测试**

在 `tests/test_state_machine.py` 的测试类中添加：

```python
    def test_can_transition_published_to_edit_proposed(self):
        """Published articles can receive edit proposals."""
        assert can_transition(ArticleStatus.PUBLISHED, ArticleStatus.EDIT_PROPOSED) is True

    def test_can_transition_edit_proposed_to_published(self):
        """Edit proposals merge back to published."""
        assert can_transition(ArticleStatus.EDIT_PROPOSED, ArticleStatus.PUBLISHED) is True

    def test_cannot_transition_edit_proposed_to_draft(self):
        """Edit proposals cannot go back to draft."""
        assert can_transition(ArticleStatus.EDIT_PROPOSED, ArticleStatus.DRAFT) is False

    def test_cannot_transition_edit_proposed_to_submitted(self):
        """Edit proposals cannot go back to submitted."""
        assert can_transition(ArticleStatus.EDIT_PROPOSED, ArticleStatus.SUBMITTED) is False

    def test_state_machine_full_edit_proposal_cycle(self):
        """Full cycle: published → edit_proposed → published."""
        sm = StateMachine(article_id="test-1", current_status=ArticleStatus.PUBLISHED)
        assert sm.can_apply(ArticleStatus.EDIT_PROPOSED) is True

        sm.apply(ArticleStatus.EDIT_PROPOSED)
        assert sm.current_status == ArticleStatus.EDIT_PROPOSED

        assert sm.can_apply(ArticleStatus.PUBLISHED) is True
        sm.apply(ArticleStatus.PUBLISHED)
        assert sm.current_status == ArticleStatus.PUBLISHED

        # Verify history
        assert len(sm.history) == 2
        assert sm.history[0] == (ArticleStatus.PUBLISHED, ArticleStatus.EDIT_PROPOSED)
        assert sm.history[1] == (ArticleStatus.EDIT_PROPOSED, ArticleStatus.PUBLISHED)

    def test_cannot_transition_draft_to_edit_proposed(self):
        """Only published articles can get edit proposals."""
        assert can_transition(ArticleStatus.DRAFT, ArticleStatus.EDIT_PROPOSED) is False
```

- [ ] **Step 3: 运行测试验证状态机**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_state_machine.py -v
Expected: all tests pass (existing 19 + new 5 = 24)
```

- [ ] **Step 4: 同步更新 protocol/messages.py 中的 ArticleStatus 枚举**

在 `peerpedia_core/protocol/messages.py` 中，在 `ArticleStatus` 枚举添加：
```python
    EDIT_PROPOSED = "edit_proposed"
```

- [ ] **Step 5: Commit**

```bash
git add peerpedia_core/workflow/state_machine.py tests/test_state_machine.py peerpedia_core/protocol/messages.py
git commit -m "feat(state-machine): add edit_proposed state with published ↔ edit_proposed transitions"
```

---

### Task 3: 贡献度计算引擎

**Files:**
- Create: `peerpedia_core/workflow/contribution.py`
- Create: `tests/test_contribution.py`

- [ ] **Step 1: 编写失败测试 — test_contribution.py**

```python
"""Tests for contribution tracking and git blame computation."""
import pytest
import tempfile
from pathlib import Path

from peerpedia_core.workflow.contribution import (
    compute_change_type_weight,
    compute_contribution_breakdown,
    compute_contribution_timeline,
    build_contribution_records_from_git,
)
from peerpedia_core.storage.compiler import ChangeType


class TestChangeTypeWeight:
    """Change type weight computation."""

    def test_new_theorem_weight(self):
        assert compute_change_type_weight("new_theorem") == 500  # 5.0 × 100

    def test_proof_fix_weight(self):
        assert compute_change_type_weight("proof_fix") == 400  # 4.0 × 100

    def test_content_weight(self):
        assert compute_change_type_weight("content") == 200  # 2.0 × 100

    def test_prose_weight(self):
        assert compute_change_type_weight("prose") == 100  # 1.0 × 100

    def test_format_weight(self):
        assert compute_change_type_weight("format") == 30  # 0.3 × 100

    def test_unknown_type_defaults_to_content(self):
        assert compute_change_type_weight("unknown") == 200


class TestContributionBreakdown:
    """Contribution percentage computation."""

    def test_single_contributor(self):
        records = [
            {"user_id": "alice", "contribution_weight": 500},
        ]
        breakdown = compute_contribution_breakdown(records)
        assert breakdown["alice"] == pytest.approx(100.0)

    def test_two_contributors(self):
        records = [
            {"user_id": "alice", "contribution_weight": 500},
            {"user_id": "bob", "contribution_weight": 500},
        ]
        breakdown = compute_contribution_breakdown(records)
        assert breakdown["alice"] == pytest.approx(50.0)
        assert breakdown["bob"] == pytest.approx(50.0)

    def test_uneven_contributors(self):
        records = [
            {"user_id": "alice", "contribution_weight": 700},
            {"user_id": "bob", "contribution_weight": 300},
        ]
        breakdown = compute_contribution_breakdown(records)
        assert breakdown["alice"] == pytest.approx(70.0)
        assert breakdown["bob"] == pytest.approx(30.0)

    def test_empty_records(self):
        breakdown = compute_contribution_breakdown([])
        assert breakdown == {}

    def test_weights_sum_to_100(self):
        records = [
            {"user_id": "a", "contribution_weight": 123},
            {"user_id": "b", "contribution_weight": 456},
            {"user_id": "c", "contribution_weight": 789},
        ]
        breakdown = compute_contribution_breakdown(records)
        total = sum(breakdown.values())
        assert total == pytest.approx(100.0)


class TestContributionTimeline:
    """Contribution timeline building."""

    def test_timeline_sorts_by_timestamp(self):
        from datetime import datetime, timezone, timedelta
        records = [
            {"user_id": "alice", "timestamp": datetime(2025, 6, 1, tzinfo=timezone.utc), "contribution_weight": 100, "commit_hash": "ccc", "commit_message": "third"},
            {"user_id": "bob", "timestamp": datetime(2025, 3, 1, tzinfo=timezone.utc), "contribution_weight": 200, "commit_message": "first", "commit_hash": "aaa"},
            {"user_id": "alice", "timestamp": datetime(2025, 4, 1, tzinfo=timezone.utc), "contribution_weight": 150, "commit_message": "second", "commit_hash": "bbb"},
        ]
        timeline = compute_contribution_timeline(records)
        assert len(timeline) == 3
        # Should be sorted oldest first
        assert timeline[0]["commit_hash"] == "aaa"
        assert timeline[1]["commit_hash"] == "bbb"
        assert timeline[2]["commit_hash"] == "ccc"


class TestBuildContributionFromGit:
    """Building contribution records from git repo."""

    def test_build_records_from_git_repo(self):
        """Build records from a real git repo created by git_backend."""
        import uuid
        from peerpedia_core.storage.git_backend import init_article_repo, commit_article

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            article_id = str(uuid.uuid4())
            repo_path = init_article_repo(article_id, base_dir=base)

            # Write a source file
            source = repo_path / "main.typ"
            source.write_text("= Introduction\n\nSome content here.\n")
            commit_article(repo_path, "Initial draft", "alice", "alice@test.com")

            # Second commit
            source.write_text("= Introduction\n\nSome content here.\n\n== Methods\n\nMore content.\n")
            commit_article(repo_path, "Add methods section", "bob", "bob@test.com")

            records = build_contribution_records_from_git(
                repo_path=repo_path,
                article_id=article_id,
                change_type="content",
            )

            assert len(records) == 2
            # First commit by alice
            assert records[0]["user_id"] == "alice"
            assert records[0]["lines_added"] > 0
            assert records[0]["commit_message"] == "Initial draft"
            # Second commit by bob
            assert records[1]["user_id"] == "bob"
            assert records[1]["lines_added"] > 0
            assert records[1]["commit_message"] == "Add methods section"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_contribution.py -v
Expected: FAIL — Module not found / functions not defined
```

- [ ] **Step 3: 实现 contribution.py**

```python
"""Layer 1: Contribution tracking engine.

Computes contribution weights from git history using git blame and
commit metadata. Versioned via PIP — weight formulas can be upgraded.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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


# ── Git blame → Contribution records ───────────────────────────────────────────

def build_contribution_records_from_git(
    repo_path: Path,
    article_id: str,
    change_type: str = "content",
) -> list[dict]:
    """Build contribution records from a git repository's commit history.

    Uses git log to extract per-commit contribution data. The change_type
    is applied uniformly — callers with domain knowledge can override
    per-commit (e.g., from EditProposal metadata).

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

    for commit in repo.iter_commits():
        # Extract author identity
        author_name = str(commit.author)

        # Get diff stats
        try:
            if commit.parents:
                diff = commit.parents[0].diff(commit)
            else:
                # Initial commit — diff against empty tree
                diff = commit.diff(git.NULL_TREE)
        except Exception:
            diff = []

        lines_added = 0
        lines_deleted = 0
        files_changed = []

        for d in diff:
            if d.a_path:
                files_changed.append(d.a_path)
            # Count lines from diff text
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
```

- [ ] **Step 4: 运行测试验证**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_contribution.py -v
Expected: 9 tests pass
```

- [ ] **Step 5: Commit**

```bash
git add peerpedia_core/workflow/contribution.py tests/test_contribution.py
git commit -m "feat(contribution): add contribution weight engine with git blame extraction"
```

---

### Task 4: 审稿期协作工作流（Mode A）

**Files:**
- Create: `peerpedia_core/workflow/collaboration.py`
- Modify: `peerpedia_core/workflow/review.py` (添加 accept_collaboration)
- Create: `tests/test_collaboration.py`

- [ ] **Step 1: 编写失败测试 — test_collaboration.py**

```python
"""Tests for collaboration workflow (Mode A: reviewer → co-author)."""
import pytest
import tempfile
from pathlib import Path

from peerpedia_core.workflow.collaboration import (
    accept_collaboration,
    CollaborationResult,
    get_collaboration_status,
)
from peerpedia_core.workflow.review import (
    assign_reviewer,
    submit_review,
)
from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    get_article,
    get_reviews_for_article,
)


@pytest.fixture
def db_url():
    return "sqlite:///:memory:"


@pytest.fixture
def engine(db_url):
    eng = get_engine(db_url)
    init_db(eng)
    return eng


class TestCollaborationAccept:
    """Accepting collaboration requests."""

    def test_accept_collaboration_adds_co_author(self, engine, db_url):
        """Accepting collaboration adds reviewer to founding_authors."""
        from peerpedia_core.storage.db import create_article
        import uuid

        session = get_session(engine)
        article_id = str(uuid.uuid4())
        create_article(
            session,
            id=article_id,
            title="Test Article",
            founding_authors=["alice"],
            abstract="Test",
            git_repo_path="/tmp/test",
        )
        session.commit()

        # Set article to in_review then submit a review with collaboration_request
        from peerpedia_core.storage.db import update_article_status
        update_article_status(session, article_id, "in_review")
        session.commit()

        submit_review(
            article_id=article_id,
            reviewer_id="bob",
            decision="revise",
            comments="Good work, I'd like to help improve.",
            collaboration_request=True,
            collaboration_message="I can improve the methods section.",
            database_url=db_url,
        )
        session.close()

        # Now accept collaboration
        result = accept_collaboration(
            article_id=article_id,
            reviewer_id="bob",
            database_url=db_url,
        )

        assert result.success is True
        assert "bob" in result.founding_authors

        # Verify in DB
        session = get_session(engine)
        article = get_article(session, article_id)
        assert "bob" in article.founding_authors
        session.close()

    def test_accept_collaboration_requires_collaboration_request(self, engine, db_url):
        """Cannot accept if review didn't request collaboration."""
        from peerpedia_core.storage.db import create_article, update_article_status
        import uuid

        session = get_session(engine)
        article_id = str(uuid.uuid4())
        create_article(
            session,
            id=article_id,
            title="Test Article",
            founding_authors=["alice"],
            abstract="Test",
            git_repo_path="/tmp/test",
        )
        session.commit()
        update_article_status(session, article_id, "in_review")
        session.commit()

        # Submit review WITHOUT collaboration_request
        submit_review(
            article_id=article_id,
            reviewer_id="bob",
            decision="accept",
            comments="Looks great.",
            collaboration_request=False,
            database_url=db_url,
        )
        session.close()

        result = accept_collaboration(
            article_id=article_id,
            reviewer_id="bob",
            database_url=db_url,
        )

        assert result.success is False
        assert "collaboration" in result.error.lower()

    def test_accept_collaboration_nonexistent_article(self, db_url):
        """Accepting collaboration on nonexistent article fails."""
        result = accept_collaboration(
            article_id="nonexistent",
            reviewer_id="bob",
            database_url=db_url,
        )
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_get_collaboration_status(self, engine, db_url):
        """Get collaboration status returns reviewer's collaboration status."""
        from peerpedia_core.storage.db import create_article, update_article_status
        import uuid

        session = get_session(engine)
        article_id = str(uuid.uuid4())
        create_article(
            session,
            id=article_id,
            title="Test",
            founding_authors=["alice"],
            abstract="Test",
            git_repo_path="/tmp/test",
        )
        session.commit()
        update_article_status(session, article_id, "in_review")
        session.commit()

        submit_review(
            article_id=article_id,
            reviewer_id="bob",
            decision="revise",
            comments="Needs work, I can help.",
            collaboration_request=True,
            collaboration_message="Let me fix the proofs.",
            database_url=db_url,
        )
        session.close()

        status = get_collaboration_status(
            article_id=article_id,
            reviewer_id="bob",
            database_url=db_url,
        )

        assert status["has_requested"] is True
        assert status["has_accepted"] is False  # Not yet accepted
        assert status["message"] == "Let me fix the proofs."
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_collaboration.py -v
Expected: FAIL — Module not found
```

- [ ] **Step 3: 实现 collaboration.py**

```python
"""Layer 1: Collaboration workflow (Mode A: reviewer → co-author).

Handles the reviewer-to-coauthor transition during peer review.
When an author accepts a review's collaboration request, the reviewer
becomes a co-author and can contribute directly via git branches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    get_article,
    get_reviews_for_article,
    update_article_founding_authors,
    Article,
)


@dataclass
class CollaborationResult:
    """Result of accepting a collaboration request."""
    success: bool
    article_id: str = ""
    reviewer_id: str = ""
    founding_authors: list[str] = field(default_factory=list)
    error: str = ""


def accept_collaboration(
    article_id: str,
    reviewer_id: str,
    *,
    database_url: str,
) -> CollaborationResult:
    """Accept a reviewer's collaboration request. Adds reviewer as co-author.

    The reviewer must have submitted a review with collaboration_request=True
    for this article.
    """
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        article = get_article(session, article_id)
        if article is None:
            return CollaborationResult(
                success=False,
                article_id=article_id,
                error="Article not found",
            )

        # Check reviewer has a collaboration request
        reviews = get_reviews_for_article(session, article_id)
        collab_review = None
        for r in reviews:
            if r.reviewer_id == reviewer_id and r.collaboration_request:
                collab_review = r
                break

        if collab_review is None:
            return CollaborationResult(
                success=False,
                article_id=article_id,
                reviewer_id=reviewer_id,
                error=f"Reviewer '{reviewer_id}' has not requested collaboration on this article",
            )

        # Add reviewer as co-author
        update_article_founding_authors(session, article_id, reviewer_id)
        session.commit()

        # Re-read to get updated authors
        updated = get_article(session, article_id)
        return CollaborationResult(
            success=True,
            article_id=article_id,
            reviewer_id=reviewer_id,
            founding_authors=list(updated.founding_authors) if updated else [],
        )
    except Exception as e:
        session.rollback()
        return CollaborationResult(
            success=False,
            article_id=article_id,
            error=str(e),
        )
    finally:
        session.close()


def get_collaboration_status(
    article_id: str,
    reviewer_id: str,
    *,
    database_url: str,
) -> dict:
    """Get the collaboration status for a reviewer on an article.

    Returns:
        Dict with keys: has_requested, has_accepted, message, reviewer_id.
    """
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        article = get_article(session, article_id)
        has_accepted = reviewer_id in (article.founding_authors if article else [])

        reviews = get_reviews_for_article(session, article_id)
        has_requested = False
        message = ""
        for r in reviews:
            if r.reviewer_id == reviewer_id and r.collaboration_request:
                has_requested = True
                message = r.collaboration_message
                break

        return {
            "reviewer_id": reviewer_id,
            "article_id": article_id,
            "has_requested": has_requested,
            "has_accepted": has_accepted,
            "message": message,
        }
    finally:
        session.close()
```

- [ ] **Step 4: 运行测试验证**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_collaboration.py -v
Expected: 4 tests pass
```

- [ ] **Step 5: Commit**

```bash
git add peerpedia_core/workflow/collaboration.py tests/test_collaboration.py
git commit -m "feat(collaboration): add Mode A reviewer-to-coauthor collaboration workflow"
```

---

### Task 5: 开放编辑提案工作流（Mode B）

**Files:**
- Create: `peerpedia_core/workflow/edit_proposal.py`
- Create: `tests/test_edit_proposal.py`

- [ ] **Step 1: 编写失败测试 — test_edit_proposal.py**

```python
"""Tests for edit proposal workflow (Mode B: post-publication editing)."""
import pytest
import tempfile
import uuid
from pathlib import Path

from peerpedia_core.workflow.edit_proposal import (
    create_proposal,
    review_proposal,
    merge_proposal,
    CreateProposalResult,
    ReviewProposalResult,
    MergeProposalResult,
)
from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    get_article,
    create_article,
    update_article_status,
    get_edit_proposal,
    get_contribution_records,
)


@pytest.fixture
def db_url():
    return "sqlite:///:memory:"


@pytest.fixture
def engine(db_url):
    eng = get_engine(db_url)
    init_db(eng)
    return eng


@pytest.fixture
def published_article(engine):
    """Create a published article for edit testing."""
    session = get_session(engine)
    article_id = str(uuid.uuid4())
    article = create_article(
        session,
        id=article_id,
        title="Test Article",
        founding_authors=["alice"],
        abstract="An abstract.",
        git_repo_path="/tmp/test_proposal",
    )
    session.commit()
    update_article_status(session, article_id, "published")
    session.commit()
    session.close()
    return article_id


class TestCreateProposal:
    """Creating edit proposals."""

    def test_create_minor_proposal(self, engine, db_url, published_article):
        """Create a minor edit proposal."""
        result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="minor",
            description="Fixed a typo in section 1.",
            database_url=db_url,
        )

        assert result.success is True
        assert result.proposal_id is not None
        assert result.proposal_type == "minor"

        # Verify in DB
        session = get_session(engine)
        proposal = get_edit_proposal(session, result.proposal_id)
        assert proposal is not None
        assert proposal.proposal_type == "minor"
        assert proposal.status == "auto_approved"  # Minor proposals auto-approve
        assert proposal.proposer_id == "bob"
        session.close()

    def test_create_medium_proposal(self, engine, db_url, published_article):
        """Create a medium edit proposal — stays pending."""
        result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="medium",
            description="Rewrote the methods section.",
            database_url=db_url,
        )

        assert result.success is True
        assert result.proposal_type == "medium"

        session = get_session(engine)
        proposal = get_edit_proposal(session, result.proposal_id)
        assert proposal.status == "pending"  # Medium needs review
        session.close()

    def test_create_major_proposal(self, engine, db_url, published_article):
        """Create a major edit proposal."""
        result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="major",
            description="Added a new chapter on applications.",
            database_url=db_url,
        )

        assert result.success is True
        assert result.proposal_type == "major"

        session = get_session(engine)
        proposal = get_edit_proposal(session, result.proposal_id)
        assert proposal.status == "pending"
        session.close()

    def test_create_proposal_nonexistent_article(self, db_url):
        """Cannot create proposal for nonexistent article."""
        result = create_proposal(
            article_id="nonexistent",
            proposer_id="bob",
            proposal_type="minor",
            description="Fix typo.",
            database_url=db_url,
        )
        assert result.success is False

    def test_create_proposal_non_published_article(self, engine, db_url):
        """Cannot create proposal for non-published article."""
        session = get_session(engine)
        article_id = str(uuid.uuid4())
        create_article(
            session,
            id=article_id,
            title="Draft",
            founding_authors=["alice"],
            abstract="Test",
            git_repo_path="/tmp/test",
        )
        session.commit()
        session.close()

        result = create_proposal(
            article_id=article_id,
            proposer_id="bob",
            proposal_type="minor",
            description="Fix.",
            database_url=db_url,
        )
        assert result.success is False
        assert "published" in result.error.lower()

    def test_invalid_proposal_type(self, engine, db_url, published_article):
        """Invalid proposal type is rejected."""
        result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="huge",  # invalid
            description="Big changes.",
            database_url=db_url,
        )
        assert result.success is False


class TestReviewProposal:
    """Reviewing edit proposals."""

    def test_approve_medium_proposal(self, engine, db_url, published_article):
        """Approve a medium proposal."""
        # Create proposal first
        create_result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="medium",
            description="Rewrote methods.",
            database_url=db_url,
        )

        # Review it
        result = review_proposal(
            proposal_id=create_result.proposal_id,
            reviewer_id="alice",  # original author
            decision="approve",
            comment="Good improvement.",
            database_url=db_url,
        )

        assert result.success is True
        assert result.new_status == "approved"

        session = get_session(engine)
        proposal = get_edit_proposal(session, create_result.proposal_id)
        assert proposal.status == "approved"
        assert proposal.reviewer_id == "alice"
        assert proposal.review_comment == "Good improvement."
        session.close()

    def test_reject_proposal(self, engine, db_url, published_article):
        """Reject a proposal."""
        create_result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="medium",
            description="Not needed change.",
            database_url=db_url,
        )

        result = review_proposal(
            proposal_id=create_result.proposal_id,
            reviewer_id="alice",
            decision="reject",
            comment="This change is unnecessary.",
            database_url=db_url,
        )

        assert result.success is True
        assert result.new_status == "rejected"

    def test_cannot_review_auto_approved_proposal(self, engine, db_url, published_article):
        """Cannot review an already auto-approved (minor) proposal."""
        create_result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="minor",
            description="Typo fix.",
            database_url=db_url,
        )

        result = review_proposal(
            proposal_id=create_result.proposal_id,
            reviewer_id="alice",
            decision="reject",
            comment="No.",
            database_url=db_url,
        )
        assert result.success is False


class TestMergeProposal:
    """Merging approved proposals."""

    def test_merge_approved_proposal(self, engine, db_url, published_article):
        """Merge an approved proposal updates article version."""
        # Create and approve
        create_result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="medium",
            description="Rewrote methods.",
            database_url=db_url,
        )
        review_proposal(
            proposal_id=create_result.proposal_id,
            reviewer_id="alice",
            decision="approve",
            comment="Good.",
            database_url=db_url,
        )

        # Merge
        result = merge_proposal(
            proposal_id=create_result.proposal_id,
            article_id=published_article,
            proposer_id="bob",
            repository_url="/tmp/test_proposal",
            database_url=db_url,
        )

        assert result.success is True
        assert result.new_version is not None
        assert result.new_version != "v0.1"

    def test_merge_auto_approved_minor_proposal(self, engine, db_url, published_article):
        """Merge an auto-approved minor proposal works directly."""
        create_result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="minor",
            description="Typo fix.",
            database_url=db_url,
        )

        result = merge_proposal(
            proposal_id=create_result.proposal_id,
            article_id=published_article,
            proposer_id="bob",
            repository_url="/tmp/test_proposal",
            database_url=db_url,
        )

        assert result.success is True

    def test_cannot_merge_pending_proposal(self, engine, db_url, published_article):
        """Cannot merge a pending (unreviewed) proposal."""
        create_result = create_proposal(
            article_id=published_article,
            proposer_id="bob",
            proposal_type="medium",
            description="Changes.",
            database_url=db_url,
        )

        result = merge_proposal(
            proposal_id=create_result.proposal_id,
            article_id=published_article,
            proposer_id="bob",
            repository_url="/tmp/test_proposal",
            database_url=db_url,
        )

        assert result.success is False
        assert "approved" in result.error.lower() or "not been" in result.error.lower()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_edit_proposal.py -v
Expected: FAIL — Module not found
```

- [ ] **Step 3: 实现 edit_proposal.py**

```python
"""Layer 1: Edit proposal workflow (Mode B: post-publication open editing).

Handles the full lifecycle of post-publication edit proposals:
    create → review → merge → contribution record updated
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from peerpedia_core.workflow.state_machine import (
    ArticleStatus,
    can_transition,
    transition,
)
from peerpedia_core.storage.db import (
    get_engine,
    init_db,
    get_session,
    get_article,
    update_article_status,
    update_article_version,
    create_edit_proposal,
    get_edit_proposal,
    update_edit_proposal_status,
    create_contribution_record,
    update_article_founding_authors,
)
from peerpedia_core.workflow.contribution import compute_change_type_weight


VALID_PROPOSAL_TYPES = {"minor", "medium", "major"}


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class CreateProposalResult:
    success: bool
    proposal_id: str = ""
    article_id: str = ""
    proposal_type: str = ""
    auto_approved: bool = False
    error: str = ""


@dataclass
class ReviewProposalResult:
    success: bool
    proposal_id: str = ""
    new_status: str = ""
    error: str = ""


@dataclass
class MergeProposalResult:
    success: bool
    proposal_id: str = ""
    article_id: str = ""
    new_version: str = ""
    contribution_record_id: str = ""
    error: str = ""


# ── Create proposal ────────────────────────────────────────────────────────────

def create_proposal(
    article_id: str,
    proposer_id: str,
    proposal_type: str,
    description: str,
    *,
    database_url: str,
    git_branch: str = "",
    diff_stat: str = "",
) -> CreateProposalResult:
    """Create a new edit proposal on a published article.

    Minor proposals auto-approve. Medium and major stay pending for review.
    """
    if proposal_type not in VALID_PROPOSAL_TYPES:
        return CreateProposalResult(
            success=False,
            error=f"Invalid proposal type '{proposal_type}'. Must be one of: {VALID_PROPOSAL_TYPES}",
        )

    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        article = get_article(session, article_id)
        if article is None:
            return CreateProposalResult(
                success=False,
                article_id=article_id,
                error="Article not found",
            )

        if article.status != ArticleStatus.PUBLISHED:
            return CreateProposalResult(
                success=False,
                article_id=article_id,
                error=f"Article must be 'published' to accept edit proposals (current: '{article.status}')",
            )

        # Minor proposals auto-approve
        auto_approved = proposal_type == "minor"
        status = "auto_approved" if auto_approved else "pending"

        # Transition article: published → edit_proposed (for medium/major)
        if not auto_approved:
            update_article_status(session, article_id, ArticleStatus.EDIT_PROPOSED)

        # Create proposal record
        proposal = create_edit_proposal(
            session,
            article_id=article_id,
            proposer_id=proposer_id,
            proposal_type=proposal_type,
            description=description,
            git_branch=git_branch,
            diff_stat=diff_stat,
        )
        # Override status for auto-approved
        proposal.status = status
        session.commit()

        return CreateProposalResult(
            success=True,
            proposal_id=proposal.id,
            article_id=article_id,
            proposal_type=proposal_type,
            auto_approved=auto_approved,
        )
    except Exception as e:
        session.rollback()
        return CreateProposalResult(
            success=False,
            article_id=article_id,
            error=str(e),
        )
    finally:
        session.close()


# ── Review proposal ────────────────────────────────────────────────────────────

def review_proposal(
    proposal_id: str,
    reviewer_id: str,
    decision: str,
    comment: str = "",
    *,
    database_url: str,
) -> ReviewProposalResult:
    """Review an edit proposal (approve or reject).

    Only pending proposals can be reviewed. Auto-approved proposals skip this step.
    """
    if decision not in ("approve", "reject"):
        return ReviewProposalResult(
            success=False,
            proposal_id=proposal_id,
            error=f"Decision must be 'approve' or 'reject', got '{decision}'",
        )

    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        proposal = get_edit_proposal(session, proposal_id)
        if proposal is None:
            return ReviewProposalResult(
                success=False,
                proposal_id=proposal_id,
                error="Proposal not found",
            )

        if proposal.status != "pending":
            return ReviewProposalResult(
                success=False,
                proposal_id=proposal_id,
                error=f"Cannot review proposal with status '{proposal.status}'. Only 'pending' proposals can be reviewed.",
            )

        new_status = "approved" if decision == "approve" else "rejected"
        update_edit_proposal_status(
            session,
            proposal_id,
            new_status,
            reviewer_id=reviewer_id,
            review_comment=comment,
        )
        session.commit()

        return ReviewProposalResult(
            success=True,
            proposal_id=proposal_id,
            new_status=new_status,
        )
    except Exception as e:
        session.rollback()
        return ReviewProposalResult(
            success=False,
            proposal_id=proposal_id,
            error=str(e),
        )
    finally:
        session.close()


# ── Merge proposal ─────────────────────────────────────────────────────────────

def merge_proposal(
    proposal_id: str,
    article_id: str,
    proposer_id: str,
    *,
    repository_url: str,
    database_url: str,
    change_type: str = "content",
) -> MergeProposalResult:
    """Merge an approved (or auto-approved) proposal.

    This:
    1. Validates proposal is approved/auto_approved
    2. Updates article version (v0.1 → v0.2, etc.)
    3. Transitions article status back to published
    4. Creates a contribution record for the proposer
    5. Adds proposer as co-author if not already
    """
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)

    try:
        proposal = get_edit_proposal(session, proposal_id)
        if proposal is None:
            return MergeProposalResult(
                success=False,
                proposal_id=proposal_id,
                error="Proposal not found",
            )

        if proposal.status not in ("approved", "auto_approved"):
            return MergeProposalResult(
                success=False,
                proposal_id=proposal_id,
                error=f"Proposal has not been approved (status: '{proposal.status}')",
            )

        article = get_article(session, article_id)
        if article is None:
            return MergeProposalResult(
                success=False,
                error="Article not found",
            )

        # Bump version
        current_version = article.version or "v0.1"
        try:
            parts = current_version.lstrip("v").split(".")
            minor = int(parts[1]) if len(parts) > 1 else 1
            new_version = f"v{parts[0]}.{minor + 1}"
        except (ValueError, IndexError):
            new_version = "v0.2"

        update_article_version(session, article_id, new_version)

        # Transition status back to published (if currently in edit_proposed)
        if article.status == ArticleStatus.EDIT_PROPOSED:
            update_article_status(session, article_id, ArticleStatus.PUBLISHED)

        # Create contribution record
        weight = compute_change_type_weight(change_type)
        contribution = create_contribution_record(
            session,
            article_id=article_id,
            user_id=proposer_id,
            commit_hash="pending",  # Will be updated with real commit hash
            commit_message=f"Edit proposal: {proposal.description[:80]}",
            lines_added=0,
            lines_deleted=0,
            change_type=change_type,
            contribution_weight=weight,
        )
        session.commit()

        # Add proposer as co-author if not already
        update_article_founding_authors(session, article_id, proposer_id)
        session.commit()

        return MergeProposalResult(
            success=True,
            proposal_id=proposal_id,
            article_id=article_id,
            new_version=new_version,
            contribution_record_id=contribution.id,
        )
    except Exception as e:
        session.rollback()
        return MergeProposalResult(
            success=False,
            proposal_id=proposal_id,
            error=str(e),
        )
    finally:
        session.close()
```

- [ ] **Step 4: 运行测试验证**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/test_edit_proposal.py -v
Expected: 10 tests pass
```

- [ ] **Step 5: Commit**

```bash
git add peerpedia_core/workflow/edit_proposal.py tests/test_edit_proposal.py
git commit -m "feat(edit-proposal): add Mode B post-publication edit proposal workflow"
```

---

### Task 6: CLI 命令实现 — collaborate + propose-edit

**Files:**
- Modify: `peerpedia/cli/main.py`

- [ ] **Step 1: 实现 `collaborate` CLI 命令**

替换 `peerpedia/cli/main.py` 中现有的 `collaborate` 占位函数：

```python
@cli.command()
@click.argument("article_id")
@click.option("--reviewer", "-r", required=True, help="审稿人 ID（申请协作的审稿人）")
def collaborate(article_id: str, reviewer: str):
    """接受审稿人的协作申请，将其添加为合作者。

    ARTICLE_ID: 文章 UUID。
    审稿人必须先提交带有协作申请的审稿意见。
    """
    from peerpedia.config.settings import settings
    from peerpedia_core.workflow.collaboration import accept_collaboration
    from peerpedia_core.storage.db import get_engine, init_db

    engine = get_engine(settings.database_url)
    init_db(engine)

    click.echo(f"接受协作申请")
    click.echo(f"  文章:  {article_id}")
    click.echo(f"  审稿人: {reviewer}")

    result = accept_collaboration(
        article_id=article_id,
        reviewer_id=reviewer,
        database_url=settings.database_url,
    )

    if result.success:
        click.echo()
        click.echo(f"✓ 协作已建立！")
        click.echo(f"  合作者: {', '.join(result.founding_authors)}")
    else:
        click.echo(f"✗ 协作失败: {result.error}", err=True)
        raise SystemExit(1)
```

- [ ] **Step 2: 实现 `propose-edit` CLI 命令**

替换 `peerpedia/cli/main.py` 中现有的 `propose_edit` 占位函数：

```python
@cli.command()
@click.argument("article_id")
@click.option("--type", "-t", "proposal_type", type=click.Choice(["minor", "medium", "major"]),
              required=True, help="修改类型: minor（微小）/ medium（中等）/ major（重大）")
@click.option("--description", "-d", required=True, help="修改描述")
@click.option("--proposer", "-p", default="anonymous", help="提案人 ID")
def propose_edit(article_id: str, proposal_type: str, description: str, proposer: str):
    """对已出版的文章提交修改提案（出版后开放编辑）。

    ARTICLE_ID: 文章 UUID。

    \b
    修改类型：
      minor  — 微小修改（错字、格式），自动通过
      medium — 中等修改（段落/公式），需原作者审核
      major  — 重大修改（新章节），需社区审核
    """
    from peerpedia.config.settings import settings
    from peerpedia_core.workflow.edit_proposal import create_proposal
    from peerpedia_core.storage.db import get_engine, init_db

    engine = get_engine(settings.database_url)
    init_db(engine)

    auto_label = "（自动通过）" if proposal_type == "minor" else "（等待审核）"

    click.echo(f"提交修改提案")
    click.echo(f"  文章:  {article_id}")
    click.echo(f"  类型:  {proposal_type} {auto_label}")
    click.echo(f"  提案人: {proposer}")

    result = create_proposal(
        article_id=article_id,
        proposer_id=proposer,
        proposal_type=proposal_type,
        description=description,
        database_url=settings.database_url,
    )

    if result.success:
        click.echo()
        click.echo(f"✓ 修改提案已提交！")
        click.echo(f"  提案 ID: {result.proposal_id}")
        if result.auto_approved:
            click.echo(f"  状态:    自动通过（微小修改）")
            click.echo(f"  下一步:  peerpedia merge-proposal {result.proposal_id}")
        else:
            click.echo(f"  状态:    等待审核")
            click.echo(f"  下一步:  原作者审核后可合并")
    else:
        click.echo(f"✗ 提案失败: {result.error}", err=True)
        raise SystemExit(1)
```

- [ ] **Step 3: 添加 `merge-proposal` CLI 命令**

```python
@cli.command()
@click.argument("proposal_id")
@click.argument("article_id")
@click.option("--proposer", "-p", default="anonymous", help="提案人 ID")
@click.option("--change-type", "-c", type=click.Choice(["new_theorem", "proof_fix", "content", "prose", "format"]),
              default="content", help="修改内容类型（影响贡献权重）")
def merge_proposal(proposal_id: str, article_id: str, proposer: str, change_type: str):
    """合并一个已通过的修改提案到文章中。

    PROPOSAL_ID: 提案 UUID。
    ARTICLE_ID: 文章 UUID。
    """
    from peerpedia.config.settings import settings
    from peerpedia_core.workflow.edit_proposal import merge_proposal
    from peerpedia_core.storage.db import get_engine, init_db

    engine = get_engine(settings.database_url)
    init_db(engine)

    click.echo(f"合并修改提案")
    click.echo(f"  提案: {proposal_id}")
    click.echo(f"  文章: {article_id}")

    result = merge_proposal(
        proposal_id=proposal_id,
        article_id=article_id,
        proposer_id=proposer,
        repository_url=str(settings.articles_dir / article_id),
        database_url=settings.database_url,
        change_type=change_type,
    )

    if result.success:
        click.echo()
        click.echo(f"✓ 提案已合并！")
        click.echo(f"  新版本:  {result.new_version}")
        click.echo(f"  贡献记录: {result.contribution_record_id}")
    else:
        click.echo(f"✗ 合并失败: {result.error}", err=True)
        raise SystemExit(1)
```

- [ ] **Step 4: 运行 CLI 验证命令存在**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && peerpedia --help
Expected: 输出中包含 collaborate, propose-edit, merge-proposal 命令
```

- [ ] **Step 5: Commit**

```bash
git add peerpedia/cli/main.py
git commit -m "feat(cli): implement collaborate, propose-edit, and merge-proposal commands"
```

---

### Task 7: Web API + 页面扩展

**Files:**
- Modify: `peerpedia/web/routes/api.py`
- Modify: `peerpedia/web/routes/pages.py`

- [ ] **Step 1: 添加 API 端点**

在 `peerpedia/web/routes/api.py` 末尾添加：

```python
# ── Collaboration ──────────────────────────────────────────────────────────────

@router.post("/articles/{article_id}/collaborate")
async def api_accept_collaboration(article_id: str, reviewer_id: str = Form(...)):
    """Accept a reviewer's collaboration request."""
    from peerpedia_core.workflow.collaboration import accept_collaboration

    result = accept_collaboration(
        article_id=article_id,
        reviewer_id=reviewer_id,
        database_url=settings.database_url,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "article_id": article_id,
        "founding_authors": result.founding_authors,
        "status": "collaboration_accepted",
    }


@router.get("/articles/{article_id}/collaboration/{reviewer_id}")
async def api_get_collaboration_status(article_id: str, reviewer_id: str):
    """Get collaboration status for a reviewer on an article."""
    from peerpedia_core.workflow.collaboration import get_collaboration_status

    status = get_collaboration_status(
        article_id=article_id,
        reviewer_id=reviewer_id,
        database_url=settings.database_url,
    )
    return status


# ── Edit Proposals ─────────────────────────────────────────────────────────────

@router.post("/articles/{article_id}/proposals")
async def api_create_proposal(
    article_id: str,
    proposer_id: str = Form(...),
    proposal_type: str = Form(...),
    description: str = Form(""),
):
    """Create an edit proposal for a published article."""
    from peerpedia_core.workflow.edit_proposal import create_proposal

    result = create_proposal(
        article_id=article_id,
        proposer_id=proposer_id,
        proposal_type=proposal_type,
        description=description,
        database_url=settings.database_url,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "proposal_id": result.proposal_id,
        "article_id": result.article_id,
        "proposal_type": result.proposal_type,
        "auto_approved": result.auto_approved,
        "status": "created",
    }


@router.get("/articles/{article_id}/proposals")
async def api_list_proposals(article_id: str, status: str = None):
    """List edit proposals for an article."""
    from peerpedia_core.storage.db import get_edit_proposals_for_article

    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")
        proposals = get_edit_proposals_for_article(session, article_id, status=status)
        return {
            "article_id": article_id,
            "proposals": [p.to_dict() for p in proposals],
            "total": len(proposals),
        }
    finally:
        session.close()


@router.post("/proposals/{proposal_id}/review")
async def api_review_proposal(
    proposal_id: str,
    reviewer_id: str = Form(...),
    decision: str = Form(...),
    comment: str = Form(""),
):
    """Review (approve/reject) an edit proposal."""
    from peerpedia_core.workflow.edit_proposal import review_proposal

    result = review_proposal(
        proposal_id=proposal_id,
        reviewer_id=reviewer_id,
        decision=decision,
        comment=comment,
        database_url=settings.database_url,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "proposal_id": proposal_id,
        "new_status": result.new_status,
    }


@router.post("/proposals/{proposal_id}/merge")
async def api_merge_proposal(
    proposal_id: str,
    article_id: str = Form(...),
    proposer_id: str = Form(...),
    change_type: str = Form("content"),
):
    """Merge an approved edit proposal."""
    from peerpedia_core.workflow.edit_proposal import merge_proposal

    result = merge_proposal(
        proposal_id=proposal_id,
        article_id=article_id,
        proposer_id=proposer_id,
        repository_url=str(settings.articles_dir / article_id),
        database_url=settings.database_url,
        change_type=change_type,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "proposal_id": proposal_id,
        "article_id": article_id,
        "new_version": result.new_version,
        "contribution_record_id": result.contribution_record_id,
    }


# ── Contribution Timeline ──────────────────────────────────────────────────────

@router.get("/articles/{article_id}/contributions")
async def api_get_contribution_timeline(article_id: str):
    """Get contribution timeline and breakdown for an article."""
    from peerpedia_core.storage.db import get_contribution_records
    from peerpedia_core.workflow.contribution import (
        compute_contribution_breakdown,
        compute_contribution_timeline,
    )

    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        records = get_contribution_records(session, article_id)
        timeline = compute_contribution_timeline([r.to_dict() for r in records])
        breakdown = compute_contribution_breakdown([r.to_dict() for r in records])

        return {
            "article_id": article_id,
            "timeline": timeline,
            "breakdown": breakdown,
            "total_records": len(records),
        }
    finally:
        session.close()
```

- [ ] **Step 2: 添加贡献时间线页面路由**

在 `peerpedia/web/routes/pages.py` 中添加：

```python
@router.get("/article/{article_id}/contributions", response_class=HTMLResponse)
async def contribution_timeline_page(request: Request, article_id: str):
    """Contribution timeline page for an article."""
    from peerpedia_core.storage.db import get_contribution_records, get_edit_proposals_for_article
    from peerpedia_core.workflow.contribution import (
        compute_contribution_breakdown,
        compute_contribution_timeline,
    )

    session = _get_db_session()
    try:
        article = get_article(session, article_id)
        if article is None:
            return templates.TemplateResponse(
                "article.html",
                {"request": request, "title": "Not Found", "article": None},
                status_code=404,
            )

        records = get_contribution_records(session, article_id)
        proposals = get_edit_proposals_for_article(session, article_id)
        timeline = compute_contribution_timeline([r.to_dict() for r in records])
        breakdown = compute_contribution_breakdown([r.to_dict() for r in records])

        return templates.TemplateResponse(
            "contributions.html",
            {
                "request": request,
                "title": f"贡献时间线: {article.title}",
                "article": article.to_dict(),
                "timeline": timeline,
                "breakdown": breakdown,
                "proposals": [p.to_dict() for p in proposals],
            },
        )
    finally:
        session.close()
```

Note: `contributions.html` template 的创建留给 Web 模板任务。

- [ ] **Step 3: 运行现有测试确认 API 扩展不破坏功能**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -q
Expected: all existing tests still pass
```

- [ ] **Step 4: Commit**

```bash
git add peerpedia/web/routes/api.py peerpedia/web/routes/pages.py
git commit -m "feat(web): add collaboration, edit proposal, and contribution API endpoints"
```

---

### Task 8: 全量测试 + 集成验证

- [ ] **Step 1: 运行全部测试套件**

```bash
cd ~/Projects/peerpedia && source .venv/bin/activate && python -m pytest tests/ -v
Expected: 87 + ~22 new tests = ~109 tests, all pass
```

- [ ] **Step 2: 端到端集成测试 — 完整协作+编辑流程**

```bash
# 端到端验证脚本
cd ~/Projects/peerpedia && source .venv/bin/activate

# 1. 初始化
peerpedia init

# 2. 检查新命令
peerpedia --help | grep -E "collaborate|propose-edit|merge-proposal"
```

- [ ] **Step 3: Commit final state**

```bash
git add -A
git commit -m "feat(m3): complete collaboration and open editing with contribution tracking

- Mode A: reviewer-to-coauthor collaboration workflow
- Mode B: post-publication edit proposals (minor/medium/major)
- Contribution records with git blame extraction
- State machine extended with edit_proposed state
- CLI commands: collaborate, propose-edit, merge-proposal
- Web API: collaboration, proposals, contribution timeline

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: 更新 STATUS.md 标记 M3 完成**
