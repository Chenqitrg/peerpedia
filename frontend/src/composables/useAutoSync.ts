// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { useTauri } from './useTauri'
import { useNetworkStatus } from './useNetworkStatus'
import { useUserStore } from '../stores/useUserStore'
import {
  createArticle,
  deleteArticle,
  getArticleHead,
  getArticleBundle,
  syncArticle,
} from '../api/articles'
import type { PendingOp } from './useTauriTypes'

function isTauriError(v: unknown): v is { error: string } {
  return typeof v === 'object' && v !== null && 'error' in v
}

/** HTTP status codes that indicate the op should be discarded (won't succeed on retry).
 *  Excludes 401 (token expired — re-auth may fix) and 429 (rate limit — backoff and retry). */
function isDiscardable(status: number): boolean {
  if (status === 401 || status === 429) return false
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
    const viewer = userStore.viewer
    if (!viewer) throw new Error('[loadPendingOps] viewer is null — must be logged in')
    const ops = await tauri.getPendingOps({ account_id: viewer.id })
    if (ops && Array.isArray(ops) && !isTauriError(ops)) {
      pendingOps.value = ops
    } else {
      pendingOps.value = []
    }
  }

  /**
   * Push local commits to server via git bundle.
   *
   * 1. GET server HEAD hash
   * 2. If server has commits we don't: pull bundle → apply locally
   * 3. Create incremental bundle from server HEAD to local HEAD
   * 4. POST bundle to /sync
   * 5. On 409 (ff-only fail): pull + retry once
   *
   * For first-ever push (server has no article yet): upload the full
   * repo as a tar.gz via createArticle({repo_bundle}).
   */
  async function pushRepo(
    articleId: string,
    authorName: string,
    authorId: string,
    msg: string,
  ): Promise<{ pushed: boolean; head: string | null }> {
    // 1. Get local HEAD
    let history: any
    try {
      history = await tauri.gitHistory({ article_id: articleId })
    } catch {
      return { pushed: false, head: null }
    }
    if (!history || isTauriError(history) || !Array.isArray(history) || history.length === 0) {
      return { pushed: false, head: null }
    }
    let localHead: string = history[0].hash

    // 2. Pull server bundle if server has commits we don't have
    try {
      const serverHead = await getArticleHead(articleId)
      if (serverHead.hash && serverHead.hash !== localHead) {
        const bundle = await getArticleBundle(articleId, localHead)
        if (bundle && bundle.byteLength > 0) {
          const bytes = Array.from(new Uint8Array(bundle))
          await tauri.gitBundleApply({ article_id: articleId, bundle_bytes: bytes })
          const updatedHistory = await tauri.gitHistory({ article_id: articleId })
          if (updatedHistory && !isTauriError(updatedHistory) && Array.isArray(updatedHistory) && updatedHistory.length > 0) {
            localHead = updatedHistory[0].hash
          }
        }
      }
    } catch {
      // Server might not have the article yet (first push) — that's fine
    }

    // 3. Create incremental bundle.  If the server doesn't have the article
    //    (getArticleHead returns no hash), do the first push via repo_bundle.
    let bundleBytes: number[]
    try {
      const serverHeadRes = await getArticleHead(articleId).catch(() => ({ hash: '' }))
      if (serverHeadRes.hash) {
        const raw = await tauri.gitBundleCreate({
          article_id: articleId,
          since_hash: serverHeadRes.hash,
        })
        if (!raw || isTauriError(raw) || !Array.isArray(raw)) {
          return { pushed: false, head: null }
        }
        bundleBytes = raw
      } else {
        // First push — upload full repo as tar.gz bundle
        const raw = await tauri.exportArticle({ article_id: articleId })
        const base64 = (raw && !isTauriError(raw)) ? String(raw) : ''
        if (!base64) return { pushed: false, head: null }
        await createArticle({
          id: articleId,
          title: '',
          content: '',
          format: 'markdown',
          commit_message: msg,
          repo_bundle: base64,
        })
        return { pushed: true, head: localHead }
      }
    } catch {
      return { pushed: false, head: null }
    }

    // 4. POST bundle to /sync
    try {
      const blob = new Blob([new Uint8Array(bundleBytes)], { type: 'application/octet-stream' })
      const result = await syncArticle(articleId, blob)
      return { pushed: true, head: result.head }
    } catch (e: any) {
      if (e?.response?.status === 409) {
        // ff-only failed — pull + retry once
        try {
          const { hash } = await getArticleHead(articleId)
          const bundle = await getArticleBundle(articleId, localHead)
          if (bundle && bundle.byteLength > 0) {
            const bytes = Array.from(new Uint8Array(bundle))
            await tauri.gitBundleApply({ article_id: articleId, bundle_bytes: bytes })
          }
          const retryRaw = await tauri.gitBundleCreate({ article_id: articleId, since_hash: hash })
          if (!retryRaw || isTauriError(retryRaw) || !Array.isArray(retryRaw)) {
            return { pushed: false, head: null }
          }
          bundleBytes = retryRaw
          const blob = new Blob([new Uint8Array(bundleBytes)], { type: 'application/octet-stream' })
          const retry = await syncArticle(articleId, blob)
          return { pushed: true, head: retry.head }
        } catch {
          return { pushed: false, head: null }
        }
      }
      return { pushed: false, head: null }
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
   * Flush all pending ops to the server via git bundle.
   * Called when isSynced becomes true (reconnect).
   *
   * Bundle-only — no REST degradation. If a push fails, the pending
   * op stays in the queue and will be retried on the next reconnect.
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
          if (op.op_type === 'delete') {
            const r = await deleteOne(op)
            if (r.pushed) synced++
            else if (r.discard) { /* gone — clear it */ }
            else failed++
            try { await tauri.clearPending({ id: op.id }) } catch { /* best-effort */ }
          } else {
            const viewer = userStore.viewer
            if (!viewer) throw new Error('[flushPendingOps] viewer is null — must be logged in')
            const res = await pushRepo(op.id, viewer.name, viewer.id, 'Auto-sync')
            if (res.pushed) {
              synced++
              try { await tauri.clearPending({ id: op.id }) } catch { /* best-effort */ }
            } else {
              failed++
              // Pending op stays in queue for next retry.
            }
          }
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
    pushRepo,
  }
}
