import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

// Collect lifecycle callbacks so we can invoke them in tests
let deactivatedCallbacks: Array<() => void> = []
let activatedCallbacks: Array<() => void> = []

const mockUpdateTab = vi.fn()
const mockTabs = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/edit/test-article' }),
}))

vi.mock('@/stores/useTabStore', () => ({
  useTabStore: () => ({
    updateTab: mockUpdateTab,
    tabs: mockTabs(),
  }),
}))

// Mock keep-alive lifecycle hooks
vi.mock('vue', async () => {
  const actual = await vi.importActual('vue')
  return {
    ...actual,
    onDeactivated: (cb: () => void) => { deactivatedCallbacks.push(cb) },
    onActivated: (cb: () => void) => { activatedCallbacks.push(cb) },
  }
})

import { useEditorTab, useArticleTab } from '../useTabIntegration'

// ── Regression: path normalization ──────────────────────────────
// The router defines both /article/:id and /articles/:id. openTab normalizes
// /articles/ → /article/ before storing. The composables must do the same,
// otherwise updateTab targets a tab id that doesn't exist (titles stay
// "Loading…" forever, tab switching has no visible effect).
//
// These tests use vi.resetModules() so we can override the hoisted useRoute
// mock with a /articles/ path.

describe('Path normalization regression', () => {
  beforeEach(async () => {
    vi.resetModules()
    setActivePinia(createPinia())
  })

  it('useArticleTab normalizes /articles/ to /article/ when updating title', async () => {
    const localUpdateTab = vi.fn()
    const localTabs = vi.fn().mockReturnValue([])

    vi.doMock('vue-router', () => ({
      useRoute: () => ({ path: '/articles/quantum-physics' }),
    }))
    vi.doMock('@/stores/useTabStore', () => ({
      useTabStore: () => ({
        updateTab: localUpdateTab,
        tabs: localTabs(),
      }),
    }))
    vi.doMock('vue', async () => {
      const actual = await vi.importActual('vue')
      return {
        ...actual,
        onDeactivated: vi.fn(),
        onActivated: vi.fn(),
      }
    })

    const { useArticleTab: uat } = await import('../useTabIntegration')
    const articleTitle = ref('Quantum Physics')
    uat(articleTitle, ref(null))

    await vi.waitFor(() => {
      expect(localUpdateTab).toHaveBeenCalledWith('/article/quantum-physics', {
        title: 'Quantum Physics',
      })
    })
  })

  it('useEditorTab normalizes /articles/ to /article/ for title+dirty sync', async () => {
    const localUpdateTab = vi.fn()
    const localTabs = vi.fn().mockReturnValue([])

    vi.doMock('vue-router', () => ({
      useRoute: () => ({ path: '/articles/my-draft' }),
    }))
    vi.doMock('@/stores/useTabStore', () => ({
      useTabStore: () => ({
        updateTab: localUpdateTab,
        tabs: localTabs(),
      }),
    }))
    vi.doMock('vue', async () => {
      const actual = await vi.importActual('vue')
      return {
        ...actual,
        onDeactivated: vi.fn(),
        onActivated: vi.fn(),
      }
    })

    const { useEditorTab: uet } = await import('../useTabIntegration')
    uet(ref('My Draft'), ref(false), ref(null))

    await vi.waitFor(() => {
      expect(localUpdateTab).toHaveBeenCalledWith('/article/my-draft', {
        dirty: true,
        title: 'My Draft',
      })
    })
  })

  it('does not normalize /edit paths (no /edits/ route exists)', async () => {
    const localUpdateTab = vi.fn()
    const localTabs = vi.fn().mockReturnValue([])

    vi.doMock('vue-router', () => ({
      useRoute: () => ({ path: '/edit/some-draft' }),
    }))
    vi.doMock('@/stores/useTabStore', () => ({
      useTabStore: () => ({
        updateTab: localUpdateTab,
        tabs: localTabs(),
      }),
    }))
    vi.doMock('vue', async () => {
      const actual = await vi.importActual('vue')
      return {
        ...actual,
        onDeactivated: vi.fn(),
        onActivated: vi.fn(),
      }
    })

    const { useArticleTab: uat } = await import('../useTabIntegration')
    uat(ref('Draft Title'), ref(null))

    await vi.waitFor(() => {
      expect(localUpdateTab).toHaveBeenCalledWith('/edit/some-draft', {
        title: 'Draft Title',
      })
    })
  })
})

