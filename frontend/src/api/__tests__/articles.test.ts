import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockClient = {
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}

vi.mock('../client', () => ({
  default: mockClient,
}))

describe('articles API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getArticles calls GET /articles with params', async () => {
    const { getArticles } = await import('../articles')
    mockClient.get.mockResolvedValue({ data: { articles: [], total: 0 } })
    await getArticles({ status: 'published', page: 1, size: 20 })
    expect(mockClient.get).toHaveBeenCalledWith('/articles', {
      params: { status: 'published', page: 1, size: 20 },
    })
  })

  it('getArticle calls GET /articles/{id}', async () => {
    const { getArticle } = await import('../articles')
    mockClient.get.mockResolvedValue({ data: { id: 'abc' } })
    const result = await getArticle('abc')
    expect(mockClient.get).toHaveBeenCalledWith('/articles/abc')
    expect(result).toEqual({ id: 'abc' })
  })

  it('createArticle calls POST /articles with body', async () => {
    const { createArticle } = await import('../articles')
    const body = { authors: ['user1'], self_review: { originality: 5, rigor: 4, completeness: 3, pedagogy: 5, impact: 4 } }
    mockClient.post.mockResolvedValue({ data: { id: 'new' } })
    const result = await createArticle(body)
    expect(mockClient.post).toHaveBeenCalledWith('/articles', body)
    expect(result).toEqual({ id: 'new' })
  })

  it('getHistory calls GET /articles/{id}/history', async () => {
    const { getHistory } = await import('../articles')
    mockClient.get.mockResolvedValue({ data: { commits: [] } })
    const result = await getHistory('abc')
    expect(mockClient.get).toHaveBeenCalledWith('/articles/abc/history')
    expect(result).toEqual({ commits: [] })
  })

  it('forkArticle calls POST /articles/{id}/fork', async () => {
    const { forkArticle } = await import('../articles')
    mockClient.post.mockResolvedValue({ data: { id: 'forked', forked_from: 'abc', status: 'draft' } })
    const result = await forkArticle('abc')
    expect(mockClient.post).toHaveBeenCalledWith('/articles/abc/fork')
    expect(result).toEqual({ id: 'forked', forked_from: 'abc', status: 'draft' })
  })

  it('getDiff calls GET /articles/{id}/diff/{h1}/{h2}', async () => {
    const { getDiff } = await import('../articles')
    mockClient.get.mockResolvedValue({ data: { diff_text: '', files: [], commit_hash: '' } })
    const result = await getDiff('abc', 'h1', 'h2')
    expect(mockClient.get).toHaveBeenCalledWith('/articles/abc/diff/h1/h2')
    expect(result).toEqual({ diff_text: '', files: [], commit_hash: '' })
  })

  it('rollbackArticle calls POST /articles/{id}/rollback/{hash}', async () => {
    const { rollbackArticle } = await import('../articles')
    mockClient.post.mockResolvedValue({ data: {} })
    await rollbackArticle('abc', 'hash1')
    expect(mockClient.post).toHaveBeenCalledWith('/articles/abc/rollback/hash1')
  })

  it('extendSink calls PUT /articles/{id}/sink-extension', async () => {
    const { extendSink } = await import('../articles')
    mockClient.put.mockResolvedValue({ data: {} })
    await extendSink('abc', { extra_days: 7 })
    expect(mockClient.put).toHaveBeenCalledWith('/articles/abc/sink-extension', { extra_days: 7 })
  })

  it('getCitations calls GET /articles/{id}/citations', async () => {
    const { getCitations } = await import('../articles')
    mockClient.get.mockResolvedValue({ data: { cites: [], cited_by: [] } })
    const result = await getCitations('abc')
    expect(mockClient.get).toHaveBeenCalledWith('/articles/abc/citations')
    expect(result).toEqual({ cites: [], cited_by: [] })
  })

  it('getMergeProposals calls GET /articles/{id}/merge-proposals', async () => {
    const { getMergeProposals } = await import('../articles')
    mockClient.get.mockResolvedValue({ data: { proposals: [] } })
    const result = await getMergeProposals('abc')
    expect(mockClient.get).toHaveBeenCalledWith('/articles/abc/merge-proposals')
    expect(result).toEqual({ proposals: [] })
  })

  it('createMergeProposal calls POST /articles/{id}/merge-proposals', async () => {
    const { createMergeProposal } = await import('../articles')
    mockClient.post.mockResolvedValue({ data: { id: 'mp1', fork_article_id: 'fork1', target_article_id: 'abc', proposer_id: 'u1', status: 'pending' } })
    const result = await createMergeProposal('abc', { fork_article_id: 'fork1', proposer_id: 'u1' })
    expect(mockClient.post).toHaveBeenCalledWith('/articles/abc/merge-proposals', {
      fork_article_id: 'fork1', proposer_id: 'u1',
    })
    expect(result.status).toBe('pending')
  })

  it('acceptMergeProposal calls POST /articles/{id}/merge-proposals/{pid}/accept', async () => {
    const { acceptMergeProposal } = await import('../articles')
    mockClient.post.mockResolvedValue({ data: {} })
    await acceptMergeProposal('abc', 'pid1')
    expect(mockClient.post).toHaveBeenCalledWith('/articles/abc/merge-proposals/pid1/accept')
  })

  it('rejectMergeProposal calls POST /articles/{id}/merge-proposals/{pid}/reject', async () => {
    const { rejectMergeProposal } = await import('../articles')
    mockClient.post.mockResolvedValue({ data: {} })
    await rejectMergeProposal('abc', 'pid1')
    expect(mockClient.post).toHaveBeenCalledWith('/articles/abc/merge-proposals/pid1/reject')
  })

  it('deleteArticle calls DELETE /articles/{id}', async () => {
    const { deleteArticle } = await import('../articles')
    mockClient.delete.mockResolvedValue({ data: undefined, status: 204 })
    await deleteArticle('abc')
    expect(mockClient.delete).toHaveBeenCalledWith('/articles/abc')
  })
})
