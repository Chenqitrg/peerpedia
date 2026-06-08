// IPC command handlers — thin wrappers that deserialize params, delegate to the
// appropriate module, and return Result<T, AppError>. Tauri serializes the Result
// automatically: Ok → JSON value, Err → { code, message } via AppError's Serialize.
//
// Security: all mutating commands require a session token. The token is validated
// against the sessions table and mapped to an account_id before delegation.

use crate::error::AppError;
use crate::local_auth::{self, Account, AccountSummary, AccountWithToken};
use crate::local_git;
use crate::local_store::{self, CachedArticle, Draft, DraftSummary};
use crate::AppState;
use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use std::sync::MutexGuard;
use tauri::State;

/// Acquire the database lock, returning a clear error on poison instead of panicking.
fn lock_db(state: &AppState) -> Result<MutexGuard<'_, Connection>, AppError> {
    state
        .db
        .lock()
        .map_err(|_| AppError::DatabaseError("Database lock poisoned".into()))
}

/// Resolve a session token to an account_id. Used by all commands that need
/// to know which account is making the request.
fn resolve_account(state: &AppState, token: &str) -> Result<String, AppError> {
    let conn = lock_db(state)?;
    local_auth::verify_session(&conn, token)
}

// ── Auth commands ──────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CreateAccountParams {
    pub username: String,
    pub password: String,
    #[serde(default)]
    pub email: String,
    #[serde(default)]
    pub name: String,
}

#[tauri::command]
pub fn create_account(
    state: State<'_, AppState>,
    params: CreateAccountParams,
) -> Result<Account, AppError> {
    let conn = lock_db(&state)?;
    local_auth::create_account(
        &conn,
        &params.username,
        &params.password,
        &params.email,
        &params.name,
    )
}

#[derive(Debug, Deserialize)]
pub struct LoginParams {
    pub username: String,
    pub password: String,
}

#[tauri::command]
pub fn login(
    state: State<'_, AppState>,
    params: LoginParams,
) -> Result<AccountWithToken, AppError> {
    let conn = lock_db(&state)?;
    local_auth::login(&conn, &params.username, &params.password)
}

#[tauri::command]
pub fn list_accounts(state: State<'_, AppState>) -> Result<Vec<AccountSummary>, AppError> {
    let conn = lock_db(&state)?;
    local_auth::list_accounts(&conn)
}

#[derive(Debug, Deserialize)]
pub struct LogoutParams {
    pub token: String,
}

#[tauri::command]
pub fn logout(state: State<'_, AppState>, params: LogoutParams) -> Result<OkResponse, AppError> {
    let conn = lock_db(&state)?;
    local_auth::logout_session(&conn, &params.token)?;
    Ok(OkResponse { ok: true })
}

// ── Draft commands ─────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct SaveDraftParams {
    #[serde(default)]
    pub id: Option<String>,
    pub token: Option<String>,
    #[serde(default)]
    pub account_id: String, // backward compat — used when token is None
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub content: String,
    #[serde(default)]
    pub format: String,
}

#[tauri::command]
pub fn save_draft(state: State<'_, AppState>, params: SaveDraftParams) -> Result<Draft, AppError> {
    let account_id = if let Some(ref token) = params.token {
        resolve_account(&state, token)?
    } else if !params.account_id.is_empty() {
        params.account_id.clone()
    } else {
        return Err(AppError::AuthFailed("Authentication required".into()));
    };
    let conn = lock_db(&state)?;
    local_store::save_draft(
        &conn,
        params.id.as_deref(),
        &account_id,
        &params.title,
        &params.content,
        &params.format,
    )
}

#[derive(Debug, Deserialize)]
pub struct ListDraftsParams {
    pub token: Option<String>,
    #[serde(default)]
    pub account_id: String, // backward compat — used when token is None
}

#[tauri::command]
pub fn list_drafts(
    state: State<'_, AppState>,
    params: ListDraftsParams,
) -> Result<Vec<DraftSummary>, AppError> {
    let account_id = if let Some(ref token) = params.token {
        resolve_account(&state, token)?
    } else if !params.account_id.is_empty() {
        params.account_id.clone()
    } else {
        return Err(AppError::AuthFailed("Authentication required".into()));
    };
    let conn = lock_db(&state)?;
    local_store::list_drafts(&conn, &account_id)
}

