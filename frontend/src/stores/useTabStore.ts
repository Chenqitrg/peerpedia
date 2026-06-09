import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { loadJSON, saveJSON } from '../composables/useLocalStorage'

export interface Tab {
  id: string
  type: 'editor' | 'article'
  title: string
  dirty: boolean
  icon: 'edit' | 'eye'
  status: 'draft' | 'published' | 'sedimentation'
  scrollTop?: number
  cursorPosition?: number
}

const STORAGE_KEY = 'peerpedia_tabs'

export const useTabStore = defineStore('tab', () => {
  const tabs = ref<Tab[]>([])
  const activeTabId = ref<string | null>(null)

  // Capture router once during store setup — useRouter() must be called
  // while the Pinia store is being initialized within a Vue app that has
  // the router plugin installed. Storing the reference avoids calling
  // useRouter() inside action callbacks where getCurrentInstance() may
  // be unavailable.
  let router: ReturnType<typeof useRouter> | null = null
  try { router = useRouter() } catch { /* no router available */ }

  function persist(): void {
    saveJSON(STORAGE_KEY, {
      tabs: tabs.value.map(t => ({
        id: t.id, type: t.type, title: t.title,
        icon: t.icon, status: t.status,
        scrollTop: t.scrollTop, cursorPosition: t.cursorPosition,
      })),
      activeTabId: activeTabId.value,
    })
  }

  function findTab(routePath: string): Tab | undefined {
    return tabs.value.find(t => t.id === routePath)
  }

  function getAdjacentTabId(closedId: string): string | null {
    const idx = tabs.value.findIndex(t => t.id === closedId)
    if (idx === -1) return null
    if (idx < tabs.value.length - 1) return tabs.value[idx + 1].id
    if (idx > 0) return tabs.value[idx - 1].id
    return null
  }

  function openTab(rawPath: string): void {
    // Normalize /articles/xxx → /article/xxx (preserve query params for uniqueness)
    const normalized = rawPath.replace(/^\/articles\//, '/article/')
    const basePath = normalized.split('?')[0]
    if (!basePath.startsWith('/edit') && !basePath.startsWith('/article')) return

    const existing = findTab(normalized)
    if (existing) { activeTabId.value = normalized; persist(); return }

    const type = basePath.startsWith('/edit') ? 'editor' : 'article'
    const status = type === 'editor' ? 'draft' : 'published'
    tabs.value.push({
      id: normalized, type,
      title: type === 'editor' ? 'Untitled' : 'Loading...',
      dirty: false,
      icon: type === 'editor' ? 'edit' : 'eye',
      status,
    })
    activeTabId.value = normalized
    persist()
  }

  function activateTab(tabId: string): void {
    activeTabId.value = tabId
    persist()
    if (router) router.push(tabId)
  }

  function updateTab(tabId: string, patch: Partial<Pick<Tab, 'title' | 'dirty' | 'status' | 'scrollTop' | 'cursorPosition'>>): void {
    const tab = findTab(tabId)
    if (!tab) return
    if (patch.title !== undefined) tab.title = patch.title
    if (patch.dirty !== undefined) tab.dirty = patch.dirty
    if (patch.status !== undefined) tab.status = patch.status
    if (patch.scrollTop !== undefined) tab.scrollTop = patch.scrollTop
    if (patch.cursorPosition !== undefined) tab.cursorPosition = patch.cursorPosition
    persist()
  }

  function closeTab(tabId: string): { shouldPrompt: boolean } {
    const tab = findTab(tabId)
    if (!tab) return { shouldPrompt: false }
    if (tab.dirty) return { shouldPrompt: true }
    removeTab(tabId)
    return { shouldPrompt: false }
  }

  function removeTab(tabId: string): void {
    const nextTabId = getAdjacentTabId(tabId)
    const wasActive = activeTabId.value === tabId
    tabs.value = tabs.value.filter(t => t.id !== tabId)

    if (wasActive) {
      if (nextTabId) {
        activeTabId.value = nextTabId
        if (router) router.push(nextTabId)
      } else {
        activeTabId.value = null
        if (router) router.push('/')
      }
    }
    persist()
  }

  function restoreTabs(): void {
    const saved = loadJSON<{ tabs: Tab[]; activeTabId: string | null }>(STORAGE_KEY)
    if (!saved?.tabs?.length) return
    tabs.value = saved.tabs.map(t => ({ ...t, dirty: false }))
    activeTabId.value = saved.activeTabId
    if (saved.activeTabId && router) router.push(saved.activeTabId)
  }

  return { tabs, activeTabId, openTab, activateTab, updateTab, closeTab, removeTab, restoreTabs }
})
