import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTabStore } from '../useTabStore'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mockPush }) }))

describe('useTabStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    mockPush.mockClear()
  })

  describe('openTab', () => {
    it('adds editor tab for /edit route', () => {
      const s = useTabStore(); s.openTab({ path: '/edit', params: {} })
      expect(s.tabs[0]).toMatchObject({ type: 'editor', title: 'Untitled', dirty: false, status: 'draft' })
    })

    it('adds article tab for /article route', () => {
      const s = useTabStore(); s.openTab({ path: '/article/abc', params: { id: 'abc' } })
      expect(s.tabs[0]).toMatchObject({ type: 'article', icon: 'eye', status: 'published' })
    })

    it('normalizes /articles/ to /article/', () => {
      const s = useTabStore(); s.openTab({ path: '/articles/abc', params: { id: 'abc' } })
      expect(s.tabs[0].id).toBe('/article/abc')
    })

    it('activates existing tab instead of duplicating', () => {
      const s = useTabStore()
      s.openTab({ path: '/edit/abc', params: { id: 'abc' } })
      s.openTab({ path: '/edit/abc', params: { id: 'abc' } })
      expect(s.tabs).toHaveLength(1)
    })

    it('ignores non-tab routes', () => {
      const s = useTabStore(); s.openTab({ path: '/pool', params: {} })
      expect(s.tabs).toHaveLength(0)
    })
  })

  describe('updateTab', () => {
    it('updates title, dirty, status, scrollTop, cursorPosition', () => {
      const s = useTabStore(); s.openTab({ path: '/edit/abc', params: { id: 'abc' } })
      s.updateTab('/edit/abc', { title: 'Draft', dirty: true, status: 'sedimentation', scrollTop: 200, cursorPosition: 50 })
      expect(s.tabs[0].title).toBe('Draft')
      expect(s.tabs[0].dirty).toBe(true)
      expect(s.tabs[0].status).toBe('sedimentation')
      expect(s.tabs[0].scrollTop).toBe(200)
    })

    it('is no-op for unknown tab', () => {
      expect(() => useTabStore().updateTab('/none', { title: 'X' })).not.toThrow()
    })
  })

  describe('closeTab', () => {
    it('removes clean tab', () => {
      const s = useTabStore(); s.openTab({ path: '/article/1', params: { id: '1' } })
      expect(s.closeTab('/article/1')).toEqual({ shouldPrompt: false })
      expect(s.tabs).toHaveLength(0)
    })

    it('returns shouldPrompt for dirty tab', () => {
      const s = useTabStore(); s.openTab({ path: '/edit/a', params: { id: 'a' } })
      s.updateTab('/edit/a', { dirty: true })
      expect(s.closeTab('/edit/a')).toEqual({ shouldPrompt: true })
      expect(s.tabs).toHaveLength(1)
    })
  })

  describe('removeTab', () => {
    it('navigates to right neighbor when closing active tab', () => {
      const s = useTabStore()
      s.openTab({ path: '/edit/a', params: { id: 'a' } })
      s.openTab({ path: '/edit/b', params: { id: 'b' } })
      s.openTab({ path: '/edit/c', params: { id: 'c' } })
      s.activateTab('/edit/b'); mockPush.mockClear()
      s.removeTab('/edit/b')
      expect(s.tabs.map(t => t.id)).toEqual(['/edit/a', '/edit/c'])
      expect(mockPush).toHaveBeenCalledWith('/edit/c')
    })

    it('closing non-active tab does not navigate', () => {
      const s = useTabStore()
      s.openTab({ path: '/edit/a', params: { id: 'a' } })
      s.openTab({ path: '/edit/b', params: { id: 'b' } })
      s.activateTab('/edit/a'); mockPush.mockClear()
      s.removeTab('/edit/b')
      expect(s.tabs.map(t => t.id)).toEqual(['/edit/a'])
      expect(mockPush).not.toHaveBeenCalled()
    })

    it('navigates to left neighbor when no right neighbor exists', () => {
      const s = useTabStore()
      s.openTab({ path: '/edit/a', params: { id: 'a' } })
      s.openTab({ path: '/edit/b', params: { id: 'b' } })
      s.activateTab('/edit/b'); mockPush.mockClear()
      s.removeTab('/edit/b')
      expect(mockPush).toHaveBeenCalledWith('/edit/a')
    })

    it('navigates to home when closing last tab', () => {
      const s = useTabStore(); s.openTab({ path: '/edit/x', params: { id: 'x' } })
      s.removeTab('/edit/x')
      expect(s.activeTabId).toBeNull()
      expect(mockPush).toHaveBeenCalledWith('/')
    })
  })

  describe('restoreTabs', () => {
    it('restores from localStorage and navigates to last active', () => {
      localStorage.setItem('peerpedia_tabs', JSON.stringify({
        tabs: [{ id: '/edit/a', type: 'editor', title: 'A', icon: 'edit', status: 'draft' }],
        activeTabId: '/edit/a',
      }))
      const s = useTabStore(); s.restoreTabs()
      expect(s.tabs[0].dirty).toBe(false)
      expect(mockPush).toHaveBeenCalledWith('/edit/a')
    })

    it('is no-op when localStorage is empty', () => {
      const s = useTabStore(); s.restoreTabs()
      expect(s.tabs).toHaveLength(0)
    })
  })
})
