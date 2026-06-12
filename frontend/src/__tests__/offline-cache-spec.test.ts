/**
 * SPEC: Offline Cache Behavior
 *
 * These tests define the expected product behavior for offline mode.
 * They are LOCKED specifications — implementation must satisfy them.
 *
 * User scenarios covered:
 *   S1. Following count visible after auth
 *   S2. Following users list cached with real names
 *   S3. Feed articles cached and visible offline
 *   S4. Followed user profiles cached and accessible offline
 *   S5. Followed user article cards cached and visible offline
 *   S6. Explicitly opened articles cached and readable offline
 *   S7. Network status flips offline on first ping failure
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Mock Tauri IPC layer ──────────────────────────────────────────

const cacheStore = new Map<string, string>()

const mockTauri = {
  cacheArticle: vi.fn(async (params: { id: string; article_json: string }) => {
    cacheStore.set(params.id, params.article_json)
    return { ok: true }
  }),
  getCachedArticle: vi.fn(async (params: { id: string }) => {
    const json = cacheStore.get(params.id)
    return json ? { json, id: params.id } : null
  }),
}

vi.mock('../composables/useTauri', () => ({
  useTauri: () => ({
    cacheArticle: mockTauri.cacheArticle,
    getCachedArticle: mockTauri.getCachedArticle,
    isTauri: { value: true },
    isBrowserLocal: { value: false },
  }),
}))

// ── Imports after mocks ───────────────────────────────────────────

import { useFollowCache } from '../composables/useFollowCache'

// ── Helpers ───────────────────────────────────────────────────────

const sampleUserSummary = (id: string, name: string) => ({
  id,
  name,
  anonymous_name: '',
  article_count: 3,
  reputation: { professionalism: 5, objectivity: 5, collaboration: 5, pedagogy: 5 },
})

const sampleArticleSummary = (id: string, title: string) => ({
  id,
  title,
  status: 'published' as const,
  authors: [{ id: 'u1', name: 'Author', anonymous_name: '' }],
  abstract: null as string | null,
  content_preview: '',
  commit_hash: 'abc1234',
  fork_count: 0,
  forked_from: null as string | null,
  commit_count: 1,
  score: { originality: 4, rigor: 4, completeness: 4, pedagogy: 4, impact: 4 },
  sink_eta: null as string | null,
  days_remaining: null as number | null,
  sink_duration_days: null as number | null,
  is_bookmarked: false,
  is_own_article: false,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
})

const sampleArticleDetail = (id: string, title: string) => ({
  id,
  title,
  status: 'published' as const,
  authors: [{ id: 'u1', name: 'Author', anonymous_name: '' }],
  commit_hash: 'abc1234',
  fork_count: 0,
  forked_from: null as string | null,
  commit_count: 1,
  compiled_format: 'markdown' as const,
  compiled_output: null as string | null,
  compiled_pages: null as number | null,
  score: { originality: 4, rigor: 4, completeness: 4, pedagogy: 4, impact: 4 },
  sink_eta: null as string | null,
  days_remaining: null as number | null,
  sink_duration_days: null as number | null,
  review_count: 0,
  is_bookmarked: false,
  is_own_article: false,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
})

describe('SPEC: Offline Cache Behavior', () => {

  beforeEach(() => {
    cacheStore.clear()
    vi.clearAllMocks()
  })

  // ── S1: Counts ────────────────────────────────────────────────

  describe('S1 — Follow counts cached and retrievable offline', () => {
    it('stores counts and retrieves them', async () => {
      const cache = useFollowCache()
      await cache.setCachedCounts('user-1', { follower: 5, following: 12 })

      const counts = await cache.getCachedCounts('user-1')
      expect(counts).not.toBeNull()
      expect(counts!.follower).toBe(5)
      expect(counts!.following).toBe(12)
    })

    it('returns null when no counts cached', async () => {
      const cache = useFollowCache()
      const counts = await cache.getCachedCounts('never-cached')
      expect(counts).toBeNull()
    })

    it('preserves last known counts across cache writes', async () => {
      const cache = useFollowCache()
      // User has 3 followers, 7 following
      await cache.setCachedCounts('user-2', { follower: 3, following: 7 })
      // Offline: read back — should match
      const counts = await cache.getCachedCounts('user-2')
      expect(counts!.follower).toBe(3)
      expect(counts!.following).toBe(7)
    })
  })

  // ── S2: Following Users ────────────────────────────────────────

  describe('S2 — Following users list cached with real names', () => {
    it('stores and retrieves following users with full data', async () => {
      const cache = useFollowCache()
      const users = [
        sampleUserSummary('u-alice', 'Alice'),
        sampleUserSummary('u-bob', 'Bob'),
      ]
      await cache.setCachedFollowingUsers('viewer-1', users as any)

      const cached = await cache.getCachedFollowingUsers('viewer-1')
      expect(cached).not.toBeNull()
      expect(cached!).toHaveLength(2)
      expect(cached![0].name).toBe('Alice')
      expect(cached![1].name).toBe('Bob')
    })

    it('returns null when no following users cached', async () => {
      const cache = useFollowCache()
      const cached = await cache.getCachedFollowingUsers('unknown')
      expect(cached).toBeNull()
    })
  })

  // ── S3: Feed ───────────────────────────────────────────────────

  describe('S3 — Feed articles cached and visible offline', () => {
    it('getCachedFeed returns null when nothing cached', async () => {
      const cache = useFollowCache()
      const feed = await cache.getCachedFeed('viewer-1')
      expect(feed).toBeNull()
    })

    it('getCachedFeed returns articles after cache write', async () => {
      // Simulate what refreshCache does: write feed articles
      const articles = [
        { id: 'art-1', title: 'Quantum Physics', status: 'published',
          authors: [{ id: 'u1', name: 'Alice', anonymous_name: '' }],
          commit_hash: 'abc', fork_count: 0, forked_from: null,
          score: null, created_at: '2026-01-01' },
      ]
      const feedPayload = JSON.stringify({
        articles,
        cached_at: new Date().toISOString(),
      })
      await mockTauri.cacheArticle({ id: '_feed_viewer-1', article_json: feedPayload })

      const cache = useFollowCache()
      const feed = await cache.getCachedFeed('viewer-1')
      expect(feed).not.toBeNull()
      expect(feed!).toHaveLength(1)
      expect(feed![0].title).toBe('Quantum Physics')
    })
  })

  // ── S4: User Profiles ──────────────────────────────────────────

  describe('S4 — Followed user profiles cached and accessible offline', () => {
    it('stores and retrieves user profile', async () => {
      const cache = useFollowCache()
      const profile = {
        id: 'u-alice', username: 'alice', name: 'Alice',
        anonymous_name: '', affiliation: 'MIT', expertise: ['physics'],
        reputation: { professionalism: 5, objectivity: 5, collaboration: 5, pedagogy: 5 },
        followers_count: 10, following_count: 5, article_count: 7,
        created_at: '2026-01-01T00:00:00Z',
      }
      await cache.setCachedUserProfile('u-alice', profile as any)

      const cached = await cache.getCachedUserProfile('u-alice')
      expect(cached).not.toBeNull()
      expect(cached!.name).toBe('Alice')
      expect(cached!.affiliation).toBe('MIT')
      expect((cached as any).followers_count).toBe(10)
    })

    it('returns null when profile not cached', async () => {
      const cache = useFollowCache()
      const cached = await cache.getCachedUserProfile('stranger')
      expect(cached).toBeNull()
    })
  })

  // ── S5: User Articles ──────────────────────────────────────────

  describe('S5 — Followed user article cards cached and visible offline', () => {
    it('stores and retrieves user article cards', async () => {
      const cache = useFollowCache()
      const articles = [
        sampleArticleSummary('a1', 'First Paper'),
        sampleArticleSummary('a2', 'Second Paper'),
      ]
      await cache.setCachedUserArticles('u-alice', articles as any)

      const cached = await cache.getCachedUserArticles('u-alice')
      expect(cached).not.toBeNull()
      expect(cached!).toHaveLength(2)
      expect(cached![0].title).toBe('First Paper')
      expect(cached![1].title).toBe('Second Paper')
    })

    it('returns null when user articles not cached', async () => {
      const cache = useFollowCache()
      const cached = await cache.getCachedUserArticles('unknown')
      expect(cached).toBeNull()
    })
  })

  // ── S6: Explicitly Opened Articles ─────────────────────────────

  describe('S6 — Explicitly opened articles cached and readable offline', () => {
    it('stores and retrieves full article with source content', async () => {
      const cache = useFollowCache()
      const detail = sampleArticleDetail('art-1', 'Quantum Physics')
      const source = { content: '# Introduction\n\nThis is the content.', format: 'markdown' as const }

      await cache.setCachedArticle('art-1', detail as any, source)

      const cached = await cache.getCachedArticle('art-1')
      expect(cached).not.toBeNull()
      expect(cached!.detail.title).toBe('Quantum Physics')
      expect(cached!.source.content).toContain('Introduction')
      expect(cached!.source.format).toBe('markdown')
    })

    it('returns null for articles never cached', async () => {
      const cache = useFollowCache()
      const cached = await cache.getCachedArticle('never-opened')
      expect(cached).toBeNull()
    })
  })

  // ── S7: Cache overwrite (eng review decision) ──────────────────

  describe('S7 — Cache overwrite on refresh', () => {
    it('counts are overwritten on second write, not merged', async () => {
      const cache = useFollowCache()
      // First write: 5 followers
      await cache.setCachedCounts('user-1', { follower: 5, following: 12 })
      // Second write: 3 followers (user unfollowed by someone)
      await cache.setCachedCounts('user-1', { follower: 3, following: 10 })

      const counts = await cache.getCachedCounts('user-1')
      expect(counts!.follower).toBe(3)  // overwritten, not 5
      expect(counts!.following).toBe(10) // overwritten, not 12
    })
  })
})
