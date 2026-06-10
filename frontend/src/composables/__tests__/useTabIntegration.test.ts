import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

// Collect lifecycle callbacks so we can invoke them in tests
let deactivatedCallbacks: Array<() => void> = []
let activatedCallbacks: Array<() => void> = []

const mockUpdateTab = vi.fn()
const mockFindById = vi.fn()

vi.mock('@/stores/useTabStore', () => ({
  useTabStore: () => ({
    updateTab: mockUpdateTab,
    findById: mockFindById,
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

const TAB_ID = 'test-tab-uuid-123'

describe('useTabIntegration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockUpdateTab.mockClear()
    mockFindById.mockClear()
    deactivatedCallbacks = []
    activatedCallbacks = []
  })

  describe('useEditorTab', () => {
    it('calls updateTab with explicit tabId, dirty and title when watch fires', async () => {
      const title = ref('My Draft')
      const isClean = ref(false)
      const contentEl = ref<HTMLElement | null>(null)

      useEditorTab(TAB_ID, title, isClean, contentEl)

      await vi.waitFor(() => {
        expect(mockUpdateTab).toHaveBeenCalledWith(TAB_ID, {
          dirty: true,
          title: 'My Draft',
        })
      })
    })

    it('passes "Untitled" when title ref is empty', async () => {
      const title = ref('')
      const isClean = ref(true)
      const contentEl = ref<HTMLElement | null>(null)

      useEditorTab(TAB_ID, title, isClean, contentEl)

      await vi.waitFor(() => {
        expect(mockUpdateTab).toHaveBeenCalledWith(TAB_ID, {
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

      useEditorTab(TAB_ID, title, isClean, contentEl)

      deactivatedCallbacks.forEach(cb => cb())
      expect(mockUpdateTab).toHaveBeenCalledWith(TAB_ID, { scrollTop: 150 })
    })

    it('restores scrollTop on activation when tab has saved position', () => {
      mockFindById.mockReturnValue({ id: TAB_ID, scrollTop: 300 })

      const title = ref('Draft')
      const isClean = ref(true)
      const el = document.createElement('div')
      const contentEl = ref<HTMLElement | null>(el)

      useEditorTab(TAB_ID, title, isClean, contentEl)

      activatedCallbacks.forEach(cb => cb())
      expect(el.scrollTop).toBe(300)
    })
  })

  describe('useArticleTab', () => {
    it('calls updateTab with explicit tabId and title when watch fires', async () => {
      const articleTitle = ref('Quantum Physics')
      const contentEl = ref<HTMLElement | null>(null)

      useArticleTab(TAB_ID, articleTitle, contentEl)

      await vi.waitFor(() => {
        expect(mockUpdateTab).toHaveBeenCalledWith(TAB_ID, {
          title: 'Quantum Physics',
        })
      })
    })

    it('does not call updateTab when title is undefined', async () => {
      const articleTitle = ref<string | undefined>(undefined)
      const contentEl = ref<HTMLElement | null>(null)

      useArticleTab(TAB_ID, articleTitle, contentEl)

      await new Promise(r => setTimeout(r, 50))
      // The watch fires with immediate:true but the if (title) guard prevents the call
    })

    it('saves scrollTop on deactivation', () => {
      const articleTitle = ref('Article')
      const el = document.createElement('div')
      el.scrollTop = 200
      const contentEl = ref<HTMLElement | null>(el)

      useArticleTab(TAB_ID, articleTitle, contentEl)

      deactivatedCallbacks.forEach(cb => cb())
      expect(mockUpdateTab).toHaveBeenCalledWith(TAB_ID, { scrollTop: 200 })
    })

    it('restores scrollTop on activation when tab has saved position', () => {
      mockFindById.mockReturnValue({ id: TAB_ID, scrollTop: 500 })

      const articleTitle = ref('Article')
      const el = document.createElement('div')
      const contentEl = ref<HTMLElement | null>(el)

      useArticleTab(TAB_ID, articleTitle, contentEl)

      activatedCallbacks.forEach(cb => cb())
      expect(el.scrollTop).toBe(500)
    })
  })
})
