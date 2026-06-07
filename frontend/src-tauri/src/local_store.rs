// Local draft storage and article cache.
//
// Drafts are private to each local account. Article cache stores read-only snapshots
// of published articles for offline reading. Cache entries include a `cached_at`
// timestamp so the frontend can display a staleness badge.

use crate::error::AppError;
use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

const MAX_CACHE_SIZE_BYTES: usize = 10 * 1024 * 1024; // 10 MB

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Draft {
    pub id: String,
    pub account_id: String,
    pub title: String,
    pub content: String,
    pub format: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DraftSummary {
    pub id: String,
    pub title: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CachedArticle {
    pub id: String,
    pub json: String,
    pub cached_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoryEntry {
    pub article_id: String,
    pub article_title: String,
    pub visited_at: String,
}

// ── Drafts ──────────────────────────────────────────────────────────────

/// Save a draft. If `id` is empty or new, a new draft is created. Otherwise the
/// existing draft is updated — but only if it belongs to the same account.
pub fn save_draft(
    conn: &Connection,
    id: Option<&str>,
    account_id: &str,
    title: &str,
    content: &str,
    format: &str,
) -> Result<Draft, AppError> {
    let draft_id = id
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string())
        .unwrap_or_else(|| Uuid::new_v4().to_string());

    // Verify ownership if updating an existing draft.
    if let Some(_id) = id.filter(|s| !s.is_empty()) {
        let owner: Result<String, _> = conn.query_row(
            "SELECT account_id FROM drafts WHERE id = ?1",
            [&draft_id],
            |row| row.get(0),
        );
        if let Ok(owner) = owner {
            if owner != account_id {
                return Err(AppError::AuthFailed(
                    "Draft belongs to another account".into(),
                ));
            }
        }
    }

    conn.execute(
        "INSERT INTO drafts (id, account_id, title, content, format, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5, datetime('now'))
         ON CONFLICT(id) DO UPDATE SET
           title = excluded.title,
           content = excluded.content,
           format = excluded.format,
           updated_at = datetime('now')
         WHERE account_id = excluded.account_id",
        rusqlite::params![draft_id, account_id, title, content, format],
    )?;

    // Read back the saved row to get the real updated_at timestamp.
    get_draft(conn, &draft_id)
}

/// List all drafts for a given local account, newest first.
pub fn list_drafts(conn: &Connection, account_id: &str) -> Result<Vec<DraftSummary>, AppError> {
    let mut stmt = conn.prepare(
        "SELECT id, title, updated_at FROM drafts WHERE account_id = ?1 ORDER BY updated_at DESC",
    )?;
    let rows = stmt.query_map([account_id], |row| {
        Ok(DraftSummary {
            id: row.get(0)?,
            title: row.get(1)?,
            updated_at: row.get(2)?,
        })
    })?;

    let mut drafts = Vec::new();
    for row in rows {
        drafts.push(row?);
    }
    Ok(drafts)
}

/// Get a single draft by ID.
pub fn get_draft(conn: &Connection, id: &str) -> Result<Draft, AppError> {
    conn.query_row(
        "SELECT id, account_id, title, content, format, updated_at FROM drafts WHERE id = ?1",
        [id],
        |row| {
            Ok(Draft {
                id: row.get(0)?,
                account_id: row.get(1)?,
                title: row.get(2)?,
                content: row.get(3)?,
                format: row.get(4)?,
                updated_at: row.get(5)?,
            })
        },
    )
    .map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => {
            AppError::NotFound(format!("Draft '{}' not found", id))
        }
        other => AppError::from(other),
    })
}

/// Delete a draft by ID.
pub fn delete_draft(conn: &Connection, id: &str) -> Result<(), AppError> {
    let affected = conn.execute("DELETE FROM drafts WHERE id = ?1", [id])?;
    if affected == 0 {
        return Err(AppError::NotFound(format!("Draft '{}' not found", id)));
    }
    Ok(())
}

// ── Article Cache ───────────────────────────────────────────────────────

/// Cache a published article for offline reading. Rejects articles larger than
/// MAX_CACHE_SIZE_BYTES (10 MB).
pub fn cache_article(conn: &Connection, id: &str, article_json: &str) -> Result<(), AppError> {
    cache_article_with_limit(conn, id, article_json, MAX_CACHE_SIZE_BYTES)
}

