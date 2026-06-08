import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mutable state for controlling mock behavior across test blocks.
const state = vi.hoisted(() => ({
  isTauri: false,
  isBrowserLocal: false,
}))

vi.mock('../../composables/useTauri', () => ({
  useTauri: () => ({
    isTauri: { value: state.isTauri },
    isBrowserLocal: { value: state.isBrowserLocal },
    setSessionToken: vi.fn(),
    getSessionToken: vi.fn(() => null),
    login: vi.fn(),
    createAccount: vi.fn(),
    listAccounts: vi.fn().mockResolvedValue([]),
  }),
}))

// Mock useLocalStorage to pass through to jsdom's real localStorage.
// This way store init (loadString/loadJSON) and test setup (localStorage.setItem)
// use the same underlying storage.
vi.mock('../../composables/useLocalStorage', () => {
  const _ls = (): Storage | null => {
    try { return (globalThis as unknown as { localStorage?: Storage }).localStorage ?? null } catch { return null }
  }
  return {
    loadString: vi.fn((key: string) => {
      const s = _ls(); return s ? s.getItem(key) : null
    }),
    saveString: vi.fn((key: string, val: string) => {
      const s = _ls(); if (s) s.setItem(key, val)
    }),
    loadJSON: vi.fn((key: string) => {
      const s = _ls(); if (!s) return null
      const raw = s.getItem(key); return raw ? JSON.parse(raw) : null
    }),
    saveJSON: vi.fn((key: string, val: unknown) => {
      const s = _ls(); if (s) s.setItem(key, JSON.stringify(val))
    }),
    remove: vi.fn((key: string) => {
      const s = _ls(); if (s) s.removeItem(key)
    }),
    extractErrorMessage: vi.fn(() => ''),
  }
})

vi.mock('../../api/auth', () => ({
  login: vi.fn().mockResolvedValue({
    user: { id: 'u1', username: 'alice', name: 'Alice', anonymous_name: '', reputation: {} },
    token: 'test-jwt-token',
  }),
  register: vi.fn().mockResolvedValue({
    user: { id: 'u2', username: 'bob', name: 'Bob', anonymous_name: '', reputation: {} },
    token: 'test-jwt-token',
  }),
  getMe: vi.fn().mockResolvedValue({
    user: { id: 'u1', username: 'alice', name: 'Alice', anonymous_name: '', reputation: {} },
    token: '',
  }),
}))


// ── Web auth tests (original coverage, now restored) ──────────────────────

describe('useUserStore — web auth', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    state.isTauri = false
    state.isBrowserLocal = false
    localStorage.clear()
  })

  it('starts with null viewer when localStorage is empty', async () => {
    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    expect(store.viewer).toBeNull()
    expect(store.token).toBeNull()
  })

  it('loads viewer from localStorage on init', async () => {
    const user = { id: 'u1', name: 'Alice' }
    localStorage.setItem('viewer', JSON.stringify(user))
    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    expect(store.viewer).toEqual(user)
  })

  it('login stores user and token', async () => {
    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.login('alice', '666666')
    expect(store.viewer).not.toBeNull()
    expect(store.viewer?.username).toBe('alice')
    expect(store.token).toBe('test-jwt-token')
    expect(localStorage.getItem('token')).toBe('test-jwt-token')
  })

  it('logout clears user and token', async () => {
    localStorage.setItem('viewer', JSON.stringify({ id: 'u1' }))
    localStorage.setItem('token', 'old-token')
    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    store.logout()
    expect(store.viewer).toBeNull()
    expect(store.token).toBeNull()
    expect(localStorage.getItem('viewer')).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('register stores user and token', async () => {
    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.register('bob', '666666', 'bob@test.com', 'Bob')
    expect(store.viewer?.username).toBe('bob')
    expect(store.token).toBe('test-jwt-token')
  })

  it('restoreSession recovers user from valid token', async () => {
    localStorage.setItem('token', 'valid-token')
    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.restoreSession()
    expect(store.viewer?.username).toBe('alice')
  })
})


// ── Local session tests (new coverage from fix/local-mode-bugs-v2) ────────

describe('useUserStore — local session restore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    state.isTauri = false
    state.isBrowserLocal = false
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('restores viewer from localStorage on init', async () => {
    const user = {
      id: 'local-user-id',
      username: 'testuser',
      name: 'Test User',
      anonymous_name: '',
      affiliation: '',
      expertise: [],
      reputation: {},
      followers_count: 0,
      following_count: 0,
      article_count: 0,
      created_at: new Date().toISOString(),
    }
    localStorage.setItem('viewer', JSON.stringify(user))
    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    expect(store.viewer).not.toBeNull()
    expect(store.viewer!.username).toBe('testuser')
  })

  it('restoreSession restores localToken from localStorage', async () => {
    localStorage.setItem('peerpedia_local_token', 'saved-session-token')

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    store.isTauriMode = true

    await store.restoreSession()

    expect(store.localToken).toBe('saved-session-token')
  })

  it('clears local token on logout', async () => {
    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    store.localToken = 'token-to-clear'
    store.clear()

    expect(store.localToken).toBeNull()
  })

  it('loadString is called during restoreSession in local mode', async () => {
    const mod = await import('../../composables/useLocalStorage')
    localStorage.setItem('peerpedia_local_token', 'existing-token')

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    store.isTauriMode = true

    await store.restoreSession()

    expect(mod.loadString).toHaveBeenCalledWith('peerpedia_local_token')
    expect(store.localToken).toBe('existing-token')
  })

  it('init block restores localToken synchronously when browserLocal is set before store creation', async () => {
    // Simulate the real page-refresh scenario: isBrowserLocal is already true
    // when the store module loads, so the init block (lines 35-41) should
    // restore localToken before any async restoreSession call.
    state.isBrowserLocal = true
    localStorage.setItem('peerpedia_browser_local', '1')
    localStorage.setItem('peerpedia_local_token', 'init-restored-token')

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()

    // The init block should have already restored the token synchronously.
    expect(store.localToken).toBe('init-restored-token')
    expect(store.isBrowserLocal).toBe(true)
  })
})
