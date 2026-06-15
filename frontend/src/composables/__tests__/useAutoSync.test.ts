// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// ── Mock Tauri composable ──────────────────────────────────────────────

const mockGetPendingOps = vi.fn()
const mockClearPending = vi.fn()
const mockGetDraft = vi.fn()
const mockDeleteArticle = vi.fn()
const mockIsTauri = vi.fn(() => true)
const mockGitHistory = vi.fn()
const mockGitBundleCreate = vi.fn()
const mockGitBundleApply = vi.fn()
const mockExportArticle = vi.fn()

vi.mock('../useTauri', () => ({
  useTauri: () => ({
    isTauri: { value: mockIsTauri() },
    getPendingOps: mockGetPendingOps,
    clearPending: mockClearPending,
    getDraft: mockGetDraft,
    deleteArticle: mockDeleteArticle,
    gitHistory: mockGitHistory,
    gitBundleCreate: mockGitBundleCreate,
    gitBundleApply: mockGitBundleApply,
    exportArticle: mockExportArticle,
  }),
}))

// ── Mock network status ───────────────────────────────────────────────

const mockIsSynced = vi.fn(() => true)
vi.mock('../useNetworkStatus', () => ({
  useNetworkStatus: () => ({
    isSynced: { value: mockIsSynced() },
  }),
}))

// ── Mock user store ───────────────────────────────────────────────────

vi.mock('../../stores/useUserStore', () => ({
  useUserStore: () => ({
    viewer: { id: 'test-user', name: 'Test', username: 'test' },
    token: 'fake-token',
  }),
}))

// ── Mock articles API (bundle sync endpoints) ─────────────────────────

const mockCreateArticle = vi.fn()
const mockApiDeleteArticle = vi.fn()
const mockGetArticleHead = vi.fn()
const mockGetArticleBundle = vi.fn()
const mockSyncArticle = vi.fn()

vi.mock('../../api/articles', () => ({
  createArticle: (...args: any[]) => mockCreateArticle(...args),
  deleteArticle: (...args: any[]) => mockApiDeleteArticle(...args),
  getArticleHead: (...args: any[]) => mockGetArticleHead(...args),
  getArticleBundle: (...args: any[]) => mockGetArticleBundle(...args),
  syncArticle: (...args: any[]) => mockSyncArticle(...args),
}))

import { useAutoSync } from '../useAutoSync'

// ── Helpers ────────────────────────────────────────────────────────────

/** Set up mocks for a successful incremental bundle push. */
function mockBundlePushSuccess(head: string = 'abc123') {
  mockGitHistory.mockResolvedValue([{ hash: 'abc123', message: 'test' }])
  mockGetArticleHead.mockResolvedValue({ hash: 'server-head' })
  mockGitBundleCreate.mockResolvedValue([1, 2, 3])  // bundle bytes as number[]
  mockSyncArticle.mockResolvedValue({ head })
}

function mockPendingOp(id: string, opType: 'push' | 'delete' = 'push') {
  return { id, title: 'Draft', op_type: opType, updated_at: '2026-01-01' }
}

