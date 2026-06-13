// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

// IPC command handlers — thin wrappers that deserialize params, delegate to the
// appropriate module, and return Result<T, AppError>. Tauri serializes the Result
// automatically: Ok → JSON value, Err → { code, message } via AppError's Serialize.
//
// Security: all mutating commands require a session token. The token is validated
// against the sessions table and mapped to an account_id before delegation.
//
// All commands are async. Database work acquires the lock, does sync operations,
// drops the lock, then awaits any async work. Git and Typst subprocess calls are
// wrapped in spawn_blocking to avoid blocking the async runtime.

use crate::error::AppError;
use crate::local_auth::{self, Account, AccountSummary, AccountWithToken};
use crate::local_git;
use crate::local_store::{self, CachedArticle, Draft, DraftSummary};
use crate::AppState;
use serde::{Deserialize, Serialize};
use tauri::State;

/// Acquire the database lock asynchronously.
async fn lock_db(
    state: &AppState,
) -> Result<tokio::sync::MutexGuard<'_, rusqlite::Connection>, AppError> {
    Ok(state.db.lock().await)
}

/// Resolve a session token to an account_id.
async fn resolve_account(state: &AppState, token: &str) -> Result<String, AppError> {
    let conn = lock_db(state).await?;
    local_auth::verify_session(&conn, token)
}

