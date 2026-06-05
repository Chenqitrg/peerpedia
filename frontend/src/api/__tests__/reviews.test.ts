import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockClient = {
  get: vi.fn(),
  post: vi.fn(),
}

vi.mock('../client', () => ({
  default: mockClient,
}))

describe('reviews API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getReviews calls GET /articles/{id}/reviews', async () => {
    const { getReviews } = await import('../reviews')
    const mockData = [{ id: 'r1', article_id: 'abc', scores: { originality: 5, rigor: 4, completeness: 3, pedagogy: 5, impact: 4 } }]
    mockClient.get.mockResolvedValue({ data: mockData })
    const result = await getReviews('abc')
    expect(mockClient.get).toHaveBeenCalledWith('/articles/abc/reviews')
    expect(result).toEqual(mockData)
  })

  it('createReview calls POST /articles/{id}/reviews with body', async () => {
    const { createReview } = await import('../reviews')
    const body = { article_id: 'abc', commit_hash: 'h1', scope: 'pool' as const, scores: { originality: 5, rigor: 4, completeness: 3, pedagogy: 5, impact: 4 } }
    mockClient.post.mockResolvedValue({ data: { id: 'r2', ...body } })
    const result = await createReview('abc', body)
    expect(mockClient.post).toHaveBeenCalledWith('/articles/abc/reviews', body)
    expect(result.id).toBe('r2')
  })

  it('postReviewMessage calls POST /articles/{id}/reviews/{rid}/messages', async () => {
    const { postReviewMessage } = await import('../reviews')
    mockClient.post.mockResolvedValue({ data: { id: 'msg1', content: 'Nice work!' } })
    const result = await postReviewMessage('abc', 'r1', { content: 'Nice work!' })
    expect(mockClient.post).toHaveBeenCalledWith('/articles/abc/reviews/r1/messages', { content: 'Nice work!' })
    expect(result.content).toBe('Nice work!')
  })
})