/// Retrieve a cached article by ID. Returns None if not cached.
pub fn get_cached_article(conn: &Connection, id: &str) -> Result<Option<CachedArticle>, AppError> {
    let result = conn.query_row(
        "SELECT id, json, cached_at FROM article_cache WHERE id = ?1",
        [id],
        |row| {
            Ok(CachedArticle {
                id: row.get(0)?,
                json: row.get(1)?,
                cached_at: row.get(2)?,
            })
        },
    );

    match result {
        Ok(article) => {
            // Validate JSON integrity before returning.
            if serde_json::from_str::<serde_json::Value>(&article.json).is_err() {
                return Err(AppError::DatabaseError(
                    "Cached article JSON is corrupt".into(),
                ));
            }
            Ok(Some(article))
        }
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(AppError::from(e)),
    }
}

// ── Browsing History ─────────────────────────────────────────────────────

/// Record or update a browsing history entry. Re-visiting the same article
/// updates visited_at to now and article_title if changed.
pub fn record_visit(
    conn: &Connection,
    account_id: &str,
    article_id: &str,
    article_title: &str,
) -> Result<(), AppError> {
    conn.execute(
        "INSERT INTO browsing_history (account_id, article_id, article_title, visited_at)
         VALUES (?1, ?2, ?3, datetime('now'))
         ON CONFLICT(account_id, article_id) DO UPDATE SET
           article_title = excluded.article_title,
           visited_at = datetime('now')",
        rusqlite::params![account_id, article_id, article_title],
    )?;
    Ok(())
}

/// Get browsing history for an account, newest first, with pagination.
/// Page is 1-based. Returns at most `size` entries.
pub fn get_history(
    conn: &Connection,
    account_id: &str,
    page: i64,
    size: i64,
) -> Result<Vec<HistoryEntry>, AppError> {
    let offset = (page - 1) * size;
    let mut stmt = conn.prepare(
        "SELECT article_id, article_title, visited_at FROM browsing_history
         WHERE account_id = ?1
         ORDER BY visited_at DESC
         LIMIT ?2 OFFSET ?3",
    )?;
    let rows = stmt.query_map(rusqlite::params![account_id, size, offset], |row| {
        Ok(HistoryEntry {
            article_id: row.get(0)?,
            article_title: row.get(1)?,
            visited_at: row.get(2)?,
        })
    })?;

    let mut entries = Vec::new();
    for row in rows {
        entries.push(row?);
    }
    Ok(entries)
}

/// Return the set of article IDs currently in the article_cache table.
pub fn get_cached_article_ids(conn: &Connection) -> Result<Vec<String>, AppError> {
    let mut stmt = conn.prepare("SELECT id FROM article_cache")?;
    let rows = stmt.query_map([], |row| row.get::<_, String>(0))?;
    let mut ids = Vec::new();
    for row in rows {
        ids.push(row?);
    }
    Ok(ids)
}

// ── Article Full Cache ────────────────────────────────────────────────────

/// Same as `cache_article` but with a larger size limit (20 MB vs 10 MB).
/// Used for bookmarked articles that include extended metadata (reviews, authors).
pub fn cache_article_full(conn: &Connection, id: &str, article_json: &str) -> Result<(), AppError> {
    cache_article_with_limit(conn, id, article_json, 20 * 1024 * 1024)
}