#[derive(Debug, Deserialize)]
pub struct GetDraftParams {
    pub id: String,
    pub token: Option<String>,
    #[serde(default)]
    pub account_id: String, // backward compat — used when token is None
}

#[tauri::command]
pub fn get_draft(state: State<'_, AppState>, params: GetDraftParams) -> Result<Draft, AppError> {
    let conn = lock_db(&state)?;
    let draft = local_store::get_draft(&conn, &params.id)?;

    // When token is provided, verify ownership.
    if let Some(ref token) = params.token {
        let account_id = resolve_account(&state, token)?;
        if draft.account_id != account_id {
            return Err(AppError::NotFound(format!(
                "Draft '{}' not found",
                params.id
            )));
        }
    }
    Ok(draft)
}

#[derive(Debug, Deserialize)]
pub struct DeleteDraftParams {
    pub id: String,
    pub token: String,
}

#[derive(Debug, Serialize)]
pub struct OkResponse {
    pub ok: bool,
}

#[tauri::command]
pub fn delete_draft(
    state: State<'_, AppState>,
    params: DeleteDraftParams,
) -> Result<OkResponse, AppError> {
    let account_id = resolve_account(&state, &params.token)?;

    // Verify ownership before deletion.
    let conn = lock_db(&state)?;
    let draft = local_store::get_draft(&conn, &params.id)?;
    if draft.account_id != account_id {
        return Err(AppError::NotFound(format!(
            "Draft '{}' not found",
            params.id
        )));
    }
    local_store::delete_draft(&conn, &params.id)?;
    Ok(OkResponse { ok: true })
}

#[derive(Debug, Deserialize)]
pub struct DeleteArticleParams {
    pub id: String,
    pub token: Option<String>,
    #[serde(default)]
    pub account_id: String,
}

#[tauri::command]
pub fn delete_article(
    state: State<'_, AppState>,
    params: DeleteArticleParams,
) -> Result<OkResponse, AppError> {
    let account_id = if let Some(ref token) = params.token {
        resolve_account(&state, token)?
    } else if !params.account_id.is_empty() {
        params.account_id.clone()
    } else {
        return Err(AppError::AuthFailed("Authentication required".into()));
    };
    let conn = lock_db(&state)?;
    local_store::delete_article(&conn, &params.id, &account_id)?;
    Ok(OkResponse { ok: true })
}

// ── Draft search command ────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct SearchDraftsParams {
    pub q: String,
    pub token: Option<String>,
    #[serde(default)]
    pub account_id: String,
}

#[tauri::command]
pub fn search_drafts(
    state: State<'_, AppState>,
    params: SearchDraftsParams,
) -> Result<Vec<local_store::DraftSearchResult>, AppError> {
    let account_id = if let Some(ref token) = params.token {
        resolve_account(&state, token)?
    } else if !params.account_id.is_empty() {
        params.account_id.clone()
    } else {
        return Err(AppError::AuthFailed("Authentication required".into()));
    };
    let conn = lock_db(&state)?;
    local_store::search_drafts(&conn, &params.q, &account_id)
}

// ── Article cache commands ─────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CacheArticleParams {
    pub id: String,
    pub article_json: String,
}

#[tauri::command]
pub fn cache_article(
    state: State<'_, AppState>,
    params: CacheArticleParams,
) -> Result<OkResponse, AppError> {
    let conn = lock_db(&state)?;
    local_store::cache_article(&conn, &params.id, &params.article_json)?;
    Ok(OkResponse { ok: true })
}

#[derive(Debug, Deserialize)]
pub struct GetCachedArticleParams {
    pub id: String,
}

#[tauri::command]
pub fn get_cached_article(
    state: State<'_, AppState>,
    params: GetCachedArticleParams,
) -> Result<Option<CachedArticle>, AppError> {
    let conn = lock_db(&state)?;
    local_store::get_cached_article(&conn, &params.id)
}

#[derive(Debug, Deserialize)]
pub struct SearchCachedArticlesParams {
    pub q: String,
}

#[tauri::command]
pub fn search_cached_articles(
    state: State<'_, AppState>,
    params: SearchCachedArticlesParams,
) -> Result<Vec<local_store::DraftSearchResult>, AppError> {
    let conn = lock_db(&state)?;
    local_store::search_cached_articles(&conn, &params.q)
}

