// Integration tests — verify the full pipeline from module functions → SQLite → response.
// Use in-memory databases to avoid polluting the persistent ~/.peerpedia/peerpedia.db.

use peerpedia::db::run_migrations;
use rusqlite::Connection;
use std::sync::{Mutex, OnceLock};

/// Serializes all git tests that modify PEERPEDIA_TEST_HOME.
/// Prevents parallel test threads from clobbering each other's env vars.
static GIT_HOME_LOCK: OnceLock<Mutex<()>> = OnceLock::new();
fn git_home_lock() -> &'static Mutex<()> {
    GIT_HOME_LOCK.get_or_init(|| Mutex::new(()))
}

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
        None,
        None,
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
fn test_get_draft_backward_compat_no_token() {
    /// Regression: ArticlePage calls getDraft({ id }) without token in Tauri mode.
    /// Must work because GetDraftParams.token is now optional.
    let conn = setup();

    let account =
        peerpedia::local_auth::create_account(&conn, "reader", "pass", "", "Reader").unwrap();

    let draft = peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "ArticlePage Draft",
        "# Hello from local draft",
        "markdown",
        None,
        None,
    )
    .unwrap();

    // Simulate ArticlePage.loadArticle: getDraft({ id: draftId }) — no token.
    let loaded = peerpedia::local_store::get_draft(&conn, &draft.id).unwrap();
    assert_eq!(loaded.id, draft.id);
    assert_eq!(loaded.title, "ArticlePage Draft");
    assert_eq!(loaded.account_id, account.id);
}

#[test]
fn test_list_drafts_backward_compat_account_id() {
    /// Regression: after we added token-based auth, listDrafts must still work
    /// with a bare account_id when no token is available (e.g., edge case
    /// during store init before restoreSession completes).
    let conn = setup();

    let account =
        peerpedia::local_auth::create_account(&conn, "writer2", "pass", "", "Writer2").unwrap();

    peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "Backward Compat Draft",
        "# Test",
        "markdown",
        None,
        None,
    )
    .unwrap();

    // Call list_drafts directly with account_id — no token.
    // This simulates the frontend sending { account_id: 'xxx' } without token.
    let drafts = peerpedia::local_store::list_drafts(&conn, &account.id).unwrap();
    assert_eq!(
        drafts.len(),
        1,
        "list_drafts with bare account_id must work"
    );
    assert_eq!(drafts[0].title, "Backward Compat Draft");
}

#[test]
fn test_save_draft_backward_compat_account_id() {
    /// Regression: EditorPage calls saveDraft({ account_id }) without token.
    /// Must work because SaveDraftParams.account_id is now a fallback.
    let conn = setup();

    let account =
        peerpedia::local_auth::create_account(&conn, "saver", "pass", "", "Saver").unwrap();

    // Save draft with bare account_id — no token, no login.
    // This simulates the frontend sending { account_id: 'xxx' } before token restore.
    let draft = peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "Newly Created Draft",
        "# Fresh content",
        "markdown",
        None,
        None,
    )
    .unwrap();
    assert!(
        !draft.id.is_empty(),
        "save_draft with bare account_id must work"
    );
    assert_eq!(draft.title, "Newly Created Draft");
    assert_eq!(draft.account_id, account.id);

    // Verify the draft is visible when listing by account_id
    let drafts = peerpedia::local_store::list_drafts(&conn, &account.id).unwrap();
    assert_eq!(drafts.len(), 1, "saved draft must be listable");
    assert_eq!(drafts[0].title, "Newly Created Draft");
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
        None,
        None,
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
        None,
        None,
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
fn test_delete_article_removes_db_row_and_git_repo() {
    let _lock = git_home_lock().lock().unwrap();
    use std::fs;

    let tmp = std::env::temp_dir().join(format!("peerpedia-test-del-{}", uuid::Uuid::new_v4()));
    let home = tmp.join("home");
    fs::create_dir_all(&home).unwrap();
    std::env::set_var("PEERPEDIA_TEST_HOME", &home);

    let conn = setup();
    let account =
        peerpedia::local_auth::create_account(&conn, "deleter", "pass", "", "Deleter").unwrap();

    // Save a draft + init git repo (like EditorPage does: saveDraft + gitInit)
    let draft = peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "To Delete",
        "# Gone",
        "markdown",
        None,
        None,
    )
    .unwrap();
    peerpedia::local_git::git_init(&draft.id, "# Gone", "markdown", "Initial", "deleter").unwrap();

    // Verify git repo directory was created
    let repo_dir = home.join(".peerpedia").join("articles").join(&draft.id);
    assert!(
        repo_dir.join(".git").is_dir(),
        "git repo should exist before deletion"
    );

    // Delete the article
    peerpedia::local_store::delete_article(&conn, &draft.id, &account.id).unwrap();

    // Verify DB row is gone
    let result = peerpedia::local_store::get_draft(&conn, &draft.id);
    assert!(result.is_err(), "DB row should be deleted");

    // Verify git repo directory is gone
    assert!(!repo_dir.exists(), "git repo directory should be removed");

    // Cleanup
    let _ = fs::remove_dir_all(&tmp);
}

