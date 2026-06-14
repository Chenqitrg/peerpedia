// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// Mock Tauri composable
const mockGetPendingOps = vi.fn()
const mockClearPending = vi.fn()
const mockGetDraft = vi.fn()
const mockDeleteArticle = vi.fn()
const mockIsTauri = vi.fn(() => true)

vi.mock('../useTauri', () => ({
  useTauri: () => ({
    isTauri: { value: mockIsTauri() },
    getPendingOps: mockGetPendingOps,
    clearPending: mockClearPending,
    getDraft: mockGetDraft,
    deleteArticle: mockDeleteArticle,
  }),
}))

// Mock network status
const mockIsSynced = vi.fn(() => true)
vi.mock('../useNetworkStatus', () => ({
  useNetworkStatus: () => ({
    isSynced: { value: mockIsSynced() },
  }),
}))

// Mock user store
vi.mock('../../stores/useUserStore', () => ({
  useUserStore: () => ({
    viewer: { id: 'test-user', name: 'Test', username: 'test' },
    token: 'fake-token',
  }),
}))

// Mock articles API
const mockCreateArticle = vi.fn()
const mockUpdateArticle = vi.fn()
const mockApiDeleteArticle = vi.fn()
vi.mock('../../api/articles', () => ({
  createArticle: (...args: any[]) => mockCreateArticle(...args),
  updateArticle: (...args: any[]) => mockUpdateArticle(...args),
  deleteArticle: (...args: any[]) => mockApiDeleteArticle(...args),
}))

import { useAutoSync } from '../useAutoSync'

describe('useAutoSync', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockIsTauri.mockReturnValue(true)
    mockIsSynced.mockReturnValue(true)
  })

  // ── pendingCount ──────────────────────────────────────────────────

  it('pendingCount starts at 0', () => {
    const { pendingCount } = useAutoSync()
    expect(pendingCount.value).toBe(0)
  })

  // ── loadPendingOps ────────────────────────────────────────────────

  it('loadPendingOps sets pendingCount from Tauri ops', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 'a1', title: 'Draft 1', op_type: 'push', updated_at: '2026-01-01' },
      { id: 'a2', title: 'Draft 2', op_type: 'delete', updated_at: '2026-01-02' },
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

  // ── flush guard (no Tauri / not synced) ───────────────────────────

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

  // ── flush — empty queue ───────────────────────────────────────────

  it('flush with empty pending ops is a noop', async () => {
    mockGetPendingOps.mockResolvedValue([])
    const { flush } = useAutoSync()
    const result = await flush()
    expect(result).toEqual({ synced: 0, failed: 0 })
  })

  // ── flush — push success ──────────────────────────────────────────

  it('flush pushes a pending push op to server', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 'a1', title: 'My Draft', op_type: 'push', updated_at: '2026-01-01' },
    ])
    mockGetDraft.mockResolvedValue({ title: 'My Draft', content: '# Hello', format: 'md' })
    mockCreateArticle.mockResolvedValue({ id: 'a1' })

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(1)
    expect(result.failed).toBe(0)
    expect(mockCreateArticle).toHaveBeenCalled()
    expect(mockClearPending).toHaveBeenCalledWith({ id: 'a1' })
  })

  // ── flush — push falls back to PUT on 409 ─────────────────────────

  it('flush falls back to PUT update on 409', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 'a1', title: 'Existing', op_type: 'push', updated_at: '2026-01-01' },
    ])
    mockGetDraft.mockResolvedValue({ title: 'Existing', content: 'updated' })
    const err: any = new Error('Conflict')
    err.response = { status: 409 }
    mockCreateArticle.mockRejectedValue(err)
    mockUpdateArticle.mockResolvedValue({ id: 'a1' })

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(1)
    expect(mockUpdateArticle).toHaveBeenCalledWith('a1', expect.any(Object))
    expect(mockClearPending).toHaveBeenCalledWith({ id: 'a1' })
  })

  // ── flush — 4xx discard ───────────────────────────────────────────

  it('flush discards pending op on 4xx (not 409/422)', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 'a1', title: 'Bad', op_type: 'push', updated_at: '2026-01-01' },
    ])
    mockGetDraft.mockResolvedValue({ title: 'Bad', content: 'x' })
    const err: any = new Error('Forbidden')
    err.response = { status: 403 }
    mockCreateArticle.mockRejectedValue(err)

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(0)
    expect(result.failed).toBe(0) // discarded, not failed
    expect(mockClearPending).toHaveBeenCalledWith({ id: 'a1' })
  })

  // ── flush — network error keeps pending ────────────────────────────

  it('flush keeps pending on network error', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 'a1', title: 'Net Fail', op_type: 'push', updated_at: '2026-01-01' },
    ])
    mockGetDraft.mockResolvedValue({ title: 'Net Fail', content: 'x' })
    mockCreateArticle.mockRejectedValue(new Error('Network Error'))

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.failed).toBe(1)
    expect(result.synced).toBe(0)
    expect(mockClearPending).not.toHaveBeenCalled()
  })

  // ── flush — delete op ─────────────────────────────────────────────

  it('flush executes a pending delete op', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 'd1', title: 'To Delete', op_type: 'delete', updated_at: '2026-01-01' },
    ])
    mockApiDeleteArticle.mockResolvedValue(undefined)

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(1)
    expect(mockApiDeleteArticle).toHaveBeenCalledWith('d1')
    expect(mockClearPending).toHaveBeenCalledWith({ id: 'd1' })
  })

  it('flush discards pending delete on 404', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 'd1', title: 'Gone', op_type: 'delete', updated_at: '2026-01-01' },
    ])
    const err: any = new Error('Not Found')
    err.response = { status: 404 }
    mockApiDeleteArticle.mockRejectedValue(err)

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(0) // discarded, not pushed
    expect(mockClearPending).toHaveBeenCalledWith({ id: 'd1' })
  })

  // ── flush — draft missing ─────────────────────────────────────────

  it('flush discards pending push when draft is missing', async () => {
    mockGetPendingOps.mockResolvedValue([
      { id: 'gone', title: 'Gone', op_type: 'push', updated_at: '2026-01-01' },
    ])
    mockGetDraft.mockResolvedValue({ error: 'not found' })

    const { flush } = useAutoSync()
    const result = await flush()

    // discarded — draft is gone, can't push
    expect(mockClearPending).toHaveBeenCalledWith({ id: 'gone' })
  })

  // ── flush — re-entry guard ────────────────────────────────────────

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

    // Start first flush — doesn't await
    const firstFlush = flush()

    // Second flush while first is still running — should be blocked by flushing guard
    const secondResult = await flush()
    expect(secondResult).toEqual({ synced: 0, failed: 0 }) // re-entry blocked

    // Let the first one complete
    resolvePending([])
    await firstFlush
  })
})
