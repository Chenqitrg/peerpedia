import { watch, onDeactivated, onActivated, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useTabStore } from '../stores/useTabStore'

/** Normalize route path to match the canonical form used by openTab. */
function normalizePath(path: string): string {
  if (path.startsWith('/articles/')) {
    return path.replace('/articles/', '/article/')
  }
  return path
}

/**
 * EditorPage tab integration: syncs title + dirty state to tab store.
 */
export function useEditorTab(title: Ref<string>, isClean: Ref<boolean>, contentEl: Ref<HTMLElement | null>) {
  const route = useRoute()
  const tabStore = useTabStore()
  const tabId = normalizePath(route.path)

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
    const tab = tabStore.tabs.find(t => t.id === tabId)
    if (tab?.scrollTop && contentEl.value) {
      contentEl.value.scrollTop = tab.scrollTop
    }
  })
}

/**
 * ArticlePage tab integration: syncs title to tab store.
 */
export function useArticleTab(articleTitle: Ref<string | undefined>, contentEl: Ref<HTMLElement | null>) {
  const route = useRoute()
  const tabStore = useTabStore()
  const tabId = normalizePath(route.path)

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
    const tab = tabStore.tabs.find(t => t.id === tabId)
    if (tab?.scrollTop && contentEl.value) {
      contentEl.value.scrollTop = tab.scrollTop
    }
  })
}
