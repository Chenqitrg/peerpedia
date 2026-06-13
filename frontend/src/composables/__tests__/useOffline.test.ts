import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useOffline } from '../useOffline'

// Mock useNetworkStatus to control isOnline.
vi.mock('../useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(),
}))

import { useNetworkStatus } from '../useNetworkStatus'

const mockedUseNetworkStatus = useNetworkStatus as ReturnType<typeof vi.fn>

function setSynced(online: boolean) {
  mockedUseNetworkStatus.mockReturnValue({
    isSynced: { value: online },
    connectionState: { value: online ? 'synced' as const : 'idle' as const },
    ping: vi.fn(),
  })
}

describe('useOffline', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('when online', () => {
    beforeEach(() => setSynced(true))

    it('all features canRead returns true', () => {
      const { canRead } = useOffline()
      expect(canRead('feed')).toBe(true)
      expect(canRead('article.fork')).toBe(true)
      expect(canRead('pool')).toBe(true)
      expect(canRead('schools')).toBe(true)
    })

    it('all features canWrite returns true', () => {
      const { canWrite } = useOffline()
      expect(canWrite('editor.publish_pool')).toBe(true)
      expect(canWrite('article.comments')).toBe(true)
      expect(canWrite('article.fork')).toBe(true)
    })
  })

  describe('when in Tauri mode AND server reachable (online)', () => {
    beforeEach(() => {
      setSynced(true) // pings say "online" — server is reachable
      ;(window as any).__TAURI__ = {}
    })

    afterEach(() => {
      delete (window as any).__TAURI__
    })

    it('pool is unblocked when server is reachable', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('pool')).toBe(true)
      expect(canWrite('pool')).toBe(true)
    })

    it('schools is unblocked when server is reachable', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('schools')).toBe(true)
      expect(canWrite('schools')).toBe(true)
    })

    it('search.network is unblocked when server is reachable', () => {
      const { canRead } = useOffline()
      expect(canRead('search.network')).toBe(true)
    })

    it('article.fork is unblocked when server is reachable', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('article.fork')).toBe(true)
      expect(canWrite('article.fork')).toBe(true)
    })

    it('local features remain accessible (feed, editor, search.local, bookmarks)', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('feed')).toBe(true)
      expect(canRead('editor')).toBe(true)
      expect(canRead('search.local')).toBe(true)
      expect(canRead('bookmarks')).toBe(true)
      expect(canRead('article.content')).toBe(true)
    })

    it('isLocalOnly returns false when Tauri AND server reachable', () => {
      const { isLocalOnly } = useOffline()
      expect(isLocalOnly()).toBe(false)
    })
  })

  describe('when in Tauri mode AND server unreachable (offline)', () => {
    beforeEach(() => {
      setSynced(false) // pings say "offline" — server is down
      ;(window as any).__TAURI__ = {}
    })

    afterEach(() => {
      delete (window as any).__TAURI__
    })

    it('pool is blocked when server is down', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('pool')).toBe(false)
      expect(canWrite('pool')).toBe(false)
    })

    it('schools is blocked when server is down', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('schools')).toBe(false)
      expect(canWrite('schools')).toBe(false)
    })

    it('isLocalOnly returns true when Tauri AND offline', () => {
      const { isLocalOnly } = useOffline()
      expect(isLocalOnly()).toBe(true)
    })

    it('getFallback returns local_mode_hint for network features when offline', () => {
      const { getFallback } = useOffline()
      expect(getFallback('pool')).toBe('offline.local_mode_hint')
      expect(getFallback('schools')).toBe('offline.local_mode_hint')
    })
  })

  describe('when offline', () => {
    beforeEach(() => setSynced(false))

    // Full-access features (local data available).
    it('feed is full', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('feed')).toBe(true)
      expect(canWrite('feed')).toBe(true)
    })

    it('bookmarks is full', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('bookmarks')).toBe(true)
      expect(canWrite('bookmarks')).toBe(true)
    })

    it('search.local is full', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('search.local')).toBe(true)
      expect(canWrite('search.local')).toBe(true)
    })

    it('user.self is full', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('user.self')).toBe(true)
      expect(canWrite('user.self')).toBe(true)
    })

    it('editor is full', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('editor')).toBe(true)
      expect(canWrite('editor')).toBe(true)
    })

    it('article.content is full', () => {
      const { canRead } = useOffline()
      expect(canRead('article.content')).toBe(true)
    })

    it('compile is full', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('compile')).toBe(true)
      expect(canWrite('compile')).toBe(true)
    })

    // Readonly features.
    it('article.comments is readonly (canRead, cannotWrite)', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('article.comments')).toBe(true)
      expect(canWrite('article.comments')).toBe(false)
    })

    it('user.follow_graph is readonly (canRead, cannotWrite)', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('user.follow_graph')).toBe(true)
      expect(canWrite('user.follow_graph')).toBe(false)
    })

    // Blocked features.
    it('pool is blocked', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('pool')).toBe(false)
      expect(canWrite('pool')).toBe(false)
    })

    it('schools is blocked', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('schools')).toBe(false)
      expect(canWrite('schools')).toBe(false)
    })

    it('article.fork is blocked', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('article.fork')).toBe(false)
      expect(canWrite('article.fork')).toBe(false)
    })

    it('article.publish is blocked', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('article.publish')).toBe(false)
      expect(canWrite('article.publish')).toBe(false)
    })

    it('editor.publish_pool is blocked', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('editor.publish_pool')).toBe(false)
      expect(canWrite('editor.publish_pool')).toBe(false)
    })

    it('search.network is blocked', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('search.network')).toBe(false)
      expect(canWrite('search.network')).toBe(false)
    })

    it('feed.online is blocked', () => {
      const { canRead, canWrite } = useOffline()
      expect(canRead('feed.online')).toBe(false)
      expect(canWrite('feed.online')).toBe(false)
    })

    // Fallback messages.
    it('getFallback returns i18n key for blocked features', () => {
      const { getFallback } = useOffline()
      expect(getFallback('pool')).toBe('offline.pool_hint')
      expect(getFallback('article.fork')).toBe('offline.fork_hint')
      expect(getFallback('article.comments')).toBe('offline.comment_hint')
    })

    it('getFallback returns empty string for full features', () => {
      const { getFallback } = useOffline()
      expect(getFallback('feed')).toBe('')
      expect(getFallback('editor')).toBe('')
    })
  })
})
