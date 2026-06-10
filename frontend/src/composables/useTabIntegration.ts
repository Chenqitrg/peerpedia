import { watch, onDeactivated, onActivated, type Ref } from 'vue'
import { useTabStore } from '../stores/useTabStore'

/**
 * EditorPage tab integration: syncs title + dirty state to tab store.
 * Receives an explicit tabId (UUID) — no route parsing needed.
 */
export function useEditorTab(
  tabId: string,
  title: Ref<string>,
  isClean: Ref<boolean>,
  contentEl: Ref<HTMLElement | null>,
) {
  const tabStore = useTabStore()

  watch([isClean, title], ([clean, t]) => {
    tabStore.updateTab(tabId, { dirty: !clean, title: t || 'Untitled' })
  }, { immediate: true })

  // Session restore: save/restore scroll position
  onDeactivated(() => {
    if (contentEl.value) {
      tabStore.updateTab(tabId, { scrollTop: contentEl.value.scrollTop })
    }
  })
  onActivated(() => {
    const tab = tabStore.findById(tabId)
    if (tab?.scrollTop && contentEl.value) {
      contentEl.value.scrollTop = tab.scrollTop
    }
  })
}

/**
 * ArticlePage tab integration: syncs title to tab store.
 * Receives an explicit tabId (UUID) — no route parsing needed.
 */
export function useArticleTab(
  tabId: string,
  articleTitle: Ref<string | undefined>,
  contentEl: Ref<HTMLElement | null>,
) {
  const tabStore = useTabStore()

  watch(articleTitle, (title) => {
    if (title) tabStore.updateTab(tabId, { title })
  }, { immediate: true })

  // Session restore
  onDeactivated(() => {
    if (contentEl.value) {
      tabStore.updateTab(tabId, { scrollTop: contentEl.value.scrollTop })
    }
  })
  onActivated(() => {
    const tab = tabStore.findById(tabId)
    if (tab?.scrollTop && contentEl.value) {
      contentEl.value.scrollTop = tab.scrollTop
    }
  })
}
