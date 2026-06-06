import apiClient from './client'
import type { SearchResult } from './types'

export interface SearchParams {
  q?: string
  category?: string
  sort?: string
}

export async function searchArticles(params: SearchParams): Promise<SearchResult> {
  const res = await apiClient.get('/search', { params })
  return res.data
}