describe('useAutoSync', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockIsTauri.mockReturnValue(true)
    mockIsSynced.mockReturnValue(true)
    // Default: no pending ops
    mockGetPendingOps.mockResolvedValue([])
  })

  // ── pendingCount ──────────────────────────────────────────────────────

  it('pendingCount starts at 0', () => {
    const { pendingCount } = useAutoSync()
    expect(pendingCount.value).toBe(0)
  })

  // ── loadPendingOps ────────────────────────────────────────────────────

  it('loadPendingOps sets pendingCount from Tauri ops', async () => {
    mockGetPendingOps.mockResolvedValue([
      mockPendingOp('a1'),
      mockPendingOp('a2', 'delete'),
    ])
    const { loadPendingOps, pendingCount } = useAutoSync()
    await loadPendingOps()
    expect(pendingCount.value).toBe(2)
  })

  it('loadPendingOps handles Tauri error gracefully', async () => {
    mockGetPendingOps.mockResolvedValue({ error: 'not found' })
    const { loadPendingOps, pendingCount } = useAutoSync()
    await loadPendingOps()
    expect(pendingCount.value).toBe(0)
  })

  it('loadPendingOps returns 0 when not in Tauri mode', async () => {
    mockIsTauri.mockReturnValue(false)
    const { loadPendingOps, pendingCount } = useAutoSync()
    await loadPendingOps()
    expect(pendingCount.value).toBe(0)
  })

  // ── flush guard ───────────────────────────────────────────────────────

  it('flush returns early when not online', async () => {
    mockIsSynced.mockReturnValue(false)
    const { flush } = useAutoSync()
    const result = await flush()
    expect(result).toEqual({ synced: 0, failed: 0 })
    expect(mockGetPendingOps).not.toHaveBeenCalled()
  })

  it('flush returns early when not in Tauri mode', async () => {
    mockIsTauri.mockReturnValue(false)
    const { flush } = useAutoSync()
    const result = await flush()
    expect(result).toEqual({ synced: 0, failed: 0 })
    expect(mockGetPendingOps).not.toHaveBeenCalled()
  })

  // ── flush — empty queue ───────────────────────────────────────────────

  it('flush with empty pending ops is a noop', async () => {
    mockGetPendingOps.mockResolvedValue([])
    const { flush } = useAutoSync()
    const result = await flush()
    expect(result).toEqual({ synced: 0, failed: 0 })
  })

  // ── flush — push via bundle (pushRepo) ────────────────────────────────

  it('flush pushes a pending push op via bundle sync', async () => {
    mockGetPendingOps.mockResolvedValue([mockPendingOp('a1')])
    mockBundlePushSuccess('abc123')

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(1)
    expect(result.failed).toBe(0)
    expect(mockSyncArticle).toHaveBeenCalled()
    expect(mockClearPending).toHaveBeenCalledWith({ id: 'a1' })
  })

  it('flush marks as failed when bundle push returns pushed=false', async () => {
    mockGetPendingOps.mockResolvedValue([mockPendingOp('a1')])
    mockGitHistory.mockResolvedValue(null)  // no local history → pushed=false

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(0)
    expect(result.failed).toBe(1)
    // Pending NOT cleared on failure
    expect(mockClearPending).not.toHaveBeenCalled()
  })

  // ── flush — delete op ─────────────────────────────────────────────────

  it('flush executes a pending delete op', async () => {
    mockGetPendingOps.mockResolvedValue([mockPendingOp('d1', 'delete')])
    mockApiDeleteArticle.mockResolvedValue(undefined)

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(1)
    expect(mockApiDeleteArticle).toHaveBeenCalledWith('d1')
    expect(mockClearPending).toHaveBeenCalledWith({ id: 'd1' })
  })

  it('flush discards pending delete on 404', async () => {
    mockGetPendingOps.mockResolvedValue([mockPendingOp('d1', 'delete')])
    const err: any = new Error('Not Found')
    err.response = { status: 404 }
    mockApiDeleteArticle.mockRejectedValue(err)

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(0)
    expect(mockClearPending).toHaveBeenCalledWith({ id: 'd1' })
  })

  // ── flush — draft missing ─────────────────────────────────────────────

  it('flush marks as failed when draft is missing (pushRepo returns false)', async () => {
    mockGetPendingOps.mockResolvedValue([mockPendingOp('gone')])
    // Missing local history → pushRepo returns { pushed: false }
    mockGitHistory.mockResolvedValue(null)

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.failed).toBe(1)
    expect(mockClearPending).not.toHaveBeenCalled()
  })

  // ── flush — first push via repo_bundle ──────────────────────────────

  it('flush does first push via createArticle repo_bundle when server has no article', async () => {
    mockGetPendingOps.mockResolvedValue([mockPendingOp('new-article')])
    mockGitHistory.mockResolvedValue([{ hash: 'local-hash', message: 'test' }])
    // Server doesn't have the article yet
    mockGetArticleHead.mockResolvedValue({ hash: '' })
    mockExportArticle.mockResolvedValue('base64content')
    mockCreateArticle.mockResolvedValue({ id: 'new-article' })

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(1)
    expect(mockCreateArticle).toHaveBeenCalled()
    expect(mockClearPending).toHaveBeenCalledWith({ id: 'new-article' })
  })

  // ── flush — re-entry guard ────────────────────────────────────────────

  it('flush is guarded against re-entry (flushing ref)', async () => {
    let resolvePending: any
    let callCount = 0
    mockGetPendingOps.mockImplementation(
      () => {
        callCount++
        if (callCount === 1) {
          return new Promise(r => { resolvePending = r })
        }
        return Promise.resolve([])
      }
    )

    const { flush } = useAutoSync()

    const firstFlush = flush()

    const secondResult = await flush()
    expect(secondResult).toEqual({ synced: 0, failed: 0 })

    resolvePending([])
    await firstFlush
  })
})
