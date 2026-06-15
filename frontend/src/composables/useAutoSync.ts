// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { useTauri } from './useTauri'
import { useNetworkStatus } from './useNetworkStatus'
import { useUserStore } from '../stores/useUserStore'
import {
  createArticle,
  updateArticle,
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
  /**
   * Push a pending offline edit to server via REST content upload.
   * @deprecated Phase B: replaced by bundle pushRepo — sends git objects, preserves hash.
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
   * Push local commits to server via git bundle (Phase C — bidirectional flow).
   *
   * 1. GET server HEAD hash
   * 2. If server has commits we don't: pull bundle → apply locally (S3)
   * 3. Create incremental bundle from server HEAD to local HEAD
   * 4. POST bundle to /sync (S1, S2)
   * 5. On 409 (ff-only fail): retry from step 1 (S4)
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
        // Server has commits the client doesn't — pull them first
        const bundle = await getArticleBundle(articleId, localHead)
        if (bundle && bundle.byteLength > 0) {
          const bytes = Array.from(new Uint8Array(bundle))
          await tauri.gitBundleApply({ article_id: articleId, bundle_bytes: bytes })
          // Re-read local HEAD after pull — it changed
          const updatedHistory = await tauri.gitHistory({ article_id: articleId })
          if (updatedHistory && !isTauriError(updatedHistory) && Array.isArray(updatedHistory) && updatedHistory.length > 0) {
            localHead = updatedHistory[0].hash
          }
        }
      }
    } catch {
      // Server might not have the article yet (first push) — that's fine
    }

    // Helper: full tar.gz fallback (first push or incremental failure)
    async function fullExportPush(): Promise<{ pushed: boolean; head: string | null }> {
      const raw = await tauri.exportArticle({ article_id: articleId })
      const base64 = (raw && !isTauriError(raw)) ? String(raw) : ''
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

    // 3. Create incremental bundle
    let bundleBytes: number[]
    try {
      const serverHeadRes = await getArticleHead(articleId).catch(() => ({ hash: '' }))
      if (serverHeadRes.hash) {
        const raw = await tauri.gitBundleCreate({
          article_id: articleId,
          since_hash: serverHeadRes.hash,
        })
        if (!raw || isTauriError(raw) || !Array.isArray(raw)) {
          return fullExportPush()
        }
        bundleBytes = raw
      } else {
        return fullExportPush()
      }
    } catch {
      return fullExportPush()
    }

    // 4. POST bundle to /sync
    try {
      const blob = new Blob([new Uint8Array(bundleBytes)], { type: 'application/octet-stream' })
      const result = await syncArticle(articleId, blob)
      return { pushed: true, head: result.head }
    } catch (e: any) {
      if (e?.response?.status === 409) {
        // ff-only failed — retry once after pulling
        try {
          const { hash } = await getArticleHead(articleId)
          const bundle = await getArticleBundle(articleId, localHead)
          if (bundle && bundle.byteLength > 0) {
            const bytes = Array.from(new Uint8Array(bundle))
            await tauri.gitBundleApply({ article_id: articleId, bundle_bytes: bytes })
          }
          // Recreate bundle and retry
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
          if (op.op_type === 'delete') {
            const r = await deleteOne(op)
            if (r.pushed) synced++
          } else {
            // Phase C: try bundle pushRepo first (preserves commit hashes)
            let pushed = false
            try {
              const res = await pushRepo(op.id, 'PeerPedia', 'local', 'Auto-sync')
              pushed = res.pushed
            } catch {
              // Fall back to legacy REST push
            }
            if (!pushed) {
              const r = await pushOne(op)
              pushed = r.pushed
            }
            if (pushed) synced++
          }
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
    pushRepo,
  }
}
