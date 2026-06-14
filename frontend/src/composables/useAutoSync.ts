// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { useTauri } from './useTauri'
import { useNetworkStatus } from './useNetworkStatus'
import { useUserStore } from '../stores/useUserStore'
import { createArticle, updateArticle, deleteArticle } from '../api/articles'
import type { PendingOp } from './useTauriTypes'

function isTauriError(v: unknown): v is { error: string } {
  return typeof v === 'object' && v !== null && 'error' in v
}

/** HTTP status codes that indicate the op should be discarded (won't succeed on retry). */
function isDiscardable(status: number): boolean {
  return status >= 400 && status < 500
}

// ── Module-level singleton — all callers share the same pending state. ──
const flushing: Ref<boolean> = ref(false)
const pendingOps: Ref<PendingOp[]> = ref([])
const pendingCount: ComputedRef<number> = computed(() => pendingOps.value.length)

/**
 * Auto-sync composable — flushes pending push/delete ops when coming online.
 *
 * Entry point: App.vue watcher calls flush() when isSynced becomes true.
 * SyncButton reads pendingCount for the red badge via module-level singleton.
 */
export function useAutoSync() {
  const tauri = useTauri()
  const { isSynced } = useNetworkStatus()
  const userStore = useUserStore()

  /** Load pending ops from Tauri storage into the shared singleton. */
  async function loadPendingOps(): Promise<void> {
    if (!tauri.isTauri.value) {
      pendingOps.value = []
      return
    }
    const ops = await tauri.getPendingOps({ account_id: userStore.viewer?.id || 'local' })
    if (ops && Array.isArray(ops) && !isTauriError(ops)) {
      pendingOps.value = ops
    } else {
      pendingOps.value = []
    }
  }

  /**
   * Push a single draft to the server.
   * Tries POST (create) first; falls back to PUT (update) on 409.
   * Returns { pushed: true } on success, { pushed: false, discard: true } on 4xx,
   * throws on network error.
   */
  async function pushOne(op: PendingOp): Promise<{ pushed: boolean; discard: boolean }> {
    const draft = await tauri.getDraft({ id: op.id })
    if (!draft || isTauriError(draft)) {
      return { pushed: false, discard: true }
    }

    const d = draft as { title: string; content?: string; format?: string }
    const fmt = d.format === 'typst' ? 'typst' as const : 'markdown' as const
    const payload = {
      id: op.id,
      title: d.title || op.title || 'Untitled',
      content: d.content || '',
      format: fmt,
      commit_message: 'Auto-sync from offline edits',
    }

    try {
      await createArticle(payload)
      return { pushed: true, discard: false }
    } catch (e: any) {
      if (e?.response?.status === 409 || e?.response?.status === 422) {
        try {
          await updateArticle(op.id, {
            title: d.title || op.title || 'Untitled',
            content: d.content || '',
            commit_message: 'Auto-sync from offline edits',
            publish: false,
          })
          return { pushed: true, discard: false }
        } catch (e2: any) {
          if (isDiscardable(e2?.response?.status || 0)) {
            return { pushed: false, discard: true }
          }
          throw e2
        }
      }
      if (isDiscardable(e?.response?.status || 0)) {
        return { pushed: false, discard: true }
      }
      throw e
    }
  }

  /**
   * Execute a pending delete on the server.
   * Returns { pushed: true } on success, { pushed: false, discard: true } on 4xx,
   * throws on network error.
   */
  async function deleteOne(op: PendingOp): Promise<{ pushed: boolean; discard: boolean }> {
    try {
      await deleteArticle(op.id)
      try { await tauri.deleteArticle({ id: op.id }) } catch { /* best-effort */ }
      return { pushed: true, discard: false }
    } catch (e: any) {
      if (isDiscardable(e?.response?.status || 0)) {
        return { pushed: false, discard: true }
      }
      throw e
    }
  }

  /**
   * Flush all pending ops to the server.
   * Called when isSynced becomes true (reconnect).
   * Guarded against re-entry via module-level flushing ref.
   */
  async function flush(): Promise<{ synced: number; failed: number }> {
    if (flushing.value || !isSynced.value) return { synced: 0, failed: 0 }
    if (!tauri.isTauri.value) return { synced: 0, failed: 0 }

    flushing.value = true
    let synced = 0
    let failed = 0

    try {
      await loadPendingOps()
      const ops = [...pendingOps.value]

      for (const op of ops) {
        try {
          let result: { pushed: boolean; discard: boolean }
          if (op.op_type === 'delete') {
            result = await deleteOne(op)
          } else {
            result = await pushOne(op)
          }

          if (result.pushed) synced++
          try { await tauri.clearPending({ id: op.id }) } catch { /* best-effort */ }
        } catch {
          failed++
        }
      }

      await loadPendingOps()
    } finally {
      flushing.value = false
    }

    return { synced, failed }
  }

  /** Refresh pending count (call on mount and after save/delete). */
  async function refresh(): Promise<void> {
    await loadPendingOps()
  }

  return {
    flushing,
    pendingCount,
    pendingOps,
    flush,
    refresh,
    loadPendingOps,
  }
}
