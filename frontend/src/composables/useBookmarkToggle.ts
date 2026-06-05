import { type Ref } from 'vue'
import { useUserStore } from '../stores/useUserStore'
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

  async function toggle(articleId: string, currentlyBookmarked: boolean) {
    if (!userStore.viewer) return
    try {
      if (currentlyBookmarked) {
        await removeBookmark(articleId)
      } else {
        await addBookmark(articleId)
      }
      const article = articles.value.find(a => a.id === articleId)
      if (article) {
        article.is_bookmarked = !currentlyBookmarked
      }
    } catch (e: any) {
      if (onError) {
        onError(e.userMessage || 'Failed to update bookmark')
      }
    }
  }

  /** Remove bookmark without toggling back (for BookmarksPage) */
  async function remove(articleId: string) {
    if (!userStore.viewer) return
    try {
      await removeBookmark(articleId)
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
