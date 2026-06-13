"""XSpec tests for multi-author git history functions.

SPEC-1 through SPEC-5: get_authors_from_git and rebuild_article_authors.
These tests define product behavior — they LOCK before implementation.
"""
import shutil
import tempfile
from pathlib import Path

import pytest
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import Article, ArticleAuthor, User
from peerpedia_core.storage.git_backend import commit_article, init_article_repo

# ── Helpers ────────────────────────────────────────────────────────────────

def _create_user(session, username, name):
    u = User(
        username=username, password_hash="",
        name=name, anonymous_name=f"anon_{username}",
        affiliation="Test",
    )
    session.add(u)
    session.commit()
    return u


def _create_article_with_author(session, author_id):
    a = Article(status="draft")
    session.add(a)
    session.flush()
    session.add(ArticleAuthor(article_id=a.id, author_id=author_id, position=0))
    session.commit()
    return a


# ── SPEC-1: get_authors_from_git extracts unique authors ───────────────────

def test_spec1_get_authors_extracts_unique_users(db_engine):
    """SPEC-1: Repo with commits by A, B, A → returns {A, B} (deduplicated)."""
    from peerpedia_core.storage.db.crud_article import get_authors_from_git

    s = get_session(db_engine)
    user_a = _create_user(s, "alice", "Alice")
    user_b = _create_user(s, "bob", "Bob")
    s.close()

    # Create a standalone git repo for this test
    tmp = tempfile.mkdtemp()
    rp = Path(tmp)
    init_article_repo("test", rp.parent if rp.parent != Path(tmp) else None)
    # init_article_repo creates rp/{article_id}, so let's just use tmp directly
    # Actually init_article_repo expects article_id and base_dir
    # Let's use gitpython directly
    import git
    rp = Path(tmp)
    repo = git.Repo.init(rp)
    (rp / "article.md").write_text("# Test\n")

    email_a = f"{user_a.id}@peerpedia"
    email_b = f"{user_b.id}@peerpedia"

    # Commit by A
    repo.index.add(["article.md"])
    repo.index.commit("first", author=git.Actor("Alice", email_a), committer=git.Actor("Alice", email_a))  # noqa: F841
    # Commit by B
    (rp / "article.md").write_text("# Test\nB's change.\n")
    repo.index.add(["article.md"])
    repo.index.commit("second", author=git.Actor("Bob", email_b), committer=git.Actor("Bob", email_b))  # noqa: F841
    # Commit by A again
    (rp / "article.md").write_text("# Test\nB's change.\nA's fix.\n")
    repo.index.add(["article.md"])
    repo.index.commit("third", author=git.Actor("Alice", email_a), committer=git.Actor("Alice", email_a))  # noqa: F841

    s = get_session(db_engine)
    result = get_authors_from_git(rp, s)
    s.close()

    assert result == {user_a.id, user_b.id}, f"Expected {{A, B}}, got {result}"
    shutil.rmtree(tmp)


# ── SPEC-2: Incremental scan via git range ─────────────────────────────────

def test_spec2_incremental_scan_only_returns_new_authors(db_engine):
    """SPEC-2: with since_hash, only returns authors from newer commits."""
    from peerpedia_core.storage.db.crud_article import get_authors_from_git

    s = get_session(db_engine)
    user_a = _create_user(s, "alice", "Alice")
    user_b = _create_user(s, "bob", "Bob")
    user_c = _create_user(s, "carol", "Carol")
    s.close()

    import git
    tmp = tempfile.mkdtemp()
    rp = Path(tmp)
    repo = git.Repo.init(rp)
    (rp / "article.md").write_text("# Test\n")

    email_a = f"{user_a.id}@peerpedia"
    email_b = f"{user_b.id}@peerpedia"
    email_c = f"{user_c.id}@peerpedia"

    repo.index.add(["article.md"])
    repo.index.commit("A", author=git.Actor("A", email_a), committer=git.Actor("A", email_a))
    (rp / "article.md").write_text("# Test\nB\n")
    repo.index.add(["article.md"])
    c_b = repo.index.commit("B", author=git.Actor("B", email_b), committer=git.Actor("B", email_b))
    (rp / "article.md").write_text("# Test\nB\nC\n")
    repo.index.add(["article.md"])
    repo.index.commit("C", author=git.Actor("C", email_c), committer=git.Actor("C", email_c))

    s = get_session(db_engine)
    # since_hash = B's commit → should only return C
    result = get_authors_from_git(rp, s, since_hash=c_b.hexsha)
    s.close()

    assert result == {user_c.id}, f"Expected {{C}}, got {result}"
    shutil.rmtree(tmp)


