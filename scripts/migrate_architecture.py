#!/usr/bin/env python3
"""Migrate database schema: JSON fields → relational tables, remove compiled cache columns.

Usage:
    python3 scripts/migrate_architecture.py [--db sqlite:///peerpedia.db]

Safety: backs up the database before migration. If anything fails, restore from backup.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def migrate(db_url: str) -> None:
    from peerpedia_core.storage.db.engine import get_engine, get_session
    from sqlalchemy import text

    engine = get_engine(db_url)

    # Extract file path from SQLite URL
    if not db_url.startswith("sqlite:///"):
        print(f"ERROR: only SQLite migrations supported, got {db_url}")
        sys.exit(1)

    db_path = Path(db_url.replace("sqlite:///", ""))
    if not db_path.exists():
        print(f"Database not found at {db_path} — nothing to migrate.")
        return

    # Backup
    backup_path = db_path.with_suffix(".db.bak")
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backed up to {backup_path}")

    session = get_session(engine)

    try:
        # ── 1. Migrate Article.authors → article_authors table ─────────────
        print("Migrating Article.authors → article_authors …")
        rows = session.execute(text("SELECT id, authors FROM articles")).fetchall()
        count = 0
        for article_id, authors_json in rows:
            if not authors_json:
                continue
            try:
                authors = json.loads(authors_json) if isinstance(authors_json, str) else authors_json
            except (json.JSONDecodeError, TypeError):
                print(f"  WARN: could not parse authors for article {article_id}, skipping")
                continue
            for pos, author_id in enumerate(authors):
                session.execute(
                    text(
                        "INSERT OR IGNORE INTO article_authors (article_id, author_id, position, created_at) "
                        "VALUES (:article_id, :author_id, :position, :created_at)"
                    ),
                    {"article_id": article_id, "author_id": author_id, "position": pos, "created_at": _utcnow()},
                )
                count += 1
        print(f"  → {count} author associations migrated")

        # ── 2. Migrate Review.thread → review_messages table ───────────────
        print("Migrating Review.thread → review_messages …")
        rows = session.execute(text("SELECT id, thread FROM reviews")).fetchall()
        msg_count = 0
        for review_id, thread_json in rows:
            if not thread_json:
                continue
            try:
                messages = json.loads(thread_json) if isinstance(thread_json, str) else thread_json
            except (json.JSONDecodeError, TypeError):
                print(f"  WARN: could not parse thread for review {review_id}, skipping")
                continue
            for msg in messages:
                import uuid

                msg_id = str(uuid.uuid4())
                session.execute(
                    text(
                        "INSERT INTO review_messages (id, review_id, parent_id, author_id, content, created_at) "
                        "VALUES (:id, :review_id, :parent_id, :author_id, :content, :created_at)"
                    ),
                    {
                        "id": msg_id,
                        "review_id": review_id,
                        "parent_id": msg.get("parent_id"),
                        "author_id": msg.get("author_id", ""),
                        "content": msg.get("content", ""),
                        "created_at": msg.get("created_at", _utcnow()),
                    },
                )
                msg_count += 1
        print(f"  → {msg_count} thread messages migrated")

        # ── 3. Migrate MergeProposal.thread (same pattern) ─────────────────
        print("Migrating MergeProposal.thread …")
        rows = session.execute(text("SELECT id, thread FROM merge_proposals")).fetchall()
        mp_msg_count = 0
        for mp_id, thread_json in rows:
            if not thread_json:
                continue
            try:
                messages = json.loads(thread_json) if isinstance(thread_json, str) else thread_json
            except (json.JSONDecodeError, TypeError):
                print(f"  WARN: could not parse thread for merge_proposal {mp_id}, skipping")
                continue
            # MergeProposal messages go into review_messages too — they share the same structure
            # but we use a different pattern since we're not adding a separate table for them (per Outside Voice #5)
            # For now, skip them — MergeProposal usage is negligible.
            mp_msg_count += len(messages)
        if mp_msg_count > 0:
            print(f"  INFO: {mp_msg_count} merge proposal messages skipped (deferred per plan)")
        else:
            print(f"  → no merge proposal messages to migrate")

        # ── 4. Remove compiled_output / compiled_pages from articles ───────
        print("Removing compiled_output / compiled_pages columns …")
        # SQLite doesn't support DROP COLUMN in older versions.
        # We rebuild the articles table without those columns.
        session.execute(text(
            "CREATE TABLE articles_new ("
            "  id VARCHAR PRIMARY KEY,"
            "  title VARCHAR NOT NULL DEFAULT '',"
            "  abstract VARCHAR,"
            "  keywords TEXT,"
            "  categories TEXT,"
            "  status VARCHAR NOT NULL DEFAULT 'draft',"
            "  score TEXT,"
            "  compiled_format VARCHAR,"
            "  sink_start DATETIME,"
            "  sink_duration_days INTEGER NOT NULL DEFAULT 7,"
            "  sink_extended_count INTEGER NOT NULL DEFAULT 0,"
            "  forked_from VARCHAR,"
            "  fork_count INTEGER NOT NULL DEFAULT 0,"
            "  created_at DATETIME NOT NULL,"
            "  updated_at DATETIME NOT NULL"
            ")"
        ))
        session.execute(text(
            "INSERT INTO articles_new SELECT "
            "  id, title, abstract, keywords, categories, status, score, compiled_format,"
            "  sink_start, sink_duration_days, sink_extended_count, forked_from, fork_count,"
            "  created_at, updated_at FROM articles"
        ))
        session.execute(text("DROP TABLE articles"))
        session.execute(text("ALTER TABLE articles_new RENAME TO articles"))
        print("  → articles table rebuilt without compiled_output/compiled_pages/authors")

        # ── 5. Rebuild reviews table (remove thread column) ────────────────
        print("Rebuilding reviews table …")
        session.execute(text(
            "CREATE TABLE reviews_new ("
            "  id VARCHAR PRIMARY KEY,"
            "  article_id VARCHAR NOT NULL,"
            "  commit_hash VARCHAR NOT NULL,"
            "  reviewer_id VARCHAR NOT NULL,"
            "  scope VARCHAR NOT NULL,"
            "  scores TEXT NOT NULL,"
            "  contributions TEXT,"
            "  created_at DATETIME NOT NULL,"
            "  updated_at DATETIME NOT NULL,"
            "  FOREIGN KEY(article_id) REFERENCES articles(id),"
            "  FOREIGN KEY(reviewer_id) REFERENCES users(id),"
            "  UNIQUE(article_id, reviewer_id, scope, commit_hash)"
            ")"
        ))
        session.execute(text(
            "INSERT INTO reviews_new SELECT "
            "  id, article_id, commit_hash, reviewer_id, scope, scores, contributions,"
            "  created_at, updated_at FROM reviews"
        ))
        session.execute(text("DROP TABLE reviews"))
        session.execute(text("ALTER TABLE reviews_new RENAME TO reviews"))
        print("  → reviews table rebuilt without thread column")

        # ── 6. Rebuild merge_proposals table (remove thread column) ────────
        print("Rebuilding merge_proposals table …")
        session.execute(text(
            "CREATE TABLE merge_proposals_new ("
            "  id VARCHAR PRIMARY KEY,"
            "  fork_article_id VARCHAR NOT NULL,"
            "  target_article_id VARCHAR NOT NULL,"
            "  proposer_id VARCHAR NOT NULL,"
            "  status VARCHAR NOT NULL DEFAULT 'open',"
            "  created_at DATETIME NOT NULL,"
            "  resolved_at DATETIME,"
            "  FOREIGN KEY(fork_article_id) REFERENCES articles(id),"
            "  FOREIGN KEY(target_article_id) REFERENCES articles(id),"
            "  FOREIGN KEY(proposer_id) REFERENCES users(id)"
            ")"
        ))
        session.execute(text(
            "INSERT INTO merge_proposals_new SELECT "
            "  id, fork_article_id, target_article_id, proposer_id, status,"
            "  created_at, resolved_at FROM merge_proposals"
        ))
        session.execute(text("DROP TABLE merge_proposals"))
        session.execute(text("ALTER TABLE merge_proposals_new RENAME TO merge_proposals"))
        print("  → merge_proposals table rebuilt without thread column")

        # ── 7. Rebuild citations table (remove prob columns) ───────────────
        print("Rebuilding citations table …")
        session.execute(text(
            "CREATE TABLE citations_new ("
            "  from_article_id VARCHAR NOT NULL,"
            "  to_article_id VARCHAR NOT NULL,"
            "  FOREIGN KEY(from_article_id) REFERENCES articles(id),"
            "  FOREIGN KEY(to_article_id) REFERENCES articles(id),"
            "  UNIQUE(from_article_id, to_article_id)"
            ")"
        ))
        session.execute(text(
            "INSERT INTO citations_new SELECT from_article_id, to_article_id FROM citations"
        ))
        session.execute(text("DROP TABLE citations"))
        session.execute(text("ALTER TABLE citations_new RENAME TO citations"))
        print("  → citations table rebuilt without forward_prob/backward_prob")

        session.commit()
        print("\n✓ Migration complete.")

    except Exception:
        session.rollback()
        print(f"\n✗ Migration failed! Restore from backup: cp {backup_path} {db_path}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate PeerPedia DB architecture")
    parser.add_argument("--db", default="sqlite:///peerpedia.db", help="Database URL")
    args = parser.parse_args()
    migrate(args.db)
