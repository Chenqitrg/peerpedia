// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { describe, it, expect, beforeEach } from 'vitest'
import { useTauri } from '../useTauri'

/** Narrow Tauri IPC mock result — casts away the error union for test assertions. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ok<T>(result: any): T {
  if (result && typeof result === 'object' && 'error' in result)
    throw new Error(`Unexpected IPC error in test: ${result.error}`)
  return result as T
}

describe('useTauri', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
  })

  it('detects Web mode (no __TAURI__)', () => {
    const tauri = useTauri()
    expect(tauri.isTauri.value).toBe(false)
  })

  it('detects Tauri mode when __TAURI__ is present', () => {
    ;(window as any).__TAURI__ = { core: { invoke: async () => ({}) } }
    const tauri = useTauri()
    expect(tauri.isTauri.value).toBe(true)
  })

  it('createAccount returns null in Web mode', async () => {
    const tauri = useTauri()
    const result = await tauri.createAccount({
      username: 'test', password: 'pass', email: '', name: '',
    })
    expect(result).toBeNull()
  })

  it('login returns null in Web mode', async () => {
    const tauri = useTauri()
    const result = await tauri.login({ username: 'test', password: 'pass' })
    expect(result).toBeNull()
  })

  it('listAccounts returns null in Web mode', async () => {
    const tauri = useTauri()
    const result = await tauri.listAccounts()
    expect(result).toBeNull()
  })

  it('calls invoke in Tauri mode for login', async () => {
    const mockInvoke = async (_cmd: string, _args?: any) => ({ id: 'u1', username: 'alice' })
    ;(window as any).__TAURI__ = { core: { invoke: mockInvoke } }

    const tauri = useTauri()
    const result = await tauri.login({ username: 'alice', password: 'pass' })
    expect(result).toEqual({ id: 'u1', username: 'alice' })
  })

  it('calls invoke in Tauri mode for saveDraft', async () => {
    let capturedCmd = ''
    let capturedArgs: any = {}
    const mockInvoke = async (cmd: string, args?: any) => {
      capturedCmd = cmd
      capturedArgs = args
      return { id: 'd1', title: 'Draft', content: '# H', format: 'md', updated_at: '2026-01-01', account_id: 'a1' }
    }
    ;(window as any).__TAURI__ = { core: { invoke: mockInvoke } }

    const tauri = useTauri()
    const result = await tauri.saveDraft({ account_id: 'a1', title: 'Draft', content: '# H', format: 'markdown' })
    expect(capturedCmd).toBe('save_draft')
    // Tauri 2.x wraps args under the named parameter key 'params'
    expect(capturedArgs.params).toMatchObject({ account_id: 'a1', title: 'Draft' })
    expect(result).toHaveProperty('id', 'd1')
  })

  it('returns error object when invoke throws', async () => {
    const mockInvoke = async () => { throw new Error('IPC failed') }
    ;(window as any).__TAURI__ = { core: { invoke: mockInvoke } }

    const tauri = useTauri()
    const result = await tauri.login({ username: 'alice', password: 'pass' })
    expect(result).toEqual({ error: 'IPC failed' })
  })

  it('returns error object when invoke returns AppError shape', async () => {
    const mockInvoke = async () => ({ code: 'AUTH_FAILED', message: 'Incorrect password' })
    ;(window as any).__TAURI__ = { core: { invoke: mockInvoke } }

    const tauri = useTauri()
    const result = await tauri.login({ username: 'alice', password: 'wrong' })
    expect(result).toEqual({ error: 'Incorrect password' })
  })

  it('returns error when core API is missing in Tauri mode', async () => {
    ;(window as any).__TAURI__ = {} // no .core
    const tauri = useTauri()
    expect(tauri.isTauri.value).toBe(true)
    const result = await tauri.login({ username: 'alice', password: 'pass' })
    expect(result).toEqual({ error: 'Tauri core API not available' })
  })
})

// ── Browser-local mode tests ──────────────────────────────────────────────

describe('useTauri — browserLocal activation', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
  })

  it('isBrowserLocal is false by default', () => {
    const tauri = useTauri()
    expect(tauri.isBrowserLocal.value).toBe(false)
  })

  it('isBrowserLocal is true when localStorage flag is set', () => {
    localStorage.setItem('peerpedia_browser_local', '1')
    const tauri = useTauri()
    expect(tauri.isBrowserLocal.value).toBe(true)
  })

  it('isBrowserLocal returns false when __TAURI__ is present (real Tauri wins)', () => {
    ;(window as any).__TAURI__ = { core: { invoke: async () => ({}) } }
    localStorage.setItem('peerpedia_browser_local', '1')
    const tauri = useTauri()
    expect(tauri.isTauri.value).toBe(true)
    expect(tauri.isBrowserLocal.value).toBe(false)
  })
})

describe('useTauri — browserLocal accounts', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
    localStorage.setItem('peerpedia_browser_local', '1')
  })

  it('createAccount creates a new account', async () => {
    const tauri = useTauri()
    const result = await tauri.createAccount({ username: 'alice', password: 'secret' })
    expect(result).toHaveProperty('id')
    expect(result).toHaveProperty('username', 'alice')
    expect(result).not.toHaveProperty('error')
  })

  it('createAccount rejects duplicate username', async () => {
    const tauri = useTauri()
    await tauri.createAccount({ username: 'alice', password: 'secret' })
    const result = await tauri.createAccount({ username: 'alice', password: 'other' })
    expect(result).toHaveProperty('error', 'Username exists')
  })

  it('login succeeds with correct credentials', async () => {
    const tauri = useTauri()
    await tauri.createAccount({ username: 'alice', password: 'secret' })
    const result = await tauri.login({ username: 'alice', password: 'secret' })
    expect(result).toHaveProperty('id')
    expect(result).toHaveProperty('username', 'alice')
    expect(result).not.toHaveProperty('error')
  })

  it('login fails with wrong password', async () => {
    const tauri = useTauri()
    await tauri.createAccount({ username: 'alice', password: 'secret' })
    const result = await tauri.login({ username: 'alice', password: 'wrong' })
    expect(result).toHaveProperty('error', 'Incorrect password')
  })

  it('login fails for non-existent user', async () => {
    const tauri = useTauri()
    const result = await tauri.login({ username: 'nobody', password: 'pass' })
    expect(result).toHaveProperty('error', 'User not found')
  })

  it('listAccounts returns all created accounts', async () => {
    const tauri = useTauri()
    await tauri.createAccount({ username: 'alice', password: 'x' })
    await tauri.createAccount({ username: 'bob', password: 'x' })
    const result = await tauri.listAccounts()
    expect(Array.isArray(result)).toBe(true)
    expect(result).toHaveLength(2)
    expect((result as any[]).map(a => a.username).sort()).toEqual(['alice', 'bob'])
  })
})

describe('useTauri — browserLocal drafts', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
    localStorage.setItem('peerpedia_browser_local', '1')
  })

  it('saveDraft creates a new draft', async () => {
    const tauri = useTauri()
    const result = await tauri.saveDraft({ account_id: 'a1', title: 'My Draft', content: '# Hello', format: 'markdown' })
    expect(result).toHaveProperty('id')
    expect(result).toHaveProperty('title', 'My Draft')
    expect(result).toHaveProperty('content', '# Hello')
    expect(result).toHaveProperty('format', 'markdown')
    expect(result).not.toHaveProperty('error')
  })

  it('saveDraft updates an existing draft', async () => {
    const tauri = useTauri()
    const created = await tauri.saveDraft({ account_id: 'a1', title: 'V1', content: 'old', format: 'markdown' }) as any
    const updated = await tauri.saveDraft({ id: created.id, account_id: 'a1', title: 'V2', content: 'new', format: 'markdown' }) as any
    expect(updated.id).toBe(created.id)
    expect(updated.title).toBe('V2')
    expect(updated.content).toBe('new')
  })

  it('getDraft returns draft by id', async () => {
    const tauri = useTauri()
    const created = await tauri.saveDraft({ account_id: 'a1', title: 'T', content: 'C', format: 'md' }) as any
    const result = await tauri.getDraft({ id: created.id })
    expect(result).toHaveProperty('title', 'T')
    expect(result).toHaveProperty('content', 'C')
  })

  it('getDraft returns error for missing draft', async () => {
    const tauri = useTauri()
    const result = await tauri.getDraft({ id: 'nonexistent' })
    expect(result).toHaveProperty('error', 'Draft not found')
  })

  it('listDrafts filters by account_id and sorts by updated_at desc', async () => {
    const tauri = useTauri()
    await tauri.saveDraft({ account_id: 'a1', title: 'A1 Draft', content: 'x', format: 'md' })
    await tauri.saveDraft({ account_id: 'a2', title: 'A2 Draft', content: 'x', format: 'md' })
    await tauri.saveDraft({ account_id: 'a1', title: 'A1 Second', content: 'y', format: 'md' })

    const a1Drafts = await tauri.listDrafts({ account_id: 'a1' })
    expect(Array.isArray(a1Drafts)).toBe(true)
    expect(a1Drafts).toHaveLength(2)

    const a2Drafts = await tauri.listDrafts({ account_id: 'a2' })
    expect(a2Drafts).toHaveLength(1)
    expect((a2Drafts as any[])[0].title).toBe('A2 Draft')
  })

  it('deleteDraft removes draft', async () => {
    const tauri = useTauri()
    const created = await tauri.saveDraft({ account_id: 'a1', title: 'To Delete', content: 'x', format: 'md' }) as any
    await tauri.deleteDraft({ id: created.id })
    const result = await tauri.getDraft({ id: created.id })
    expect(result).toHaveProperty('error', 'Draft not found')
  })
})

describe('useTauri — follow methods return null (server is source of truth)', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
    localStorage.setItem('peerpedia_browser_local', '1')
  })

  it('follow methods return null to signal REST API fallback', async () => {
    const tauri = useTauri()
    expect(await tauri.followUser({ follower_id: 'u1', followed_id: 'u2' })).toBeNull()
    expect(await tauri.unfollowUser({ follower_id: 'u1', followed_id: 'u2' })).toBeNull()
    expect(await tauri.isFollowing({ follower_id: 'u1', followed_id: 'u2' })).toBeNull()
    expect(await tauri.getFollowing({ user_id: 'u1' })).toBeNull()
    expect(await tauri.getFollowers({ user_id: 'u1' })).toBeNull()
    expect(await tauri.getFollowerCount({ user_id: 'u1' })).toBeNull()
    expect(await tauri.getFollowingCount({ user_id: 'u1' })).toBeNull()
  })
})

describe('useTauri — browserLocal bookmarks', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
    localStorage.setItem('peerpedia_browser_local', '1')
  })

  it('addBookmark creates a bookmark', async () => {
    const tauri = useTauri()
    const result = await tauri.addBookmark({ user_id: 'u1', article_id: 'art1' })
    expect(result).toEqual({ ok: true })
  })

  it('addBookmark is idempotent (double bookmark is safe)', async () => {
    const tauri = useTauri()
    await tauri.addBookmark({ user_id: 'u1', article_id: 'art1' })
    await tauri.addBookmark({ user_id: 'u1', article_id: 'art1' })
    const result = await tauri.isBookmarked({ user_id: 'u1', article_id: 'art1' })
    expect(result).toEqual({ bookmarked: true })
  })

  it('removeBookmark removes a bookmark', async () => {
    const tauri = useTauri()
    await tauri.addBookmark({ user_id: 'u1', article_id: 'art1' })
    await tauri.removeBookmark({ user_id: 'u1', article_id: 'art1' })
    const result = await tauri.isBookmarked({ user_id: 'u1', article_id: 'art1' })
    expect(result).toEqual({ bookmarked: false })
  })

  it('isBookmarked returns false when not bookmarked', async () => {
    const tauri = useTauri()
    const result = await tauri.isBookmarked({ user_id: 'u1', article_id: 'art9' })
    expect(result).toEqual({ bookmarked: false })
  })

  it('getBookmarks returns user bookmarks only', async () => {
    const tauri = useTauri()
    await tauri.addBookmark({ user_id: 'u1', article_id: 'art1' })
    await tauri.addBookmark({ user_id: 'u1', article_id: 'art2' })
    await tauri.addBookmark({ user_id: 'u2', article_id: 'art3' })

    const u1Bookmarks = await tauri.getBookmarks({ user_id: 'u1' })
    expect(Array.isArray(u1Bookmarks)).toBe(true)
    expect(u1Bookmarks).toHaveLength(2)
    expect((u1Bookmarks as any[]).map(b => b.article_id).sort()).toEqual(['art1', 'art2'])

    const u2Bookmarks = await tauri.getBookmarks({ user_id: 'u2' })
    expect(u2Bookmarks).toHaveLength(1)
    expect((u2Bookmarks as any[])[0].article_id).toBe('art3')
  })
})

describe('useTauri — browserLocal article cache', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
    localStorage.setItem('peerpedia_browser_local', '1')
  })

  it('cacheArticle stores and getCachedArticle retrieves', async () => {
    const tauri = useTauri()
    await tauri.cacheArticle({ id: 'art1', article_json: '{"title":"Hello"}' })
    const result = await tauri.getCachedArticle({ id: 'art1' })
    expect(result).toHaveProperty('id', 'art1')
    expect(result).toHaveProperty('json', '{"title":"Hello"}')
    expect(result).toHaveProperty('cached_at')
  })

  it('getCachedArticle returns null for unknown id', async () => {
    const tauri = useTauri()
    const result = await tauri.getCachedArticle({ id: 'nonexistent' })
    expect(result).toBeNull()
  })
})

describe('useTauri — browserLocal error handling', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
    localStorage.setItem('peerpedia_browser_local', '1')
  })

  it('browserLocalInvoke returns { ok: true } for known commands', async () => {
    // Use cacheArticle — a valid non-follow command through browserLocalBackend.
    const tauri = useTauri()
    const result = await tauri.cacheArticle({ id: 'test', article_json: '{}' })
    expect(result).toEqual({ ok: true })
  })
})

describe('useTauri — session token sharing', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
    localStorage.setItem('peerpedia_browser_local', '1')
  })

  it('setSessionToken on one instance is visible to another instance', () => {
    const tauriA = useTauri()
    tauriA.setSessionToken('shared-token')

    const tauriB = useTauri()
    expect(tauriB.getSessionToken()).toBe('shared-token')
  })

  it('setSessionToken(null) clears token across instances', () => {
    const tauriA = useTauri()
    tauriA.setSessionToken('shared-token')

    const tauriB = useTauri()
    tauriB.setSessionToken(null)

    const tauriC = useTauri()
    expect(tauriC.getSessionToken()).toBeNull()
  })

  it('session token is injected into listDrafts args replacing account_id', async () => {
    // Simulate the EXACT real flow: login → get token → setSessionToken → save draft
    // (same instance, like useUserStore does) → then use DIFFERENT instance for listDrafts
    // (like UserPage does). The critical point: setSessionToken must use the token from
    // the login response, which matches a real session in the mock backend.
    const tauriA = useTauri()

    // Step 1: Create account (like registerLocal)
    await tauriA.createAccount({ username: 'alice', password: 'secret' })

    // Step 2: Login and use the ACTUAL returned token (like loginLocal)
    const loginResult = await tauriA.login({ username: 'alice', password: 'secret' }) as any
    const accountId = loginResult.id
    const realToken = loginResult.token
    expect(realToken).toBeTruthy()
    tauriA.setSessionToken(realToken)

    // Step 3: Save a draft (like EditorPage.saveDraft via _invoke)
    await tauriA.saveDraft({ account_id: accountId, title: 'My Draft', content: '# Hello', format: 'markdown' })

    // Step 4: Page refresh simulation — new useTauri() instance (like UserPage)
    // The module-level _sessionToken should still be set from step 2
    const tauriB = useTauri()
    const drafts = await tauriB.listDrafts({ account_id: 'any-id-should-be-replaced' })
    expect(Array.isArray(drafts)).toBe(true)
    expect(drafts).toHaveLength(1)
    expect((drafts as any[])[0].title).toBe('My Draft')
  })

  it('listDrafts works WITHOUT session token via backward compat account_id fallback', async () => {
    // This tests the case where isLocalMode() returns false → token not restored
    const tauri = useTauri()
    // NEVER call setSessionToken — simulate store init failing to restore token
    await tauri.createAccount({ username: 'bob', password: 'pass' })
    const loginResult = await tauri.login({ username: 'bob', password: 'pass' }) as any
    const accountId = loginResult.id
    // Save draft with account_id
    await tauri.saveDraft({ account_id: accountId, title: 'Backward Compat Draft', content: '# Test', format: 'markdown' })
    // List drafts — _resolveToken should fall back to a.account_id since token is null
    const drafts = ok<Array<{ title: string }>>(await tauri.listDrafts({ account_id: accountId }))
    expect(drafts).toHaveLength(1)
    expect(drafts[0].title).toBe('Backward Compat Draft')
  })

  it('full login→save→pageRefresh→list cycle (simulates user flow)', async () => {
    // Phase 1: Initial login
    const tauri1 = useTauri()
    await tauri1.createAccount({ username: 'carol', password: 's3cret', email: '', name: 'Carol' })
    const login = await tauri1.login({ username: 'carol', password: 's3cret' }) as any
    const aid = login.id
    const tok = login.token

    // Simulate useUserStore.loginLocal: save token, set session
    tauri1.setSessionToken(tok)
    localStorage.setItem('peerpedia_local_token', tok)
    // Also save the viewer so store.init can find it
    const viewer = { id: aid, username: 'carol', name: 'Carol' }
    localStorage.setItem('viewer', JSON.stringify(viewer))

    // Phase 2: Save a draft (simulates EditorPage)
    const saved = await tauri1.saveDraft({ account_id: aid, title: 'Test Draft', content: '# Hi', format: 'markdown' }) as any
    expect(saved).toHaveProperty('id')

    // Phase 3: Simulate page REFRESH — the module-level _sessionToken resets
    // to null. The store.init re-reads from localStorage and calls
    // setSessionToken (simulated here).
    const tauri2 = useTauri()
    const restoredToken = localStorage.getItem('peerpedia_local_token')
    expect(restoredToken).toBe(tok)
    tauri2.setSessionToken(restoredToken)

    // Phase 4: UserPage.loadArticles — list drafts
    const drafts = ok<Array<{ title: string }>>(await tauri2.listDrafts({ account_id: aid }))
    expect(drafts.length).toBeGreaterThanOrEqual(1)
    expect(drafts[0].title).toBe('Test Draft')
  })
})

describe('useTauri — browserLocal searchCachedArticles', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
    localStorage.setItem('peerpedia_browser_local', '1')
  })

  it('returns articles matching query by title', async () => {
    const tauri = useTauri()
    await tauri.cacheArticle({ id: 'a1', article_json: JSON.stringify({ title: 'Quantum Mechanics', content_preview: 'Intro to QM' }) })
    await tauri.cacheArticle({ id: 'a2', article_json: JSON.stringify({ title: 'Classical Physics', content_preview: 'Newtonian' }) })
    await tauri.cacheArticle({ id: 'a3', article_json: JSON.stringify({ title: 'Quantum Computing', content_preview: 'Qubits' }) })

    const results = ok<Array<{ id: string }>>(await tauri.searchCachedArticles({ q: 'quantum' }))
    expect(results.length).toBe(2)
    expect(results.map(r => r.id).sort()).toEqual(['a1', 'a3'])
  })

  it('returns articles matching query by content_preview', async () => {
    const tauri = useTauri()
    await tauri.cacheArticle({ id: 'a1', article_json: JSON.stringify({ title: 'Article One', content_preview: 'About deep learning' }) })
    await tauri.cacheArticle({ id: 'a2', article_json: JSON.stringify({ title: 'Article Two', content_preview: 'About physics' }) })

    const results = ok<Array<{ id: string }>>(await tauri.searchCachedArticles({ q: 'deep learning' }))
    expect(results.length).toBe(1)
    expect(results[0].id).toBe('a1')
  })

  it('returns all cached articles when query is empty', async () => {
    const tauri = useTauri()
    await tauri.cacheArticle({ id: 'a1', article_json: JSON.stringify({ title: 'A' }) })
    await tauri.cacheArticle({ id: 'a2', article_json: JSON.stringify({ title: 'B' }) })

    const results = ok<Array<{ id: string }>>(await tauri.searchCachedArticles({ q: '' }))
    expect(results.length).toBe(2)
  })

  it('returns empty array when nothing matches', async () => {
    const tauri = useTauri()
    await tauri.cacheArticle({ id: 'a1', article_json: JSON.stringify({ title: 'Physics' }) })

    const results = await tauri.searchCachedArticles({ q: 'biology' })
    expect(results).toEqual([])
  })

  it('returns null in Web mode', async () => {
    localStorage.clear()
    const tauri = useTauri()
    const results = await tauri.searchCachedArticles({ q: 'test' })
    expect(results).toBeNull()
  })

  it('includes updated_at in results', async () => {
    const tauri = useTauri()
    await tauri.cacheArticle({ id: 'a1', article_json: JSON.stringify({ title: 'Test Article', updated_at: '2026-06-01T00:00:00Z' }) })

    const results = ok<Array<{ id: string; title: string }>>(await tauri.searchCachedArticles({ q: 'test' }))
    expect(results[0]).toHaveProperty('id', 'a1')
    expect(results[0]).toHaveProperty('title', 'Test Article')
    expect(results[0]).toHaveProperty('updated_at')
  })
})

describe('useTauri — searchDrafts via account_id (SearchPage flow)', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
    localStorage.setItem('peerpedia_browser_local', '1')
  })

  it('🔴 BUG REPRO: searchDrafts finds draft by account_id from viewer', async () => {
    // Simulate SearchPage flow: login → create draft → search via account_id
    const tauri = useTauri()

    // Step 1: Create account
    const acct = await tauri.createAccount({ username: 'alice', password: 'secret' }) as any
    expect(acct.id).toBeTruthy()
    const accountId = acct.id

    // Step 2: Login (sets session token)
    await tauri.login({ username: 'alice', password: 'secret' })

    // Step 3: Create a draft (uses the session token to scope to account)
    await tauri.saveDraft({
      account_id: accountId,
      title: 'Quantum Mechanics Draft',
      content: '# Quantum Mechanics\n\nIntroduction to QM.',
      format: 'markdown',
    })

    // Step 4: Search — exactly what SearchPage does in local mode
    // SearchPage passes userStore.viewer?.id as account_id
    const results = ok<Array<{ title: string }>>(await tauri.searchDrafts({
      q: 'quantum',
      account_id: accountId,
    }))

    // Should find the draft by title
    expect(results.length).toBe(1)
    expect(results[0].title).toBe('Quantum Mechanics Draft')
  })

  it('🔴 BUG REPRO: searchDrafts finds draft when q is empty (browse all)', async () => {
    const tauri = useTauri()
    const acct = await tauri.createAccount({ username: 'bob', password: 'secret' }) as any
    await tauri.login({ username: 'bob', password: 'secret' })
    await tauri.saveDraft({
      account_id: acct.id,
      title: 'General Relativity Notes',
      content: 'Einstein field equations.',
      format: 'markdown',
    })

    const results = ok<Array<{ title: string }>>(await tauri.searchDrafts({ q: '', account_id: acct.id }))
    expect(results.length).toBeGreaterThanOrEqual(1)
    expect(results.some((r: any) => r.title === 'General Relativity Notes')).toBe(true)
  })

  it('searchDrafts finds draft by account_id without session token', async () => {
    const tauri = useTauri()
    // Create account but DON'T login (no session token set)
    const acct = await tauri.createAccount({ username: 'carol', password: 'secret' }) as any
    // Create draft directly with account_id (like saveDraft mock would)
    // Save draft explicitly sets the account_id
    await tauri.saveDraft({
      account_id: acct.id,
      title: 'Cosmology Notes',
      content: 'Dark energy.',
      format: 'markdown',
    })

    // Now search with account_id but WITHOUT session token
    // This simulates SearchPage: userStore.viewer?.id as account_id
    const results = ok<Array<{ title: string }>>(await tauri.searchDrafts({ q: 'cosmology', account_id: acct.id }))
    expect(results.length).toBe(1)
    expect(results[0].title).toBe('Cosmology Notes')
  })
})

describe('useTauri — browserLocal deleteArticle', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
    localStorage.setItem('peerpedia_browser_local', '1')
  })

  it('🔴 BUG: deleteArticle removes draft from listDrafts', async () => {
    const tauri = useTauri()
    // Create account and draft
    const acct = await tauri.createAccount({ username: 'deluser', password: 'pass' }) as any
    await tauri.login({ username: 'deluser', password: 'pass' })
    await tauri.saveDraft({
      account_id: acct.id,
      title: 'To Be Deleted',
      content: 'Delete me.',
      format: 'markdown',
    })

    // Verify draft exists
    let drafts = ok<Array<{ id: string }>>(await tauri.listDrafts({ account_id: acct.id }))
    expect(drafts.length).toBe(1)

    // Delete it
    const result = await tauri.deleteArticle({ id: drafts[0].id, account_id: acct.id })
    expect(result).toEqual({ ok: true })

    // Verify it's gone
    drafts = ok<Array<{ id: string }>>(await tauri.listDrafts({ account_id: acct.id }))
    expect(drafts.length).toBe(0)
  })

  it('🔴 RECURSIVE: deleted article is fully removed — no draft, no git, no cache', async () => {
    const tauri = useTauri()
    const acct = await tauri.createAccount({ username: 'rectest', password: 'pass' }) as any
    await tauri.login({ username: 'rectest', password: 'pass' })
    await tauri.saveDraft({
      account_id: acct.id,
      title: 'Recursive Delete Test',
      content: '# Recursive\n\nThis article should be fully deleted.',
      format: 'markdown',
    })

    // 1. Verify draft exists
    const draftsBefore = ok<Array<{ id: string }>>(await tauri.listDrafts({ account_id: acct.id }))
    expect(draftsBefore.length).toBe(1)
    const draftId = draftsBefore[0].id

    // 2. Verify draft can be retrieved individually
    const draft = await tauri.getDraft({ id: draftId })
    expect(draft).toHaveProperty('id', draftId)
    expect(draft).toHaveProperty('title', 'Recursive Delete Test')

    // 3. Cache the article (simulating browsing)
    await tauri.cacheArticle({ id: draftId, article_json: JSON.stringify({ title: 'Recursive Delete Test' }) })
    const cachedBefore = await tauri.getCachedArticle({ id: draftId })
    expect(cachedBefore).toHaveProperty('id', draftId)

    // 4. Init git history for the draft
    await tauri.gitInit({ article_id: draftId, content: '# Recursive', format: 'markdown', commit_message: 'init', author: 'rectest', author_id: 'uuid-rectest' })
    const historyBefore = await tauri.gitHistory({ article_id: draftId })
    expect(Array.isArray(historyBefore)).toBe(true)
    expect((historyBefore as any[]).length).toBeGreaterThanOrEqual(1)

    // 5. DELETE
    const result = await tauri.deleteArticle({ id: draftId, account_id: acct.id })
    expect(result).toEqual({ ok: true })

    // 6. Verify draft is gone from list
    const draftsAfter = ok<Array<{ id: string }>>(await tauri.listDrafts({ account_id: acct.id }))
    expect(draftsAfter.length).toBe(0)

    // 7. Verify getDraft returns error (not found)
    const draftAfter = await tauri.getDraft({ id: draftId })
    expect(draftAfter).toHaveProperty('error')

    // 8. Verify cache entry is removed
    const cachedAfter = await tauri.getCachedArticle({ id: draftId })
    expect(cachedAfter).toBeNull()

    // 9. Verify git history is cleaned up
    const historyAfter = await tauri.gitHistory({ article_id: draftId })
    expect(Array.isArray(historyAfter)).toBe(true)
    expect((historyAfter as any[]).length).toBe(0)
  })
})