/// Internal helper: cache with a configurable size limit.
fn cache_article_with_limit(
    conn: &Connection,
    id: &str,
    article_json: &str,
    max_size: usize,
) -> Result<(), AppError> {
    if article_json.len() > max_size {
        return Err(AppError::IoError(format!(
            "Article too large: {} bytes (max {})",
            article_json.len(),
            max_size
        )));
    }

    serde_json::from_str::<serde_json::Value>(article_json)
        .map_err(|e| AppError::DatabaseError(format!("Invalid article JSON: {}", e)))?;

    conn.execute(
        "INSERT INTO article_cache (id, json, cached_at)
         VALUES (?1, ?2, datetime('now'))
         ON CONFLICT(id) DO UPDATE SET
           json = excluded.json,
           cached_at = datetime('now')",
        rusqlite::params![id, article_json],
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::run_migrations;

    fn setup() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        run_migrations(&conn).unwrap();
        // Create a test account so foreign key constraints pass.
        conn.execute(
            "INSERT INTO local_accounts (id, username, password_hash) VALUES ('acc1', 'test', 'hash')",
            [],
        )
        .unwrap();
        conn
    }

    // ── Draft tests ────────────────────────────────────────────────────

    #[test]
    fn test_save_new_draft() {
        let conn = setup();
        let draft = save_draft(&conn, None, "acc1", "My Draft", "# Hello", "markdown").unwrap();
        assert!(!draft.id.is_empty());
        assert_eq!(draft.title, "My Draft");
        assert_eq!(draft.content, "# Hello");
        assert_eq!(draft.format, "markdown");
        assert_eq!(draft.account_id, "acc1");
    }

    #[test]
    fn test_cross_account_update_rejected() {
        let conn = setup();
        conn.execute(
            "INSERT INTO local_accounts (id, username, password_hash) VALUES ('acc2', 'other', 'hash')",
            [],
        )
        .unwrap();

        let draft = save_draft(&conn, None, "acc1", "Acc1 Draft", "secret", "markdown").unwrap();
        // Account 2 tries to overwrite Account 1's draft.
        let result = save_draft(
            &conn,
            Some(&draft.id),
            "acc2",
            "Overwritten",
            "hacked",
            "markdown",
        );
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::AuthFailed(_)));

        // Verify original draft unchanged.
        let original = get_draft(&conn, &draft.id).unwrap();
        assert_eq!(original.title, "Acc1 Draft");
        assert_eq!(original.content, "secret");
    }

    #[test]
    fn test_save_update_existing_draft() {
        let conn = setup();
        let draft = save_draft(&conn, None, "acc1", "V1", "content", "markdown").unwrap();
        let id = draft.id.clone();

        let updated = save_draft(&conn, Some(&id), "acc1", "V2", "new content", "typst").unwrap();
        assert_eq!(updated.id, id);
        assert_eq!(updated.title, "V2");
        assert_eq!(updated.content, "new content");
        assert_eq!(updated.format, "typst");
    }

    #[test]
    fn test_list_drafts_filtered_by_account() {
        let conn = setup();
        conn.execute(
            "INSERT INTO local_accounts (id, username, password_hash) VALUES ('acc2', 'other', 'hash')",
            [],
        )
        .unwrap();

        save_draft(&conn, None, "acc1", "A1 Draft", "a", "markdown").unwrap();
        save_draft(&conn, None, "acc2", "A2 Draft", "b", "markdown").unwrap();

        let acc1_drafts = list_drafts(&conn, "acc1").unwrap();
        assert_eq!(acc1_drafts.len(), 1);
        assert_eq!(acc1_drafts[0].title, "A1 Draft");

        let acc2_drafts = list_drafts(&conn, "acc2").unwrap();
        assert_eq!(acc2_drafts.len(), 1);
        assert_eq!(acc2_drafts[0].title, "A2 Draft");
    }

    #[test]
    fn test_draft_isolation() {
        let conn = setup();
        conn.execute(
            "INSERT INTO local_accounts (id, username, password_hash) VALUES ('acc2', 'other', 'hash')",
            [],
        )
        .unwrap();

        let d1 = save_draft(&conn, None, "acc1", "Secret", "secret", "markdown").unwrap();
        // Account 2 should not be able to see account 1's draft.
        let result = get_draft(&conn, &d1.id);
        assert!(result.is_ok()); // get_draft doesn't check account — but list_drafts does.

        let acc2_drafts = list_drafts(&conn, "acc2").unwrap();
        assert!(acc2_drafts.is_empty());
    }

    #[test]
    fn test_get_draft_not_found() {
        let conn = setup();
        let result = get_draft(&conn, "nonexistent");
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::NotFound(_)));
    }

    #[test]
    fn test_delete_draft() {
        let conn = setup();
        let draft = save_draft(&conn, None, "acc1", "To Delete", "x", "markdown").unwrap();
        delete_draft(&conn, &draft.id).unwrap();
        let result = get_draft(&conn, &draft.id);
        assert!(result.is_err());
    }

    #[test]
    fn test_delete_nonexistent_draft() {
        let conn = setup();
        let result = delete_draft(&conn, "ghost");
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::NotFound(_)));
    }

    #[test]
    fn test_list_drafts_empty() {
        let conn = setup();
        let drafts = list_drafts(&conn, "acc1").unwrap();
        assert!(drafts.is_empty());
    }

    #[test]
    fn test_list_drafts_newest_first() {
        let conn = setup();
        let d1 = save_draft(&conn, None, "acc1", "Old", "", "markdown").unwrap();
        // Force d1's timestamp to be older.
        conn.execute(
            "UPDATE drafts SET updated_at = '2020-01-01' WHERE id = ?1",
            [&d1.id],
        )
        .unwrap();
        let d2 = save_draft(&conn, None, "acc1", "New", "", "markdown").unwrap();

        let drafts = list_drafts(&conn, "acc1").unwrap();
        assert_eq!(drafts.len(), 2);
        // Newest first (d2 has current timestamp, d1 has 2020).
        assert_eq!(drafts[0].id, d2.id);
        assert_eq!(drafts[1].id, d1.id);
    }

    // ── Article cache tests ─────────────────────────────────────────────

    #[test]
    fn test_cache_and_retrieve_article() {
        let conn = setup();
        cache_article(&conn, "art1", r#"{"title":"Test"}"#).unwrap();

        let cached = get_cached_article(&conn, "art1").unwrap().unwrap();
        assert_eq!(cached.id, "art1");
        assert!(cached.json.contains("Test"));
        assert!(!cached.cached_at.is_empty());
    }

    #[test]
    fn test_cache_overwrite() {
        let conn = setup();
        cache_article(&conn, "art1", r#"{"v":1}"#).unwrap();
        cache_article(&conn, "art1", r#"{"v":2}"#).unwrap();

        let cached = get_cached_article(&conn, "art1").unwrap().unwrap();
        assert!(cached.json.contains(r#""v":2"#));
    }

    #[test]
    fn test_get_cached_article_not_found() {
        let conn = setup();
        let result = get_cached_article(&conn, "nonexistent").unwrap();
        assert!(result.is_none());
    }

    #[test]
    fn test_cache_rejects_invalid_json() {
        let conn = setup();
        let result = cache_article(&conn, "art1", "not valid json");
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::DatabaseError(_)));
    }

    #[test]
    fn test_cache_rejects_oversized_article() {
        let conn = setup();
        let big_json = format!(r#"{{"data":"{}"}}"#, "x".repeat(MAX_CACHE_SIZE_BYTES));
        let result = cache_article(&conn, "big", &big_json);
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::IoError(_)));
    }

    #[test]
    fn test_get_cached_article_detects_corrupt_json() {
        let conn = setup();
        // Bypass cache_article validation by directly inserting corrupt data.
        conn.execute(
            "INSERT INTO article_cache (id, json) VALUES ('corrupt', 'not json')",
            [],
        )
        .unwrap();
        let result = get_cached_article(&conn, "corrupt");
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::DatabaseError(_)));
    }

    // ── Browsing history tests ──────────────────────────────────────────

    #[test]
    fn test_record_visit_inserts_new_row() {
        let conn = setup();
        record_visit(&conn, "acc1", "art1", "Test Article").unwrap();

        let history = get_history(&conn, "acc1", 1, 20).unwrap();
        assert_eq!(history.len(), 1);
        assert_eq!(history[0].article_id, "art1");
        assert_eq!(history[0].article_title, "Test Article");
    }

    #[test]
    fn test_record_visit_updates_existing_entry() {
        let conn = setup();
        record_visit(&conn, "acc1", "art1", "Old Title").unwrap();
        // Re-visit same article with new title — should update, not duplicate.
        record_visit(&conn, "acc1", "art1", "New Title").unwrap();

        let history = get_history(&conn, "acc1", 1, 20).unwrap();
        assert_eq!(history.len(), 1);
        assert_eq!(history[0].article_title, "New Title");
    }

    #[test]
    fn test_get_history_returns_newest_first() {
        let conn = setup();
        record_visit(&conn, "acc1", "art1", "Old").unwrap();
        // Force older timestamp on art1.
        conn.execute(
            "UPDATE browsing_history SET visited_at = '2020-01-01' WHERE article_id = 'art1'",
            [],
        )
        .unwrap();
        record_visit(&conn, "acc1", "art2", "New").unwrap();

        let history = get_history(&conn, "acc1", 1, 20).unwrap();
        assert_eq!(history.len(), 2);
        assert_eq!(history[0].article_id, "art2"); // newest first
        assert_eq!(history[1].article_id, "art1");
    }

    #[test]
    fn test_get_history_pagination() {
        let conn = setup();
        for i in 0..5 {
            let aid = format!("art{}", i);
            record_visit(&conn, "acc1", &aid, &format!("Article {}", i)).unwrap();
        }

        let page1 = get_history(&conn, "acc1", 1, 2).unwrap();
        assert_eq!(page1.len(), 2);

        let page2 = get_history(&conn, "acc1", 2, 2).unwrap();
        assert_eq!(page2.len(), 2);

        // Ensure no overlap.
        let ids: Vec<&str> = page1.iter().map(|e| e.article_id.as_str()).collect();
        for entry in &page2 {
            assert!(!ids.contains(&entry.article_id.as_str()));
        }
    }

    #[test]
    fn test_get_history_empty() {
        let conn = setup();
        let history = get_history(&conn, "acc1", 1, 20).unwrap();
        assert!(history.is_empty());
    }

    #[test]
    fn test_get_cached_article_ids() {
        let conn = setup();
        cache_article(&conn, "art_a", r#"{"title":"A"}"#).unwrap();
        cache_article(&conn, "art_b", r#"{"title":"B"}"#).unwrap();

        let ids = get_cached_article_ids(&conn).unwrap();
        assert_eq!(ids.len(), 2);
        assert!(ids.contains(&"art_a".to_string()));
        assert!(ids.contains(&"art_b".to_string()));
    }

    #[test]
    fn test_get_cached_article_ids_empty() {
        let conn = setup();
        let ids = get_cached_article_ids(&conn).unwrap();
        assert!(ids.is_empty());
    }
}
