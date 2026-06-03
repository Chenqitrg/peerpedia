"""Tests for contribution tracking and git blame computation."""
import tempfile
import uuid
from pathlib import Path

import pytest

from peerpedia_core.workflow.contribution import (
    build_contribution_records_from_git,
    compute_change_type_weight,
    compute_contribution_breakdown,
    compute_contribution_timeline,
)


class TestChangeTypeWeight:
    """Change type weight computation."""

    def test_new_theorem_weight(self):
        assert compute_change_type_weight("new_theorem") == 500  # 5.0 x 100

    def test_proof_fix_weight(self):
        assert compute_change_type_weight("proof_fix") == 400  # 4.0 x 100

    def test_content_weight(self):
        assert compute_change_type_weight("content") == 200  # 2.0 x 100

    def test_prose_weight(self):
        assert compute_change_type_weight("prose") == 100  # 1.0 x 100

    def test_format_weight(self):
        assert compute_change_type_weight("format") == 30  # 0.3 x 100

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
        from datetime import datetime, timezone
        records = [
            {"user_id": "alice", "timestamp": datetime(2025, 6, 1, tzinfo=timezone.utc), "contribution_weight": 100, "commit_hash": "ccc", "commit_message": "third"},
            {"user_id": "bob", "timestamp": datetime(2025, 3, 1, tzinfo=timezone.utc), "contribution_weight": 200, "commit_message": "first", "commit_hash": "aaa"},
            {"user_id": "alice", "timestamp": datetime(2025, 4, 1, tzinfo=timezone.utc), "contribution_weight": 150, "commit_message": "second", "commit_hash": "bbb"},
        ]
        timeline = compute_contribution_timeline(records)
        assert len(timeline) == 3
        assert timeline[0]["commit_hash"] == "aaa"
        assert timeline[1]["commit_hash"] == "bbb"
        assert timeline[2]["commit_hash"] == "ccc"


class TestBuildContributionFromGit:
    """Building contribution records from git repo."""

    def test_build_records_from_git_repo(self):
        """Build records from a real git repo created by git_backend."""
        from peerpedia_core.storage.git_backend import commit_article, init_article_repo

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            article_id = str(uuid.uuid4())
            repo_path = init_article_repo(article_id, base_dir=base)

            source = repo_path / "main.typ"
            source.write_text("= Introduction\n\nSome content here.\n")
            commit_article(repo_path, "Initial draft", "alice", "alice@test.com")

            source.write_text("= Introduction\n\nSome content here.\n\n== Methods\n\nMore content.\n")
            commit_article(repo_path, "Add methods section", "bob", "bob@test.com")

            records = build_contribution_records_from_git(
                repo_path=repo_path,
                article_id=article_id,
                change_type="content",
            )

            assert len(records) == 2
            assert records[0]["user_id"] == "alice"
            assert records[0]["lines_added"] > 0
            assert records[0]["commit_message"] == "Initial draft"
            assert records[1]["user_id"] == "bob"
            assert records[1]["lines_added"] > 0
            assert records[1]["commit_message"] == "Add methods section"
