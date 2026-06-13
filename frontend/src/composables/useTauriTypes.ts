// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

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
  author: string       // display name
  author_id: string    // UUID
}

export interface GitCommitParams {
  article_id: string
  content?: string
  format?: string
  commit_message?: string
  author: string       // display name
  author_id: string    // UUID
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
  author: string       // display name
  author_id: string    // UUID
}

export interface PendingOp {
  id: string
  title: string
  op_type: string  // "push" | "delete"
  updated_at: string
  offline_since?: string | null
}

export interface PendingOpsParams {
  token?: string
  account_id?: string
}

export interface PendingResolveParams {
  id: string
  token?: string
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
  pending_push?: boolean
  pending_delete?: boolean
  offline_since?: string | null
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
