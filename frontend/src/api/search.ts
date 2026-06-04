import apiClient from './client'
import type { SearchResult } from './types'

export async function searchArticles(query: string): Promise<SearchResult> {
  const res = await apiClient.get('/search', { params: { q: query } })
  return res.data
}
