import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mutable state for controlling mock behavior across test blocks.
const state = vi.hoisted(() => ({
  isTauri: false,
  isBrowserLocal: false,
  loginResult: undefined as any,
  createAccountResult: undefined as any,
}))

vi.mock('../../composables/useTauri', () => ({
  useTauri: () => ({
    isTauri: { value: state.isTauri },
    isBrowserLocal: { value: state.isBrowserLocal },
    setSessionToken: vi.fn(),
    getSessionToken: vi.fn(() => null),
    login: vi.fn(() => state.loginResult),
    createAccount: vi.fn(() => state.createAccountResult),
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

// ── SPEC-AUTH: server token sync tests ─────────────────────────────────

describe('SPEC-AUTH: server token sync', () => {
  beforeEach(async () => {
    vi.resetModules()
    setActivePinia(createPinia())
    state.isTauri = true
    state.isBrowserLocal = false
    localStorage.clear()
    vi.clearAllMocks()

    // Set up Tauri login mock to return email/name (T1 change)
    state.loginResult = {
      id: 'local-1',
      username: 'alice',
      token: 'session-token',
      email: 'alice@test.com',
      name: 'Alice Test',
    }
  })

  it('SPEC-AUTH-6: loginLocal captures email and name from Tauri login result', async () => {
    const authMocks = await import('../../api/auth')
    // apiLogin fails during loginLocal (server unreachable)
    ;(authMocks.login as any).mockRejectedValueOnce(new Error('Network Error'))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.loginLocal('alice', '666666')

    expect(store.viewer).not.toBeNull()
    expect(store.token).toBeNull() // Server was unreachable

    // trySyncServerAuth: apiLogin fails (still unreachable), apiRegister succeeds
    ;(authMocks.login as any).mockRejectedValueOnce(new Error('Network Error'))
    ;(authMocks.register as any).mockResolvedValueOnce({
      user: { id: 's1', username: 'alice', name: 'Alice', anonymous_name: '', reputation: {} },
      token: 'synced-jwt',
    })
    const result = await store.trySyncServerAuth()
    expect(result).toBe(true)
    expect(store.token).toBe('synced-jwt')
    expect(authMocks.register).toHaveBeenCalledWith({
      username: 'alice',
      password: '666666',
      email: 'alice@test.com',
      name: 'Alice Test',
    })
  })

  it('SPEC-AUTH-7: falls back to apiRegister when apiLogin fails', async () => {
    const authMocks = await import('../../api/auth')
    // apiLogin fails during loginLocal (server unreachable)
    ;(authMocks.login as any).mockRejectedValueOnce(new Error('Network Error'))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.loginLocal('alice', '666666')

    // trySyncServerAuth: apiLogin fails (user not on server), apiRegister succeeds
    ;(authMocks.login as any).mockRejectedValueOnce({ response: { status: 401, data: { detail: 'Invalid credentials' } } })
    ;(authMocks.register as any).mockResolvedValueOnce({
      user: { id: 's1', username: 'alice', name: 'Alice', anonymous_name: '', reputation: {} },
      token: 'registered-jwt',
    })

    const result = await store.trySyncServerAuth()
    expect(result).toBe(true)
    expect(store.token).toBe('registered-jwt')
    expect(authMocks.login).toHaveBeenCalled()
    expect(authMocks.register).toHaveBeenCalled()
  })

  it('SPEC-AUTH-8: sets syncError on username conflict', async () => {
    const authMocks = await import('../../api/auth')
    // apiLogin fails during loginLocal (server unreachable)
    ;(authMocks.login as any).mockRejectedValueOnce(new Error('Network Error'))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.loginLocal('alice', '666666')

    // trySyncServerAuth: apiLogin fails, apiRegister fails with "already exists"
    ;(authMocks.login as any).mockRejectedValueOnce({ response: { status: 401 } })
    ;(authMocks.register as any).mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'Username already exists' } },
    })

    const result = await store.trySyncServerAuth()
    expect(result).toBe(false)
    expect(store.syncError).toBeTruthy()
    expect(store.syncError).toContain('alice')
    expect(store.token).toBeNull()
  })

  it('SPEC-AUTH-9: keeps credentials after failed sync for retry', async () => {
    const authMocks = await import('../../api/auth')
    // apiLogin fails during loginLocal (server unreachable)
    ;(authMocks.login as any).mockRejectedValueOnce(new Error('Network Error'))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.loginLocal('alice', '666666')

    // First trySyncServerAuth: both apiLogin and apiRegister fail
    ;(authMocks.login as any).mockRejectedValueOnce(new Error('Network Error'))
    ;(authMocks.register as any).mockRejectedValueOnce(new Error('Server error'))

    await store.trySyncServerAuth()
    expect(store.token).toBeNull()

    // Second trySyncServerAuth: apiLogin succeeds (server now up)
    ;(authMocks.login as any).mockResolvedValueOnce({
      user: { id: 's1', username: 'alice', name: 'Alice', anonymous_name: '', reputation: {} },
      token: 'delayed-jwt',
    })
    const result = await store.trySyncServerAuth()
    expect(result).toBe(true)
    expect(store.token).toBe('delayed-jwt')
  })
})

// ═══════════════════════════════════════════════════════════════════════════
// SPEC-SYNC-CLOSED-LOOP — Large-scale user journey specifications
// ═══════════════════════════════════════════════════════════════════════════
// These tests define product behavior as observable outcomes of user actions.
// The system is treated as a black box — only the store's public API is used.
// External boundaries (Tauri IPC, REST API, localStorage) are mocked.
//
// SPECIFICATION STATUS = LOCKED.
// ===========================================================================

describe('SPEC-SYNC-CLOSED-LOOP-1: Cold start — register local, server comes up, bookmark works', () => {
  beforeEach(async () => {
    vi.resetModules()
    setActivePinia(createPinia())
    state.isTauri = true
    state.isBrowserLocal = false
    localStorage.clear()
    vi.clearAllMocks()

    state.createAccountResult = { id: 'local-1', username: 'newuser' }
    state.loginResult = {
      id: 'local-1',
      username: 'newuser',
      token: 'local-session',
      email: 'newuser@test.com',
      name: 'New User',
    }
  })

  it('complete user journey: register offline, server online, bookmark via sync', async () => {
    // ── Step 1: User registers locally while server is down ──────────────
    const authMocks = await import('../../api/auth')
    ;(authMocks.register as any).mockRejectedValueOnce(new Error('Network Error'))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.registerLocal('newuser', 'secret123', 'newuser@test.com', 'New User')

    // After registration: viewer exists, local token exists, server token is null
    expect(store.viewer).not.toBeNull()
    expect(store.viewer!.username).toBe('newuser')
    expect(store.localToken).toBe('local-session')
    expect(store.token).toBeNull()                    // Server was down

    // ── Step 2: Server becomes reachable ────────────────────────────────
    // (No user action — just the network state changing)

    // ── Step 3: User clicks bookmark → sync triggers automatically ──────
    // apiLogin fails (user not on server yet) → apiRegister succeeds
    ;(authMocks.login as any).mockRejectedValueOnce({ response: { status: 401 } })
    ;(authMocks.register as any).mockResolvedValueOnce({
      user: { id: 'srv-1', username: 'newuser', name: 'New User', anonymous_name: '', reputation: {} },
      token: 'server-jwt',
    })

    const synced = await store.trySyncServerAuth()
    expect(synced).toBe(true)
    expect(store.token).toBe('server-jwt')
    expect(localStorage.getItem('token')).toBe('server-jwt')
  })

  it('viewer profile uses name from Tauri login, not only username', async () => {
    const authMocks = await import('../../api/auth')
    ;(authMocks.login as any).mockRejectedValueOnce(new Error('Network Error'))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.loginLocal('newuser', 'secret123')

    expect(store.viewer!.name).toBe('New User')       // From Tauri login, not 'newuser'
    expect(store.viewer!.username).toBe('newuser')
  })
})

describe('SPEC-SYNC-CLOSED-LOOP-2: Retry recovery — first attempt fails, server appears, retry succeeds', () => {
  beforeEach(async () => {
    vi.resetModules()
    setActivePinia(createPinia())
    state.isTauri = true
    state.isBrowserLocal = false
    localStorage.clear()
    vi.clearAllMocks()

    state.loginResult = {
      id: 'local-2',
      username: 'bob',
      token: 'local-session-2',
      email: 'bob@test.com',
      name: 'Bob',
    }
  })

  it('user gets error on first sync, then automatically succeeds on retry after server appears', async () => {
    // ── Step 1: User logs in locally while server is down ───────────────
    const authMocks = await import('../../api/auth')
    ;(authMocks.login as any).mockRejectedValueOnce(new Error('Network Error'))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.loginLocal('bob', 'secret456')

    expect(store.viewer).not.toBeNull()
    expect(store.token).toBeNull()
    expect(store.syncError).toBeNull()                // No error yet

    // ── Step 2: Try to bookmark, server still unreachable ───────────────
    ;(authMocks.login as any).mockRejectedValueOnce(new Error('Network Error'))
    ;(authMocks.register as any).mockRejectedValueOnce(new Error('Network Error'))

    const firstSync = await store.trySyncServerAuth()
    expect(firstSync).toBe(false)
    expect(store.token).toBeNull()                    // Still no token
    // Credentials retained — user can retry

    // ── Step 3: Server comes online, user retries ───────────────────────
    ;(authMocks.login as any).mockResolvedValueOnce({
      user: { id: 'srv-2', username: 'bob', name: 'Bob', anonymous_name: '', reputation: {} },
      token: 'recovered-jwt',
    })

    const secondSync = await store.trySyncServerAuth()
    expect(secondSync).toBe(true)
    expect(store.token).toBe('recovered-jwt')
    expect(localStorage.getItem('token')).toBe('recovered-jwt')
    expect(store.syncError).toBeNull()                // Error cleared

    // ── Step 4: Third attempt is a no-op (credentials consumed) ─────────
    const thirdSync = await store.trySyncServerAuth()
    expect(thirdSync).toBe(false)
  })

  it('logout clears pending credentials and syncError', async () => {
    const authMocks = await import('../../api/auth')
    ;(authMocks.login as any).mockRejectedValueOnce(new Error('Network Error'))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.loginLocal('bob', 'secret456')

    // Sync fails with conflict → syncError set
    ;(authMocks.login as any).mockRejectedValueOnce({ response: { status: 401 } })
    ;(authMocks.register as any).mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'Username already exists' } },
    })
    await store.trySyncServerAuth()
    expect(store.syncError).toBeTruthy()

    // User logs out
    store.logout()
    expect(store.viewer).toBeNull()
    expect(store.token).toBeNull()
    expect(store.syncError).toBeNull()

    // After logout, no pending credentials
    const result = await store.trySyncServerAuth()
    expect(result).toBe(false)
  })
})

