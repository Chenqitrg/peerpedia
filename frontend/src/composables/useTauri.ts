// Platform abstraction: Tauri IPC vs Web no-op.
//
// In Tauri mode: calls window.__TAURI__.core.invoke() for each IPC command.
// In Web mode:   all methods return null (caller falls back to REST).
//
// Error handling: invoke errors and AppError returns are caught and converted
// to { error: string } so the caller always gets a uniform shape.

import { computed } from 'vue'

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
  account_id: string
  title?: string
  content?: string
  format?: string
}

export interface ListDraftsParams {
  account_id: string
}

export interface GetDraftParams {
  id: string
}

export interface DeleteDraftParams {
  id: string
}

export interface CacheArticleParams {
  id: string
  article_json: string
}

export interface GetCachedArticleParams {
  id: string
}

// ── Return types ──────────────────────────────────────────────────────

export interface Account {
  id: string
  username: string
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

// ── Tauri API access ─────────────────────────────────────────────────

// Use window.__TAURI__.core.invoke directly to avoid static import
// analysis issues with @tauri-apps/api in test environments.
function getInvoke(): ((cmd: string, args?: Record<string, unknown>) => Promise<unknown>) | null {
  const tauriWindow = window as unknown as { __TAURI__?: { core?: { invoke?: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> } } }
  return tauriWindow.__TAURI__?.core?.invoke ?? null
}

// ── Composable ────────────────────────────────────────────────────────

export function useTauri() {
  const isTauri = computed(() => {
    if (typeof window === 'undefined') return false
    return '__TAURI__' in window
  })

  async function _invoke<T>(command: string, args?: Record<string, unknown>): Promise<T | { error: string } | null> {
    if (!isTauri.value) return null

    const invokeFn = getInvoke()
    if (!invokeFn) return { error: 'Tauri core API not available' }

    try {
      // Tauri 2.x uses named arguments: invoke(cmd, { paramName: args })
      const result = await invokeFn(command, args ? { params: args } : undefined)

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

  return {
    isTauri,

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

    // Article cache
    async cacheArticle(params: CacheArticleParams) {
      return _invoke<{ ok: boolean }>('cache_article', params as unknown as Record<string, unknown>)
    },
    async getCachedArticle(params: GetCachedArticleParams) {
      return _invoke<CachedArticle>('get_cached_article', params as unknown as Record<string, unknown>)
    },
  }
}
