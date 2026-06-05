import apiClient from './client'
import type { FeedResponse } from './types'

export async function fetchFeed(userId?: string): Promise<FeedResponse> {
  const res = await apiClient.get('/feed', { params: userId ? { user_id: userId } : {} })
  return res.data
}