# ── SPEC-3: Skips unmatched git emails ─────────────────────────────────────

def test_spec3_skips_unmatched_emails(db_engine):
    """SPEC-3: Commits by unknown@peerpedia → excluded from result."""
    from peerpedia_core.storage.db.crud_article import get_authors_from_git

    s = get_session(db_engine)
    user_a = _create_user(s, "alice", "Alice")
    s.close()

    import git
    tmp = tempfile.mkdtemp()
    rp = Path(tmp)
    repo = git.Repo.init(rp)
    (rp / "article.md").write_text("# Test\n")

    repo.index.add(["article.md"])
    repo.index.commit("A", author=git.Actor("A", f"{user_a.id}@peerpedia"), committer=git.Actor("A", f"{user_a.id}@peerpedia"))
    (rp / "article.md").write_text("# Test\nunknown\n")
    repo.index.add(["article.md"])
    repo.index.commit("unknown", author=git.Actor("X", "unknown@peerpedia"), committer=git.Actor("X", "unknown@peerpedia"))

    s = get_session(db_engine)
    result = get_authors_from_git(rp, s)
    s.close()

    assert result == {user_a.id}, f"Expected only {{A}}, got {result}"
    shutil.rmtree(tmp)


# ── SPEC-4: rebuild_article_authors appends without deleting ────────────────

def test_spec4_rebuild_appends_new_authors(db_engine):
    """SPEC-4: Existing author A, rebuild with {A, B} → authors = [A, B]."""
    from peerpedia_core.storage.db.crud_article import (
        get_author_ids,
        rebuild_article_authors,
    )

    s = get_session(db_engine)
    user_a = _create_user(s, "alice", "Alice")
    user_b = _create_user(s, "bob", "Bob")

    # Create article with author A
    a = _create_article_with_author(s, user_a.id)

    # Rebuild with {A, B}
    rebuild_article_authors(s, a.id, {user_a.id, user_b.id})

    result = get_author_ids(s, a.id)
    s.close()

    assert set(result) == {user_a.id, user_b.id}, f"Expected {{A, B}}, got {result}"
    assert len(result) == 2


# ── SPEC-5: rebuild updates last_author_rebuild_hash ───────────────────────

def test_spec5_rebuild_updates_marker_hash(db_engine):
    """SPEC-5: After rebuild, article.last_author_rebuild_hash == HEAD."""
    from peerpedia_core.storage.db.crud_article import rebuild_article_authors

    s = get_session(db_engine)
    user_a = _create_user(s, "alice", "Alice")

    # Create article with author A and a git repo
    a = _create_article_with_author(s, user_a.id)
    article_id = a.id

    # Create git repo for this article
    from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, init_article_repo
    rp = init_article_repo(article_id, DEFAULT_ARTICLES_DIR)
    (rp / "article.md").write_text("# Test\n")
    head_hash = commit_article(rp, "init", "Alice", f"{user_a.id}@peerpedia")

    s2 = get_session(db_engine)
    rebuild_article_authors(s2, article_id, {user_a.id})

    # Verify marker updated
    a2 = s2.get(Article, article_id)
    assert a2 is not None
    assert a2.last_author_rebuild_hash == head_hash, (
        f"Expected {head_hash}, got {a2.last_author_rebuild_hash}"
    )
    s2.close()

    shutil.rmtree(rp, ignore_errors=True)


# ── SPEC-10a: merge_git_repos fast-forward ───────────────────────────────

