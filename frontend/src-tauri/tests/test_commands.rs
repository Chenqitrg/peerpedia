// Integration tests — verify the full pipeline from module functions → SQLite → response.
// Use in-memory databases to avoid polluting the persistent ~/.peerpedia/peerpedia.db.

use peerpedia::db::run_migrations;
use rusqlite::Connection;

fn setup() -> Connection {
    let conn = Connection::open_in_memory().unwrap();
    run_migrations(&conn).unwrap();
    conn
}

#[test]
fn test_full_account_flow() {
    let conn = setup();

    // Create account
    let account = peerpedia::local_auth::create_account(
        &conn,
        "testuser",
        "password123",
        "test@test.com",
        "Test User",
    )
    .unwrap();
    assert_eq!(account.username, "testuser");

    // Login — returns AccountWithToken with session token
    let logged = peerpedia::local_auth::login(&conn, "testuser", "password123").unwrap();
    assert_eq!(logged.id, account.id);
    assert!(
        !logged.token.is_empty(),
        "login should return a session token"
    );

    // Verify session token works
    let verified_id = peerpedia::local_auth::verify_session(&conn, &logged.token).unwrap();
    assert_eq!(verified_id, account.id);

    // Invalid token is rejected
    let bad = peerpedia::local_auth::verify_session(&conn, "invalid-token");
    assert!(bad.is_err());

    // List
    let accounts = peerpedia::local_auth::list_accounts(&conn).unwrap();
    assert_eq!(accounts.len(), 1);

    // Duplicate rejected
    let dup = peerpedia::local_auth::create_account(&conn, "testuser", "otherpass", "", "Other");
    assert!(dup.is_err());
}

#[test]
fn test_token_list_drafts_flow() {
    /// Reproduce the user-page drafts bug: login → get token → resolve token →
    /// list drafts via resolved account_id. This is exactly what the frontend
    /// does after a page refresh.
    let conn = setup();

    // Create account + login to get token
    let account =
        peerpedia::local_auth::create_account(&conn, "writer", "pass", "", "Writer").unwrap();
    let logged = peerpedia::local_auth::login(&conn, "writer", "pass").unwrap();

    // Save a draft using raw account_id (simulates initial save)
    let draft = peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "My Draft",
        "# Hello",
        "markdown",
    )
    .unwrap();
    assert_eq!(draft.account_id, account.id);

    // Simulate page refresh: resolve token → account_id → list drafts
    // This is what the frontend does after restoreSession
    let resolved_id = peerpedia::local_auth::verify_session(&conn, &logged.token).unwrap();
    assert_eq!(resolved_id, account.id);

    let drafts = peerpedia::local_store::list_drafts(&conn, &resolved_id).unwrap();
    assert_eq!(
        drafts.len(),
        1,
        "should find draft via token-resolved account_id"
    );
    assert_eq!(drafts[0].title, "My Draft");
}

#[test]
fn test_full_draft_flow() {
    let conn = setup();

    // Create account first
    let account =
        peerpedia::local_auth::create_account(&conn, "writer", "pass", "", "Writer").unwrap();

    // Save draft
    let draft = peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "My Draft",
        "# Hello",
        "markdown",
    )
    .unwrap();
    assert_eq!(draft.title, "My Draft");
    assert_eq!(draft.account_id, account.id);

    // Update
    let updated = peerpedia::local_store::save_draft(
        &conn,
        Some(&draft.id),
        &account.id,
        "Updated",
        "new",
        "markdown",
    )
    .unwrap();
    assert_eq!(updated.title, "Updated");

    // List
    let drafts = peerpedia::local_store::list_drafts(&conn, &account.id).unwrap();
    assert_eq!(drafts.len(), 1);

    // Delete
    peerpedia::local_store::delete_draft(&conn, &draft.id).unwrap();
    let result = peerpedia::local_store::get_draft(&conn, &draft.id);
    assert!(result.is_err());
}

#[test]
fn test_full_cache_flow() {
    let conn = setup();

    // Cache article
    peerpedia::local_store::cache_article(
        &conn,
        "art-1",
        r#"{"title":"Test Article","score":{"O":4,"R":3}}"#,
    )
    .unwrap();

    // Retrieve
    let cached = peerpedia::local_store::get_cached_article(&conn, "art-1")
        .unwrap()
        .unwrap();
    assert_eq!(cached.id, "art-1");
    assert!(cached.json.contains("Test Article"));

    // Overwrite
    peerpedia::local_store::cache_article(&conn, "art-1", r#"{"title":"Updated"}"#).unwrap();
    let updated = peerpedia::local_store::get_cached_article(&conn, "art-1")
        .unwrap()
        .unwrap();
    assert!(updated.json.contains("Updated"));

    // Not found
    let missing = peerpedia::local_store::get_cached_article(&conn, "nonexistent").unwrap();
    assert!(missing.is_none());
}
