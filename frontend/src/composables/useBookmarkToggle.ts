// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { type Ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '../stores/useUserStore'
import { useTauri } from './useTauri'
import { useNetworkStatus } from './useNetworkStatus'
import { saveJSON, loadJSON } from './useLocalStorage'
import { addBookmark, removeBookmark } from '../api/bookmarks'
import { getArticle } from '../api/articles'
import type { ArticleSummary } from '../api/types'
import { articlePermissions } from '../lib/permissions'

/**
 * Shared bookmark toggle logic used by HomePage, PoolPage, UserPage,
 * SearchPage, and BookmarksPage.
 *
 * @param articles - reactive array of articles to update in-place
 * @param onError  - optional callback for error messages (skips if omitted)
 */
export function useBookmarkToggle(
  articles: Ref<ArticleSummary[]>,
  onError?: (msg: string) => void,
) {
  const userStore = useUserStore()
  const tauri = useTauri()
  const { t } = useI18n()
  const { connectionState } = useNetworkStatus()
  const isLocal = computed(() =>
    (userStore.isTauriMode || userStore.isBrowserLocal) && connectionState.value !== 'synced'
  )

  async function _syncBookmarkCache(viewerId: string, articleId: string, add: boolean) {
    const cacheKey = `bookmarks-${viewerId}`
    const items = loadJSON<ArticleSummary[]>(cacheKey) || []
    let filtered = items.filter(a => a.id !== articleId)
    if (add) {
      let article = articles.value.find(a => a.id === articleId)
      // If not in the current page's articles, fetch from API.
      if (!article) {
        try {
          const detail = await getArticle(articleId)
          article = { ...detail, abstract: null, content_preview: '' } as unknown as ArticleSummary
        } catch { /* can't fetch, skip */ }
      }
      if (article) {
        filtered.push({ ...article, is_bookmarked: true })
      }
    }
    saveJSON(cacheKey, filtered)
  }

  async function toggle(articleId: string, currentlyBookmarked: boolean) {
    if (!userStore.viewer) return
    const article = articles.value.find(a => a.id === articleId)
    if (!article) return

    // Policy gate: bookmark requires auth + not own article
    if (!articlePermissions(article, !!userStore.viewer).canBookmark) return

    const previous = article.is_bookmarked
    article.is_bookmarked = !currentlyBookmarked

    // If server is reachable but we have no token, try to sync local creds first.
    // Without this, Tauri users who registered locally while the server was down
    // would see "Authentication required" on every bookmark click.
    const needsSync = (userStore.isTauriMode || userStore.isBrowserLocal)
      && connectionState.value === 'synced'
      && !userStore.token

    if (needsSync) {
      console.log('[bookmark] needsSync, calling trySyncServerAuth')
      const synced = await userStore.trySyncServerAuth()
      console.log('[bookmark] trySyncServerAuth result:', synced, 'token:', !!userStore.token)
      if (!synced || !userStore.token) {
        article.is_bookmarked = previous
        if (onError) {
          onError(userStore.syncError || t('bookmark.serverRequired'))
        }
        return
      }
    }

    try {
      if (isLocal.value) {
        // L4: bookmarks require server connection — rollback optimistic update.
        article.is_bookmarked = previous
        if (onError) {
          onError(t('bookmark.serverRequired'))
        }
        return
      } else {
        if (currentlyBookmarked) {
          await removeBookmark(articleId)
          await _syncBookmarkCache(userStore.viewer.id, articleId, false)
        } else {
          await addBookmark(articleId)
          await _syncBookmarkCache(userStore.viewer.id, articleId, true)
        }
      }
    } catch (e: any) {
      article.is_bookmarked = previous
      if (onError) {
        onError(e.userMessage || 'Failed to update bookmark')
      }
    }
  }

  /** Remove bookmark without toggling back (for BookmarksPage) */
  async function remove(articleId: string) {
    if (!userStore.viewer) return
    try {
      if (isLocal.value) {
        if (onError) {
          onError(t('bookmark.serverRequired'))
        }
        return
      } else {
        await removeBookmark(articleId)
        await _syncBookmarkCache(userStore.viewer.id, articleId, false)
      }
      const idx = articles.value.findIndex(a => a.id === articleId)
      if (idx !== -1) {
        articles.value.splice(idx, 1)
      }
    } catch (e: any) {
      if (onError) {
        onError(e.userMessage || 'Failed to remove bookmark')
      }
    }
  }

  return { toggle, remove }
}
