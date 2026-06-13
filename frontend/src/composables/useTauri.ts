// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

// Platform abstraction: Tauri IPC vs browser-local vs Web.
//
// In Tauri mode:              calls window.__TAURI__.core.invoke() for each IPC command.
// In browser-local mode:      uses localStorage-backed backend (activated by ?tauri URL param).
// In Web mode (neither):      all methods return null (caller falls back to REST).
//
// Error handling: invoke errors and AppError returns are caught and converted
// to { error: string } so the caller always gets a uniform shape.
//
// Types:     useTauriTypes.ts  — parameter + return type definitions
// Mock:      browserLocalBackend.ts — localStorage-backed CRUD for dev mode

import { computed } from 'vue'
import { browserLocalInvoke, isBrowserLocalActive } from './browserLocalBackend'

// Re-export all types so existing imports don't break
export type {
  CreateAccountParams, LoginParams, SaveDraftParams, ListDraftsParams,
  GetDraftParams, DeleteDraftParams, DeleteArticleParams,
  CacheArticleParams, GetCachedArticleParams,
  BookmarkParams, GetBookmarksParams,
  GitInitParams, GitCommitParams, GitHistoryParams, GitShowParams, GitRollbackParams, GitResetParams, InvalidateCacheParams,
  PendingOp, PendingOpsParams, PendingResolveParams,
  GitCommitResult, CommitEntry,
  Account, AccountSummary, Draft, DraftSummary, CachedArticle,
} from './useTauriTypes'

import type {
  CreateAccountParams, LoginParams, SaveDraftParams, ListDraftsParams,
  GetDraftParams, DeleteDraftParams, DeleteArticleParams,
  CacheArticleParams, GetCachedArticleParams,
  BookmarkParams, GetBookmarksParams,
  GitInitParams, GitCommitParams, GitHistoryParams, GitShowParams, GitRollbackParams, GitResetParams, InvalidateCacheParams,
  PendingOp, PendingOpsParams, PendingResolveParams,
  GitCommitResult, CommitEntry,
  Account, AccountSummary, Draft, DraftSummary, CachedArticle,
} from './useTauriTypes'

// ── Tauri API access ─────────────────────────────────────────────────

// Use window.__TAURI__.core.invoke directly to avoid static import
// analysis issues with @tauri-apps/api in test environments.
function getInvoke(): ((cmd: string, args?: Record<string, unknown>) => Promise<unknown>) | null {
  const tauriWindow = window as unknown as { __TAURI__?: { core?: { invoke?: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> } } }
  return tauriWindow.__TAURI__?.core?.invoke ?? null
}

// ── Shared session token (module-level — shared across all useTauri() calls) ──
// Set by useUserStore after login, used by _invoke to authenticate Tauri commands.
// Must be module-level, not per-instance, because useUserStore and every page
// component call useTauri() independently — they must share the same token.
let _sessionToken: string | null = null

// ── Composable ────────────────────────────────────────────────────────

