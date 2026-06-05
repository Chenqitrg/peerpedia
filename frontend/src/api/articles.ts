import apiClient from './client'

export interface ArticleListParams {
  status?: string
  author_id?: string
  page?: number
  size?: number
}

export async function getArticles(params?: ArticleListParams) {
  const res = await apiClient.get('/articles', { params })
  return res.data
}

export async function getArticle(id: string) {
  const res = await apiClient.get(`/articles/${id}`)
  return res.data
}

export async function getArticleSource(id: string): Promise<{ content: string; format: string }> {
  const res = await apiClient.get(`/articles/${id}/source`)
  return res.data
}

export async function createArticle(body: Record<string, unknown>) {
  const res = await apiClient.post('/articles', body)
  return res.data
}

export async function getHistory(id: string) {
  const res = await apiClient.get(`/articles/${id}/history`)
  return res.data
}

export async function forkArticle(id: string) {
  const res = await apiClient.post(`/articles/${id}/fork`)
  return res.data
}

export async function getDiff(id: string, h1: string, h2: string) {
  const res = await apiClient.get(`/articles/${id}/diff/${h1}/${h2}`)
  return res.data
}

export async function rollbackArticle(id: string, hash: string) {
  const res = await apiClient.post(`/articles/${id}/rollback/${hash}`)
  return res.data
}

export async function updateArticle(id: string, body: Record<string, unknown>) {
  const res = await apiClient.put(`/articles/${id}`, body)
  return res.data
}

export async function extendSink(id: string, body: { extra_days: number }) {
  const res = await apiClient.put(`/articles/${id}/sink-extension`, body)
  return res.data
}

export async function getCitations(id: string) {
  const res = await apiClient.get(`/articles/${id}/citations`)
  return res.data
}

export async function getMergeProposals(id: string) {
  const res = await apiClient.get(`/articles/${id}/merge-proposals`)
  return res.data
}

export async function createMergeProposal(id: string, body: { fork_article_id: string; proposer_id: string }) {
  const res = await apiClient.post(`/articles/${id}/merge-proposals`, body)
  return res.data
}

export async function acceptMergeProposal(id: string, pid: string) {
  const res = await apiClient.post(`/articles/${id}/merge-proposals/${pid}/accept`)
  return res.data
}

export async function rejectMergeProposal(id: string, pid: string) {
  const res = await apiClient.post(`/articles/${id}/merge-proposals/${pid}/reject`)
  return res.data
}
