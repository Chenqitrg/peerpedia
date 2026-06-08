import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const _lsStore: Record<string, string> = {
  viewer: JSON.stringify({
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
  }),
}

vi.mock('../../composables/useLocalStorage', () => {
  const store: Record<string, string> = {
    viewer: JSON.stringify({
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
    }),
  }
  return {
    loadString: vi.fn((key: string) => store[key] ?? null),
    saveString: vi.fn((key: string, val: string) => { store[key] = val }),
    loadJSON: vi.fn((key: string) => {
      const raw = store[key]
      return raw ? JSON.parse(raw) : null
    }),
    saveJSON: vi.fn((key: string, val: unknown) => { store[key] = JSON.stringify(val) }),
    remove: vi.fn((key: string) => { delete store[key] }),
    extractErrorMessage: vi.fn(() => ''),
  }
})

describe('useUserStore — local session restore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('restores viewer from localStorage on init', async () => {
    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    expect(store.viewer).not.toBeNull()
    expect(store.viewer!.username).toBe('testuser')
  })

  it('restoreSession restores localToken from localStorage', async () => {
    const mod = await import('../../composables/useLocalStorage')
    // Simulate a persisted token (as if user previously logged in)
    ;(mod.saveString as any)('peerpedia_local_token', 'saved-session-token')

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
    ;(mod.saveString as any)('peerpedia_local_token', 'existing-token')

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    store.isTauriMode = true

    await store.restoreSession()

    expect(mod.loadString).toHaveBeenCalledWith('peerpedia_local_token')
    expect(store.localToken).toBe('existing-token')
  })
})
