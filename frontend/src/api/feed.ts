import apiClient from './client'
import type { FeedItem } from './types'

export async function fetchFeed(userId?: number): Promise<FeedItem[]> {
  const res = await apiClient.get('/feed', { params: userId ? { user_id: userId } : {} })
  return res.data
}
