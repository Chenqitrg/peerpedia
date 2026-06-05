import apiClient from './client'
import type { FeedResponse } from './types'

export async function fetchFeed(): Promise<FeedResponse> {
  const res = await apiClient.get('/feed')
  return res.data
}
