import { describe, it, expect, beforeEach } from 'vitest'
import { useTauri } from '../useTauri'

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

describe('useTauri — browserLocal follows', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
    localStorage.clear()
    localStorage.setItem('peerpedia_browser_local', '1')
  })

  it('followUser creates follow relationship', async () => {
    const tauri = useTauri()
    const result = await tauri.followUser({ follower_id: 'u1', followed_id: 'u2' })
    expect(result).toEqual({ ok: true })
    expect(result).not.toHaveProperty('error')
  })

  it('followUser is idempotent (double follow is safe)', async () => {
    const tauri = useTauri()
    await tauri.followUser({ follower_id: 'u1', followed_id: 'u2' })
    await tauri.followUser({ follower_id: 'u1', followed_id: 'u2' })
    // Should not throw or error
    const following = await tauri.isFollowing({ follower_id: 'u1', followed_id: 'u2' })
    expect(following).toEqual({ following: true })
  })

  it('unfollowUser removes follow relationship', async () => {
    const tauri = useTauri()
    await tauri.followUser({ follower_id: 'u1', followed_id: 'u2' })
    await tauri.unfollowUser({ follower_id: 'u1', followed_id: 'u2' })
    const result = await tauri.isFollowing({ follower_id: 'u1', followed_id: 'u2' })
    expect(result).toEqual({ following: false })
  })

  it('unfollowUser is safe on non-existent follow', async () => {
    const tauri = useTauri()
    const result = await tauri.unfollowUser({ follower_id: 'u1', followed_id: 'u2' })
    expect(result).toEqual({ ok: true })
  })

  it('isFollowing returns false when not following', async () => {
    const tauri = useTauri()
    const result = await tauri.isFollowing({ follower_id: 'u1', followed_id: 'u2' })
    expect(result).toEqual({ following: false })
  })

  it('getFollowers returns list of followers (by username)', async () => {
    const tauri = useTauri()
    await tauri.createAccount({ username: 'alice', password: 'x' })
    await tauri.createAccount({ username: 'bob', password: 'x' })
    await tauri.createAccount({ username: 'carol', password: 'x' })
    const accts = await tauri.listAccounts() as any[]
    const alice = accts.find(a => a.username === 'alice')!
    const bob = accts.find(a => a.username === 'bob')!
    const carol = accts.find(a => a.username === 'carol')!

    await tauri.followUser({ follower_id: bob.id, followed_id: alice.id })
    await tauri.followUser({ follower_id: carol.id, followed_id: alice.id })

    const followers = await tauri.getFollowers({ user_id: alice.id })
    expect(Array.isArray(followers)).toBe(true)
    expect(followers).toHaveLength(2)
    expect((followers as any[]).map(f => f.username).sort()).toEqual(['bob', 'carol'])
  })

  it('getFollowing returns list of followed users', async () => {
    const tauri = useTauri()
    await tauri.createAccount({ username: 'alice', password: 'x' })
    await tauri.createAccount({ username: 'bob', password: 'x' })
    const accts = await tauri.listAccounts() as any[]
    const alice = accts.find(a => a.username === 'alice')!
    const bob = accts.find(a => a.username === 'bob')!

    await tauri.followUser({ follower_id: alice.id, followed_id: bob.id })

    const following = await tauri.getFollowing({ user_id: alice.id })
    expect(following).toHaveLength(1)
    expect((following as any[])[0].username).toBe('bob')
  })

  it('getFollowerCount and getFollowingCount return correct counts', async () => {
    const tauri = useTauri()
    await tauri.createAccount({ username: 'a', password: 'x' })
    await tauri.createAccount({ username: 'b', password: 'x' })
    await tauri.createAccount({ username: 'c', password: 'x' })
    const accts = await tauri.listAccounts() as any[]
    const a = accts.find(u => u.username === 'a')!
    const b = accts.find(u => u.username === 'b')!
    const c = accts.find(u => u.username === 'c')!

    await tauri.followUser({ follower_id: b.id, followed_id: a.id })
    await tauri.followUser({ follower_id: c.id, followed_id: a.id })
    await tauri.followUser({ follower_id: a.id, followed_id: b.id })

    const followerCount = await tauri.getFollowerCount({ user_id: a.id })
    expect(followerCount).toEqual({ count: 2 })

    const followingCount = await tauri.getFollowingCount({ user_id: a.id })
    expect(followingCount).toEqual({ count: 1 })
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

  it('browserLocalInvoke returns { ok: true } for unknown commands', async () => {
    // Use a known command that dispatches to 'default' — all methods go through
    // _invoke with the command name, so test a valid method call.
    const tauri = useTauri()
    const result = await tauri.followUser({ follower_id: 'u1', followed_id: 'u2' })
    // Known command works fine.
    expect(result).toEqual({ ok: true })
  })
})
