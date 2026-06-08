import apiClient from './client'
import type { ArticleCreatePayload, ArticleUpdatePayload } from './types'

export interface ArticleListParams {
  status?: string
  author_id?: string
  page?: number
  size?: number
}

export async function getArticles(params?: ArticleListParams): Promise<{articles: import('./types').ArticleSummary[], total: number, page: number, size: number}> {
  const res = await apiClient.get('/articles', { params })
  return res.data
}

export async function getArticle(id: string): Promise<import('./types').ArticleDetail> {
  const res = await apiClient.get(`/articles/${id}`)
  return res.data
}

export async function getArticleSource(id: string): Promise<{ content: string; format: string }> {
  const res = await apiClient.get(`/articles/${id}/source`)
  return res.data
}

export async function createArticle(body: ArticleCreatePayload): Promise<import('./types').ArticleDetail> {
  const res = await apiClient.post('/articles', body)
  return res.data
}

export async function getHistory(id: string): Promise<import('./types').ArticleHistory> {
  const res = await apiClient.get(`/articles/${id}/history`)
  return res.data
}

export async function forkArticle(id: string): Promise<{id: string; forked_from: string; status: string}> {
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

export async function updateArticle(id: string, body: ArticleUpdatePayload): Promise<import('./types').ArticleDetail> {
  const res = await apiClient.put(`/articles/${id}`, body)
  return res.data
}

export async function extendSink(id: string, body: { extra_days: number }): Promise<import('./types').ArticleDetail> {
  const res = await apiClient.put(`/articles/${id}/sink-extension`, body)
  return res.data
}

export async function getCitations(id: string): Promise<import('./types').CitationGraph> {
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
