// Browser-local backend — localStorage-backed mock of Tauri IPC.
// Activated by ?tauri URL param. Used during development without Tauri.
// Extracted from useTauri.ts — zero behavior change.

import { loadString, loadJSON, saveString, saveJSON, remove } from './useLocalStorage'

// ── Mock types ─────────────────────────────────────────────────────────

interface MockAccount { id: string; username: string; password: string }
interface MockDraft { id: string; account_id: string; title: string; content: string; format: string; updated_at: string }
interface MockCacheEntry { id: string; json: string; cached_at: string }
interface MockFollow { follower_id: string; followed_id: string; created_at: string }
interface MockBookmark { user_id: string; article_id: string; created_at: string }

// ── Browser-local activation (module-level, runs once on import) ─────────

if (typeof window !== 'undefined') {
  const q = new URLSearchParams(window.location.search)
  if (q.has('tauri')) {
    if (q.get('tauri') === '0') remove('peerpedia_browser_local')
    else saveString('peerpedia_browser_local', '1')
  }
}

export function isBrowserLocalActive(): boolean {
  if (typeof window === 'undefined') return false
  try {
    return loadString('peerpedia_browser_local') === '1'
  } catch {
    return false
  }
}

// ── Storage helpers ────────────────────────────────────────────────────

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

// ── Mock backend ───────────────────────────────────────────────────────

export async function browserLocalInvoke(cmd: string, args?: Record<string, unknown>): Promise<unknown> {
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
      // Return raw IDs — followed users may be server users
      // whose UUIDs don't exist in local accounts.
      return follows.filter(x => x.followed_id === targetId).map(x => ({ id: x.follower_id }))
    }
    case 'get_following': {
      const targetId = (a.followed_id as string) || (a.user_id as string) || ''
      // Return raw IDs — followed users may be server users
      // whose UUIDs don't exist in local accounts.
      return follows.filter(x => x.follower_id === targetId).map(x => ({ id: x.followed_id }))
    }
    case 'get_follower_count': {
      const targetId = (a.followed_id as string) || (a.user_id as string) || ''
      return { count: follows.filter(x => x.followed_id === targetId).length }
    }
    case 'get_following_count': {
      const targetId = (a.followed_id as string) || (a.user_id as string) || ''
      return { count: follows.filter(x => x.follower_id === targetId).length }
    }
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
      const draft = drafts.find(x => x.id === a.article_id)
      return (draft?.content) || ''
    }
    case 'compile_typst': {
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
