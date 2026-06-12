// PeerPedia Tauri Desktop — library crate root.
// Re-exports all public modules so integration tests (in src-tauri/tests/) can
// import from `peerpedia::*`.

pub mod commands;
pub mod db;
pub mod error;
pub mod local_auth;
pub mod local_git;
pub mod local_store;

use rusqlite::Connection;
use tokio::sync::Mutex;

/// Shared database connection, protected by a Mutex for thread safety.
/// Uses tokio::sync::Mutex so the guard can be held safely across
/// async command boundaries.
pub struct AppState {
    pub db: Mutex<Connection>,
}