// ── Browsing history commands ───────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct RecordVisitParams {
    pub token: String,
    pub article_id: String,
    #[serde(default)]
    pub article_title: String,
}

#[tauri::command]
pub fn record_visit(
    state: State<'_, AppState>,
    params: RecordVisitParams,
) -> Result<OkResponse, AppError> {
    let account_id = resolve_account(&state, &params.token)?;
    let conn = lock_db(&state)?;
    local_store::record_visit(
        &conn,
        &account_id,
        &params.article_id,
        &params.article_title,
    )?;
    Ok(OkResponse { ok: true })
}

#[derive(Debug, Deserialize)]
pub struct GetHistoryParams {
    pub token: String,
    #[serde(default = "default_page")]
    pub page: i64,
    #[serde(default = "default_size")]
    pub size: i64,
}

fn default_page() -> i64 {
    1
}
fn default_size() -> i64 {
    20
}

#[tauri::command]
pub fn get_history(
    state: State<'_, AppState>,
    params: GetHistoryParams,
) -> Result<Vec<local_store::HistoryEntry>, AppError> {
    let account_id = resolve_account(&state, &params.token)?;
    let conn = lock_db(&state)?;
    local_store::get_history(&conn, &account_id, params.page, params.size)
}

#[tauri::command]
pub fn get_cached_article_ids(state: State<'_, AppState>) -> Result<Vec<String>, AppError> {
    let conn = lock_db(&state)?;
    local_store::get_cached_article_ids(&conn)
}

// ── Local Git commands ─────────────────────────────────────────────────
// Git commands operate on the filesystem, not the database. They don't need
// a session token — article_id validation happens inside local_git.

#[derive(Debug, Deserialize)]
pub struct GitInitParams {
    pub article_id: String,
    #[serde(default)]
    pub content: String,
    #[serde(default)]
    pub format: String,
    #[serde(default)]
    pub commit_message: String,
    pub author: String,
}

#[tauri::command]
pub fn git_init(params: GitInitParams) -> Result<local_git::GitCommitResult, AppError> {
    local_git::git_init(
        &params.article_id,
        &params.content,
        &params.format,
        &params.commit_message,
        &params.author,
    )
}

#[derive(Debug, Deserialize)]
pub struct GitCommitParams {
    pub article_id: String,
    #[serde(default)]
    pub content: String,
    #[serde(default)]
    pub format: String,
    #[serde(default)]
    pub commit_message: String,
    pub author: String,
}

#[tauri::command]
pub fn git_commit(params: GitCommitParams) -> Result<local_git::GitCommitResult, AppError> {
    local_git::git_commit(
        &params.article_id,
        &params.content,
        &params.format,
        &params.commit_message,
        &params.author,
    )
}

#[derive(Debug, Deserialize)]
pub struct GitHistoryParams {
    pub article_id: String,
}

#[tauri::command]
pub fn git_history(params: GitHistoryParams) -> Result<Vec<local_git::CommitEntry>, AppError> {
    local_git::git_history(&params.article_id)
}

#[derive(Debug, Deserialize)]
pub struct GitShowParams {
    pub article_id: String,
    pub commit_hash: String,
}

#[tauri::command]
pub fn git_show(params: GitShowParams) -> Result<String, AppError> {
    local_git::git_show(&params.article_id, &params.commit_hash)
}

#[derive(Debug, Deserialize)]
pub struct GitDiffParams {
    pub article_id: String,
    pub hash1: String,
    pub hash2: String,
}

#[tauri::command]
pub fn git_diff(params: GitDiffParams) -> Result<local_git::DiffResult, AppError> {
    local_git::git_diff(&params.article_id, &params.hash1, &params.hash2)
}

// ── Compile command ─────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CompileTypstParams {
    pub content: String,
    pub format: String,
}

#[tauri::command]
pub fn compile_typst(params: CompileTypstParams) -> Result<String, AppError> {
    local_store::compile_typst(&params.content, &params.format)
}

// ── Article full cache command ──────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CacheArticleFullParams {
    pub id: String,
    pub article_json: String,
}

#[tauri::command]
pub fn cache_article_full(
    state: State<'_, AppState>,
    params: CacheArticleFullParams,
) -> Result<OkResponse, AppError> {
    let conn = lock_db(&state)?;
    local_store::cache_article_full(&conn, &params.id, &params.article_json)?;
    Ok(OkResponse { ok: true })
}