describe('SPEC-SYNC-CLOSED-LOOP-3: Username conflict — local user collides with server user', () => {
  beforeEach(async () => {
    vi.resetModules()
    setActivePinia(createPinia())
    state.isTauri = true
    state.isBrowserLocal = false
    localStorage.clear()
    vi.clearAllMocks()

    state.createAccountResult = { id: 'local-3', username: 'einstein' }
    state.loginResult = {
      id: 'local-3',
      username: 'einstein',
      token: 'local-session-3',
      email: '',
      name: 'Albert',
    }
  })

  it('user registers as existing seed username, sees conflict error, then logs in with server password', async () => {
    // ── Step 1: User registers locally as "einstein" with password "localpass" ──
    const authMocks = await import('../../api/auth')
    ;(authMocks.register as any).mockRejectedValueOnce(new Error('Network Error'))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.registerLocal('einstein', 'localpass', '', 'Albert')

    expect(store.viewer!.username).toBe('einstein')
    expect(store.token).toBeNull()

    // ── Step 2: Server comes online, sync fails with conflict ───────────
    ;(authMocks.login as any).mockRejectedValueOnce({ response: { status: 401 } })
    ;(authMocks.register as any).mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'Username already exists' } },
    })

    const result = await store.trySyncServerAuth()
    expect(result).toBe(false)
    expect(store.token).toBeNull()
    expect(store.syncError).toBeTruthy()
    expect(store.syncError!).toContain('einstein')    // User sees the conflicting name

    // ── Step 3: User enters server password via AuthModal ───────────────
    ;(authMocks.login as any).mockResolvedValueOnce({
      user: { id: 'seed-einstein', username: 'einstein', name: 'Albert Einstein', anonymous_name: '', reputation: {} },
      token: 'correct-server-jwt',
    })
    await store.login('einstein', '666666')            // Server login with correct password
    expect(store.token).toBe('correct-server-jwt')
    expect(store.syncError).toBeNull()                // Error cleared
  })

  it('conflict retries fail until password is corrected', async () => {
    const authMocks = await import('../../api/auth')
    ;(authMocks.register as any).mockRejectedValueOnce(new Error('Network Error'))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.registerLocal('einstein', 'localpass', '', 'Albert')

    // Retry with same wrong password — fails again
    ;(authMocks.login as any).mockRejectedValueOnce({ response: { status: 401 } })
    ;(authMocks.register as any).mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'Username already exists' } },
    })
    let result = await store.trySyncServerAuth()
    expect(result).toBe(false)
    expect(store.syncError).toBeTruthy()

    // Another retry — still fails (credentials unchanged)
    ;(authMocks.login as any).mockRejectedValueOnce({ response: { status: 401 } })
    ;(authMocks.register as any).mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'Username already exists' } },
    })
    result = await store.trySyncServerAuth()
    expect(result).toBe(false)

    // Credentials persist across retries — user hasn't fixed password yet
  })
})

