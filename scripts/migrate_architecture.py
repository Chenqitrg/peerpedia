#!/usr/bin/env python3
"""Migrate database schema: JSON fields -> relational tables.

Usage:
    python3 scripts/migrate_architecture.py [--db sqlite:///peerpedia.db]

Idempotent — safe to run multiple times, skips already-migrated data.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _migrate_authors(session, text):
    """Migrate Article.authors JSON -> article_authors table."""
    print("Migrating Article.authors ...")
    rows = session.execute(text("SELECT id, authors FROM articles")).fetchall()
    cnt = 0
    for aid, aj in rows:
        if not aj:
            continue
        try:
            authors = json.loads(aj) if isinstance(aj, str) else aj
        except (json.JSONDecodeError, TypeError):
            continue
        for pos, uid in enumerate(authors):
            session.execute(
                text(
                    "INSERT OR IGNORE INTO article_authors "
                    "(article_id, author_id, position, created_at) "
                    "VALUES (:a, :u, :p, :t)"
                ),
                {"a": aid, "u": uid, "p": pos, "t": _utcnow()},
            )
            cnt += 1
    print(f"  {cnt} author associations migrated")


def _migrate_thread(session, text):
    """Migrate Review.thread JSON -> review_messages table."""
    print("Migrating Review.thread ...")
    rows = session.execute(text("SELECT id, thread FROM reviews")).fetchall()
    cnt = 0
    for rid, tj in rows:
        if not tj:
            continue
        try:
            msgs = json.loads(tj) if isinstance(tj, str) else tj
        except (json.JSONDecodeError, TypeError):
            continue
        for m in msgs:
            session.execute(
                text(
                    "INSERT INTO review_messages "
                    "(id, review_id, parent_id, author_id, content, created_at) "
                    "VALUES (:i, :r, :p, :a, :c, :t)"
                ),
                {
                    "i": str(_uuid.uuid4()),
                    "r": rid,
                    "p": m.get("parent_id"),
                    "a": m.get("author_id", ""),
                    "c": m.get("content", ""),
                    "t": m.get("created_at", _utcnow()),
                },
            )
            cnt += 1
    print(f"  {cnt} thread messages migrated")


def _rebuild_articles(session, text):
    """Rebuild articles table without authors/compiled_output/compiled_pages."""
    print("Rebuilding articles table ...")
    session.execute(
        text(
            "CREATE TABLE articles_new ("
            "  id VARCHAR PRIMARY KEY, title VARCHAR NOT NULL DEFAULT '',"
            "  abstract VARCHAR, keywords TEXT, categories TEXT,"
            "  status VARCHAR NOT NULL DEFAULT 'draft', score TEXT,"
            "  compiled_format VARCHAR, sink_start DATETIME,"
            "  sink_duration_days INTEGER NOT NULL DEFAULT 7,"
            "  sink_extended_count INTEGER NOT NULL DEFAULT 0,"
            "  forked_from VARCHAR, fork_count INTEGER NOT NULL DEFAULT 0,"
            "  created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL"
            ")"
        )
    )
    session.execute(
        text(
            "INSERT INTO articles_new SELECT "
            "id, title, abstract, keywords, categories, status, score, compiled_format,"
            "sink_start, sink_duration_days, sink_extended_count, forked_from, fork_count,"
            "created_at, updated_at FROM articles"
        )
    )
    session.execute(text("DROP TABLE articles"))
    session.execute(text("ALTER TABLE articles_new RENAME TO articles"))
    print("  done")


def _rebuild_reviews(session, text):
    """Rebuild reviews table without thread column."""
    print("Rebuilding reviews table ...")
    session.execute(
        text(
            "CREATE TABLE reviews_new ("
            "  id VARCHAR PRIMARY KEY, article_id VARCHAR NOT NULL,"
            "  commit_hash VARCHAR NOT NULL, reviewer_id VARCHAR NOT NULL,"
            "  scope VARCHAR NOT NULL, scores TEXT NOT NULL,"
            "  contributions TEXT, created_at DATETIME NOT NULL,"
            "  updated_at DATETIME NOT NULL,"
            "  FOREIGN KEY(article_id) REFERENCES articles(id),"
            "  FOREIGN KEY(reviewer_id) REFERENCES users(id),"
            "  UNIQUE(article_id, reviewer_id, scope, commit_hash)"
            ")"
        )
    )
    session.execute(
        text(
            "INSERT INTO reviews_new SELECT "
            "id, article_id, commit_hash, reviewer_id, scope, scores, contributions,"
            "created_at, updated_at FROM reviews"
        )
    )
    session.execute(text("DROP TABLE reviews"))
    session.execute(text("ALTER TABLE reviews_new RENAME TO reviews"))
    print("  done")


def _rebuild_merge_proposals(session, text):
    """Rebuild merge_proposals table without thread column."""
    print("Rebuilding merge_proposals table ...")
    session.execute(
        text(
            "CREATE TABLE merge_proposals_new ("
            "  id VARCHAR PRIMARY KEY, fork_article_id VARCHAR NOT NULL,"
            "  target_article_id VARCHAR NOT NULL, proposer_id VARCHAR NOT NULL,"
            "  status VARCHAR NOT NULL DEFAULT 'open',"
            "  created_at DATETIME NOT NULL, resolved_at DATETIME,"
            "  FOREIGN KEY(fork_article_id) REFERENCES articles(id),"
            "  FOREIGN KEY(target_article_id) REFERENCES articles(id),"
            "  FOREIGN KEY(proposer_id) REFERENCES users(id)"
            ")"
        )
    )
    session.execute(
        text(
            "INSERT INTO merge_proposals_new SELECT "
            "id, fork_article_id, target_article_id, proposer_id, status,"
            "created_at, resolved_at FROM merge_proposals"
        )
    )
    session.execute(text("DROP TABLE merge_proposals"))
    session.execute(text("ALTER TABLE merge_proposals_new RENAME TO merge_proposals"))
    print("  done")


def _rebuild_citations(session, text):
    """Rebuild citations table without forward_prob/backward_prob."""
    print("Rebuilding citations table ...")
    session.execute(
        text(
            "CREATE TABLE citations_new ("
            "  from_article_id VARCHAR NOT NULL, to_article_id VARCHAR NOT NULL,"
            "  FOREIGN KEY(from_article_id) REFERENCES articles(id),"
            "  FOREIGN KEY(to_article_id) REFERENCES articles(id),"
            "  UNIQUE(from_article_id, to_article_id)"
            ")"
        )
    )
    session.execute(
        text(
            "INSERT INTO citations_new SELECT from_article_id, to_article_id FROM citations"
        )
    )
    session.execute(text("DROP TABLE citations"))
    session.execute(text("ALTER TABLE citations_new RENAME TO citations"))
    print("  done")


def migrate(db_url: str) -> None:
    """Run the architecture migration. Idempotent."""
    from peerpedia_core.storage.db import models  # noqa: F401
    from peerpedia_core.storage.db.engine import get_engine, get_session, init_db
    from sqlalchemy import text

    engine = get_engine(db_url)

    if not db_url.startswith("sqlite:///"):
        print("ERROR: only SQLite supported")
        sys.exit(1)

    db_path = Path(db_url.replace("sqlite:///", ""))
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return

    backup_path = db_path.with_suffix(".db.bak")
    shutil.copy2(db_path, backup_path)
    print(f"Backup: {backup_path}")

    init_db(engine)
    print("New tables ensured")

    s = get_session(engine)

    # Idempotency check
    ac = [r[1] for r in s.execute(text("PRAGMA table_info('articles')")).fetchall()]
    rc = [r[1] for r in s.execute(text("PRAGMA table_info('reviews')")).fetchall()]
    cc_cols = [r[1] for r in s.execute(text("PRAGMA table_info('citations')")).fetchall()]
    mc = [r[1] for r in s.execute(text("PRAGMA table_info('merge_proposals')")).fetchall()]

    needs = any(
        x in ac + rc + cc_cols + mc
        for x in ["authors", "compiled_output", "thread", "forward_prob"]
    )
    if not needs:
        print("Already migrated — nothing to do.")
        s.close()
        return

    s.execute(text("PRAGMA foreign_keys = OFF"))
    s.commit()

    try:
        if "authors" in ac:
            _migrate_authors(s, text)
        if "thread" in rc:
            _migrate_thread(s, text)
        if "authors" in ac or "compiled_output" in ac:
            _rebuild_articles(s, text)
        if "thread" in rc:
            _rebuild_reviews(s, text)
        if "thread" in mc:
            _rebuild_merge_proposals(s, text)
        if "forward_prob" in cc_cols:
            _rebuild_citations(s, text)

        s.commit()
        print("\n✓ Migration complete.")
    except Exception:
        s.rollback()
        print(f"\n✗ FAILED! Restore: cp {backup_path} {db_path}")
        raise
    finally:
        s.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate PeerPedia DB")
    parser.add_argument("--db", default="sqlite:///peerpedia.db")
    args = parser.parse_args()
    migrate(args.db)
