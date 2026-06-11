// PeerPedia Tauri Desktop — binary entry point.
// Registers IPC commands and initializes the local SQLite database.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use peerpedia::commands;
use peerpedia::db::init_db;
use peerpedia::AppState;
use std::sync::Mutex;

fn main() {
    let conn = init_db().expect("Failed to initialize database");
    let state = AppState {
        db: Mutex::new(conn),
    };

    tauri::Builder::default()
        .manage(state)
        .invoke_handler(tauri::generate_handler![
            commands::create_account,
            commands::login,
            commands::logout,
            commands::list_accounts,
            commands::save_draft,
            commands::list_drafts,
            commands::get_draft,
            commands::delete_draft,
            commands::delete_article,
            commands::cache_article,
            commands::get_cached_article,
            commands::record_visit,
            commands::get_history,
            commands::get_cached_article_ids,
            commands::cache_article_full,
            commands::git_init,
            commands::git_commit,
            commands::git_history,
            commands::git_show,
            commands::git_diff,
            commands::git_rollback,
            commands::invalidate_article_cache,
            commands::search_drafts,
            commands::search_cached_articles,
            commands::compile_typst,
            commands::compile_typst_pdf,
            commands::export_article,
            commands::set_server_article_id,
            commands::follow_user,
            commands::unfollow_user,
            commands::is_following,
            commands::get_following,
            commands::get_followers,
        ])
        .run(tauri::generate_context!())
        .expect("error while running PeerPedia");
}
