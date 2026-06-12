// Offline cache for follow data.
// Stores following IDs + followed users' article metadata in the
// existing article_cache table (via Tauri IPC). Uses namespaced cache
// keys that never collide with real article UUIDs.
//
// Cache entries:
//   _follow_ids_{userId} → { ids: string[], cached_at: string }
//   _feed_{userId}       → { articles: LightFeedArticle[], cached_at: string }

import { useTauri } from './useTauri'
import { getFeedCache } from '../api/feed'
import type { FeedCacheResponse } from '../api/feed'

const FOLLOW_IDS_PREFIX = '_follow_ids_'
const FEED_PREFIX = '_feed_'

function idsKey(userId: string): string {
  return `${FOLLOW_IDS_PREFIX}${userId}`
}

function feedKey(userId: string): string {
  return `${FEED_PREFIX}${userId}`
}

export function useFollowCache() {
  const tauri = useTauri()

  /** Fetch feed cache from server and store in local article_cache. */
  async function refreshCache(userId: string): Promise<void> {
    try {
      const data: FeedCacheResponse = await getFeedCache()

      // Store following IDs.
      const idsPayload = JSON.stringify({
        ids: data.following_ids,
        cached_at: new Date().toISOString(),
      })
      await tauri.cacheArticle({
        id: idsKey(userId),
        article_json: idsPayload,
      })

      // Store lightweight feed articles.
      const articles = data.articles.map(a => ({
        id: a.id,
        title: a.title,
        status: a.status,
        authors: a.authors,
        commit_hash: a.commit_hash,
        fork_count: a.fork_count,
        forked_from: a.forked_from,
        score: a.score,
        created_at: a.created_at,
      }))
      const feedPayload = JSON.stringify({
        articles,
        cached_at: new Date().toISOString(),
      })
      await tauri.cacheArticle({
        id: feedKey(userId),
        article_json: feedPayload,
      })
    } catch {
      // Fire-and-forget — silently ignore failures.
    }
  }

  /** Get cached following user IDs, or null if no cache exists. */
  async function getCachedFollowingIds(userId: string): Promise<string[] | null> {
    try {
      const r = await tauri.getCachedArticle({ id: idsKey(userId) })
      if (!r || 'error' in r || !r.json) return null
      const parsed = JSON.parse(r.json)
      return Array.isArray(parsed.ids) ? parsed.ids : null
    } catch {
      return null
    }
  }

  /** Get cached feed articles, or null if no cache exists. */
  async function getCachedFeed(userId: string): Promise<FeedCacheResponse['articles'] | null> {
    try {
      const r = await tauri.getCachedArticle({ id: feedKey(userId) })
      if (!r || 'error' in r || !r.json) return null
      const parsed = JSON.parse(r.json)
      return Array.isArray(parsed.articles) ? parsed.articles : null
    } catch {
      return null
    }
  }

  return { refreshCache, getCachedFollowingIds, getCachedFeed }
}
