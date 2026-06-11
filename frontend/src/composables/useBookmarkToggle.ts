import { type Ref } from 'vue'
import { useUserStore } from '../stores/useUserStore'
import { useTauri } from './useTauri'
import { useNetworkStatus } from './useNetworkStatus'
import { addBookmark, removeBookmark } from '../api/bookmarks'
import type { ArticleSummary } from '../api/types'

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
  const { isOnline } = useNetworkStatus()
  const isLocal = (userStore.isTauriMode || userStore.isBrowserLocal) && !isOnline.value

  async function toggle(articleId: string, currentlyBookmarked: boolean) {
    if (!userStore.viewer) return
    const article = articles.value.find(a => a.id === articleId)
    if (!article) return

    // SPEC-1.5: 静默忽略自收藏（防止 API 调用）
    if (article.is_own_article) return

    const previous = article.is_bookmarked
    article.is_bookmarked = !currentlyBookmarked

    // If server is reachable but we have no token, try to sync local creds first.
    // Without this, Tauri users who registered locally while the server was down
    // would see "Authentication required" on every bookmark click.
    const needsSync = (userStore.isTauriMode || userStore.isBrowserLocal)
      && isOnline.value
      && !userStore.token?.value

    if (needsSync) {
      const synced = await userStore.trySyncServerAuth()
      if (!synced || !userStore.token?.value) {
        article.is_bookmarked = previous
        if (onError) {
          onError(userStore.syncError?.value || '书签功能需要服务器账号')
        }
        return
      }
    }

    try {
      if (isLocal) {
        // L4: bookmarks require server connection — rollback optimistic update.
        article.is_bookmarked = previous
        if (onError) {
          onError('书签功能需要服务器连接')
        }
        return
      } else {
        if (currentlyBookmarked) {
          await removeBookmark(articleId)
        } else {
          await addBookmark(articleId)
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
      if (isLocal) {
        if (onError) {
          onError('书签功能需要服务器连接')
        }
        return
      } else {
        await removeBookmark(articleId)
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
