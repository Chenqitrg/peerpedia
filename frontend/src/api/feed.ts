import apiClient from './client'
import type { FeedResponse } from './types'

export async function fetchFeed(): Promise<FeedResponse> {
  const res = await apiClient.get('/feed')
  return res.data
}

export interface FeedCacheResponse {
  following_ids: string[]
  articles: {
    id: string
    title: string
    status: string
    authors: { id: string; name: string; anonymous_name?: string; affiliation?: string; expertise?: string[] }[]
    commit_hash: string
    fork_count: number
    forked_from: string | null
    score: Record<string, number> | null
    created_at: string
  }[]
}

export async function getFeedCache(): Promise<FeedCacheResponse> {
  const res = await apiClient.get('/feed/cache')
  return res.data
}
