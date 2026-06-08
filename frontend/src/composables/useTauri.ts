// Platform abstraction: Tauri IPC vs browser-local vs Web.
//
// In Tauri mode:              calls window.__TAURI__.core.invoke() for each IPC command.
// In browser-local mode:      uses localStorage-backed backend (activated by ?tauri URL param).
// In Web mode (neither):      all methods return null (caller falls back to REST).
//
// Error handling: invoke errors and AppError returns are caught and converted
// to { error: string } so the caller always gets a uniform shape.

import { computed } from 'vue'
import { loadString, loadJSON, saveString, saveJSON, remove } from './useLocalStorage'

// ── Browser-local activation (module-level, runs once on import) ─────────

if (typeof window !== 'undefined') {
  const q = new URLSearchParams(window.location.search)
  if (q.has('tauri')) {
    if (q.get('tauri') === '0') remove('peerpedia_browser_local')
    else saveString('peerpedia_browser_local', '1')
  }
}

function isBrowserLocalActive(): boolean {
  if (typeof window === 'undefined') return false
  try {
    return loadString('peerpedia_browser_local') === '1'
  } catch {
    return false
  }
}

// ── Browser-local storage (localStorage-backed) ──────────────────────────

interface MockAccount { id: string; username: string; password: string }
interface MockDraft { id: string; account_id: string; title: string; content: string; format: string; updated_at: string }
interface MockCacheEntry { id: string; json: string; cached_at: string }
interface MockFollow { follower_id: string; followed_id: string; created_at: string }
interface MockBookmark { user_id: string; article_id: string; created_at: string }

function _load<T>(key: string, fallback: T): T {
  return loadJSON<T>(key) ?? fallback
}
function _save<T>(key: string, val: T) {
  saveJSON(key, val)
}

const _draftsKey = '_t_drafts', _cacheKey = '_t_cache', _acctsKey = '_t_accts'
const _followsKey = '_t_follows', _bookmarksKey = '_t_bookmarks'
const _sessionsKey = '_t_sessions'

/// Resolve a token to account_id in mock mode, or return a raw user identifier.
/// Falls back through: token session lookup → account_id → follower_id → user_id.
function _resolveToken(a: Record<string, unknown>, sessions: { token: string; account_id: string }[]): string | undefined {
  if (a.token) {
    const s = sessions.find(s => s.token === a.token)
    if (s) return s.account_id
  }
  return (a.account_id as string) || (a.follower_id as string) || (a.user_id as string) || undefined
}

