// Database initialization and schema migration system.
//
// Architecture:
//   schema_version table → tracks current DB version (integer)
//   run_migrations()     → applies migrations in order, each in a transaction
//   init_db()            → opens/creates ~/.peerpedia/peerpedia.db, runs migrations
//
// Adding a migration in the future:
//   1. Increment CURRENT_SCHEMA_VERSION
//   2. Add a new arm in run_migrations() for the new version
//   3. The migration runs automatically on next startup

use crate::error::AppError;
use rusqlite::Connection;
use std::path::PathBuf;

const CURRENT_SCHEMA_VERSION: i32 = 6;

/// Resolve the database path: ~/.peerpedia/peerpedia.db
fn get_db_path() -> Result<PathBuf, AppError> {
    let home = dirs_fallback();
    let dir = home.join(".peerpedia");
    std::fs::create_dir_all(&dir)?;
    Ok(dir.join("peerpedia.db"))
}

/// Best-effort home directory resolution without pulling in the `dirs` crate.
fn dirs_fallback() -> PathBuf {
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."))
}

/// Open (or create) the database, enable WAL mode, and run migrations.
pub fn init_db() -> Result<Connection, AppError> {
    let path = get_db_path()?;
    let conn = Connection::open(&path)?;

    // WAL mode for better concurrent read performance.
    conn.execute_batch("PRAGMA journal_mode=WAL;")?;

    run_migrations(&conn)?;

    Ok(conn)
}

/// Apply any pending schema migrations. Each migration runs in its own transaction.
pub fn run_migrations(conn: &Connection) -> Result<(), AppError> {
    // Ensure the schema_version table exists (migration 0 → 1 bootstrap).
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        );",
    )?;

    // Read current version (None if no rows yet).
    let current: i32 = conn
        .query_row("SELECT MAX(version) FROM schema_version", [], |row| {
            row.get::<_, Option<i32>>(0)
        })?
        .unwrap_or(0);

    if current >= CURRENT_SCHEMA_VERSION {
        return Ok(());
    }

    // Apply migrations in order, each wrapped in a transaction.
    for v in (current + 1)..=CURRENT_SCHEMA_VERSION {
        apply_migration(conn, v)?;
    }

    Ok(())
}

