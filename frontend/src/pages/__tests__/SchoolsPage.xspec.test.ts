/**
 * xspec Specification Tests — SchoolsPage Follow State
 *
 * SPECIFICATION: Follow data lives on the server (sole source of truth).
 * Online: REST API. Offline: grayed button (useOffline blocks write),
 * follow state reads from useFollowCache.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick, computed } from 'vue'

// ── Hoisted mock data ────────────────────────────────────────────────────

const { mockUsers, mockFollowing, mockViewer, viewerRef } = vi.hoisted(() => {
  const v = {
    id: 'uuid-einstein', name: 'Albert Einstein', username: 'einstein',
    anonymous_name: '', affiliation: 'Princeton', expertise: ['physics'],
    reputation: {}, followers_count: 5, following_count: 3, article_count: 1,
  }
  return {
    mockUsers: [
      { id: 'uuid-feynman', name: 'Richard Feynman', affiliation: 'Caltech',
        expertise: ['physics'], article_count: 16, reputation: {} },
      { id: 'uuid-bohr', name: 'Niels Bohr', affiliation: 'Copenhagen',
        expertise: ['quantum mechanics'], article_count: 3, reputation: {} },
    ],
    mockFollowing: [{ id: 'uuid-bohr', name: 'Niels Bohr' }],
    mockViewer: v,
    viewerRef: { current: v as typeof v | null },
  }
})

// ── Module-level mutable state for mock control ──────────────────────────

import { ref as vRef } from 'vue'
const mockIsSynced = vRef(true)
let mockCanReadSchools = true
let mockCanWriteFollow = true

// ── Module mocks ─────────────────────────────────────────────────────────

const mockGetUsers = vi.fn().mockResolvedValue(mockUsers)
const mockGetFollowing = vi.fn().mockResolvedValue(mockFollowing)
const mockFollowUser = vi.fn().mockResolvedValue({})
const mockUnfollowUser = vi.fn().mockResolvedValue({})

vi.mock('../../api/users', () => ({
  getUsers: (...args: any[]) => mockGetUsers(...args),
  getFollowing: (...args: any[]) => mockGetFollowing(...args),
  followUser: (...args: any[]) => mockFollowUser(...args),
  unfollowUser: (...args: any[]) => mockUnfollowUser(...args),
}))

const mockCacheGetFollowingIds = vi.fn().mockResolvedValue(null)
const mockCacheRefresh = vi.fn().mockResolvedValue(undefined)
const mockCacheGetFeed = vi.fn().mockResolvedValue(null)

vi.mock('../../composables/useFollowCache', () => ({
  useFollowCache: () => ({
    getCachedFollowingIds: (...args: any[]) => mockCacheGetFollowingIds(...args),
    getCachedFeed: (...args: any[]) => mockCacheGetFeed(...args),
    refreshCache: (...args: any[]) => mockCacheRefresh(...args),
  }),
}))

vi.mock('../../composables/useTauri', () => ({
  useTauri: () => ({
    listAccounts: vi.fn(),
    isTauri: { value: false },
    isBrowserLocal: { value: false },
  }),
}))

vi.mock('../../stores/useUserStore', () => ({
  useUserStore: () => ({
    get viewer() { return viewerRef.current },
    isTauriMode: false,
    isBrowserLocal: false,
    token: { value: 'test-token' },
  }),
}))

vi.mock('../../composables/useOffline', () => ({
  useOffline: () => ({
    canRead: (feature: string) => feature === 'schools' ? mockCanReadSchools : true,
    canWrite: (feature: string) => feature === 'user.follow_graph' ? mockCanWriteFollow : true,
    getFallback: () => '',
    isLocalOnly: () => false,
  }),
}))

vi.mock('../../composables/useNetworkStatus', () => ({
  useNetworkStatus: () => ({
    isSynced: mockIsSynced,
    isSynced: computed(() => mockIsSynced.value),
    connectionState: computed(() => mockIsSynced.value ? 'synced' as const : 'idle' as const),
    ping: vi.fn(),
  }),
}))

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({ params: {}, query: {}, path: '/' }),
}))

// ── Imports ───────────────────────────────────────────────────────────────

import SchoolsPage from '../SchoolsPage.vue'

describe('xspec: SchoolsPage Follow State', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsSynced.value = true
    mockCanReadSchools = true
    mockCanWriteFollow = true
    mockGetUsers.mockResolvedValue(mockUsers)
    mockGetFollowing.mockResolvedValue(mockFollowing)
    mockFollowUser.mockResolvedValue({})
    mockUnfollowUser.mockResolvedValue({})
    mockCacheGetFollowingIds.mockResolvedValue(null)
    mockCacheRefresh.mockResolvedValue(undefined)
  })

  async function mountAndSettle() {
    const wrapper = mount(SchoolsPage)
    await nextTick()
    await new Promise(r => setTimeout(r, 50))
    return wrapper
  }

  // ═══════════════════════════════════════════════════════════════════════
  // loadFollowState: online uses REST API
  // ═══════════════════════════════════════════════════════════════════════
  describe('loadFollowState: online uses REST API', () => {
    it('GIVEN online '
     + 'WHEN the Schools page loads '
     + 'THEN follow state is fetched via REST API', async () => {
      mockIsSynced.value = true

      await mountAndSettle()

      expect(mockGetFollowing).toHaveBeenCalledWith('uuid-einstein')
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // loadFollowState: offline reads from cache
  // ═══════════════════════════════════════════════════════════════════════
  describe('loadFollowState: offline reads from cache', () => {
    it('GIVEN offline '
     + 'WHEN the Schools page loads '
     + 'THEN follow state is read from useFollowCache', async () => {
      mockIsSynced.value = false
      mockCacheGetFollowingIds.mockResolvedValue(['uuid-bohr'])

      await mountAndSettle()

      expect(mockCacheGetFollowingIds).toHaveBeenCalledWith('uuid-einstein')
      expect(mockGetFollowing).not.toHaveBeenCalled()
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // toggleFollow: uses REST API when online
  // ═══════════════════════════════════════════════════════════════════════
  describe('toggleFollow: uses REST API', () => {
    it('GIVEN online '
     + 'WHEN the user clicks Follow '
     + 'THEN follow is persisted via REST API', async () => {
      mockIsSynced.value = true

      const wrapper = await mountAndSettle()
      const btn = wrapper.findAll('button').find(b => b.text().trim() === 'Follow')
      expect(btn).toBeTruthy()
      await btn!.trigger('click')
      await nextTick()

      expect(mockFollowUser).toHaveBeenCalled()
      // Cache refreshed after mutation.
      expect(mockCacheRefresh).toHaveBeenCalledWith('uuid-einstein')
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // toggleFollow: revert on failure
  // ═══════════════════════════════════════════════════════════════════════
  describe('toggleFollow: revert on failure', () => {
    it('GIVEN follow API call fails '
     + 'WHEN the user clicks Follow '
     + 'THEN the button reverts to "Follow"', async () => {
      mockFollowUser.mockRejectedValueOnce(new Error('Network error'))

      const wrapper = await mountAndSettle()
      const btn = wrapper.findAll('button').find(b => b.text().trim() === 'Follow')
      await btn!.trigger('click')
      await nextTick()
      await new Promise(r => setTimeout(r, 10))

      // Button should revert to "Follow" after failed API call
      const btns = wrapper.findAll('button')
      const followBtn = btns.find(b => b.text().trim() === 'Follow')
      expect(followBtn).toBeTruthy()
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // toggleFollow: unfollow calls REST API
  // ═══════════════════════════════════════════════════════════════════════
  describe('toggleFollow: unfollow calls REST API', () => {
    it('GIVEN a user is already followed '
     + 'WHEN the user clicks the "Following" button '
     + 'THEN unfollowUser REST API is called', async () => {
      // Bohr is in mockFollowing — he is already followed
      mockGetFollowing.mockResolvedValue(mockFollowing)

      const wrapper = await mountAndSettle()
      const btns = wrapper.findAll('button')
      const followingBtn = btns.find(b => b.text().trim() === 'Following')
      expect(followingBtn).toBeTruthy()

      await followingBtn!.trigger('click')
      await nextTick()

      expect(mockUnfollowUser).toHaveBeenCalled()
      expect(mockCacheRefresh).toHaveBeenCalledWith('uuid-einstein')
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Regression: offline write is blocked by useOffline
  // ═══════════════════════════════════════════════════════════════════════
  describe('Regression: offline follow write is blocked', () => {
    it('GIVEN offline '
     + 'WHEN useOffline blocks follow write '
     + 'THEN follow button is disabled', async () => {
      mockIsSynced.value = false
      mockCanWriteFollow = false

      const wrapper = await mountAndSettle()
      const btns = wrapper.findAll('button')
      // Follow buttons should be disabled when canWrite is false for user.follow_graph
      const followBtns = btns.filter(b => {
        const text = b.text().trim()
        return text === 'Follow' || text === 'Following'
      })
      for (const btn of followBtns) {
        expect((btn.element as HTMLButtonElement).disabled).toBe(true)
      }
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Regression: no follow state loaded without viewer
  // ═══════════════════════════════════════════════════════════════════════
  describe('loadFollowState: no viewer = no call', () => {
    it('GIVEN no viewer is logged in '
     + 'WHEN the Schools page loads '
     + 'THEN no follow API call is made', async () => {
      viewerRef.current = null

      await mountAndSettle()

      expect(mockGetFollowing).not.toHaveBeenCalled()
      expect(mockCacheGetFollowingIds).not.toHaveBeenCalled()

      viewerRef.current = mockViewer
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Regression: follow loads after users (no race condition)
  // ═══════════════════════════════════════════════════════════════════════
  describe('loadFollowState: runs after users fetch', () => {
    it('GIVEN users take time to load '
     + 'WHEN the Schools page is mounted '
     + 'THEN follow state is loaded after users arrive', async () => {
      let resolveUsers: (v: any) => void
      mockGetUsers.mockReturnValue(new Promise(r => { resolveUsers = r }))

      mount(SchoolsPage)
      await nextTick()

      // getFollowing should NOT be called before users resolve
      expect(mockGetFollowing).not.toHaveBeenCalled()

      // Resolve users
      resolveUsers!(mockUsers)
      await nextTick()
      await new Promise(r => setTimeout(r, 10))

      // Now getFollowing should be called
      expect(mockGetFollowing).toHaveBeenCalledWith('uuid-einstein')
    })
  })
})