#[test]
fn test_git_diff_parses_hunks() {
    let _lock = git_home_lock().lock().unwrap();
    use std::fs;

    let tmp = std::env::temp_dir().join(format!("peerpedia-test-diff-{}", uuid::Uuid::new_v4()));
    let home = tmp.join("home");
    fs::create_dir_all(&home).unwrap();
    std::env::set_var("PEERPEDIA_TEST_HOME", &home);

    // Create two commits with different content
    let r1 = peerpedia::local_git::git_init(
        "diff-test",
        "# Version 1\n\nHello",
        "markdown",
        "First",
        "tester",
    );
    assert!(r1.is_ok(), "git_init failed: {:?}", r1.err());
    let hash1 = r1.unwrap().hash;

    let r2 = peerpedia::local_git::git_commit(
        "diff-test",
        "# Version 2\n\nHello World\n\nNew line",
        "markdown",
        "Second",
        "tester",
    );
    assert!(r2.is_ok(), "git_commit failed: {:?}", r2.err());
    let hash2 = r2.unwrap().hash;

    // Call git_diff
    let diff = peerpedia::local_git::git_diff("diff-test", &hash1, &hash2).unwrap();
    assert!(
        !diff.files.is_empty(),
        "should have at least one file changed"
    );
    assert!(!diff.hunks.is_empty(), "should have at least one hunk");

    // Verify hunk content
    let has_additions = diff.hunks.iter().any(|h| {
        h.lines
            .iter()
            .any(|l| matches!(l.line_type, peerpedia::local_git::DiffLineType::Add))
    });
    let has_deletions = diff.hunks.iter().any(|h| {
        h.lines
            .iter()
            .any(|l| matches!(l.line_type, peerpedia::local_git::DiffLineType::Delete))
    });
    assert!(has_additions, "diff should contain added lines");
    assert!(has_deletions, "diff should contain deleted lines");

    let _ = fs::remove_dir_all(&tmp);
}

#[test]
fn test_git_diff_same_commit_returns_empty() {
    let _lock = git_home_lock().lock().unwrap();
    use std::fs;

    let tmp = std::env::temp_dir().join(format!("peerpedia-test-diff2-{}", uuid::Uuid::new_v4()));
    let home = tmp.join("home");
    fs::create_dir_all(&home).unwrap();
    std::env::set_var("PEERPEDIA_TEST_HOME", &home);

    let r =
        peerpedia::local_git::git_init("diff-empty", "# No change", "markdown", "Init", "tester")
            .unwrap();
    let hash = r.hash;

    let diff = peerpedia::local_git::git_diff("diff-empty", &hash, &hash).unwrap();
    assert!(
        diff.hunks.is_empty(),
        "diff between same commit should be empty"
    );
    assert!(
        diff.files.is_empty(),
        "diff between same commit should have no files"
    );

    let _ = fs::remove_dir_all(&tmp);
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

#[test]
fn test_search_drafts_fts() {
    let conn = setup();
    let account =
        peerpedia::local_auth::create_account(&conn, "searcher", "pass", "", "Searcher").unwrap();

    // Save drafts with distinct titles
    peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "Quantum Mechanics",
        "# Quantum",
        "markdown",
        None,
        None,
    )
    .unwrap();
    peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "Classical Physics",
        "# Classical",
        "markdown",
        None,
        None,
    )
    .unwrap();
    peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "Cooking Recipes",
        "# Pasta",
        "markdown",
        None,
        None,
    )
    .unwrap();

    let results = peerpedia::local_store::search_drafts(&conn, "quantum", &account.id).unwrap();
    assert_eq!(
        results.len(),
        1,
        "should find exactly one draft matching 'quantum'"
    );
    assert_eq!(results[0].title, "Quantum Mechanics");
}

