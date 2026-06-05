import apiClient from './client'
import type { CitationGraph, CitationClickPayload } from './types'

export async function getCitations(articleId: string): Promise<CitationGraph> {
  const res = await apiClient.get(`/articles/${articleId}/citations`)
  return res.data
}

export async function recordCitationClick(payload: CitationClickPayload): Promise<void> {
  await apiClient.post('/citations/click', payload)
}
