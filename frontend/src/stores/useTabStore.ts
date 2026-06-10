import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { loadJSON, saveJSON } from '../composables/useLocalStorage'

export interface Tab {
  id: string            // UUID — stable identity, never changes
  routePath: string     // associated route (for lookup + navigation)
  type: 'editor' | 'article'
  title: string
  dirty: boolean
  icon: 'edit' | 'eye'
  status: 'draft' | 'published' | 'sedimentation'
  scrollTop?: number
  cursorPosition?: number
}

const STORAGE_KEY = 'peerpedia_tabs'

/** Generate a unique tab id. Falls back to timestamp+random in HTTP contexts. */
function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return Date.now().toString(36) + Math.random().toString(36).slice(2)
}

/** Normalize /articles/xxx → /article/xxx for consistent routePath lookup. */
function normalizePath(path: string): string {
  if (path.startsWith('/articles/')) {
    return path.replace('/articles/', '/article/')
  }
  return path
}

const TAB_DEFAULTS: Record<Tab['type'], Pick<Tab, 'title' | 'icon' | 'status'>> = {
  editor: { title: 'Untitled', icon: 'edit', status: 'draft' },
  article: { title: 'Loading...', icon: 'eye', status: 'published' },
}

export const useTabStore = defineStore('tab', () => {
  const tabs = ref<Tab[]>([])
  const activeTabId = ref<string | null>(null)

  // Capture router once during store setup — useRouter() must be called
  // while the Pinia store is being initialized within a Vue app that has
  // the router plugin installed.
  let router: ReturnType<typeof useRouter> | null = null
  try { router = useRouter() } catch { /* no router available */ }

  function persist(): void {
    saveJSON(STORAGE_KEY, {
      tabs: tabs.value.map(t => ({
        id: t.id, routePath: t.routePath, type: t.type, title: t.title,
        icon: t.icon, status: t.status,
        scrollTop: t.scrollTop, cursorPosition: t.cursorPosition,
      })),
      activeTabId: activeTabId.value,
    })
  }

  function findById(id: string): Tab | undefined {
    return tabs.value.find(t => t.id === id)
  }

  function findByRoutePath(routePath: string): Tab | undefined {
    const normalized = normalizePath(routePath)
    return tabs.value.find(t => t.routePath === normalized)
  }

  function getAdjacentTabId(closedId: string): string | null {
    const idx = tabs.value.findIndex(t => t.id === closedId)
    if (idx === -1) return null
    if (idx < tabs.value.length - 1) return tabs.value[idx + 1].id
    if (idx > 0) return tabs.value[idx - 1].id
    return null
  }

  /**
   * Create or retrieve a tab for the given route. Called by page components
   * during setup to register themselves. Returns the stable UUID.
   */
  function ensureTab(type: Tab['type'], rawPath: string): string {
    const normalized = normalizePath(rawPath)
    const basePath = normalized.split('?')[0]
    if (!basePath.startsWith('/edit') && !basePath.startsWith('/article')) {
      // Not a tab-tracked route — still return an id so callers don't crash
      return ''
    }

    const existing = findByRoutePath(normalized)
    if (existing) {
      activeTabId.value = existing.id
      persist()
      return existing.id
    }

    const id = generateId()
    const defaults = TAB_DEFAULTS[type]
    tabs.value.push({
      id,
      routePath: normalized,
      type,
      title: defaults.title,
      dirty: false,
      icon: defaults.icon,
      status: defaults.status,
    })
    activeTabId.value = id
    persist()
    return id
  }

  /**
   * Activate the tab matching the given route path. Used by router.afterEach
   * to sync active tab with URL navigation. No-op if no tab matches.
   */
  function activateTabByRoute(rawPath: string): void {
    const tab = findByRoutePath(rawPath)
    if (tab && activeTabId.value !== tab.id) {
      activeTabId.value = tab.id
      persist()
    }
  }

  function activateTab(tabId: string): void {
    const tab = findById(tabId)
    if (!tab) {
      if (import.meta.env.DEV) console.error(`activateTab: tab ${tabId} not found`)
      return
    }
    activeTabId.value = tabId
    persist()
    if (router) router.push(tab.routePath)
  }

  function updateTab(tabId: string, patch: Partial<Pick<Tab, 'title' | 'dirty' | 'status' | 'scrollTop' | 'cursorPosition'>>): void {
    const tab = findById(tabId)
    if (!tab) {
      if (import.meta.env.DEV) console.error(`updateTab: tab ${tabId} not found`)
      return
    }
    if (patch.title !== undefined) tab.title = patch.title
    if (patch.dirty !== undefined) tab.dirty = patch.dirty
    if (patch.status !== undefined) tab.status = patch.status
    if (patch.scrollTop !== undefined) tab.scrollTop = patch.scrollTop
    if (patch.cursorPosition !== undefined) tab.cursorPosition = patch.cursorPosition
    persist()
  }

  function closeTab(tabId: string): { shouldPrompt: boolean } {
    const tab = findById(tabId)
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
        const nextTab = findById(nextTabId)
        activeTabId.value = nextTabId
        if (router && nextTab) router.push(nextTab.routePath)
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

    // If saved tabs have old path-based IDs (no routePath field and id starts
    // with '/'), clear and start fresh — the user loses their tab session once.
    const isOldFormat = saved.tabs.some(t => !t.routePath && t.id.startsWith('/'))
    if (isOldFormat) {
      localStorage.removeItem(STORAGE_KEY)
      return
    }

    tabs.value = saved.tabs.map(t => ({ ...t, dirty: false }))
    activeTabId.value = saved.activeTabId
    if (saved.activeTabId && router) {
      const tab = findById(saved.activeTabId)
      if (tab) router.push(tab.routePath)
    }
  }

  return {
    tabs, activeTabId,
    ensureTab, activateTabByRoute, activateTab, updateTab, closeTab, removeTab, restoreTabs,
    findById, findByRoutePath,
  }
})