#[test]
fn test_search_drafts_empty_query_returns_all() {
    let conn = setup();
    let account =
        peerpedia::local_auth::create_account(&conn, "searcher2", "pass", "", "Searcher2").unwrap();

    peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "Draft A",
        "# A",
        "markdown",
        None,
        None,
    )
    .unwrap();
    peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "Draft B",
        "# B",
        "markdown",
        None,
        None,
    )
    .unwrap();

    let results = peerpedia::local_store::search_drafts(&conn, "", &account.id).unwrap();
    assert_eq!(results.len(), 2, "empty query returns all drafts");
}

#[test]
fn test_search_drafts_fts_content() {
    let conn = setup();
    let account =
        peerpedia::local_auth::create_account(&conn, "searcher3", "pass", "", "Searcher3").unwrap();

    peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "Title One",
        "This draft discusses gravity waves",
        "markdown",
        None,
        None,
    )
    .unwrap();
    peerpedia::local_store::save_draft(
        &conn,
        None,
        &account.id,
        "Title Two",
        "This draft discusses electromagnetism",
        "markdown",
        None,
        None,
    )
    .unwrap();

    // Search by content (not just title)
    let results = peerpedia::local_store::search_drafts(&conn, "gravity", &account.id).unwrap();
    assert_eq!(results.len(), 1, "should find by content match");
    assert_eq!(results[0].title, "Title One");
}

#[test]
fn test_search_drafts_account_isolation() {
    let conn = setup();
    let account1 =
        peerpedia::local_auth::create_account(&conn, "searcher4a", "pass", "", "Searcher4a")
            .unwrap();
    let account2 =
        peerpedia::local_auth::create_account(&conn, "searcher4b", "pass", "", "Searcher4b")
            .unwrap();

    peerpedia::local_store::save_draft(
        &conn,
        None,
        &account1.id,
        "Alice Draft",
        "# Alice",
        "markdown",
        None,
        None,
    )
    .unwrap();
    peerpedia::local_store::save_draft(
        &conn,
        None,
        &account2.id,
        "Bob Draft",
        "# Bob",
        "markdown",
        None,
        None,
    )
    .unwrap();

    // Alice should only see her own draft
    let results = peerpedia::local_store::search_drafts(&conn, "draft", &account1.id).unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].title, "Alice Draft");
}

#[test]
fn test_compile_typst_missing_cli() {
    // When typst is not installed, should return a clear error
    let result = peerpedia::local_store::compile_typst("# Hello", "markdown");
    // Either succeeds (if typst is installed) or fails with a descriptive error
    match result {
        Ok(svg) => {
            // Success — typst is installed
            assert!(!svg.is_empty(), "SVG output should not be empty");
        }
        Err(e) => {
            let msg = format!("{}", e);
            // Should mention typst or the command failing
            assert!(
                msg.to_lowercase().contains("typst")
                    || msg.to_lowercase().contains("not found")
                    || msg.to_lowercase().contains("failed"),
                "Error should be about typst: {}",
                msg
            );
        }
    }
}

#[test]
fn test_compile_typst_handles_invalid_format() {
    // Should reject non-typst formats gracefully
    let result = peerpedia::local_store::compile_typst("# Hello", "markdown");
    // Markdown is not typst — the function should return an error
    assert!(
        result.is_err(),
        "Markdown content should not compile as Typst"
    );
}