describe('SPEC-SYNC-CLOSED-LOOP-4: Synced token reused across sessions and operations', () => {
  beforeEach(async () => {
    vi.resetModules()
    setActivePinia(createPinia())
    state.isTauri = true
    state.isBrowserLocal = false
    localStorage.clear()
    vi.clearAllMocks()

    state.createAccountResult = { id: 'local-4', username: 'carol' }
    state.loginResult = {
      id: 'local-4',
      username: 'carol',
      token: 'local-session-4',
      email: 'carol@test.com',
      name: 'Carol',
    }
  })

  it('after sync, token persists in localStorage and survives page refresh', async () => {
    // ── Step 1: Register locally, server down ────────────────────────────
    const authMocks = await import('../../api/auth')
    ;(authMocks.register as any).mockRejectedValueOnce(new Error('Network Error'))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    await store.registerLocal('carol', 'password', 'carol@test.com', 'Carol')

    // ── Step 2: Sync succeeds ────────────────────────────────────────────
    ;(authMocks.login as any).mockRejectedValueOnce(new Error('Network Error'))
    ;(authMocks.register as any).mockResolvedValueOnce({
      user: { id: 'srv-4', username: 'carol', name: 'Carol', anonymous_name: '', reputation: {} },
      token: 'carol-jwt',
    })
    await store.trySyncServerAuth()
    expect(store.token).toBe('carol-jwt')
    expect(localStorage.getItem('token')).toBe('carol-jwt')

    // ── Step 3: Simulate page refresh — new store instance ──────────────
    vi.resetModules()
    const { useUserStore: useStore2 } = await import('../useUserStore')
    const store2 = useStore2()
    // Token loaded from localStorage on init
    expect(store2.token).toBe('carol-jwt')

    // No pending credentials — sync is a no-op
    const result = await store2.trySyncServerAuth()
    expect(result).toBe(false)
  })

  it('persisted token and viewer are available immediately on store init', async () => {
    // ── Pre-condition: previous session saved token and viewer ──────────
    localStorage.setItem('token', 'persisted-jwt')
    localStorage.setItem('viewer', JSON.stringify({
      id: 'srv-4',
      username: 'carol',
      name: 'Carol',
      anonymous_name: '',
      affiliation: 'MIT',
      expertise: ['Quantum Computing'],
      reputation: { professionalism: 4, objectivity: 3, collaboration: 5, pedagogy: 4 },
      followers_count: 3,
      following_count: 5,
      article_count: 0,
      created_at: new Date().toISOString(),
    }))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()

    // Token and viewer immediately available from localStorage
    expect(store.token).toBe('persisted-jwt')
    expect(store.viewer).not.toBeNull()
    expect(store.viewer!.username).toBe('carol')
    expect(store.viewer!.affiliation).toBe('MIT')
    expect(store.viewer!.following_count).toBe(5)
  })
})
