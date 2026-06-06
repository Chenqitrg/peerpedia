// IPC command handlers — thin wrappers that deserialize params, delegate to the
// appropriate module, and return Result<T, AppError>. Tauri serializes the Result
// automatically: Ok → JSON value, Err → { code, message } via AppError's Serialize.

use crate::error::AppError;
use crate::local_auth::{self, Account, AccountSummary};
use crate::local_store::{self, CachedArticle, Draft, DraftSummary};
use crate::AppState;
use serde::{Deserialize, Serialize};
use tauri::State;

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
    let conn = state.db.lock().unwrap();
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
pub fn login(state: State<'_, AppState>, params: LoginParams) -> Result<Account, AppError> {
    let conn = state.db.lock().unwrap();
    local_auth::login(&conn, &params.username, &params.password)
}

#[tauri::command]
pub fn list_accounts(state: State<'_, AppState>) -> Result<Vec<AccountSummary>, AppError> {
    let conn = state.db.lock().unwrap();
    local_auth::list_accounts(&conn)
}

// ── Draft commands ─────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct SaveDraftParams {
    #[serde(default)]
    pub id: Option<String>,
    pub account_id: String,
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub content: String,
    #[serde(default)]
    pub format: String,
}

#[tauri::command]
pub fn save_draft(state: State<'_, AppState>, params: SaveDraftParams) -> Result<Draft, AppError> {
    let conn = state.db.lock().unwrap();
    local_store::save_draft(
        &conn,
        params.id.as_deref(),
        &params.account_id,
        &params.title,
        &params.content,
        &params.format,
    )
}

#[derive(Debug, Deserialize)]
pub struct ListDraftsParams {
    pub account_id: String,
}

#[tauri::command]
pub fn list_drafts(
    state: State<'_, AppState>,
    params: ListDraftsParams,
) -> Result<Vec<DraftSummary>, AppError> {
    let conn = state.db.lock().unwrap();
    local_store::list_drafts(&conn, &params.account_id)
}

#[derive(Debug, Deserialize)]
pub struct GetDraftParams {
    pub id: String,
}

#[tauri::command]
pub fn get_draft(state: State<'_, AppState>, params: GetDraftParams) -> Result<Draft, AppError> {
    let conn = state.db.lock().unwrap();
    local_store::get_draft(&conn, &params.id)
}

#[derive(Debug, Deserialize)]
pub struct DeleteDraftParams {
    pub id: String,
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
    let conn = state.db.lock().unwrap();
    local_store::delete_draft(&conn, &params.id)?;
    Ok(OkResponse { ok: true })
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
    let conn = state.db.lock().unwrap();
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
    let conn = state.db.lock().unwrap();
    local_store::get_cached_article(&conn, &params.id)
}
