// Parameter and return types for Tauri IPC commands.
// Extracted from useTauri.ts — pure type definitions, no runtime code.

// ── Parameter types (mirrors Rust IPC command params) ─────────────────

export interface CreateAccountParams {
  username: string
  password: string
  email?: string
  name?: string
}

export interface LoginParams {
  username: string
  password: string
}

export interface SaveDraftParams {
  id?: string
  token?: string
  account_id?: string  // backward compat
  title?: string
  content?: string
  format?: string
}

export interface ListDraftsParams {
  token?: string
  account_id?: string  // backward compat — _invoke auto-replaces with token
}

export interface GetDraftParams {
  id: string
  token?: string
  account_id?: string  // backward compat
}

export interface DeleteDraftParams {
  id: string
  token?: string
  account_id?: string  // backward compat
}

export interface DeleteArticleParams {
  id: string
  token?: string
  account_id?: string
}

export interface CacheArticleParams {
  id: string
  article_json: string
}

export interface GetCachedArticleParams {
  id: string
}

export interface FollowUserParams {
  token?: string
  follower_id?: string  // backward compat — _invoke replaces with token
  followed_id: string
}

export interface IsFollowingParams {
  token?: string
  follower_id?: string  // backward compat
  followed_id: string
}

export interface GetFollowListParams {
  token?: string
  user_id?: string  // backward compat — used to query followers of another user
}

export interface BookmarkParams {
  token?: string
  user_id?: string  // backward compat
  article_id: string
}

export interface GetBookmarksParams {
  token?: string
  user_id?: string  // backward compat
}

// ── Git params ─────────────────────────────────────────────────────────

export interface GitInitParams {
  article_id: string
  content?: string
  format?: string
  commit_message?: string
  author: string
}

export interface GitCommitParams {
  article_id: string
  content?: string
  format?: string
  commit_message?: string
  author: string
}

export interface GitHistoryParams {
  article_id: string
}

export interface GitShowParams {
  article_id: string
  commit_hash: string
}

export interface GitRollbackParams {
  article_id: string
  commit_hash: string
  author: string
}

export interface SetServerArticleIdParams {
  draft_id: string
  server_article_id: string
  server_commit_hash: string
  token?: string
  account_id?: string
}

export interface InvalidateCacheParams {
  article_id: string
}

export interface GitCommitResult {
  hash: string
  message: string
}

export interface CommitEntry {
  hash: string
  message: string
  author: string
  timestamp: string
}

// ── Return types ──────────────────────────────────────────────────────

export interface Account {
  id: string
  username: string
  email?: string  // from Rust login (AccountWithToken)
  name?: string   // from Rust login (AccountWithToken)
}

export interface AccountSummary {
  id: string
  username: string
}

export interface Draft {
  id: string
  account_id: string
  title: string
  content: string
  format: string
  updated_at: string
  server_article_id?: string | null
  server_commit_hash?: string | null
}

export interface DraftSummary {
  id: string
  title: string
  updated_at: string
}

export interface CachedArticle {
  id: string
  json: string
  cached_at: string
}