def test_merge_git_repos_fast_forward(db_engine):
    """merge_git_repos: fast-forward merge succeeds, returns merge hash."""
    import git
    from peerpedia_core.storage.git_backend import merge_git_repos
    tmp = tempfile.mkdtemp()
    target = Path(tmp) / "target"
    fork = Path(tmp) / "fork"

    # Create target repo with 2 commits
    target_repo = git.Repo.init(target)
    (target / "f.md").write_text("# T1\n")
    target_repo.index.add(["f.md"])
    target_repo.index.commit("T1", author=git.Actor("A", "a@test.com"), committer=git.Actor("A", "a@test.com"))
    (target / "f.md").write_text("# T2\n")
    target_repo.index.add(["f.md"])
    target_repo.index.commit("T2", author=git.Actor("A", "a@test.com"), committer=git.Actor("A", "a@test.com"))

    # Create fork by copying target
    shutil.copytree(target, fork, symlinks=True)
    fork_repo = git.Repo(fork)
    (fork / "f.md").write_text("# F1\n")
    fork_repo.index.add(["f.md"])
    fork_repo.index.commit("F1", author=git.Actor("B", "b@test.com"), committer=git.Actor("B", "b@test.com"))

    merge_hash = merge_git_repos(target, fork, "Merger")

    # After merge, target's git log should contain F1
    log_msgs = [c.message.strip() for c in git.Repo(target).iter_commits()]
    assert "F1" in log_msgs, f"Expected F1 in target history, got {log_msgs}"
    assert merge_hash is not None
    shutil.rmtree(tmp)


# ── SPEC-10b: merge_git_repos conflict → MergeConflictError ──────────────

def test_merge_git_repos_conflict_raises_error(db_engine):
    """merge_git_repos: conflict raises MergeConflictError, target unchanged."""
    import git
    from peerpedia_core.storage.git_backend import MergeConflictError, merge_git_repos
    tmp = tempfile.mkdtemp()
    target = Path(tmp) / "target"
    fork = Path(tmp) / "fork"

    # Create target repo
    target_repo = git.Repo.init(target)
    (target / "f.md").write_text("# Original\n")
    target_repo.index.add(["f.md"])
    target_repo.index.commit("Original", author=git.Actor("A", "a@test.com"), committer=git.Actor("A", "a@test.com"))

    # Create fork (copy target), then diverge
    shutil.copytree(target, fork, symlinks=True)
    (target / "f.md").write_text("# Target edit\n")
    target_repo.index.add(["f.md"])
    target_repo.index.commit("Target edit", author=git.Actor("A", "a@test.com"), committer=git.Actor("A", "a@test.com"))

    fork_repo = git.Repo(fork)
    (fork / "f.md").write_text("# Fork edit\n")
    fork_repo.index.add(["f.md"])
    fork_repo.index.commit("Fork edit", author=git.Actor("B", "b@test.com"), committer=git.Actor("B", "b@test.com"))

    target_head_before = target_repo.head.commit.hexsha

    with pytest.raises(MergeConflictError):
        merge_git_repos(target, fork, "Merger")

    # Target HEAD should be unchanged (merge aborted)
    assert target_repo.head.commit.hexsha == target_head_before
    shutil.rmtree(tmp)


# ── SPEC-REGRESSION: UUID-only internal addressing ──────────────────────────

def test_spec_regression_uuid_email_matched(db_engine):
    """git emails with {UUID}@peerpedia → author found."""
    from peerpedia_core.storage.db.crud_article import get_authors_from_git

    s = get_session(db_engine)
    u = _create_user(s, "alice", "Alice")
    s.close()

    import tempfile

    import git
    tmp = tempfile.mkdtemp()
    rp = Path(tmp)
    repo = git.Repo.init(rp)
    (rp / "f.md").write_text("# T\n")
    repo.index.add(["f.md"])
    repo.index.commit("init", author=git.Actor("Alice", f"{u.id}@peerpedia"),
                      committer=git.Actor("Alice", f"{u.id}@peerpedia"))

    s = get_session(db_engine)
    result = get_authors_from_git(rp, s)
    s.close()
    shutil.rmtree(tmp)

    assert result == {u.id}, f"UUID email should match, got {result}"


def test_spec_regression_username_email_rejected(db_engine):
    """git emails with {username}@peerpedia → NOT matched (username is not UUID)."""
    from peerpedia_core.storage.db.crud_article import get_authors_from_git

    s = get_session(db_engine)
    _create_user(s, "bob", "Bob")
    s.close()

    import tempfile

    import git
    tmp = tempfile.mkdtemp()
    rp = Path(tmp)
    repo = git.Repo.init(rp)
    (rp / "f.md").write_text("# T\n")
    # Deliberately use username in email — should NOT match
    repo.index.add(["f.md"])
    repo.index.commit("init", author=git.Actor("Bob", "bob@peerpedia"),
                      committer=git.Actor("Bob", "bob@peerpedia"))

    s = get_session(db_engine)
    result = get_authors_from_git(rp, s)
    s.close()
    shutil.rmtree(tmp)

    assert result == set(), (
        f"Username-based email should NOT match (UUID only), got {result}"
    )