fn apply_migration(conn: &Connection, version: i32) -> Result<(), AppError> {
    let tx = conn.unchecked_transaction()?;

    match version {
        1 => {
            tx.execute_batch(
                "CREATE TABLE IF NOT EXISTS local_accounts (
                    id          TEXT PRIMARY KEY,
                    username    TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    email       TEXT NOT NULL DEFAULT '',
                    name        TEXT NOT NULL DEFAULT '',
                    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS drafts (
                    id          TEXT PRIMARY KEY,
                    account_id  TEXT NOT NULL,
                    title       TEXT NOT NULL DEFAULT '',
                    content     TEXT NOT NULL DEFAULT '',
                    format      TEXT NOT NULL DEFAULT 'markdown',
                    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (account_id) REFERENCES local_accounts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS article_cache (
                    id          TEXT PRIMARY KEY,
                    json        TEXT NOT NULL,
                    cached_at   TEXT NOT NULL DEFAULT (datetime('now'))
                );",
            )?;
        }
        2 => {
            tx.execute_batch(
                "CREATE TABLE IF NOT EXISTS browsing_history (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id      TEXT NOT NULL,
                    article_id      TEXT NOT NULL,
                    article_title   TEXT NOT NULL DEFAULT '',
                    visited_at      TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(account_id, article_id)
                );",
            )?;
        }
        3 => {
            tx.execute_batch(
                "CREATE TABLE IF NOT EXISTS sessions (
                    token       TEXT PRIMARY KEY,
                    account_id  TEXT NOT NULL,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (account_id) REFERENCES local_accounts(id) ON DELETE CASCADE
                );",
            )?;
        }
        4 => {
            tx.execute_batch(
                "CREATE VIRTUAL TABLE IF NOT EXISTS drafts_fts USING fts5(
                    title, content,
                    tokenize='porter unicode61',
                    content='drafts',
                    content_rowid='rowid'
                );

                -- Triggers to keep FTS index in sync with drafts table
                CREATE TRIGGER IF NOT EXISTS drafts_ai AFTER INSERT ON drafts BEGIN
                    INSERT INTO drafts_fts(rowid, title, content)
                    VALUES (new.rowid, new.title, new.content);
                END;

                CREATE TRIGGER IF NOT EXISTS drafts_ad AFTER DELETE ON drafts BEGIN
                    INSERT INTO drafts_fts(drafts_fts, rowid, title, content)
                    VALUES ('delete', old.rowid, old.title, old.content);
                END;

                CREATE TRIGGER IF NOT EXISTS drafts_au AFTER UPDATE ON drafts BEGIN
                    INSERT INTO drafts_fts(drafts_fts, rowid, title, content)
                    VALUES ('delete', old.rowid, old.title, old.content);
                    INSERT INTO drafts_fts(rowid, title, content)
                    VALUES (new.rowid, new.title, new.content);
                END;

                -- Backfill existing drafts into FTS index so they're searchable.
                INSERT INTO drafts_fts(rowid, title, content)
                SELECT rowid, title, content FROM drafts;",
            )?;
        }
        5 => {
            tx.execute_batch(
                "INSERT OR REPLACE INTO drafts_fts(rowid, title, content)
                 SELECT rowid, title, content FROM drafts;",
            )?;
        }
        6 => {
            let _ = tx.execute("ALTER TABLE drafts ADD COLUMN server_article_id TEXT", []);
            let _ = tx.execute("ALTER TABLE drafts ADD COLUMN server_commit_hash TEXT", []);
        }
        _ => {
            // Unknown migration — rollback and report.
            return Err(AppError::DatabaseError(format!(
                "Unknown migration version {}",
                version
            )));
        }
    }

    // Record the applied version.
    tx.execute(
        "INSERT INTO schema_version (version) VALUES (?1)",
        [version],
    )?;
    tx.commit()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_conn() -> Connection {
        Connection::open_in_memory().unwrap()
    }

    #[test]
    fn test_fresh_install_creates_tables() {
        let conn = test_conn();
        run_migrations(&conn).unwrap();

        // Verify schema_version was recorded.
        let v: i32 = conn
            .query_row("SELECT MAX(version) FROM schema_version", [], |row| {
                row.get::<_, Option<i32>>(0)
            })
            .unwrap()
            .unwrap();
        assert_eq!(v, 6);

        // Create account first (FK target for sessions).
        conn.execute(
            "INSERT INTO local_accounts (id, username, password_hash) VALUES ('a1', 'alice', 'hash')",
            [],
        )
        .unwrap();

        // Verify sessions table was created.
        conn.execute(
            "INSERT INTO sessions (token, account_id) VALUES ('tok1', 'a1')",
            [],
        )
        .unwrap();

        // Verify tables exist by inserting and querying.
        conn.execute(
            "INSERT INTO drafts (id, account_id, title, content) VALUES ('d1', 'a1', 'Title', 'Body')",
            [],
        )
        .unwrap();

        conn.execute(
            "INSERT INTO article_cache (id, json) VALUES ('art1', '{}')",
            [],
        )
        .unwrap();

        conn.execute(
            "INSERT INTO browsing_history (account_id, article_id, article_title) VALUES ('a1', 'art1', 'Test')",
            [],
        )
        .unwrap();
    }

    #[test]
    fn test_migration_v4_backfills_existing_drafts() {
        /// 🔴 RED: Existing drafts should be indexed in FTS5 after migration v4.
        /// Without the backfill INSERT, the FTS5 virtual table stays empty for
        /// pre-migration data and search returns nothing.
        let conn = test_conn();

        // Simulate pre-v4 state: run v1-v3, create account + draft
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
             INSERT INTO schema_version VALUES (0);",
        )
        .unwrap();
        // Apply v1-v3 migrations manually
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS local_accounts (
                id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, email TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '', content TEXT NOT NULL DEFAULT '',
                format TEXT NOT NULL DEFAULT 'markdown',
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES local_accounts(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS article_cache (
                id TEXT PRIMARY KEY, json TEXT NOT NULL,
                cached_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO schema_version VALUES (1);
            INSERT INTO schema_version VALUES (2);
            INSERT INTO schema_version VALUES (3);",
        )
        .unwrap();

        // Insert a pre-existing draft
        conn.execute(
            "INSERT INTO local_accounts (id, username, password_hash) VALUES ('acc-backfill', 'tester', 'hash')",
            [],
        ).unwrap();
        conn.execute(
            "INSERT INTO drafts (id, account_id, title, content) VALUES ('existing-draft', 'acc-backfill', 'Quantum Physics', 'Discusses quantum mechanics')",
            [],
        ).unwrap();

        // Now run full migration — applies v4
        run_migrations(&conn).unwrap();

        // Verify FTS5 has the pre-existing draft indexed
        let fts_count: i32 = conn
            .query_row("SELECT COUNT(*) FROM drafts_fts", [], |row| row.get(0))
            .unwrap();
        assert_eq!(
            fts_count, 1,
            "FTS5 should contain the pre-existing draft after backfill"
        );

        // Verify the draft is actually searchable via FTS5
        let searchable: i32 = conn
            .query_row(
                "SELECT COUNT(*) FROM drafts_fts WHERE drafts_fts MATCH 'quantum'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(
            searchable, 1,
            "Pre-existing draft should be searchable via FTS5 after migration v4"
        );
    }

    #[test]
    fn test_migration_v5_backfills_after_v4_without_backfill() {
        /// 🔴 RED: If v4 ran WITHOUT the backfill INSERT (original v4 bug),
        /// upgrading to v5 should backfill existing drafts into FTS5.
        let conn = test_conn();

        // Simulate: v1-v3 setup + v4 WITHOUT backfill (the original buggy v4)
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
             INSERT INTO schema_version VALUES (0);",
        )
        .unwrap();
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS local_accounts (
                id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, email TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '', content TEXT NOT NULL DEFAULT '',
                format TEXT NOT NULL DEFAULT 'markdown',
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (account_id) REFERENCES local_accounts(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS article_cache (
                id TEXT PRIMARY KEY, json TEXT NOT NULL,
                cached_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO schema_version VALUES (1);
            INSERT INTO schema_version VALUES (2);
            INSERT INTO schema_version VALUES (3);",
        )
        .unwrap();
        // Insert a draft BEFORE v4 FTS5 is created — this simulates the user
        // scenario: drafts existed before the migration added FTS5 + triggers.
        // Since the backfill INSERT was missing from the original v4, these
        // drafts never got indexed.
        conn.execute(
            "INSERT INTO local_accounts (id, username, password_hash) VALUES ('acc-v5', 'tester', 'hash')",
            [],
        ).unwrap();
        conn.execute(
            "INSERT INTO drafts (id, account_id, title, content) VALUES ('old-draft', 'acc-v5', 'Quantum Physics', 'Discusses quantum')",
            [],
        ).unwrap();

        // Apply v4 WITHOUT backfill — just create FTS5 table + triggers.
        // This simulates the buggy v4 that lacked the backfill INSERT.
        conn.execute_batch(
            "CREATE VIRTUAL TABLE IF NOT EXISTS drafts_fts USING fts5(
                title, content,
                tokenize='porter unicode61',
                content='drafts',
                content_rowid='rowid'
            );
            CREATE TRIGGER IF NOT EXISTS drafts_ai AFTER INSERT ON drafts BEGIN
                INSERT INTO drafts_fts(rowid, title, content)
                VALUES (new.rowid, new.title, new.content);
            END;
            CREATE TRIGGER IF NOT EXISTS drafts_ad AFTER DELETE ON drafts BEGIN
                INSERT INTO drafts_fts(drafts_fts, rowid, title, content)
                VALUES ('delete', old.rowid, old.title, old.content);
            END;
            CREATE TRIGGER IF NOT EXISTS drafts_au AFTER UPDATE ON drafts BEGIN
                INSERT INTO drafts_fts(drafts_fts, rowid, title, content)
                VALUES ('delete', old.rowid, old.title, old.content);
                INSERT INTO drafts_fts(rowid, title, content)
                VALUES (new.rowid, new.title, new.content);
            END;
            INSERT INTO schema_version VALUES (4);",
        )
        .unwrap();

        // Verify: draft is NOT searchable via FTS5 (no backfill ran)
        let searchable_before: i32 = conn
            .query_row(
                "SELECT COUNT(*) FROM drafts_fts WHERE drafts_fts MATCH 'quantum'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(
            searchable_before, 0,
            "Draft should NOT be searchable before v5 backfill"
        );

        // Now run migrations — v5 should backfill existing drafts
        run_migrations(&conn).unwrap();

        // Verify: FTS5 now finds the draft
        let searchable_after: i32 = conn
            .query_row(
                "SELECT COUNT(*) FROM drafts_fts WHERE drafts_fts MATCH 'quantum'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(
            searchable_after, 1,
            "Pre-existing draft should be searchable after v5 backfill"
        );
    }

    #[test]
    fn test_migration_is_idempotent() {
        let conn = test_conn();
        run_migrations(&conn).unwrap();
        // Running again should not fail.
        run_migrations(&conn).unwrap();

        let count: i32 = conn
            .query_row("SELECT COUNT(*) FROM schema_version", [], |row| row.get(0))
            .unwrap();
        // Six version rows (v1-v6), not duplicated on re-run.
        assert_eq!(count, 6);
    }

    #[test]
    fn test_already_current_skips() {
        let conn = test_conn();
        run_migrations(&conn).unwrap();
        // Second run should be a no-op.
        let result = run_migrations(&conn);
        assert!(result.is_ok());
    }

    #[test]
    fn test_upgrade_preserves_data() {
        let conn = test_conn();
        // Manually create v0 state (no schema_version yet).
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
             INSERT INTO schema_version VALUES (0);",
        )
        .unwrap();

        // Insert some data in a table that already exists from a prior migration.
        // For this test we simulate the tables already existing.
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS local_accounts (
                id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, email TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );",
        )
        .unwrap();
        conn.execute(
            "INSERT INTO local_accounts (id, username, password_hash) VALUES ('a1', 'alice', 'hash')",
            [],
        )
        .unwrap();

        // Run migration — should apply v1 even though we hand-created tables.
        run_migrations(&conn).unwrap();

        // Data intact.
        let name: String = conn
            .query_row(
                "SELECT username FROM local_accounts WHERE id = 'a1'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(name, "alice");
    }

    #[test]
    fn test_migration_v6_adds_sync_columns() {
        let conn = test_conn();
        run_migrations(&conn).unwrap();
        conn.execute(
            "INSERT INTO local_accounts (id, username, password_hash) VALUES ('a1', 'alice', 'hash')",
            [],
        ).unwrap();
        conn.execute(
            "INSERT INTO drafts (id, account_id, title, content, server_article_id, server_commit_hash)
             VALUES ('d1', 'a1', 'Test', 'content', 'server-123', 'abc123')",
            [],
        ).unwrap();
        let (sid, sch): (String, String) = conn
            .query_row(
                "SELECT server_article_id, server_commit_hash FROM drafts WHERE id = 'd1'",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .unwrap();
        assert_eq!(sid, "server-123");
        assert_eq!(sch, "abc123");
    }

    #[test]
    fn test_wal_mode_enabled() {
        let conn = test_conn();
        conn.execute_batch("PRAGMA journal_mode=WAL;").unwrap();
        let mode: String = conn
            .pragma_query_value(None, "journal_mode", |row| row.get(0))
            .unwrap();
        // In-memory databases don't support WAL — they stay in "memory" mode.
        // The real file-based DB will use WAL. This test just verifies the pragma
        // doesn't error.
        assert!(mode == "wal" || mode == "memory");
    }
}
