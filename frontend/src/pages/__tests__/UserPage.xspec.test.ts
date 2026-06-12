/**
 * xspec Specification Tests — UserPage Profile Loading
 *
 * SPECIFICATION STATUS = LOCKED
 *
 * Regression tests for the "User not found" bug: server-only users must
 * be reachable via REST API fallback when in Tauri+online mode.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

// ── Hoisted mock data ────────────────────────────────────────────────────

const { mockServerUser, mockLocalAccounts } = vi.hoisted(() => ({
  mockServerUser: {
    id: 'uuid-feynman', username: 'feynman', name: 'Richard Feynman',
    anonymous_name: 'BongoPlayer', affiliation: 'Caltech',
    expertise: ['physics'], reputation: { professionalism: 4, objectivity: 4, collaboration: 4, pedagogy: 4 },
    followers_count: 4, following_count: 6, article_count: 16,
    created_at: '2026-01-01T00:00:00Z',
  },
  mockLocalAccounts: [{ id: 'uuid-einstein', username: 'einstein' }],
}))

// ── Module-level mutable state ───────────────────────────────────────────

let mockIsOnline = true
let mockIsBrowserLocal = false

// ── Module mocks ─────────────────────────────────────────────────────────

const mockGetUser = vi.fn().mockResolvedValue(mockServerUser)
const mockGetFollowing = vi.fn().mockResolvedValue([])
const mockFollowUser = vi.fn().mockResolvedValue({})
const mockUnfollowUser = vi.fn().mockResolvedValue({})

vi.mock('../../api/users', () => ({
  getUser: (...args: any[]) => mockGetUser(...args),
  getFollowing: (...args: any[]) => mockGetFollowing(...args),
  followUser: (...args: any[]) => mockFollowUser(...args),
  unfollowUser: (...args: any[]) => mockUnfollowUser(...args),
}))

vi.mock('../../api/articles', () => ({
  getArticles: vi.fn().mockResolvedValue([]),
}))

const mockTauriListAccounts = vi.fn().mockResolvedValue(mockLocalAccounts)

vi.mock('../../composables/useTauri', () => ({
  useTauri: () => ({
    listAccounts: (...args: any[]) => mockTauriListAccounts(...args),
    isFollowing: vi.fn().mockResolvedValue({ following: false }),
    followUser: vi.fn(),
    unfollowUser: vi.fn(),
    getFollowing: vi.fn(),
    isTauri: { value: false },
    isBrowserLocal: { value: mockIsBrowserLocal },
  }),
}))

vi.mock('../../composables/useNetworkStatus', () => ({
  useNetworkStatus: () => ({
    isOnline: { value: mockIsOnline },
    ping: vi.fn(),
  }),
}))

vi.mock('../../composables/useOffline', () => ({
  useOffline: () => ({
    canRead: () => true,
    canWrite: () => true,
    getFallback: () => '',
    isLocalOnly: () => false,
  }),
}))

vi.mock('../../composables/useBookmarkToggle', () => ({
  useBookmarkToggle: () => ({ toggle: vi.fn() }),
}))

vi.mock('../../stores/useUserStore', () => ({
  useUserStore: () => ({
    viewer: { id: 'uuid-einstein', name: 'Albert Einstein', username: 'einstein' },
    isTauriMode: false,
    isBrowserLocal: mockIsBrowserLocal,
    token: { value: 'test-token' },
    trySyncServerAuth: vi.fn().mockResolvedValue(true),
  }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ params: { id: 'uuid-feynman' }, query: {}, path: '/user/uuid-feynman' }),
}))

// ── Imports ───────────────────────────────────────────────────────────────

import UserPage from '../UserPage.vue'

describe('xspec: UserPage Profile Loading', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsOnline = true
    mockIsBrowserLocal = false
    mockGetUser.mockResolvedValue(mockServerUser)
    mockTauriListAccounts.mockResolvedValue(mockLocalAccounts)
  })

  async function mountAndSettle() {
    const wrapper = mount(UserPage)
    await nextTick()
    await new Promise(r => setTimeout(r, 50))
    return wrapper
  }

  // ═══════════════════════════════════════════════════════════════════════
  // Regression: Tauri+online falls back to REST API for server users
  // ═══════════════════════════════════════════════════════════════════════
  describe('Regression: Tauri+online falls back to REST API', () => {
    it('GIVEN Tauri/local mode with server reachable '
     + 'AND the target user exists only on the server (not local) '
     + 'WHEN the profile page loads '
     + 'THEN the profile is fetched via REST API', async () => {
      mockIsBrowserLocal = true
      mockIsOnline = true
      // listAccounts returns only local accounts — no feynman
      mockTauriListAccounts.mockResolvedValue(mockLocalAccounts)

      await mountAndSettle()

      // Must call REST API as fallback
      expect(mockGetUser).toHaveBeenCalledWith('uuid-feynman')
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Regression: Tauri+offline with local user loads from local
  // ═══════════════════════════════════════════════════════════════════════
  describe('Regression: Tauri+offline loads from local accounts', () => {
    it('GIVEN Tauri mode without server '
     + 'AND the target user exists in local accounts '
     + 'WHEN the profile page loads '
     + 'THEN the profile loads locally (no REST call)', async () => {
      mockIsBrowserLocal = true
      mockIsOnline = false
      mockTauriListAccounts.mockResolvedValue([
        { id: 'uuid-feynman', username: 'feynman' },
      ])

      await mountAndSettle()

      // Must NOT call REST API — found locally
      expect(mockGetUser).not.toHaveBeenCalled()
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Regression: Web mode uses REST API
  // ═══════════════════════════════════════════════════════════════════════
  describe('Regression: Web mode uses REST API', () => {
    it('GIVEN pure web mode '
     + 'WHEN the profile page loads '
     + 'THEN the profile is fetched via REST API', async () => {
      mockIsBrowserLocal = false

      await mountAndSettle()

      expect(mockGetUser).toHaveBeenCalledWith('uuid-feynman')
    })
  })

  // ═══════════════════════════════════════════════════════════════════════
  // Regression: Tauri+offline without local user shows "User not found"
  // ═══════════════════════════════════════════════════════════════════════
  describe('Regression: Tauri+offline without local user', () => {
    it('GIVEN Tauri mode without server '
     + 'AND the target user does not exist locally '
     + 'WHEN the profile page loads '
     + 'THEN "User not found" is displayed', async () => {
      mockIsBrowserLocal = true
      mockIsOnline = false

      const wrapper = await mountAndSettle()

      expect(mockGetUser).not.toHaveBeenCalled()
      expect(wrapper.text()).toContain('User not found')
    })
  })
})