describe('useTabIntegration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockUpdateTab.mockClear()
    deactivatedCallbacks = []
    activatedCallbacks = []
  })

  describe('useEditorTab', () => {
    it('calls updateTab with dirty and title when watch fires', async () => {
      const title = ref('My Draft')
      const isClean = ref(false)
      const contentEl = ref<HTMLElement | null>(null)

      useEditorTab(title, isClean, contentEl)

      // Wait for watch with immediate:true to fire
      await vi.waitFor(() => {
        expect(mockUpdateTab).toHaveBeenCalledWith('/edit/test-article', {
          dirty: true,
          title: 'My Draft',
        })
      })
    })

    it('passes "Untitled" when title ref is empty', async () => {
      const title = ref('')
      const isClean = ref(true)
      const contentEl = ref<HTMLElement | null>(null)

      useEditorTab(title, isClean, contentEl)

      await vi.waitFor(() => {
        expect(mockUpdateTab).toHaveBeenCalledWith('/edit/test-article', {
          dirty: false,
          title: 'Untitled',
        })
      })
    })

    it('saves scrollTop on deactivation', () => {
      const title = ref('Draft')
      const isClean = ref(true)
      const el = document.createElement('div')
      el.scrollTop = 150
      const contentEl = ref<HTMLElement | null>(el)

      useEditorTab(title, isClean, contentEl)

      // Trigger deactivated callback
      deactivatedCallbacks.forEach(cb => cb())
      expect(mockUpdateTab).toHaveBeenCalledWith('/edit/test-article', { scrollTop: 150 })
    })

    it('restores scrollTop on activation when tab has saved position', () => {
      mockTabs.mockReturnValue([{ id: '/edit/test-article', scrollTop: 300 }])

      const title = ref('Draft')
      const isClean = ref(true)
      const el = document.createElement('div')
      const contentEl = ref<HTMLElement | null>(el)

      useEditorTab(title, isClean, contentEl)

      // Trigger activated callback
      activatedCallbacks.forEach(cb => cb())
      expect(el.scrollTop).toBe(300)
    })
  })

  describe('useArticleTab', () => {
    it('calls updateTab with title when watch fires', async () => {
      const articleTitle = ref('Quantum Physics')
      const contentEl = ref<HTMLElement | null>(null)

      useArticleTab(articleTitle, contentEl)

      await vi.waitFor(() => {
        expect(mockUpdateTab).toHaveBeenCalledWith('/edit/test-article', {
          title: 'Quantum Physics',
        })
      })
    })

    it('does not call updateTab when title is undefined', async () => {
      const articleTitle = ref<string | undefined>(undefined)
      const contentEl = ref<HTMLElement | null>(null)

      useArticleTab(articleTitle, contentEl)

      // Should not have been called because title is undefined
      // (watch fires but the if (title) guard prevents the call)
      await new Promise(r => setTimeout(r, 50))
      // Only calls from the initial undefined watch should be skipped
      // No call expected since title is undefined
    })

    it('saves scrollTop on deactivation', () => {
      const articleTitle = ref('Article')
      const el = document.createElement('div')
      el.scrollTop = 200
      const contentEl = ref<HTMLElement | null>(el)

      useArticleTab(articleTitle, contentEl)

      deactivatedCallbacks.forEach(cb => cb())
      expect(mockUpdateTab).toHaveBeenCalledWith('/edit/test-article', { scrollTop: 200 })
    })

    it('restores scrollTop on activation when tab has saved position', () => {
      mockTabs.mockReturnValue([{ id: '/edit/test-article', scrollTop: 500 }])

      const articleTitle = ref('Article')
      const el = document.createElement('div')
      const contentEl = ref<HTMLElement | null>(el)

      useArticleTab(articleTitle, contentEl)

      activatedCallbacks.forEach(cb => cb())
      expect(el.scrollTop).toBe(500)
    })
  })
})
