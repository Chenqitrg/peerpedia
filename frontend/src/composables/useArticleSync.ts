// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '../stores/useUserStore'
import { useTauri } from './useTauri'
import { useNetworkStatus } from './useNetworkStatus'
import { updateArticle } from '../api/articles'
import { extractErrorMessage } from './useLocalStorage'
import type { Draft } from './useTauriTypes'

export type SyncState = 'upload' | 'synced' | 'conflict' | 'offline' | 'loading'

/** Check if a Tauri IPC result is an error shape: { error: string }. */
function isTauriError(v: unknown): v is { error: string } {
  return typeof v === 'object' && v !== null && 'error' in v
}

/**
 * Article sync state machine — L4 specification.
 *
 * Three observable product states:
 *   upload   — no server_article_id (never uploaded)
 *   synced   — server_commit_hash === local HEAD (quiet, no icon)
 *   conflict — server_commit_hash !== local HEAD (must resolve)
 *   offline  — network unavailable (hide icons)
 *   loading  — push in progress
 */
export function useArticleSync(
  draftId: () => string,
  serverArticleId: () => string | null | undefined,
  serverCommitHash: () => string | null | undefined,
  localHeadHash: () => string | null,
) {
  const userStore = useUserStore()
  const tauri = useTauri()
  const { isSynced } = useNetworkStatus()
  const { t } = useI18n()

  const error = ref<string | null>(null)
  const pushing = ref(false)

  const syncState = computed<SyncState>(() => {
    if (!isSynced.value) return 'offline'
    if (pushing.value) return 'loading'
    const sid = serverArticleId()
    const srvHead = serverCommitHash()
    const locHead = localHeadHash()
    if (!sid) return 'upload'
    if (!locHead || !srvHead) return 'synced'
    if (locHead !== srvHead) return 'conflict'
    return 'synced'
  })

  /**
   * Push local changes to server via REST content upload.
   * @deprecated Phase B: replaced by bundle pushRepo — git bundle preserves commit hash.
   */
  async function pushUpdate(): Promise<boolean> {
    const sid = serverArticleId()
    if (!sid || !userStore.token) {
      error.value = t('sync.updateNoId')
      return false
    }
    const id = draftId()
    if (!id) return false

    pushing.value = true
    error.value = null

    try {
      const draft = await tauri.getDraft({ id })
      if (!draft || isTauriError(draft)) throw new Error(t('sync.cannotReadDraft'))

      const history = await tauri.gitHistory({ article_id: id })
      if (!history || isTauriError(history)) throw new Error(t('sync.cannotReadHistory'))
      const headHash =
        Array.isArray(history) && history.length > 0 ? history[0].hash : null
      if (!headHash) throw new Error(t('sync.noCommits'))

      const contentResult = await tauri.gitShow({
        article_id: id,
        commit_hash: headHash,
      })
      if (!contentResult || isTauriError(contentResult))
        throw new Error(t('sync.cannotReadContent'))

      const d = draft as Draft
      await updateArticle(sid, {
        title: d.title,
        content: contentResult as string,
      })

      return true
    } catch (e: unknown) {
      error.value = extractErrorMessage(e) || t('sync.updateFailed')
      return false
    } finally {
      pushing.value = false
    }
  }

  /** Use remote version: rollback local git to server commit. */
  async function useRemote(remoteCommitHash: string): Promise<boolean> {
    const id = draftId()
    if (!id) return false

    pushing.value = true
    error.value = null

    try {
      const viewer = userStore.viewer
      if (!viewer) throw new Error('[useRemote] viewer is null — must be logged in')
      await tauri.gitRollback({
        article_id: id,
        commit_hash: remoteCommitHash,
        author: viewer.name,
        author_id: viewer.id,
      })

      return true
    } catch (e: unknown) {
      error.value = extractErrorMessage(e) || t('sync.rollbackFailed')
      return false
    } finally {
      pushing.value = false
    }
  }

  /** Get content at a specific commit for diff comparison. */
  async function getContentAtCommit(hash: string): Promise<string | null> {
    const id = draftId()
    if (!id) return null
    const result = await tauri.gitShow({
      article_id: id,
      commit_hash: hash,
    })
    if (!result || isTauriError(result)) return null
    return result as string
  }

  function clearError() {
    error.value = null
  }

  return {
    syncState,
    error,
    pushing,
    pushUpdate,
    useRemote,
    getContentAtCommit,
    clearError,
  }
}
