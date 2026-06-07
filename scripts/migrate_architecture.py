#!/usr/bin/env python3
"""Migrate database: JSON fields -> relational tables. Idempotent."""
from __future__ import annotations
import argparse, json, shutil, sys, uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

def _utcnow(): return datetime.now(timezone.utc)

def migrate(db_url: str):
    from peerpedia_core.storage.db import models  # noqa: F401
    from peerpedia_core.storage.db.engine import get_engine, get_session, init_db
    from sqlalchemy import text
    engine = get_engine(db_url)
    if not db_url.startswith("sqlite:///"): print("ERROR: SQLite only"); sys.exit(1)
    db_path = Path(db_url.replace("sqlite:///", ""))
    if not db_path.exists(): print(f"DB not found: {db_path}"); return
    backup = db_path.with_suffix(".db.bak")
    shutil.copy2(db_path, backup); print(f"Backup: {backup}")
    init_db(engine); print("New tables created")
    s = get_session(engine)
    ac = [r[1] for r in s.execute(text("PRAGMA table_info('articles')")).fetchall()]
    rc = [r[1] for r in s.execute(text("PRAGMA table_info('reviews')")).fetchall()]
    cc = [r[1] for r in s.execute(text("PRAGMA table_info('citations')")).fetchall()]
    mc = [r[1] for r in s.execute(text("PRAGMA table_info('merge_proposals')")).fetchall()]
    if not any(x in ac+rc+cc+mc for x in ['authors','compiled_output','thread','forward_prob']):
        print("Already migrated"); return
    s.execute(text("PRAGMA foreign_keys = OFF")); s.commit()
    try:
        if 'authors' in ac:
            print("Migrating Article.authors ...")
            rows = s.execute(text("SELECT id, authors FROM articles")).fetchall()
            cnt = 0
            for aid, aj in rows:
                if not aj: continue
                try: authors = json.loads(aj) if isinstance(aj, str) else aj
                except: continue
                for pos, uid in enumerate(authors):
                    s.execute(text("INSERT OR IGNORE INTO article_authors (article_id,author_id,position,created_at) VALUES (:a,:u,:p,:t)"),
                              {"a":aid,"u":uid,"p":pos,"t":_utcnow()}); cnt+=1
            print(f"  {cnt} authors")
        if 'thread' in rc:
            print("Migrating Review.thread ...")
            rows = s.execute(text("SELECT id, thread FROM reviews")).fetchall()
            cnt = 0
            for rid, tj in rows:
                if not tj: continue
                try: msgs = json.loads(tj) if isinstance(tj, str) else tj
                except: continue
                for m in msgs:
                    s.execute(text("INSERT INTO review_messages (id,review_id,parent_id,author_id,content,created_at) VALUES (:i,:r,:p,:a,:c,:t)"),
                              {"i":str(_uuid.uuid4()),"r":rid,"p":m.get("parent_id"),"a":m.get("author_id",""),"c":m.get("content",""),"t":m.get("created_at",_utcnow())}); cnt+=1
            print(f"  {cnt} messages")
        if 'authors' in ac or 'compiled_output' in ac:
            print("Rebuilding articles ...")
            s.execute(text("CREATE TABLE articles_new (id VARCHAR PRIMARY KEY,title VARCHAR NOT NULL DEFAULT '',abstract VARCHAR,keywords TEXT,categories TEXT,status VARCHAR NOT NULL DEFAULT 'draft',score TEXT,compiled_format VARCHAR,sink_start DATETIME,sink_duration_days INTEGER NOT NULL DEFAULT 7,sink_extended_count INTEGER NOT NULL DEFAULT 0,forked_from VARCHAR,fork_count INTEGER NOT NULL DEFAULT 0,created_at DATETIME NOT NULL,updated_at DATETIME NOT NULL)"))
            s.execute(text("INSERT INTO articles_new SELECT id,title,abstract,keywords,categories,status,score,compiled_format,sink_start,sink_duration_days,sink_extended_count,forked_from,fork_count,created_at,updated_at FROM articles"))
            s.execute(text("DROP TABLE articles")); s.execute(text("ALTER TABLE articles_new RENAME TO articles"))
            print("  done")
        if 'thread' in rc:
            print("Rebuilding reviews ...")
            s.execute(text("CREATE TABLE reviews_new (id VARCHAR PRIMARY KEY,article_id VARCHAR NOT NULL,commit_hash VARCHAR NOT NULL,reviewer_id VARCHAR NOT NULL,scope VARCHAR NOT NULL,scores TEXT NOT NULL,contributions TEXT,created_at DATETIME NOT NULL,updated_at DATETIME NOT NULL,FOREIGN KEY(article_id) REFERENCES articles(id),FOREIGN KEY(reviewer_id) REFERENCES users(id),UNIQUE(article_id,reviewer_id,scope,commit_hash))"))
            s.execute(text("INSERT INTO reviews_new SELECT id,article_id,commit_hash,reviewer_id,scope,scores,contributions,created_at,updated_at FROM reviews"))
            s.execute(text("DROP TABLE reviews")); s.execute(text("ALTER TABLE reviews_new RENAME TO reviews"))
            print("  done")
        if 'thread' in mc:
            print("Rebuilding merge_proposals ...")
            s.execute(text("CREATE TABLE merge_proposals_new (id VARCHAR PRIMARY KEY,fork_article_id VARCHAR NOT NULL,target_article_id VARCHAR NOT NULL,proposer_id VARCHAR NOT NULL,status VARCHAR NOT NULL DEFAULT 'open',created_at DATETIME NOT NULL,resolved_at DATETIME,FOREIGN KEY(fork_article_id) REFERENCES articles(id),FOREIGN KEY(target_article_id) REFERENCES articles(id),FOREIGN KEY(proposer_id) REFERENCES users(id))"))
            s.execute(text("INSERT INTO merge_proposals_new SELECT id,fork_article_id,target_article_id,proposer_id,status,created_at,resolved_at FROM merge_proposals"))
            s.execute(text("DROP TABLE merge_proposals")); s.execute(text("ALTER TABLE merge_proposals_new RENAME TO merge_proposals"))
            print("  done")
        if 'forward_prob' in cc:
            print("Rebuilding citations ...")
            s.execute(text("CREATE TABLE citations_new (from_article_id VARCHAR NOT NULL,to_article_id VARCHAR NOT NULL,FOREIGN KEY(from_article_id) REFERENCES articles(id),FOREIGN KEY(to_article_id) REFERENCES articles(id),UNIQUE(from_article_id,to_article_id))"))
            s.execute(text("INSERT INTO citations_new SELECT from_article_id,to_article_id FROM citations"))
            s.execute(text("DROP TABLE citations")); s.execute(text("ALTER TABLE citations_new RENAME TO citations"))
            print("  done")
        s.commit(); print("Migration complete.")
    except Exception as e:
        s.rollback(); print(f"FAILED! Restore: cp {backup} {db_path}"); raise
    finally: s.close()

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--db", default="sqlite:///peerpedia.db"); a = p.parse_args()
    migrate(a.db)
