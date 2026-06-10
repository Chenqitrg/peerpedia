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

  describe('ensureTab', () => {
    it('creates an editor tab for /edit route and returns a UUID', () => {
      const s = useTabStore()
      const id = s.ensureTab('editor', '/edit')
      expect(id).toMatch(/^[0-9a-f-]{16,}$/)
      expect(s.tabs[0]).toMatchObject({ id, routePath: '/edit', type: 'editor', title: 'Untitled', dirty: false, status: 'draft' })
    })

    it('creates an article tab for /article route and returns a UUID', () => {
      const s = useTabStore()
      const id = s.ensureTab('article', '/article/abc')
      expect(id).toMatch(/^[0-9a-f-]{16,}$/)
      expect(s.tabs[0]).toMatchObject({ id, routePath: '/article/abc', type: 'article', icon: 'eye', status: 'published' })
    })

    it('normalizes /articles/ to /article/ in routePath', () => {
      const s = useTabStore()
      s.ensureTab('article', '/articles/abc')
      expect(s.tabs[0].routePath).toBe('/article/abc')
    })

    it('activates existing tab instead of duplicating', () => {
      const s = useTabStore()
      const id1 = s.ensureTab('editor', '/edit/abc')
      const id2 = s.ensureTab('editor', '/edit/abc')
      expect(id2).toBe(id1)
      expect(s.tabs).toHaveLength(1)
    })

    it('returns empty string for non-tab routes', () => {
      const s = useTabStore()
      const id = s.ensureTab('editor', '/pool')
      expect(id).toBe('')
      expect(s.tabs).toHaveLength(0)
    })

    it('generates unique UUIDs for different routes', () => {
      const s = useTabStore()
      const id1 = s.ensureTab('editor', '/edit/a')
      const id2 = s.ensureTab('editor', '/edit/b')
      expect(id1).not.toBe(id2)
      expect(s.tabs).toHaveLength(2)
    })
  })

  describe('findById', () => {
    it('finds tab by UUID', () => {
      const s = useTabStore()
      const id = s.ensureTab('editor', '/edit/x')
      expect(s.findById(id)).toBeTruthy()
      expect(s.findById('nonexistent')).toBeUndefined()
    })
  })

  describe('findByRoutePath', () => {
    it('finds tab by route path', () => {
      const s = useTabStore()
      s.ensureTab('editor', '/edit/x')
      expect(s.findByRoutePath('/edit/x')).toBeTruthy()
      expect(s.findByRoutePath('/article/y')).toBeUndefined()
    })

    it('normalizes /articles/ when looking up', () => {
      const s = useTabStore()
      s.ensureTab('article', '/articles/abc')
      expect(s.findByRoutePath('/article/abc')).toBeTruthy()
      expect(s.findByRoutePath('/articles/abc')).toBeTruthy()
    })
  })

  describe('updateTab', () => {
    it('updates title, dirty, status, scrollTop, cursorPosition by UUID', () => {
      const s = useTabStore()
      const id = s.ensureTab('editor', '/edit/abc')
      s.updateTab(id, { title: 'Draft', dirty: true, status: 'sedimentation', scrollTop: 200, cursorPosition: 50 })
      expect(s.tabs[0].title).toBe('Draft')
      expect(s.tabs[0].dirty).toBe(true)
      expect(s.tabs[0].status).toBe('sedimentation')
      expect(s.tabs[0].scrollTop).toBe(200)
    })

    it('is no-op for unknown UUID', () => {
      expect(() => useTabStore().updateTab('nonexistent', { title: 'X' })).not.toThrow()
    })
  })

  describe('closeTab', () => {
    it('removes clean tab by UUID', () => {
      const s = useTabStore()
      const id = s.ensureTab('article', '/article/1')
      expect(s.closeTab(id)).toEqual({ shouldPrompt: false })
      expect(s.tabs).toHaveLength(0)
    })

    it('returns shouldPrompt for dirty tab', () => {
      const s = useTabStore()
      const id = s.ensureTab('editor', '/edit/a')
      s.updateTab(id, { dirty: true })
      expect(s.closeTab(id)).toEqual({ shouldPrompt: true })
      expect(s.tabs).toHaveLength(1)
    })
  })

  describe('removeTab', () => {
    it('navigates to right neighbor when closing active tab', () => {
      const s = useTabStore()
      const a = s.ensureTab('editor', '/edit/a')
      const b = s.ensureTab('editor', '/edit/b')
      const c = s.ensureTab('editor', '/edit/c')
      s.activateTab(b); mockPush.mockClear()
      s.removeTab(b)
      expect(s.tabs.map(t => t.routePath)).toEqual(['/edit/a', '/edit/c'])
      expect(mockPush).toHaveBeenCalledWith('/edit/c')
    })

    it('closing non-active tab does not navigate', () => {
      const s = useTabStore()
      const a = s.ensureTab('editor', '/edit/a')
      const b = s.ensureTab('editor', '/edit/b')
      s.activateTab(a); mockPush.mockClear()
      s.removeTab(b)
      expect(s.tabs.map(t => t.routePath)).toEqual(['/edit/a'])
      expect(mockPush).not.toHaveBeenCalled()
    })

    it('navigates to left neighbor when no right neighbor exists', () => {
      const s = useTabStore()
      const a = s.ensureTab('editor', '/edit/a')
      const b = s.ensureTab('editor', '/edit/b')
      s.activateTab(b); mockPush.mockClear()
      s.removeTab(b)
      expect(mockPush).toHaveBeenCalledWith('/edit/a')
    })

    it('navigates to home when closing last tab', () => {
      const s = useTabStore()
      const id = s.ensureTab('editor', '/edit/x')
      s.removeTab(id)
      expect(s.activeTabId).toBeNull()
      expect(mockPush).toHaveBeenCalledWith('/')
    })
  })

  describe('activateTab', () => {
    it('navigates to tab routePath via router', () => {
      const s = useTabStore()
      const id = s.ensureTab('editor', '/edit/xyz')
      mockPush.mockClear()
      s.activateTab(id)
      expect(mockPush).toHaveBeenCalledWith('/edit/xyz')
    })
  })

  describe('activateTabByRoute', () => {
    it('activates the tab matching the given route', () => {
      const s = useTabStore()
      const id = s.ensureTab('article', '/article/foo')
      s.activateTabByRoute('/article/foo')
      expect(s.activeTabId).toBe(id)
    })
  })

  describe('restoreTabs', () => {
    it('restores from localStorage with UUID-based tabs and navigates to last active', () => {
      localStorage.setItem('peerpedia_tabs', JSON.stringify({
        tabs: [{ id: 'test-uuid-123', routePath: '/edit/a', type: 'editor', title: 'A', icon: 'edit', status: 'draft' }],
        activeTabId: 'test-uuid-123',
      }))
      const s = useTabStore(); s.restoreTabs()
      expect(s.tabs[0].dirty).toBe(false)
      expect(s.tabs[0].id).toBe('test-uuid-123')
      expect(mockPush).toHaveBeenCalledWith('/edit/a')
    })

    it('clears old path-based format data', () => {
      localStorage.setItem('peerpedia_tabs', JSON.stringify({
        tabs: [{ id: '/edit/a', type: 'editor', title: 'A', icon: 'edit', status: 'draft' }],
        activeTabId: '/edit/a',
      }))
      const s = useTabStore(); s.restoreTabs()
      expect(s.tabs).toHaveLength(0)
    })

    it('is no-op when localStorage is empty', () => {
      const s = useTabStore(); s.restoreTabs()
      expect(s.tabs).toHaveLength(0)
    })
  })
})
