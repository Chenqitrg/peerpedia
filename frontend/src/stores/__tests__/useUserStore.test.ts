import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

describe('useUserStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('setViewer stores user in localStorage', async () => {
    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    const user = { id: 'u1', name: 'Alice' }
    store.setViewer(user)
    expect(store.viewer).toEqual(user)
    expect(JSON.parse(localStorage.getItem('viewer')!)).toEqual(user)
  })

  it('getViewer retrieves user from localStorage', async () => {
    const user = { id: 'u1', name: 'Alice' }
    localStorage.setItem('viewer', JSON.stringify(user))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    expect(store.viewer).toEqual(user)
  })

  it('getViewer returns null when no user in localStorage', async () => {
    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    expect(store.viewer).toBeNull()
  })

  it('clearViewer removes user from state and localStorage', async () => {
    const user = { id: 'u1', name: 'Alice' }
    localStorage.setItem('viewer', JSON.stringify(user))

    const { useUserStore } = await import('../useUserStore')
    const store = useUserStore()
    store.clearViewer()
    expect(store.viewer).toBeNull()
    expect(localStorage.getItem('viewer')).toBeNull()
  })
})
