// Platform abstraction: Tauri IPC vs Web no-op vs Dev mock.
//
// In Tauri mode:           calls window.__TAURI__.core.invoke() for each IPC command.
// In Dev mock mode:         uses localStorage-backed mock (activated by ?tauri URL param).
// In Web mode (neither):    all methods return null (caller falls back to REST).
//
// Error handling: invoke errors and AppError returns are caught and converted
// to { error: string } so the caller always gets a uniform shape.

import { computed } from 'vue'
import { loadString, loadJSON, saveString, saveJSON, remove } from './useLocalStorage'

// ── Dev mock activation (module-level, runs once on import) ────────────

if (typeof window !== 'undefined') {
  const q = new URLSearchParams(window.location.search)
  if (q.has('tauri')) {
    if (q.get('tauri') === '0') remove('peerpedia_dev_tauri')
    else saveString('peerpedia_dev_tauri', '1')
  }
}

function isDevMockActive(): boolean {
  if (typeof window === 'undefined') return false
  try {
    return loadString('peerpedia_dev_tauri') === '1'
  } catch {
    return false
  }
}

// ── Dev mock storage (localStorage-backed) ─────────────────────────────

interface MockAccount { id: string; username: string; password: string }
interface MockDraft { id: string; account_id: string; title: string; content: string; format: string; updated_at: string }
interface MockCacheEntry { id: string; json: string; cached_at: string }

function _load<T>(key: string, fallback: T): T {
  return loadJSON<T>(key) ?? fallback
}
function _save<T>(key: string, val: T) {
  saveJSON(key, val)
}

const _draftsKey = '_t_drafts', _cacheKey = '_t_cache', _acctsKey = '_t_accts'

async function devMockInvoke(cmd: string, args?: Record<string, unknown>): Promise<unknown> {
  const a = (args && (args as any).params) || {}
  const accounts = _load<MockAccount[]>(_acctsKey, [])
  const drafts = _load<MockDraft[]>(_draftsKey, [])
  const cache = _load<Record<string, MockCacheEntry>>(_cacheKey, {})

  switch (cmd) {
    case 'create_account': {
      if (accounts.find(x => x.username === a.username))
        return { code: 'DUPLICATE', message: 'Username exists' }
      const acct: MockAccount = { id: crypto.randomUUID(), username: a.username, password: a.password }
      accounts.push(acct)
      _save(_acctsKey, accounts)
      return { id: acct.id, username: acct.username }
    }
    case 'login': {
      const acct = accounts.find(x => x.username === a.username)
      if (!acct) return { code: 'NOT_FOUND', message: 'User not found' }
      if (acct.password !== a.password) return { code: 'AUTH_FAILED', message: 'Incorrect password' }
      return { id: acct.id, username: acct.username }
    }
    case 'list_accounts':
      return accounts.map(x => ({ id: x.id, username: x.username }))
    case 'save_draft': {
      const id: string = (a.id as string) || crypto.randomUUID()
      const draft: MockDraft = { id, account_id: a.account_id as string || '', title: (a.title as string) || '', content: (a.content as string) || '', format: (a.format as string) || 'markdown', updated_at: new Date().toISOString() }
      const idx = drafts.findIndex(x => x.id === id)
      if (idx >= 0) drafts[idx] = draft; else drafts.push(draft)
      _save(_draftsKey, drafts)
      return draft
    }
    case 'list_drafts':
      return drafts.filter(x => x.account_id === a.account_id).sort((x, y) => y.updated_at.localeCompare(x.updated_at)).map(x => ({ id: x.id, title: x.title, updated_at: x.updated_at }))
    case 'get_draft': {
      const d = drafts.find(x => x.id === a.id)
      return d || { code: 'NOT_FOUND', message: 'Draft not found' }
    }
    case 'delete_draft':
      _save(_draftsKey, drafts.filter(x => x.id !== a.id))
      return { ok: true }
    case 'cache_article': {
      const entry: MockCacheEntry = { id: a.id as string, json: a.article_json as string, cached_at: new Date().toISOString() }
      cache[a.id as string] = entry
      _save(_cacheKey, cache)
      return { ok: true }
    }
    case 'get_cached_article':
      return cache[a.id as string] || null
    default:
      return { ok: true }
  }
}

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

  const isDevMock = computed(() => !isTauri.value && isDevMockActive())

  async function _invoke<T>(command: string, args?: Record<string, unknown>): Promise<T | { error: string } | null> {
    // Real Tauri IPC
    if (isTauri.value) {
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

    // Dev mock (browser-only)
    if (isDevMock.value) {
      try {
        const result = await devMockInvoke(command, args)
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
    isDevMock,

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