export function useTauri() {
  const isTauri = computed(() => {
    if (typeof window === 'undefined') return false
    return '__TAURI__' in window
  })

  const isBrowserLocal = computed(() => !isTauri.value && isBrowserLocalActive())

  /** Store a session token for authenticating subsequent Tauri commands. */
  function setSessionToken(token: string | null) {
    _sessionToken = token
  }

  /** Current session token, if any. */
  function getSessionToken(): string | null {
    return _sessionToken
  }

  async function _invoke<T>(command: string, args?: Record<string, unknown>): Promise<T | { error: string } | null> {
    // If a session token is set, add it alongside existing args. We do NOT
    // delete account_id/follower_id/user_id — the backend (both Rust and
    // browser-local mock) resolves token first and falls back to bare IDs.
    // This preserves backward compat when the token hasn't been restored yet
    // (e.g., page refresh before login, or existing users upgrading).
    let resolvedArgs = args
    if (_sessionToken && args && !('token' in args)) {
      resolvedArgs = { ...args, token: _sessionToken }
    }

    // Real Tauri IPC
    if (isTauri.value) {
      const invokeFn = getInvoke()
      if (!invokeFn) return { error: 'Tauri core API not available' }

      try {
        // Tauri 2.x uses named arguments: invoke(cmd, { paramName: args })
        const result = await invokeFn(command, resolvedArgs ? { params: resolvedArgs } : undefined)

        // Check if Rust returned an AppError (serialized as { code, message }).
        if (result && typeof result === 'object' && 'code' in result && 'message' in result) {
          const err = result as unknown as { code: string; message: string }
          return { error: err.message }
        }

        return result as T
      } catch (e: unknown) {
        // Tauri rejects with objects (not Error instances) on command failure.
        const message =
          e instanceof Error ? e.message
          : (typeof e === 'object' && e !== null && 'message' in e) ? String((e as Record<string, unknown>).message)
          : String(e)
        return { error: message }
      }
    }

    // Browser-local backend (browser-only)
    if (isBrowserLocal.value) {
      try {
        const result = await browserLocalInvoke(command, resolvedArgs)
        // Check if mock returned an error shape.
        if (result && typeof result === 'object' && 'code' in result && 'message' in result) {
          const err = result as unknown as { code: string; message: string }
          return { error: err.message }
        }
        return result as T
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : String(e)
        return { error: message }
      }
    }

    return null
  }

  return {
    isTauri,
    isBrowserLocal,
    setSessionToken,
    getSessionToken,

    // Auth
    async createAccount(params: CreateAccountParams) {
      return _invoke<Account>('create_account', params as unknown as Record<string, unknown>)
    },
    async login(params: LoginParams) {
      return _invoke<Account>('login', params as unknown as Record<string, unknown>)
    },
    async listAccounts() {
      return _invoke<AccountSummary[]>('list_accounts')
    },
    async logout(params: { token: string }) {
      return _invoke<{ ok: boolean }>('logout', params as unknown as Record<string, unknown>)
    },

    // Drafts
    async saveDraft(params: SaveDraftParams) {
      return _invoke<Draft>('save_draft', params as unknown as Record<string, unknown>)
    },
    async listDrafts(params: ListDraftsParams) {
      return _invoke<DraftSummary[]>('list_drafts', params as unknown as Record<string, unknown>)
    },
    async getDraft(params: GetDraftParams) {
      return _invoke<Draft>('get_draft', params as unknown as Record<string, unknown>)
    },
    async deleteDraft(params: DeleteDraftParams) {
      return _invoke<{ ok: boolean }>('delete_draft', params as unknown as Record<string, unknown>)
    },
    async deleteArticle(params: DeleteArticleParams) {
      return _invoke<{ ok: boolean }>('delete_article', params as unknown as Record<string, unknown>)
    },

    // Article cache
    async cacheArticle(params: CacheArticleParams) {
      return _invoke<{ ok: boolean }>('cache_article', params as unknown as Record<string, unknown>)
    },
    async getCachedArticle(params: GetCachedArticleParams) {
      return _invoke<CachedArticle>('get_cached_article', params as unknown as Record<string, unknown>)
    },

    // Follows — server is source of truth; these always return null so
    // callers fall back to REST API (online) or useFollowCache (offline).
    async followUser(_params?: Record<string, unknown>) {
      return null as unknown as { ok: boolean }
    },
    async unfollowUser(_params?: Record<string, unknown>) {
      return null as unknown as { ok: boolean }
    },
    async isFollowing(_params?: Record<string, unknown>) {
      return null as unknown as { following: boolean }
    },
    async getFollowers(_params?: Record<string, unknown>) {
      return null as unknown as AccountSummary[]
    },
    async getFollowing(_params?: Record<string, unknown>) {
      return null as unknown as AccountSummary[]
    },
    async getFollowerCount(_params?: Record<string, unknown>) {
      return null as unknown as { count: number }
    },
    async getFollowingCount(_params?: Record<string, unknown>) {
      return null as unknown as { count: number }
    },

    // Bookmarks
    async addBookmark(params: BookmarkParams) {
      return _invoke<{ ok: boolean }>('add_bookmark', params as unknown as Record<string, unknown>)
    },
    async removeBookmark(params: BookmarkParams) {
      return _invoke<{ ok: boolean }>('remove_bookmark', params as unknown as Record<string, unknown>)
    },
    async isBookmarked(params: BookmarkParams) {
      return _invoke<{ bookmarked: boolean }>('is_bookmarked', params as unknown as Record<string, unknown>)
    },
    async getBookmarks(params: GetBookmarksParams) {
      return _invoke<{ user_id: string; article_id: string; created_at: string }[]>('get_bookmarks', params as unknown as Record<string, unknown>)
    },

    // Git
    async gitInit(params: GitInitParams) {
      return _invoke<GitCommitResult>('git_init', params as unknown as Record<string, unknown>)
    },
    async gitCommit(params: GitCommitParams) {
      return _invoke<GitCommitResult>('git_commit', params as unknown as Record<string, unknown>)
    },
    async gitHistory(params: GitHistoryParams) {
      return _invoke<CommitEntry[]>('git_history', params as unknown as Record<string, unknown>)
    },
    async gitShow(params: GitShowParams) {
      return _invoke<string>('git_show', params as unknown as Record<string, unknown>)
    },
    async gitDiff(params: { article_id: string; hash1: string; hash2: string }) {
      return _invoke<{ files: string[]; hunks: { old_start: number; old_lines: number; new_start: number; new_lines: number; header: string; lines: { line_type: 'add' | 'del' | 'ctx'; content: string; old_lineno: number | null; new_lineno: number | null }[] }[] }>('git_diff', params as unknown as Record<string, unknown>)
    },
    async gitRollback(params: GitRollbackParams) {
      return _invoke<GitCommitResult>('git_rollback', params as unknown as Record<string, unknown>)
    },
    async gitResetHard(params: GitResetParams) {
      return _invoke<{ ok: boolean }>('git_reset_hard', params as unknown as Record<string, unknown>)
    },
    async invalidateArticleCache(params: InvalidateCacheParams) {
      return _invoke<{ ok: boolean }>('invalidate_article_cache', params as unknown as Record<string, unknown>)
    },

    // Search
    async searchDrafts(params: { q: string; account_id?: string; token?: string }) {
      return _invoke<{ id: string; title: string; content: string; updated_at: string }[]>('search_drafts', params as unknown as Record<string, unknown>)
    },
    async searchCachedArticles(params: { q: string }) {
      return _invoke<{ id: string; title: string; updated_at: string }[]>('search_cached_articles', params as unknown as Record<string, unknown>)
    },

    // Compile
    async compileTypst(params: { content: string; format: string }) {
      return _invoke<string>('compile_typst', params as unknown as Record<string, unknown>)
    },
    async compileTypstPdf(params: { content: string }) {
      return _invoke<string>('compile_typst_pdf', params as unknown as Record<string, unknown>)
    },
    // Export
    async exportArticle(params: { article_id: string }) {
      return _invoke<string>('export_article', params as unknown as Record<string, unknown>)
    },

    // Pending operations (offline queue)
    async getPendingOps(params: PendingOpsParams) {
      return _invoke<PendingOp[]>('get_pending_ops', params as unknown as Record<string, unknown>)
    },
    async clearPending(params: PendingResolveParams) {
      return _invoke<{ ok: boolean }>('clear_pending', params as unknown as Record<string, unknown>)
    },
    async setPendingDelete(params: PendingResolveParams) {
      return _invoke<{ ok: boolean }>('set_pending_delete', params as unknown as Record<string, unknown>)
    },
    async setPendingPush(params: PendingResolveParams) {
      return _invoke<{ ok: boolean }>('set_pending_push', params as unknown as Record<string, unknown>)
    },
  }
}