async function browserLocalInvoke(cmd: string, args?: Record<string, unknown>): Promise<unknown> {
  const a = args || {}
  const accounts = _load<MockAccount[]>(_acctsKey, [])
  const sessions = _load<{ token: string; account_id: string }[]>(_sessionsKey, [])
  const drafts = _load<MockDraft[]>(_draftsKey, [])
  const cache = _load<Record<string, MockCacheEntry>>(_cacheKey, {})
  const follows = _load<MockFollow[]>(_followsKey, [])
  const bookmarks = _load<MockBookmark[]>(_bookmarksKey, [])

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
      const token = crypto.randomUUID()
      sessions.push({ token, account_id: acct.id })
      _save(_sessionsKey, sessions)
      return { id: acct.id, username: acct.username, token }
    }
    case 'logout': {
      const idx = sessions.findIndex(s => s.token === a.token)
      if (idx >= 0) sessions.splice(idx, 1)
      _save(_sessionsKey, sessions)
      return { ok: true }
    }
    case 'list_accounts':
      return accounts.map(x => ({ id: x.id, username: x.username }))
    case 'save_draft': {
      const accountId = _resolveToken(a, sessions) || ''
      const id: string = (a.id as string) || crypto.randomUUID()
      const draft: MockDraft = { id, account_id: accountId, title: (a.title as string) || '', content: (a.content as string) || '', format: (a.format as string) || 'markdown', updated_at: new Date().toISOString() }
      const idx = drafts.findIndex(x => x.id === id)
      if (idx >= 0) drafts[idx] = draft; else drafts.push(draft)
      _save(_draftsKey, drafts)
      return draft
    }
    case 'list_drafts': {
      const accountId = _resolveToken(a, sessions) || ''
      return drafts.filter(x => x.account_id === accountId).sort((x, y) => y.updated_at.localeCompare(x.updated_at)).map(x => ({ id: x.id, title: x.title, updated_at: x.updated_at }))
    }
    case 'get_draft': {
      const d = drafts.find(x => x.id === a.id)
      return d || { code: 'NOT_FOUND', message: 'Draft not found' }
    }
    case 'delete_draft':
      _save(_draftsKey, drafts.filter(x => x.id !== a.id))
      return { ok: true }
    case 'delete_article':
      // Remove draft + git history + cache entry
      _save(_draftsKey, drafts.filter(x => x.id !== (a.id as string)))
      const gitKey = `_t_git_${a.id}`
      remove(gitKey)
      if (cache[a.id as string]) {
        delete cache[a.id as string]
        _save(_cacheKey, cache)
      }
      return { ok: true }
    case 'cache_article': {
      const entry: MockCacheEntry = { id: a.id as string, json: a.article_json as string, cached_at: new Date().toISOString() }
      cache[a.id as string] = entry
      _save(_cacheKey, cache)
      return { ok: true }
    }
    case 'get_cached_article':
      return cache[a.id as string] || null
    // ── Follows ──────────────────────────────────────────────────────────
    case 'follow_user': {
      const accountId = _resolveToken(a, sessions) || ''
      const exists = follows.find(x => x.follower_id === accountId && x.followed_id === a.followed_id)
      if (!exists) {
        follows.push({ follower_id: accountId, followed_id: a.followed_id as string, created_at: new Date().toISOString() })
        _save(_followsKey, follows)
      }
      return { ok: true }
    }
    case 'unfollow_user': {
      const accountId = _resolveToken(a, sessions) || ''
      _save(_followsKey, follows.filter(x => !(x.follower_id === accountId && x.followed_id === a.followed_id)))
      return { ok: true }
    }
    case 'is_following': {
      const accountId = _resolveToken(a, sessions) || ''
      const f = follows.find(x => x.follower_id === accountId && x.followed_id === a.followed_id)
      return { following: !!f }
    }
    case 'get_followers': {
      const targetId = (a.followed_id as string) || (a.user_id as string) || ''
      const ids = follows.filter(x => x.followed_id === targetId).map(x => x.follower_id)
      return accounts.filter(acct => ids.includes(acct.id)).map(x => ({ id: x.id, username: x.username }))
    }
    case 'get_following': {
      const targetId = (a.followed_id as string) || (a.user_id as string) || ''
      const ids = follows.filter(x => x.follower_id === targetId).map(x => x.followed_id)
      return accounts.filter(acct => ids.includes(acct.id)).map(x => ({ id: x.id, username: x.username }))
    }
    case 'get_follower_count': {
      const targetId = (a.followed_id as string) || (a.user_id as string) || ''
      return { count: follows.filter(x => x.followed_id === targetId).length }
    }
    case 'get_following_count': {
      const targetId = (a.followed_id as string) || (a.user_id as string) || ''
      return { count: follows.filter(x => x.follower_id === targetId).length }
    }
    // ── Bookmarks ────────────────────────────────────────────────────────
    case 'add_bookmark': {
      const accountId = _resolveToken(a, sessions) || ''
      const bm = bookmarks.find(x => x.user_id === accountId && x.article_id === a.article_id)
      if (!bm) {
        bookmarks.push({ user_id: accountId, article_id: a.article_id as string, created_at: new Date().toISOString() })
        _save(_bookmarksKey, bookmarks)
      }
      return { ok: true }
    }
    case 'remove_bookmark': {
      const accountId = _resolveToken(a, sessions) || ''
      _save(_bookmarksKey, bookmarks.filter(x => !(x.user_id === accountId && x.article_id === a.article_id)))
      return { ok: true }
    }
    case 'is_bookmarked': {
      const accountId = _resolveToken(a, sessions) || ''
      const bm = bookmarks.find(x => x.user_id === accountId && x.article_id === a.article_id)
      return { bookmarked: !!bm }
    }
    case 'get_bookmarks': {
      const accountId = _resolveToken(a, sessions) || ''
      const bms = bookmarks.filter(x => x.user_id === accountId)
      return bms.map(b => ({ user_id: b.user_id, article_id: b.article_id, created_at: b.created_at }))
    }
    // ── Git commands ────────────────────────────────────────────────────
    case 'git_init': {
      const key = `_t_git_${a.article_id}`
      const now = new Date().toISOString()
      _save(key, [{
        hash: `0000000${(a.article_id as string).substring(0, 7)}`,
        message: (a.commit_message as string) || 'Initial draft',
        author: (a.author as string) || 'local',
        timestamp: now,
      }])
      return { hash: `0000000${(a.article_id as string).substring(0, 7)}`, message: (a.commit_message as string) || 'Initial draft' }
    }
    case 'git_commit': {
      const key = `_t_git_${a.article_id}`
      const history = _load<any[]>(key, [])
      const newCommit = {
        hash: `1111111${(a.article_id as string).substring(0, 7)}`,
        message: (a.commit_message as string) || 'Edit',
        author: (a.author as string) || 'local',
        timestamp: new Date().toISOString(),
      }
      history.unshift(newCommit)
      _save(key, history)
      return { hash: newCommit.hash, message: newCommit.message }
    }
    case 'git_history': {
      const key = `_t_git_${a.article_id}`
      return _load<any[]>(key, [])
    }
    case 'git_show': {
      // For mock, return draft content as the file at any commit
      const draft = drafts.find(x => x.id === a.article_id)
      return (draft?.content) || ''
    }
    case 'compile_typst': {
      // Mock: return a simple SVG placeholder
      return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><rect width="400" height="200" fill="#0d1117" rx="8"/><text x="20" y="40" fill="#c9d1d9" font-family="monospace" font-size="14">Typst compiled (mock)</text><text x="20" y="65" fill="#8b949e" font-family="monospace" font-size="12">Content: ' + ((a.content as string) || '').substring(0, 50) + '...</text></svg>'
    }
    case 'search_drafts': {
      const q = ((a.q as string) || '').toLowerCase().trim()
      const accountId = _resolveToken(a, sessions) || ''
      let results = drafts.filter(x => x.account_id === accountId)
      if (q) {
        results = results.filter(x =>
          x.title.toLowerCase().includes(q) || x.content.toLowerCase().includes(q)
        )
        // Sort by relevance: exact title > title starts with > title contains > content contains
        results.sort((a, b) => {
          const ta = a.title.toLowerCase(), tb = b.title.toLowerCase()
          const ca = a.content.toLowerCase(), cb = b.content.toLowerCase()
          const ascore = ta === q ? 100 : ta.startsWith(q) ? 50 : ta.includes(q) ? 10 : ca.includes(q) ? 1 : 0
          const bscore = tb === q ? 100 : tb.startsWith(q) ? 50 : tb.includes(q) ? 10 : cb.includes(q) ? 1 : 0
          return bscore - ascore
        })
      }
      return results.map(x => ({ id: x.id, title: x.title, content: x.content, updated_at: x.updated_at }))
    }
    case 'search_cached_articles': {
      const q = ((a.q as string) || '').toLowerCase().trim()
      const values = Object.values(cache) as MockCacheEntry[]
      if (!q) {
        return values.map(e => {
          const parsed = JSON.parse(e.json)
          return { id: e.id, title: parsed.title || '', updated_at: parsed.updated_at || e.cached_at }
        })
      }
      const matched: { id: string; title: string; updated_at: string; _score: number }[] = []
      for (const e of values) {
        try {
          const parsed = JSON.parse(e.json)
          const title = (parsed.title || '').toLowerCase()
          const content = (parsed.content_preview || '').toLowerCase()
          let score = 0
          if (title === q) score = 100
          else if (title.startsWith(q)) score = 50
          else if (title.includes(q)) score = 10
          else if (content.includes(q)) score = 1
          if (score > 0) {
            matched.push({ id: e.id, title: parsed.title || '', updated_at: parsed.updated_at || e.cached_at, _score: score })
          }
        } catch { /* skip corrupt cache entries */ }
      }
      matched.sort((a, b) => b._score - a._score)
      return matched.map(({ id, title, updated_at }) => ({ id, title, updated_at }))
    }
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

    // Follows
    async followUser(params: FollowUserParams) {
      return _invoke<{ ok: boolean }>('follow_user', params as unknown as Record<string, unknown>)
    },
    async unfollowUser(params: FollowUserParams) {
      return _invoke<{ ok: boolean }>('unfollow_user', params as unknown as Record<string, unknown>)
    },
    async isFollowing(params: IsFollowingParams) {
      return _invoke<{ following: boolean }>('is_following', params as unknown as Record<string, unknown>)
    },
    async getFollowers(params: GetFollowListParams) {
      return _invoke<AccountSummary[]>('get_followers', params as unknown as Record<string, unknown>)
    },
    async getFollowing(params: GetFollowListParams) {
      return _invoke<AccountSummary[]>('get_following', params as unknown as Record<string, unknown>)
    },
    async getFollowerCount(params: GetFollowListParams) {
      return _invoke<{ count: number }>('get_follower_count', params as unknown as Record<string, unknown>)
    },
    async getFollowingCount(params: GetFollowListParams) {
      return _invoke<{ count: number }>('get_following_count', params as unknown as Record<string, unknown>)
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
      return _invoke<MockBookmark[]>('get_bookmarks', params as unknown as Record<string, unknown>)
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
  }
}
