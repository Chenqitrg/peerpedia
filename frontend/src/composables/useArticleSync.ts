import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '../stores/useUserStore'
import { useTauri } from './useTauri'
import { useNetworkStatus } from './useNetworkStatus'
import { createArticle, updateArticle } from '../api/articles'
import { extractErrorMessage } from './useLocalStorage'
import type { Draft, SetServerArticleIdParams } from './useTauriTypes'

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
  const { isOnline } = useNetworkStatus()
  const { t } = useI18n()

  const error = ref<string | null>(null)
  const pushing = ref(false)

  const syncState = computed<SyncState>(() => {
    if (!isOnline.value) return 'offline'
    if (pushing.value) return 'loading'
    const sid = serverArticleId()
    const sch = serverCommitHash()
    const lh = localHeadHash()
    if (!sid) return 'upload'
    if (!lh || !sch) return 'synced'
    if (lh !== sch) return 'conflict'
    return 'synced'
  })

  /** First upload: POST to create server article, store sync mapping. */
  async function upload(): Promise<boolean> {
    if (!userStore.token?.value) {
      error.value = t('sync.loginRequired')
      return false
    }
    const id = draftId()
    if (!id) {
      error.value = t('sync.noArticle')
      return false
    }

    pushing.value = true
    error.value = null

    try {
      const draft = await tauri.getDraft({ id })
      if (!draft || isTauriError(draft)) {
        error.value = t('sync.cannotReadDraft')
        return false
      }
      const d = draft as Draft

      const history = await tauri.gitHistory({ article_id: id })
      if (!history || isTauriError(history)) {
        error.value = t('sync.cannotReadHistory')
        return false
      }
      const headHash =
        Array.isArray(history) && history.length > 0 ? history[0].hash : null
      if (!headHash) {
        error.value = t('sync.noCommits')
        return false
      }

      const contentResult = await tauri.gitShow({
        article_id: id,
        commit_hash: headHash,
      })
      if (!contentResult || isTauriError(contentResult)) {
        error.value = t('sync.cannotReadContent')
        return false
      }

      const viewer = userStore.viewer
      const result = await createArticle({
        title: d.title || 'Untitled',
        content: contentResult as string,
        format: (d.format as 'markdown' | 'typst') || 'markdown',
        authors: viewer ? [viewer.name || viewer.username] : ['Anonymous'],
        keywords: [],
        categories: [],
        abstract: '',
        commit_message: 'Initial upload from PeerPedia Desktop',
        self_review: {
          originality: 3,
          rigor: 3,
          completeness: 3,
          pedagogy: 3,
          impact: 3,
        },
      })

      const serverId = result?.id
      if (!serverId) {
        error.value = t('sync.serverError')
        return false
      }

      const sidParams: SetServerArticleIdParams = {
        draft_id: id,
        server_article_id: serverId,
        server_commit_hash: headHash,
        token: userStore.localToken?.value || undefined,
        account_id: userStore.viewer?.id || '',
      }
      await tauri.setServerArticleId(sidParams)

      return true
    } catch (e: unknown) {
      error.value = extractErrorMessage(e) || t('sync.uploadFailed')
      return false
    } finally {
      pushing.value = false
    }
  }

  /** Push local changes to server (Keep Local in conflict resolution). */
  async function pushUpdate(): Promise<boolean> {
    const sid = serverArticleId()
    if (!sid || !userStore.token?.value) {
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

      const sidParams: SetServerArticleIdParams = {
        draft_id: id,
        server_article_id: sid,
        server_commit_hash: headHash,
        token: userStore.localToken?.value || undefined,
        account_id: userStore.viewer?.id || '',
      }
      await tauri.setServerArticleId(sidParams)

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
      await tauri.gitRollback({
        article_id: id,
        commit_hash: remoteCommitHash,
        author: userStore.viewer?.name || 'PeerPedia',
      })

      const sid = serverArticleId()
      const sidParams: SetServerArticleIdParams = {
        draft_id: id,
        server_article_id: sid || '',
        server_commit_hash: remoteCommitHash,
        token: userStore.localToken?.value || undefined,
        account_id: userStore.viewer?.id || '',
      }
      await tauri.setServerArticleId(sidParams)

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
    upload,
    pushUpdate,
    useRemote,
    getContentAtCommit,
    clearError,
  }
}
