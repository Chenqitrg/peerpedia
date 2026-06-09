import { watch, onDeactivated, onActivated, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useTabStore } from '../stores/useTabStore'

/**
 * EditorPage tab integration: syncs title + dirty state to tab store.
 * Returns a ref used by EditorPage to detect close-dialog trigger.
 */
export function useEditorTab(title: Ref<string>, isClean: Ref<boolean>, contentEl: Ref<HTMLElement | null>) {
  const route = useRoute()
  const tabStore = useTabStore()

  watch([isClean, title], ([clean, t]) => {
    tabStore.updateTab(route.path, { dirty: !clean, title: t || 'Untitled' })
  }, { immediate: true })

  // Session restore: save/restore scroll position
  onDeactivated(() => {
    if (contentEl.value) {
      tabStore.updateTab(route.path, { scrollTop: contentEl.value.scrollTop })
    }
  })
  onActivated(() => {
    const tab = tabStore.tabs.find(t => t.id === route.path)
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

  watch(articleTitle, (title) => {
    if (title) tabStore.updateTab(route.path, { title })
  }, { immediate: true })

  // Session restore
  onDeactivated(() => {
    if (contentEl.value) {
      tabStore.updateTab(route.path, { scrollTop: contentEl.value.scrollTop })
    }
  })
  onActivated(() => {
    const tab = tabStore.tabs.find(t => t.id === route.path)
    if (tab?.scrollTop && contentEl.value) {
      contentEl.value.scrollTop = tab.scrollTop
    }
  })
}
