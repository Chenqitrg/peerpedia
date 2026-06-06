// PeerPedia Tauri Desktop — library crate root.
// Re-exports all public modules so integration tests (in src-tauri/tests/) can
// import from `peerpedia::*`.

pub mod commands;
pub mod db;
pub mod error;
pub mod local_auth;
pub mod local_store;

use std::sync::Mutex;
use rusqlite::Connection;

/// Shared database connection, protected by a Mutex for thread safety.
pub struct AppState {
    pub db: Mutex<Connection>,
}
