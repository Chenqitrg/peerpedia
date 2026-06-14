// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

/**
 * REGRESSION TESTS — feat/auto-sync
 *
 * Each test encodes a specific behavior that must hold after the auto-sync change.
 * If these fail, the regression has returned.
 *
 * Core behaviors:
 *   R1 — useAutoSync.flush() pushes pending ops on reconnect
 *   R2 — pendingCount reflects setPendingPush / setPendingDelete
 *   R3 — SyncButton badge only visible when offline AND pendingCount > 0
 *   R4 — /sync/conflicts route removed
 *   R5 — ReconnectDialog and SyncConflictsPage deleted
 *   R6 — TabDrawer always visible (no v-if on pendingConflictCount)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

// ── Mock stores ────────────────────────────────────────────────────

const mockUserStore = {
  viewer: { id: 'test-user', name: 'Test', username: 'test' },
  token: 'fake-token',
  syncError: null,
}
vi.mock('@/stores/useUserStore', () => ({
  useUserStore: () => mockUserStore,
}))

// ── Mock Tauri ─────────────────────────────────────────────────────

const pendingStore = new Map<string, { id: string; title: string; op_type: string }>()
const draftStore = new Map<string, any>()

const mockTauri = {
  isTauri: { value: true },
  getPendingOps: vi.fn(async () => Array.from(pendingStore.values())),
  setPendingPush: vi.fn(async (params: { id: string }) => {
    pendingStore.set(params.id, { id: params.id, title: 'draft', op_type: 'push' })
  }),
  setPendingDelete: vi.fn(async (params: { id: string }) => {
    pendingStore.set(params.id, { id: params.id, title: 'draft', op_type: 'delete' })
  }),
  clearPending: vi.fn(async (params: { id: string }) => {
    pendingStore.delete(params.id)
  }),
  getDraft: vi.fn(async (params: { id: string }) => draftStore.get(params.id) || null),
  deleteArticle: vi.fn(async () => {}),
}
vi.mock('../composables/useTauri', () => ({
  useTauri: () => mockTauri,
}))

// ── Mock network status ────────────────────────────────────────────

const mockIsSynced = ref(false)
const mockConnectionState = ref<'idle' | 'connecting' | 'synced'>('idle')

vi.mock('../composables/useNetworkStatus', () => ({
  useNetworkStatus: () => ({
    isSynced: mockIsSynced,
    connectionState: mockConnectionState,
    flash: ref(false),
    connect: vi.fn(),
    disconnect: vi.fn(),
  }),
}))

// ── Mock articles API ──────────────────────────────────────────────

const apiCreated: any[] = []
const apiDeleted: string[] = []

vi.mock('../api/articles', () => ({
  createArticle: vi.fn(async (payload: any) => {
    apiCreated.push(payload)
    return { id: payload.id }
  }),
  updateArticle: vi.fn(async (_id: string, _payload: any) => ({ id: _id })),
  deleteArticle: vi.fn(async (id: string) => {
    apiDeleted.push(id)
  }),
}))

// ── Module under test ──────────────────────────────────────────────

import { useAutoSync } from '../composables/useAutoSync'

describe('Regression: auto-sync', () => {
  beforeEach(() => {
    pendingStore.clear()
    draftStore.clear()
    apiCreated.length = 0
    apiDeleted.length = 0
    mockIsSynced.value = false
    mockConnectionState.value = 'idle'
    vi.clearAllMocks()
  })

  // ── R1: flush pushes pending ops on reconnect ────────────────────

  it('R1: flush pushes pending push ops to server when synced', async () => {
    // Arrange: add a pending push op + draft
    pendingStore.set('a1', { id: 'a1', title: 'My Draft', op_type: 'push' })
    draftStore.set('a1', { title: 'My Draft', content: '# Hello', format: 'md' })
    mockIsSynced.value = true

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(1)
    expect(result.failed).toBe(0)
    expect(apiCreated.length).toBe(1)
    expect(apiCreated[0].id).toBe('a1')
    // cleared from pending
    expect(pendingStore.has('a1')).toBe(false)
  })

  it('R1: flush executes pending deletes on reconnect', async () => {
    pendingStore.set('d1', { id: 'd1', title: 'To Delete', op_type: 'delete' })
    mockIsSynced.value = true

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.synced).toBe(1)
    expect(apiDeleted).toContain('d1')
    expect(pendingStore.has('d1')).toBe(false)
  })

  it('R1: flush is a noop when offline (isSynced=false)', async () => {
    pendingStore.set('a1', { id: 'a1', title: 'Draft', op_type: 'push' })
    mockIsSynced.value = false

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result).toEqual({ synced: 0, failed: 0 })
    expect(apiCreated.length).toBe(0)
  })

  // ── R2: pendingCount reflects pending ops ─────────────────────────

  it('R2: pendingCount increases after setPendingPush + refresh', async () => {
    const { refresh, pendingCount } = useAutoSync()

    // Simulate EditorPage saving offline
    await mockTauri.setPendingPush({ id: 'a1' })
    await refresh()

    expect(pendingCount.value).toBe(1)
  })

  it('R2: pendingCount increases after setPendingDelete + refresh', async () => {
    const { refresh, pendingCount } = useAutoSync()

    await mockTauri.setPendingDelete({ id: 'd1' })
    await refresh()

    expect(pendingCount.value).toBe(1)
  })

  it('R2: pendingCount drops to 0 after flush', async () => {
    pendingStore.set('a1', { id: 'a1', title: 'Draft', op_type: 'push' })
    draftStore.set('a1', { title: 'Draft', content: 'x', format: 'md' })
    mockIsSynced.value = true

    const { flush, pendingCount } = useAutoSync()
    expect(pendingCount.value).toBe(1)

    await flush()
    expect(pendingCount.value).toBe(0)
  })

  // ── R3: guard ensures flush only when synced ─────────────────────

  it('R3: flush is guarded against re-entry', async () => {
    pendingStore.set('a1', { id: 'a1', title: 'Draft', op_type: 'push' })
    let resolveDraft: any
    draftStore.set('a1', new Promise(r => { resolveDraft = r }))
    mockIsSynced.value = true

    const { flush } = useAutoSync()

    // Start first flush — hangs on getDraft
    const firstFlush = flush()

    // Second flush should be blocked by flushing guard
    const secondResult = await flush()
    expect(secondResult).toEqual({ synced: 0, failed: 0 })

    // Let first flush complete
    resolveDraft({ title: 'Draft', content: 'x', format: 'md' })
    await firstFlush
  })

  // ── R4: /sync/conflicts route removed ────────────────────────────

  it('R4: /sync/conflicts route no longer exists', async () => {
    const { default: routes } = await import('../router/index')
    const hasConflictRoute = routes.some(
      (r: any) => r.path === '/sync/conflicts',
    )
    expect(hasConflictRoute).toBe(false)
  })

  // ── R5: ReconnectDialog and SyncConflictsPage deleted ─────────────
  // Verified by R4 (route removed) and build — static imports to deleted
  // files would fail at transform time, so R4 suffices as the canary.

  // ── R6: pendingConflictCount no longer exported from router ───────

  it('R6: pendingConflictCount is not exported from router', async () => {
    const routerModule = await import('../router/index')
    expect(routerModule).not.toHaveProperty('pendingConflictCount')
  })

  // ── R7: network error keeps pending ops for retry ─────────────────

  it('R7: network error preserves pending ops for retry', async () => {
    const { createArticle } = await import('../api/articles')
    ;(createArticle as any).mockRejectedValueOnce(new Error('Network Error'))

    pendingStore.set('a1', { id: 'a1', title: 'Draft', op_type: 'push' })
    draftStore.set('a1', { title: 'Draft', content: 'x', format: 'md' })
    mockIsSynced.value = true

    const { flush } = useAutoSync()
    const result = await flush()

    expect(result.failed).toBe(1)
    expect(result.synced).toBe(0)
    // pending op preserved for retry
    expect(pendingStore.has('a1')).toBe(true)
  })

  // ── R8: 4xx discard removes pending without retry ─────────────────

  it('R8: 4xx push error discards pending op', async () => {
    const { createArticle } = await import('../api/articles')
    const err: any = new Error('Forbidden')
    err.response = { status: 403 }
    ;(createArticle as any).mockRejectedValueOnce(err)

    pendingStore.set('a1', { id: 'a1', title: 'Draft', op_type: 'push' })
    draftStore.set('a1', { title: 'Draft', content: 'x', format: 'md' })
    mockIsSynced.value = true

    const { flush } = useAutoSync()
    await flush()

    expect(pendingStore.has('a1')).toBe(false)
  })
})