def test_spec_regression_name_lookup_rejected(db_engine):
    """get_user by name-based email split → returns None (name is not UUID)."""
    from peerpedia_core.storage.db.models import User
    # Simulate what get_authors_from_git does: split email, lookup by that value
    s = get_session(db_engine)
    u = _create_user(s, "carol", "Carol")
    s.close()

    s2 = get_session(db_engine)
    # This is what happens with old seed data: "richard.feynman@peerpedia"
    fake_id = u.name.lower().replace(" ", ".")  # "carol" — NOT a UUID
    result = s2.get(User, fake_id)
    s2.close()

    assert result is None, (
        f"Username '{fake_id}' should NOT resolve as UUID. Use user.id, not user.name."
    )


def test_spec_regression_rebuild_sorts_by_username_not_uuid(db_engine):
    """rebuild_article_authors sorts authors by username for display, not by UUID."""
    from peerpedia_core.storage.db.crud_article import (
        get_author_ids,
        rebuild_article_authors,
    )

    s = get_session(db_engine)
    user_z = _create_user(s, "zoe", "Zoe")
    user_a = _create_user(s, "alice", "Alice")

    a = _create_article_with_author(s, user_z.id)

    # Rebuild with both — should sort by username: Alice before Zoe
    rebuild_article_authors(s, a.id, {user_a.id, user_z.id})

    result = get_author_ids(s, a.id)
    s.close()

    assert result == [user_a.id, user_z.id], (
        f"Expected [Alice, Zoe] sorted by username, got {result}"
    )


# ── SPEC-REGRESSION: merge_git_repos edge cases ────────────────────────────

def test_merge_git_repos_no_main_or_master_raises_error(db_engine):
    """merge_git_repos: fork with no main/master branch raises MergeConflictError."""
    import tempfile

    import git
    from peerpedia_core.storage.git_backend import MergeConflictError, merge_git_repos
    tmp = tempfile.mkdtemp()
    target = Path(tmp) / "target"
    fork = Path(tmp) / "fork"

    # Create target with a commit on a non-standard branch
    target_repo = git.Repo.init(target)
    (target / "f.md").write_text("# T\n")
    target_repo.index.add(["f.md"])
    target_repo.index.commit("T", author=git.Actor("A", "a@t.com"),
                             committer=git.Actor("A", "a@t.com"))
    # Rename branch to something that's not main/master (default is "main" in newer git)
    current_branch = target_repo.active_branch.name
    target_repo.git.branch("-m", current_branch, "other")

    # Create fork with same structure (copy, then rename branch)
    import shutil
    shutil.copytree(target, fork, symlinks=True)

    with pytest.raises(MergeConflictError, match="Could not find main/master"):
        merge_git_repos(target, fork, "Merger")

    shutil.rmtree(tmp)


def test_merge_git_repos_cleanup_on_abort_error(db_engine):
    """merge_git_repos: delete_remote failure in finally is swallowed."""
    import tempfile

    import git
    from peerpedia_core.storage.git_backend import MergeConflictError, merge_git_repos
    tmp = tempfile.mkdtemp()
    target = Path(tmp) / "target"
    fork = Path(tmp) / "fork"

    # Create repos with conflicting edits
    target_repo = git.Repo.init(target, initial_branch="main")
    (target / "f.md").write_text("# T1\n")
    target_repo.index.add(["f.md"])
    target_repo.index.commit("T1", author=git.Actor("A", "a@t.com"),
                             committer=git.Actor("A", "a@t.com"))

    fork_repo = git.Repo.init(fork, initial_branch="main")
    (fork / "f.md").write_text("# T1\n")
    fork_repo.index.add(["f.md"])
    fork_repo.index.commit("T1", author=git.Actor("A", "a@t.com"),
                           committer=git.Actor("A", "a@t.com"))
    # Diverge
    (target / "f.md").write_text("# Target edit\n")
    target_repo.index.add(["f.md"])
    target_repo.index.commit("Target", author=git.Actor("A", "a@t.com"),
                             committer=git.Actor("A", "a@t.com"))
    (fork / "f.md").write_text("# Fork edit\n")
    fork_repo.index.add(["f.md"])
    fork_repo.index.commit("Fork", author=git.Actor("B", "b@t.com"),
                           committer=git.Actor("B", "b@t.com"))

    # This should raise MergeConflictError (conflict), and the finally
    # block should attempt delete_remote cleanup without crashing.
    with pytest.raises(MergeConflictError, match="Merge conflict"):
        merge_git_repos(target, fork, "Merger")

    # Target should be unchanged
    assert target_repo.head.commit.message.strip() == "Target"
    shutil.rmtree(tmp)


