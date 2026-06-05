import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('../../api/articles', () => ({
  getArticles: vi.fn(),
  getArticle: vi.fn(),
  createArticle: vi.fn(),
}))

describe('useArticleStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchArticles populates articles state', async () => {
    const { getArticles } = await import('../../api/articles')
    const mockArticles = {
      articles: [
        { id: '1', title: 'Paper 1', status: 'published', authors: ['Alice'], fork_count: 0, review_count: 0 },
        { id: '2', title: 'Paper 2', status: 'draft', authors: ['Bob'], fork_count: 0, review_count: 0 },
      ],
      total: 2,
    }
    vi.mocked(getArticles).mockResolvedValue(mockArticles)

    const { useArticleStore } = await import('../useArticleStore')
    const store = useArticleStore()
    await store.fetchArticles({ status: 'published' })

    expect(getArticles).toHaveBeenCalledWith({ status: 'published' })
    expect(store.articles).toHaveLength(2)
    expect(store.total).toBe(2)
  })

  it('fetchArticle sets currentArticle', async () => {
    const { getArticle } = await import('../../api/articles')
    const mockArticle = { id: '1', title: 'Paper 1', status: 'published', authors: ['Alice'], fork_count: 0, review_count: 0 }
    vi.mocked(getArticle).mockResolvedValue(mockArticle)

    const { useArticleStore } = await import('../useArticleStore')
    const store = useArticleStore()
    await store.fetchArticle('1')

    expect(getArticle).toHaveBeenCalledWith('1')
    expect(store.currentArticle).toEqual(mockArticle)
  })

  it('createArticle adds to articles and returns new article', async () => {
    const { createArticle } = await import('../../api/articles')
    const body = { authors: ['Alice'], self_review: { originality: 5, rigor: 4, completeness: 3, pedagogy: 5, impact: 4 } }
    const newArticle = { id: '3', title: 'New Paper', status: 'draft', authors: ['Alice'], fork_count: 0, review_count: 0 }
    vi.mocked(createArticle).mockResolvedValue(newArticle)

    const { useArticleStore } = await import('../useArticleStore')
    const store = useArticleStore()
    const result = await store.createArticle(body)

    expect(createArticle).toHaveBeenCalledWith(body)
    expect(result).toEqual(newArticle)
  })

  it('has initial empty state', async () => {
    const { useArticleStore } = await import('../useArticleStore')
    const store = useArticleStore()

    expect(store.articles).toEqual([])
    expect(store.total).toBe(0)
    expect(store.currentArticle).toBeNull()
  })
})
