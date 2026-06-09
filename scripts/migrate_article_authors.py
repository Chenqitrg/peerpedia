#!/usr/bin/env python3
"""One-shot migration: create article_authors table and migrate JSON data.

Usage:
    python scripts/migrate_article_authors.py [--db sqlite:///peerpedia.db]

After running this script, the Article.authors JSON column can be removed
from the model. The data is now in the article_authors join table.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from peerpedia_core.storage.db.engine import Base, get_engine
from peerpedia_core.storage.db.models import ArticleAuthor


def migrate(db_url: str) -> dict:
    """Create article_authors table and migrate all existing JSON data.

    Returns a dict with migration statistics.
    """
    engine = get_engine(db_url)
    # Create new table
    ArticleAuthor.__table__.create(engine, checkfirst=True)
    print("✓ article_authors table ready")

    from peerpedia_core.storage.db.engine import get_session
    session = get_session(engine)

    stats = {"articles_scanned": 0, "authors_migrated": 0, "skipped": 0}
    session.autoflush = False

    try:
        # Read old JSON column via raw SQL (column removed from ORM model)
        from sqlalchemy import text
        result = session.execute(text("SELECT id, authors FROM articles"))
        rows = list(result.fetchall())
        stats["articles_scanned"] = len(rows)

        # Pre-fetch valid user IDs
        valid_user_ids = {row[0] for row in session.execute(text("SELECT id FROM users")).fetchall()}

        for row in rows:
            article_id = row[0]
            author_ids = row[1]

            if not author_ids:
                stats["skipped"] += 1
                continue

            # Parse JSON string from SQLite
            if isinstance(author_ids, str):
                try:
                    author_ids = json.loads(author_ids)
                except json.JSONDecodeError:
                    print(f"  WARNING: could not parse authors for article {article_id}")
                    stats["skipped"] += 1
                    continue

            if not isinstance(author_ids, list):
                print(f"  WARNING: unexpected authors type for {article_id}: {type(author_ids)}")
                stats["skipped"] += 1
                continue

            for pos, author_id in enumerate(author_ids):
                # Skip invalid foreign keys
                if author_id not in valid_user_ids:
                    print(f"  WARNING: skipping unknown author_id {author_id} for article {article_id}")
                    continue

                session.add(ArticleAuthor(
                    article_id=article_id,
                    author_id=author_id,
                    position=pos,
                ))
                stats["authors_migrated"] += 1

        session.commit()
        print(f"✓ Migrated {stats['authors_migrated']} author relations "
              f"from {stats['articles_scanned']} articles "
              f"({stats['skipped']} articles had no authors)")

        # Verify
        aa_count = session.query(ArticleAuthor).count()
        print(f"✓ Verification: {aa_count} rows in article_authors table")

    except Exception as e:
        session.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        session.close()
        engine.dispose()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrate Article.authors JSON → article_authors join table")
    parser.add_argument("--db", default="sqlite:///peerpedia.db",
                        help="Database URL (default: sqlite:///peerpedia.db)")
    args = parser.parse_args()

    print(f"Migrating: {args.db}")
    migrate(args.db)
    print("\n✅ Migration complete. You can now remove the authors column from the Article model.")


if __name__ == "__main__":
    main()
