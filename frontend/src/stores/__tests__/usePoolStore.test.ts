import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('../../api/pool', () => ({
  getPool: vi.fn(),
}))

describe('usePoolStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchPool populates poolArticles state', async () => {
    const { getPool } = await import('../../api/pool')
    const mockPool = {
      articles: [
        { id: 'a1', title: 'Paper 1', authors: ['Alice'], sink_eta: null, days_remaining: 5, review_count: 2 },
        { id: 'a2', title: 'Paper 2', authors: ['Bob'], sink_eta: '2026-06-10', days_remaining: 3, review_count: 0 },
      ],
    }
    vi.mocked(getPool).mockResolvedValue(mockPool)

    const { usePoolStore } = await import('../usePoolStore')
    const store = usePoolStore()
    await store.fetchPool()

    expect(getPool).toHaveBeenCalledOnce()
    expect(store.poolArticles).toHaveLength(2)
    expect(store.loading).toBe(false)
  })

  it('has initial empty state', async () => {
    const { usePoolStore } = await import('../usePoolStore')
    const store = usePoolStore()
    expect(store.poolArticles).toEqual([])
    expect(store.loading).toBe(false)
  })
})
