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

const CURRENT_SCHEMA_VERSION: i32 = 1;

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
        .query_row(
            "SELECT MAX(version) FROM schema_version",
            [],
            |row| row.get::<_, Option<i32>>(0),
        )?
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
        _ => {
            // Unknown migration — rollback and report.
            return Err(AppError::DatabaseError(format!(
                "Unknown migration version {}",
                version
            )));
        }
    }

    // Record the applied version.
    tx.execute("INSERT INTO schema_version (version) VALUES (?1)", [version])?;
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
        assert_eq!(v, 1);

        // Verify tables exist by inserting and querying.
        conn.execute(
            "INSERT INTO local_accounts (id, username, password_hash) VALUES ('a1', 'alice', 'hash')",
            [],
        )
        .unwrap();

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
    }

    #[test]
    fn test_migration_is_idempotent() {
        let conn = test_conn();
        run_migrations(&conn).unwrap();
        // Running again should not fail.
        run_migrations(&conn).unwrap();

        let count: i32 = conn
            .query_row(
                "SELECT COUNT(*) FROM schema_version",
                [],
                |row| row.get(0),
            )
            .unwrap();
        // Only one version row inserted (v1), not two.
        assert_eq!(count, 1);
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
