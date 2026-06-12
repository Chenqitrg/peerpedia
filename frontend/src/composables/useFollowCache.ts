// Offline cache for follow data.
// Stores following IDs + followed users' article metadata in the
// existing article_cache table (via Tauri IPC). Uses namespaced cache
// keys that never collide with real article UUIDs.
//
// Cache entries:
//   _follow_ids_{userId}     → { ids: string[], cached_at: string }
//   _counts_{userId}         → { follower: number, following: number, cached_at: string }
//   _following_users_{userId}→ { users: UserSummary[], cached_at: string }
//   _feed_{userId}           → { articles: LightFeedArticle[], cached_at: string }
//   _user_articles_{userId}  → { articles: ArticleSummary[], cached_at: string }
//   _article_{articleId}     → { detail: ArticleDetail, source: ArticleSource, cached_at: string }

import { useTauri } from './useTauri'
import { getFeedCache } from '../api/feed'
import type { FeedCacheResponse } from '../api/feed'
import type { ArticleDetail, ArticleSource, ArticleSummary, UserSummary } from '../api/types'

const FOLLOW_IDS_PREFIX = '_follow_ids_'
const COUNTS_PREFIX = '_counts_'
const FOLLOWING_USERS_PREFIX = '_following_users_'
const FEED_PREFIX = '_feed_'
const USER_ARTICLES_PREFIX = '_user_articles_'
const ARTICLE_PREFIX = '_article_'

function idsKey(userId: string): string { return `${FOLLOW_IDS_PREFIX}${userId}` }
function countsKey(userId: string): string { return `${COUNTS_PREFIX}${userId}` }
function followingUsersKey(userId: string): string { return `${FOLLOWING_USERS_PREFIX}${userId}` }
function feedKey(userId: string): string { return `${FEED_PREFIX}${userId}` }
function userArticlesKey(userId: string): string { return `${USER_ARTICLES_PREFIX}${userId}` }
function articleKey(articleId: string): string { return `${ARTICLE_PREFIX}${articleId}` }

export function useFollowCache() {
  const tauri = useTauri()

  /** Fetch feed cache from server and overwrite all local caches. */
  async function refreshCache(userId: string): Promise<void> {
    try {
      const data: FeedCacheResponse = await getFeedCache()

      // Overwrite following IDs.
      const idsPayload = JSON.stringify({
        ids: data.following_ids,
        cached_at: new Date().toISOString(),
      })
      await tauri.cacheArticle({ id: idsKey(userId), article_json: idsPayload })

      // Overwrite counts (from feed cache: following_ids.length; follower not in feed cache).
      const countsPayload = JSON.stringify({
        following: data.following_ids.length,
        cached_at: new Date().toISOString(),
      })
      await tauri.cacheArticle({ id: countsKey(userId), article_json: countsPayload })

      // Overwrite lightweight feed articles.
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
      await tauri.cacheArticle({ id: feedKey(userId), article_json: feedPayload })
    } catch {
      // Fire-and-forget — silently ignore failures.
    }
  }

  // ── Following IDs ──────────────────────────────────────────────────

  async function getCachedFollowingIds(userId: string): Promise<string[] | null> {
    try {
      const r = await tauri.getCachedArticle({ id: idsKey(userId) })
      if (!r || 'error' in r || !r.json) return null
      const parsed = JSON.parse(r.json)
      return Array.isArray(parsed.ids) ? parsed.ids : null
    } catch { return null }
  }

  // ── Counts ─────────────────────────────────────────────────────────

  async function getCachedCounts(userId: string): Promise<{ follower?: number; following?: number } | null> {
    try {
      const r = await tauri.getCachedArticle({ id: countsKey(userId) })
      if (!r || 'error' in r || !r.json) return null
      const parsed = JSON.parse(r.json)
      return { follower: parsed.follower, following: parsed.following }
    } catch { return null }
  }

  async function setCachedCounts(userId: string, counts: { follower?: number; following?: number }): Promise<void> {
    try {
      const payload = JSON.stringify({
        ...counts,
        cached_at: new Date().toISOString(),
      })
      await tauri.cacheArticle({ id: countsKey(userId), article_json: payload })
    } catch { /* ignore */ }
  }

  // ── Following Users (with names) ───────────────────────────────────

  async function getCachedFollowingUsers(userId: string): Promise<UserSummary[] | null> {
    try {
      const r = await tauri.getCachedArticle({ id: followingUsersKey(userId) })
      if (!r || 'error' in r || !r.json) return null
      const parsed = JSON.parse(r.json)
      return Array.isArray(parsed.users) ? parsed.users : null
    } catch { return null }
  }

  async function setCachedFollowingUsers(userId: string, users: UserSummary[]): Promise<void> {
    try {
      const payload = JSON.stringify({
        users,
        cached_at: new Date().toISOString(),
      })
      await tauri.cacheArticle({ id: followingUsersKey(userId), article_json: payload })
    } catch { /* ignore */ }
  }

  // ── Feed (lightweight articles) ────────────────────────────────────

  async function getCachedFeed(userId: string): Promise<FeedCacheResponse['articles'] | null> {
    try {
      const r = await tauri.getCachedArticle({ id: feedKey(userId) })
      if (!r || 'error' in r || !r.json) return null
      const parsed = JSON.parse(r.json)
      return Array.isArray(parsed.articles) ? parsed.articles : null
    } catch { return null }
  }

  // ── User Articles (per-user article cards) ─────────────────────────

  async function getCachedUserArticles(userId: string): Promise<ArticleSummary[] | null> {
    try {
      const r = await tauri.getCachedArticle({ id: userArticlesKey(userId) })
      if (!r || 'error' in r || !r.json) return null
      const parsed = JSON.parse(r.json)
      return Array.isArray(parsed.articles) ? parsed.articles : null
    } catch { return null }
  }

  async function setCachedUserArticles(userId: string, articles: ArticleSummary[]): Promise<void> {
    try {
      const payload = JSON.stringify({
        articles,
        cached_at: new Date().toISOString(),
      })
      await tauri.cacheArticle({ id: userArticlesKey(userId), article_json: payload })
    } catch { /* ignore */ }
  }

  // ── Explicitly opened articles (full content) ──────────────────────

  async function getCachedArticle(articleId: string): Promise<{ detail: ArticleDetail; source: ArticleSource } | null> {
    try {
      const r = await tauri.getCachedArticle({ id: articleKey(articleId) })
      if (!r || 'error' in r || !r.json) return null
      const parsed = JSON.parse(r.json)
      return parsed.detail ? parsed : null
    } catch { return null }
  }

  async function setCachedArticle(articleId: string, detail: ArticleDetail, source: ArticleSource): Promise<void> {
    try {
      const payload = JSON.stringify({
        detail,
        source,
        cached_at: new Date().toISOString(),
      })
      await tauri.cacheArticle({ id: articleKey(articleId), article_json: payload })
    } catch { /* ignore */ }
  }

  return {
    refreshCache,
    getCachedFollowingIds,
    getCachedCounts,
    setCachedCounts,
    getCachedFollowingUsers,
    setCachedFollowingUsers,
    getCachedFeed,
    getCachedUserArticles,
    setCachedUserArticles,
    getCachedArticle,
    setCachedArticle,
  }
}
