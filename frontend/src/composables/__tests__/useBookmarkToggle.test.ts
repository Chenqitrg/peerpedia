import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

// Mock useNetworkStatus — Layer 1 test controls isOnline directly.
const mockIsOnline = ref(false)
vi.mock('../useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(() => ({
    isOnline: mockIsOnline,
    startPing: vi.fn(),
    stopPing: vi.fn(),
  })),
}))

// Mock useTauri — test controls Tauri presence and IPC behavior.
const mockIsTauri = ref(false)
const mockAddBookmarkIpc = vi.fn()
const mockRemoveBookmarkIpc = vi.fn()
vi.mock('../useTauri', () => ({
  useTauri: vi.fn(() => ({
    isTauri: mockIsTauri,
    isBrowserLocal: ref(false),
    addBookmark: mockAddBookmarkIpc,
    removeBookmark: mockRemoveBookmarkIpc,
  })),
}))

// Mock useUserStore
const mockViewer = ref<{ id: string } | null>({ id: 'u1' })
const mockIsTauriMode = ref(false)
const mockToken = ref<string | null>(null)
const mockSyncError = ref<string | null>(null)
const mockTrySyncServerAuth = vi.fn().mockResolvedValue(false)
vi.mock('../../stores/useUserStore', () => ({
  useUserStore: vi.fn(() => ({
    viewer: mockViewer,
    isTauriMode: mockIsTauriMode,
    isBrowserLocal: false,
    token: mockToken,
    syncError: mockSyncError,
    trySyncServerAuth: mockTrySyncServerAuth,
  })),
}))

// Mock REST API
vi.mock('../../api/bookmarks', () => ({
  addBookmark: vi.fn(),
  removeBookmark: vi.fn(),
}))

import { useBookmarkToggle } from '../useBookmarkToggle'
import { addBookmark, removeBookmark } from '../../api/bookmarks'

describe('useBookmarkToggle', () => {
  let articles: ReturnType<typeof ref<{ id: string; is_bookmarked: boolean; is_own_article: boolean }[]>>

  beforeEach(() => {
    vi.clearAllMocks()
    articles = ref([
      { id: 'a1', is_bookmarked: false, is_own_article: false },
      { id: 'a2', is_bookmarked: true, is_own_article: false },
    ])
    mockIsOnline.value = false
    mockIsTauri.value = false
    mockIsTauriMode.value = false
    mockViewer.value = { id: 'u1' }
  })

  describe('S-BM1: Tauri + server reachable → REST API', () => {
    beforeEach(() => {
      mockIsTauri.value = true
      mockIsTauriMode.value = true
      mockIsOnline.value = true // Server reachable
      mockToken.value = 'existing-jwt' // Already have server token, skip sync
    })

    it('routes add bookmark through REST API', async () => {
      const { toggle } = useBookmarkToggle(articles)
      await toggle('a1', false)
      expect(addBookmark).toHaveBeenCalledWith('a1')
    })

    it('routes remove bookmark through REST API', async () => {
      const { toggle } = useBookmarkToggle(articles)
      await toggle('a2', true)
      expect(removeBookmark).toHaveBeenCalledWith('a2')
    })

    it('optimistically updates is_bookmarked on add', async () => {
      const { toggle } = useBookmarkToggle(articles)
      const promise = toggle('a1', false)
      expect(articles.value[0].is_bookmarked).toBe(true) // optimistic
      await promise
      expect(articles.value[0].is_bookmarked).toBe(true) // confirmed
    })

    it('optimistically updates is_bookmarked on remove', async () => {
      const { toggle } = useBookmarkToggle(articles)
      const promise = toggle('a2', true)
      expect(articles.value[1].is_bookmarked).toBe(false) // optimistic
      await promise
      expect(articles.value[1].is_bookmarked).toBe(false) // confirmed
    })
  })

  describe('S-BM2: Tauri + server unreachable → IPC', () => {
    beforeEach(() => {
      mockIsTauri.value = true
      mockIsTauriMode.value = true
      mockIsOnline.value = false // Server unreachable
      mockAddBookmarkIpc.mockRejectedValue(new Error('command not found'))
      mockRemoveBookmarkIpc.mockRejectedValue(new Error('command not found'))
    })

    it('does not call REST API', async () => {
      const { toggle } = useBookmarkToggle(articles)
      await toggle('a1', false)
      expect(addBookmark).not.toHaveBeenCalled()
      expect(removeBookmark).not.toHaveBeenCalled()
    })

    it('reverts optimistic state on IPC error', async () => {
      const { toggle } = useBookmarkToggle(articles)
      await toggle('a1', false)
      expect(articles.value[0].is_bookmarked).toBe(false)
    })
  })

  describe('Edge cases', () => {
    it('skips own article (self-bookmark prevention)', async () => {
      articles.value[0].is_own_article = true
      const { toggle } = useBookmarkToggle(articles)
      await toggle('a1', false)
      expect(addBookmark).not.toHaveBeenCalled()
      expect(articles.value[0].is_bookmarked).toBe(false)
    })

    it('does nothing when viewer is null', async () => {
      mockViewer.value = null
      const { toggle } = useBookmarkToggle(articles)
      await toggle('a1', false)
      expect(addBookmark).not.toHaveBeenCalled()
    })
  })

  describe('SPEC-AUTH-BM-2: Bookmark awaits sync when no token', () => {
    beforeEach(() => {
      mockIsTauri.value = true
      mockIsTauriMode.value = true
      mockIsOnline.value = true // Server reachable
      mockToken.value = null    // No token — need sync
      mockTrySyncServerAuth.mockReset()
    })

    it('calls trySyncServerAuth and rolls back on sync failure', async () => {
      mockTrySyncServerAuth.mockResolvedValue(false)
      mockSyncError.value = '服务器上已有用户 alice'

      const { toggle } = useBookmarkToggle(articles)
      await toggle('a1', false)

      expect(mockTrySyncServerAuth).toHaveBeenCalled()
      // Optimistic update set is_bookmarked=true, then rolled back to false
      expect(articles.value[0].is_bookmarked).toBe(false)
    })

    it('proceeds with REST API when sync succeeds', async () => {
      // Simulate sync populating the token
      mockTrySyncServerAuth.mockImplementation(async () => {
        mockToken.value = 'newly-synced-jwt'
        return true
      })

      const { toggle } = useBookmarkToggle(articles)
      await toggle('a1', false)

      expect(mockTrySyncServerAuth).toHaveBeenCalled()
      expect(addBookmark).toHaveBeenCalledWith('a1')
      expect(articles.value[0].is_bookmarked).toBe(true)
    })
  })
})