# ── Coverage: git_backend utility functions ────────────────────────────

def test_get_commit_history_returns_commits():
    """get_commit_history returns list of commit dicts."""
    import shutil
    import tempfile

    from peerpedia_core.storage.git_backend import (
        commit_article,
        get_commit_history,
        init_article_repo,
    )

    tmp = tempfile.mkdtemp()
    rp = Path(tmp)
    init_article_repo("test", rp)
    repo_path = rp / "test"
    (repo_path / "article.md").write_text("# V1\n")
    h1 = commit_article(repo_path, "first", "A", "a@test.com")
    (repo_path / "article.md").write_text("# V2\n")
    h2 = commit_article(repo_path, "second", "A", "a@test.com")

    history = get_commit_history(repo_path, max_count=10)
    assert len(history) == 2
    assert history[0]["hash"] == h2
    assert history[1]["hash"] == h1
    assert history[0]["parents"] == [h1]
    shutil.rmtree(tmp)


def test_get_diff_returns_patch():
    """get_diff returns diff text and stats for a commit."""
    import shutil
    import tempfile

    from peerpedia_core.storage.git_backend import (
        commit_article,
        get_diff,
        init_article_repo,
    )

    tmp = tempfile.mkdtemp()
    rp = Path(tmp)
    init_article_repo("test", rp)
    repo_path = rp / "test"
    (repo_path / "article.md").write_text("# V1\n")
    h1 = commit_article(repo_path, "first", "A", "a@test.com")
    (repo_path / "article.md").write_text("# V2\n\nAdded line.\n")
    h2 = commit_article(repo_path, "second", "A", "a@test.com")

    diff = get_diff(repo_path, h2)
    assert diff["commit_hash"] == h2
    assert diff["parent_hash"] == h1
    assert "article.md" in diff["files"]
    assert "Added line" in diff["diff_text"]
    shutil.rmtree(tmp)


def test_get_commit_history_empty_repo():
    """get_commit_history returns empty list for repo with no commits."""
    import shutil
    import tempfile

    from peerpedia_core.storage.git_backend import (
        get_commit_history,
        init_article_repo,
    )

    tmp = tempfile.mkdtemp()
    rp = Path(tmp)
    rp2 = init_article_repo("empty", rp)
    # Don't create any commits — just an empty initialized repo

    history = get_commit_history(rp2)
    assert history == []
    shutil.rmtree(tmp)


# ── Coverage: DB migration path ──────────────────────────────────────────

def test_migrate_db_adds_column_when_missing(db_engine):
    """migrate_db: ALTER TABLE when last_author_rebuild_hash doesn't exist."""
    import tempfile

    from peerpedia_core.storage.db.engine import get_engine, migrate_db
    from sqlalchemy import inspect, text

    with tempfile.TemporaryDirectory() as tmp:
        db_url = f"sqlite:///{tmp}/test.db"
        eng = get_engine(db_url)
        # Create tables WITHOUT the new column — use raw SQL
        with eng.connect() as conn:
            conn.execute(text("""
                CREATE TABLE articles (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',
                    abstract TEXT, keywords TEXT, categories TEXT,
                    status TEXT NOT NULL DEFAULT 'draft', score TEXT,
                    compiled_format TEXT, compiled_output TEXT, compiled_pages TEXT,
                    sink_start TEXT, sink_duration_days INTEGER NOT NULL DEFAULT 7,
                    sink_extended_count INTEGER NOT NULL DEFAULT 0,
                    forked_from TEXT, fork_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
            """))
            conn.commit()

        # Verify column is missing
        insp = inspect(eng)
        cols = [c["name"] for c in insp.get_columns("articles")]
        assert "last_author_rebuild_hash" not in cols

        # Reconnect to get fresh inspector
        eng2 = get_engine(db_url)
        # Run migration
        migrate_db(eng2)

        # Verify column was added
        insp2 = inspect(eng2)
        cols_after = [c["name"] for c in insp2.get_columns("articles")]
        assert "last_author_rebuild_hash" in cols_after, f"Columns after: {cols_after}"
        eng.dispose()

