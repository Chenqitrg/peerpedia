import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockClient = {
  get: vi.fn(),
}

vi.mock('../client', () => ({
  default: mockClient,
}))

describe('pool API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getPool calls GET /pool', async () => {
    const { getPool } = await import('../pool')
    const mockData = { articles: [{ id: 'a1', title: 'Test', authors: ['Alice'], sink_eta: null, days_remaining: null, review_count: 0 }] }
    mockClient.get.mockResolvedValue({ data: mockData })
    const result = await getPool()
    expect(mockClient.get).toHaveBeenCalledWith('/pool')
    expect(result.articles).toHaveLength(1)
  })
})
