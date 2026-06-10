import { type Ref } from 'vue'
import { useUserStore } from '../stores/useUserStore'
import { useTauri } from './useTauri'
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
  const isLocal = userStore.isTauriMode || userStore.isBrowserLocal

  async function toggle(articleId: string, currentlyBookmarked: boolean) {
    if (!userStore.viewer) return
    const article = articles.value.find(a => a.id === articleId)
    if (!article) return

    // SPEC-1.5: 静默忽略自收藏（防止 API 调用）
    if (article.is_own_article) return

    const previous = article.is_bookmarked
    article.is_bookmarked = !currentlyBookmarked

    try {
      if (isLocal) {
        if (currentlyBookmarked) {
          await tauri.removeBookmark({ user_id: userStore.viewer.id, article_id: articleId })
        } else {
          await tauri.addBookmark({ user_id: userStore.viewer.id, article_id: articleId })
        }
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
        await tauri.removeBookmark({ user_id: userStore.viewer.id, article_id: articleId })
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
