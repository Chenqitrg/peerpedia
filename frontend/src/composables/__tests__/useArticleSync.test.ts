import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

// ── Mock useNetworkStatus ──────────────────────────────────────────────
const mockIsSynced = ref(true)
vi.mock('../useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(() => ({ isSynced: mockIsSynced })),
}))

// ── Mock useTauri ──────────────────────────────────────────────────────
const mockGetDraft = vi.fn()
const mockGitHistory = vi.fn()
const mockGitShow = vi.fn()
const mockGitRollback = vi.fn()
const mockSetServerArticleId = vi.fn()
vi.mock('../useTauri', () => ({
  useTauri: vi.fn(() => ({
    isTauri: ref(true),
    isBrowserLocal: ref(false),
    getDraft: mockGetDraft,
    gitHistory: mockGitHistory,
    gitShow: mockGitShow,
    gitRollback: mockGitRollback,
    setServerArticleId: mockSetServerArticleId,
  })),
}))

// ── Mock useUserStore ──────────────────────────────────────────────────
const mockViewer = ref<{ id: string; name: string; username: string } | null>({
  id: 'u1', name: 'Test User', username: 'test',
})
const mockToken = ref<string | null>('test-token')
const mockLocalToken = ref<string | null>('local-token')
vi.mock('../../stores/useUserStore', () => ({
  useUserStore: vi.fn(() => ({
    get viewer() { return mockViewer.value },
    get token() { return mockToken.value },
    get localToken() { return mockLocalToken.value },
    isTauriMode: false,
    isBrowserLocal: false,
    trySyncServerAuth: vi.fn(),
    syncError: ref(null),
  })),
}))

// ── Mock REST API — inline mocks to avoid closure/TDZ issues ──────────
vi.mock('../../api/articles', () => ({
  createArticle: vi.fn().mockResolvedValue({ id: 'server-1' }),
  updateArticle: vi.fn().mockResolvedValue({ id: 'server-1' }),
}))

import { createArticle, updateArticle } from '../../api/articles'
const mockCreateArticle = createArticle as unknown as ReturnType<typeof vi.fn>
const mockUpdateArticle = updateArticle as unknown as ReturnType<typeof vi.fn>

// ── Module under test ──────────────────────────────────────────────────
import { useArticleSync } from '../useArticleSync'

describe('useArticleSync — SPEC-SYNC state machine', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsSynced.value = true
    mockToken.value = 'test-token'
    mockLocalToken.value = 'local-token'
    mockViewer.value = { id: 'u1', name: 'Test User', username: 'test' }
    mockGetDraft.mockResolvedValue({
      id: 'd1', account_id: 'u1', title: 'Test', content: '# Hello',
      format: 'markdown', updated_at: '2026-01-01',
      server_article_id: null, server_commit_hash: null,
    })
    mockGitHistory.mockResolvedValue([
      { hash: 'abc123', message: '', author: '', timestamp: '' },
    ])
    mockGitShow.mockResolvedValue('# Content')
    mockGitRollback.mockResolvedValue({ hash: 'def456', message: '' })
    mockSetServerArticleId.mockResolvedValue({ ok: true })
    mockCreateArticle.mockResolvedValue({ id: 'server-1' })
    mockUpdateArticle.mockResolvedValue({ id: 'server-1' })
  })

  it('SPEC-SYNC-STATE-1: syncState is "upload" when no serverArticleId', () => {
    const { syncState } = useArticleSync(() => 'd1', () => null, () => null, () => 'abc123')
    expect(syncState.value).toBe('upload')
  })

  it('SPEC-SYNC-STATE-2: syncState is "synced" when hashes match', () => {
    const { syncState } = useArticleSync(() => 'd1', () => 's1', () => 'abc123', () => 'abc123')
    expect(syncState.value).toBe('synced')
  })

  it('SPEC-SYNC-STATE-3: syncState is "conflict" when hashes differ', () => {
    const { syncState } = useArticleSync(() => 'd1', () => 's1', () => 'old_hash', () => 'new_hash')
    expect(syncState.value).toBe('conflict')
  })

  it('SPEC-SYNC-STATE-4: syncState is "offline" when not online', () => {
    mockIsSynced.value = false
    const { syncState } = useArticleSync(() => 'd1', () => 's1', () => 'old', () => 'new')
    expect(syncState.value).toBe('offline')
  })

  it('SPEC-SYNC-ACTION-1: upload() returns true on success', async () => {
    const { upload } = useArticleSync(() => 'd1', () => null, () => null, () => 'abc123')
    const result = await upload()
    expect(result).toBe(true)
    expect(mockCreateArticle).toHaveBeenCalled()
    expect(mockSetServerArticleId).toHaveBeenCalledWith(
      expect.objectContaining({ draft_id: 'd1', server_article_id: 'server-1', server_commit_hash: 'abc123' }),
    )
  })

  it('SPEC-SYNC-ACTION-2: pushUpdate() returns true on success', async () => {
    // pushUpdate reads gitHistory directly — must return the new local HEAD hash
    mockGitHistory.mockResolvedValue([{ hash: 'new_hash', message: '', author: '', timestamp: '' }])
    const { pushUpdate } = useArticleSync(() => 'd1', () => 's1', () => 'old_hash', () => 'new_hash')
    const result = await pushUpdate()
    expect(result).toBe(true)
    expect(mockUpdateArticle).toHaveBeenCalled()
    expect(mockSetServerArticleId).toHaveBeenCalledWith(
      expect.objectContaining({ draft_id: 'd1', server_article_id: 's1', server_commit_hash: 'new_hash' }),
    )
  })

  it('SPEC-SYNC-REGRESSION-1: upload() sends payload without hardcoded authors', async () => {
    // Authors are now auto-derived by the backend from git history + auth token.
    // Frontend no longer hardcodes authors — backend defaults to current_user.
    mockViewer.value = { id: 'u1', name: 'ChenqiMeng', username: 'test' }
    const { upload } = useArticleSync(() => 'd1', () => null, () => null, () => 'abc123')
    await upload()
    expect(mockCreateArticle).toHaveBeenCalled()
    // Verify authors field is NOT in the payload (backend handles it)
    const callArg = mockCreateArticle.mock.calls[0][0]
    expect(callArg.authors).toBeUndefined()
  })

  it('SPEC-SYNC-REGRESSION-2: upload() still works when viewer is null', async () => {
    // Backend derives author from auth token, not request body.
    mockViewer.value = null
    const { upload } = useArticleSync(() => 'd1', () => null, () => null, () => 'abc123')
    await upload()
    expect(mockCreateArticle).toHaveBeenCalled()
    const callArg = mockCreateArticle.mock.calls[0][0]
    expect(callArg.authors).toBeUndefined()
  })
})
