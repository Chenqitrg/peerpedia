import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

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

describe('useUserStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
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
