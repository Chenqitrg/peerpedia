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
            commands::list_accounts,
            commands::save_draft,
            commands::list_drafts,
            commands::get_draft,
            commands::delete_draft,
            commands::cache_article,
            commands::get_cached_article,
        ])
        .run(tauri::generate_context!())
        .expect("error while running PeerPedia");
}