async fn resolve_account_id(
    state: &AppState,
    token: &Option<String>,
    account_id: &str,
) -> Result<String, AppError> {
    if let Some(ref token) = token {
        resolve_account(state, token).await
    } else if !account_id.is_empty() {
        Ok(account_id.to_string())
    } else {
        Err(AppError::AuthFailed("Authentication required".into()))
    }
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
pub async fn create_account(
    state: State<'_, AppState>,
    params: CreateAccountParams,
) -> Result<Account, AppError> {
    let conn = lock_db(&state).await?;
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
pub async fn login(
    state: State<'_, AppState>,
    params: LoginParams,
) -> Result<AccountWithToken, AppError> {
    let conn = lock_db(&state).await?;
    local_auth::login(&conn, &params.username, &params.password)
}

#[tauri::command]
pub async fn list_accounts(state: State<'_, AppState>) -> Result<Vec<AccountSummary>, AppError> {
    let conn = lock_db(&state).await?;
    local_auth::list_accounts(&conn)
}

#[derive(Debug, Deserialize)]
pub struct LogoutParams {
    pub token: String,
}

#[tauri::command]
pub async fn logout(
    state: State<'_, AppState>,
    params: LogoutParams,
) -> Result<OkResponse, AppError> {
    let conn = lock_db(&state).await?;
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
pub async fn save_draft(
    state: State<'_, AppState>,
    params: SaveDraftParams,
) -> Result<Draft, AppError> {
    let account_id = if let Some(ref token) = params.token {
        resolve_account(&state, token)
            .await
            .unwrap_or_else(|_| params.account_id.clone())
    } else {
        params.account_id.clone()
    };
    if account_id.is_empty() {
        return Err(AppError::AuthFailed("Authentication required".into()));
    }
    let conn = lock_db(&state).await?;
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
pub async fn list_drafts(
    state: State<'_, AppState>,
    params: ListDraftsParams,
) -> Result<Vec<DraftSummary>, AppError> {
    let account_id = if let Some(ref token) = params.token {
        resolve_account(&state, token).await?
    } else if !params.account_id.is_empty() {
        params.account_id.clone()
    } else {
        return Err(AppError::AuthFailed("Authentication required".into()));
    };
    let conn = lock_db(&state).await?;
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
pub async fn get_draft(
    state: State<'_, AppState>,
    params: GetDraftParams,
) -> Result<Draft, AppError> {
    // Scope the first lock so conn is dropped before resolve_account,
    // which also calls lock_db. std::sync::Mutex is not reentrant.
    let draft = {
        let conn = lock_db(&state).await?;
        local_store::get_draft(&conn, &params.id)?
    }; // conn dropped here, lock released

    // When token is provided, verify ownership.
    if let Some(ref token) = params.token {
        let account_id = resolve_account(&state, token).await?;
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
pub async fn delete_draft(
    state: State<'_, AppState>,
    params: DeleteDraftParams,
) -> Result<OkResponse, AppError> {
    let account_id = resolve_account(&state, &params.token).await?;

    // Verify ownership before deletion.
    let conn = lock_db(&state).await?;
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
pub async fn delete_article(
    state: State<'_, AppState>,
    params: DeleteArticleParams,
) -> Result<OkResponse, AppError> {
    let account_id = if let Some(ref token) = params.token {
        resolve_account(&state, token).await?
    } else if !params.account_id.is_empty() {
        params.account_id.clone()
    } else {
        return Err(AppError::AuthFailed("Authentication required".into()));
    };
    let conn = lock_db(&state).await?;
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
pub async fn search_drafts(
    state: State<'_, AppState>,
    params: SearchDraftsParams,
) -> Result<Vec<local_store::DraftSearchResult>, AppError> {
    let account_id = if let Some(ref token) = params.token {
        resolve_account(&state, token).await?
    } else if !params.account_id.is_empty() {
        params.account_id.clone()
    } else {
        return Err(AppError::AuthFailed("Authentication required".into()));
    };
    let conn = lock_db(&state).await?;
    local_store::search_drafts(&conn, &params.q, &account_id)
}

// ── Article cache commands ─────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CacheArticleParams {
    pub id: String,
    pub article_json: String,
}

#[tauri::command]
pub async fn cache_article(
    state: State<'_, AppState>,
    params: CacheArticleParams,
) -> Result<OkResponse, AppError> {
    let conn = lock_db(&state).await?;
    local_store::cache_article(&conn, &params.id, &params.article_json)?;
    Ok(OkResponse { ok: true })
}

#[derive(Debug, Deserialize)]
pub struct GetCachedArticleParams {
    pub id: String,
}

#[tauri::command]
pub async fn get_cached_article(
    state: State<'_, AppState>,
    params: GetCachedArticleParams,
) -> Result<Option<CachedArticle>, AppError> {
    let conn = lock_db(&state).await?;
    local_store::get_cached_article(&conn, &params.id)
}

#[derive(Debug, Deserialize)]
pub struct SearchCachedArticlesParams {
    pub q: String,
}

#[tauri::command]
pub async fn search_cached_articles(
    state: State<'_, AppState>,
    params: SearchCachedArticlesParams,
) -> Result<Vec<local_store::DraftSearchResult>, AppError> {
    let conn = lock_db(&state).await?;
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
pub async fn record_visit(
    state: State<'_, AppState>,
    params: RecordVisitParams,
) -> Result<OkResponse, AppError> {
    let account_id = resolve_account(&state, &params.token).await?;
    let conn = lock_db(&state).await?;
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
pub async fn get_history(
    state: State<'_, AppState>,
    params: GetHistoryParams,
) -> Result<Vec<local_store::HistoryEntry>, AppError> {
    let account_id = resolve_account(&state, &params.token).await?;
    let conn = lock_db(&state).await?;
    local_store::get_history(&conn, &account_id, params.page, params.size)
}

#[tauri::command]
pub async fn get_cached_article_ids(state: State<'_, AppState>) -> Result<Vec<String>, AppError> {
    let conn = lock_db(&state).await?;
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
    pub author: String,    // display name (username)
    pub author_id: String, // UUID identity
}

#[tauri::command]
pub async fn git_init(params: GitInitParams) -> Result<local_git::GitCommitResult, AppError> {
    let article_id = params.article_id;
    let content = params.content;
    let format = params.format;
    let commit_message = params.commit_message;
    let author = params.author;
    let author_id = params.author_id;
    tokio::task::spawn_blocking(move || {
        local_git::git_init(
            &article_id,
            &content,
            &format,
            &commit_message,
            &author,
            &author_id,
        )
    })
    .await
    .map_err(|e| AppError::IoError(format!("git_init panicked: {}", e)))?
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
    pub author: String,    // display name (username)
    pub author_id: String, // UUID identity
}

#[tauri::command]
pub async fn git_commit(params: GitCommitParams) -> Result<local_git::GitCommitResult, AppError> {
    let article_id = params.article_id;
    let content = params.content;
    let format = params.format;
    let commit_message = params.commit_message;
    let author = params.author;
    let author_id = params.author_id;
    tokio::task::spawn_blocking(move || {
        local_git::git_commit(
            &article_id,
            &content,
            &format,
            &commit_message,
            &author,
            &author_id,
        )
    })
    .await
    .map_err(|e| AppError::IoError(format!("git_commit panicked: {}", e)))?
}

#[derive(Debug, Deserialize)]
pub struct GitHistoryParams {
    pub article_id: String,
}

#[tauri::command]
pub async fn git_history(
    params: GitHistoryParams,
) -> Result<Vec<local_git::CommitEntry>, AppError> {
    let article_id = params.article_id;
    tokio::task::spawn_blocking(move || local_git::git_history(&article_id))
        .await
        .map_err(|e| AppError::IoError(format!("git_history panicked: {}", e)))?
}

#[derive(Debug, Deserialize)]
pub struct GitShowParams {
    pub article_id: String,
    pub commit_hash: String,
}

#[tauri::command]
pub async fn git_show(params: GitShowParams) -> Result<String, AppError> {
    let article_id = params.article_id;
    let commit_hash = params.commit_hash;
    tokio::task::spawn_blocking(move || {
        let (content, _format) = local_git::git_show(&article_id, &commit_hash)?;
        Ok(content)
    })
    .await
    .map_err(|e| AppError::IoError(format!("git_show panicked: {}", e)))?
}

#[derive(Debug, Deserialize)]
pub struct GitDiffParams {
    pub article_id: String,
    pub hash1: String,
    pub hash2: String,
}

#[tauri::command]
pub async fn git_diff(params: GitDiffParams) -> Result<local_git::DiffResult, AppError> {
    let article_id = params.article_id;
    let hash1 = params.hash1;
    let hash2 = params.hash2;
    tokio::task::spawn_blocking(move || local_git::git_diff(&article_id, &hash1, &hash2))
        .await
        .map_err(|e| AppError::IoError(format!("git_diff panicked: {}", e)))?
}

#[derive(Debug, Deserialize)]
pub struct GitRollbackParams {
    pub article_id: String,
    pub commit_hash: String,
    pub author: String,    // display name
    pub author_id: String, // UUID identity
}

#[tauri::command]
pub async fn git_rollback(
    params: GitRollbackParams,
) -> Result<local_git::GitCommitResult, AppError> {
    let article_id = params.article_id;
    let commit_hash = params.commit_hash;
    let author = params.author;
    let author_id = params.author_id;
    tokio::task::spawn_blocking(move || {
        local_git::git_rollback(&article_id, &commit_hash, &author, &author_id)
    })
    .await
    .map_err(|e| AppError::IoError(format!("git_rollback panicked: {}", e)))?
}

#[tauri::command]
pub async fn git_reset_hard(params: GitResetParams) -> Result<OkResponse, AppError> {
    tokio::task::spawn_blocking(move || {
        local_git::git_reset_hard(&params.article_id, &params.commit_hash)?;
        Ok(OkResponse { ok: true })
    })
    .await
    .map_err(|e| AppError::IoError(format!("git_reset_hard panicked: {}", e)))?
}

#[derive(Debug, Deserialize)]
pub struct GitResetParams {
    pub article_id: String,
    pub commit_hash: String,
}

#[derive(Debug, Deserialize)]
pub struct InvalidateCacheParams {
    pub article_id: String,
}

#[tauri::command]
pub async fn invalidate_article_cache(
    state: State<'_, AppState>,
    params: InvalidateCacheParams,
) -> Result<(), AppError> {
    let conn = lock_db(&state).await?;
    local_store::delete_cached_article(&conn, &params.article_id)
}

// ── Compile command ─────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CompileTypstParams {
    pub content: String,
    pub format: String,
}

#[tauri::command]
pub async fn compile_typst(params: CompileTypstParams) -> Result<String, AppError> {
    let content = params.content;
    let format = params.format;
    tokio::task::spawn_blocking(move || local_store::compile_typst(&content, &format))
        .await
        .map_err(|e| AppError::IoError(format!("compile_typst panicked: {}", e)))?
}

#[derive(Deserialize)]
pub struct CompileTypstPdfParams {
    pub content: String,
}

#[tauri::command]
pub async fn compile_typst_pdf(params: CompileTypstPdfParams) -> Result<String, AppError> {
    let content = params.content;
    tokio::task::spawn_blocking(move || local_store::compile_typst_pdf(&content))
        .await
        .map_err(|e| AppError::IoError(format!("compile_typst_pdf panicked: {}", e)))?
}

// ── Article full cache command ──────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CacheArticleFullParams {
    pub id: String,
    pub article_json: String,
}

#[tauri::command]
pub async fn cache_article_full(
    state: State<'_, AppState>,
    params: CacheArticleFullParams,
) -> Result<OkResponse, AppError> {
    let conn = lock_db(&state).await?;
    local_store::cache_article_full(&conn, &params.id, &params.article_json)?;
    Ok(OkResponse { ok: true })
}

// ── Article sync command ────────────────────────────────────────────────

// ── Pending ops commands ─────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct PendingOpsParams {
    pub token: Option<String>,
    #[serde(default)]
    pub account_id: String,
}

#[tauri::command]
pub async fn get_pending_ops(
    state: State<'_, AppState>,
    params: PendingOpsParams,
) -> Result<Vec<local_store::PendingOp>, AppError> {
    let account_id = resolve_account_id(&state, &params.token, &params.account_id).await?;
    let conn = lock_db(&state).await?;
    local_store::get_pending_ops(&conn, &account_id)
}

#[derive(Debug, Deserialize)]
pub struct PendingResolveParams {
    pub id: String,
    pub token: Option<String>,
}

#[tauri::command]
pub async fn clear_pending(
    state: State<'_, AppState>,
    params: PendingResolveParams,
) -> Result<OkResponse, AppError> {
    let conn = lock_db(&state).await?;
    local_store::clear_pending(&conn, &params.id)?;
    Ok(OkResponse { ok: true })
}

#[tauri::command]
pub async fn set_pending_delete(
    state: State<'_, AppState>,
    params: PendingResolveParams,
) -> Result<OkResponse, AppError> {
    let conn = lock_db(&state).await?;
    local_store::set_pending_delete(&conn, &params.id)?;
    Ok(OkResponse { ok: true })
}

#[tauri::command]
pub async fn set_pending_push(
    state: State<'_, AppState>,
    params: PendingResolveParams,
) -> Result<OkResponse, AppError> {
    let conn = lock_db(&state).await?;
    local_store::set_pending_push(&conn, &params.id)?;
    Ok(OkResponse { ok: true })
}

// ── Export command ──────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct ExportArticleParams {
    pub article_id: String,
}

#[tauri::command]
pub async fn export_article(params: ExportArticleParams) -> Result<String, AppError> {
    let article_id = params.article_id;
    tokio::task::spawn_blocking(move || local_git::export_article(&article_id))
        .await
        .map_err(|e| AppError::IoError(format!("export_article panicked: {}", e)))?
}
