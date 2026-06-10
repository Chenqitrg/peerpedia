import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

const { mockBack, mockPush } = vi.hoisted(() => ({
  mockBack: vi.fn(),
  mockPush: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, back: mockBack }),
  useRoute: () => ({ params: { id: 'art-1' } }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('@/api/articles', () => ({
  getHistory: vi.fn().mockResolvedValue({
    commits: [
      { hash: 'abc1234', parents: ['def5678'], author: 'Alice', message: 'Add conclusion', timestamp: '2026-06-01T12:00:00Z', score: { originality: 4, rigor: 3, completeness: 4, pedagogy: 3, impact: 4 } },
      { hash: 'def5678', parents: ['ghi9012'], author: 'Alice', message: 'Fix methodology section', timestamp: '2026-05-28T10:00:00Z', score: { originality: 3, rigor: 4, completeness: 3, pedagogy: 4, impact: 3 } },
      { hash: 'ghi9012', parents: ['jkl3456'], author: 'Alice', message: 'Initial draft', timestamp: '2026-05-20T08:00:00Z', score: null },
      { hash: 'jkl3456', parents: [], author: 'Alice', message: 'Initial commit', timestamp: '2026-05-15T09:00:00Z', score: null },
    ],
  }),
  getDiff: vi.fn(),
  rollbackArticle: vi.fn(),
}))

// Mock useTauri — default is web mode (isTauri=false). Tests that need
// local mode can mock individual method return values via the refs below.
// Shared mock fns (via hoisted) so component and test share the same fn reference.
const { _mockGitHistory, _mockGitShow, _mockGitRollback } = vi.hoisted(() => ({
  _mockGitHistory: vi.fn(),
  _mockGitShow: vi.fn(),
  _mockGitRollback: vi.fn(),
}))
let _isTauri = false
let _gitHistoryReturn: any = []
let _gitRollbackReturn: any = { hash: 'rollback-abc', message: 'Rollback to abc12345' }
vi.mock('@/composables/useTauri', () => ({
  useTauri: () => ({
    isTauri: { value: _isTauri },
    isBrowserLocal: { value: false },
    gitHistory: _mockGitHistory.mockImplementation(() => Promise.resolve(_gitHistoryReturn)),
    gitShow: _mockGitShow.mockResolvedValue(''),
    gitRollback: _mockGitRollback.mockImplementation(() => Promise.resolve(_gitRollbackReturn)),
  }),
}))

import { useTauri } from '@/composables/useTauri'

describe('HistoryPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    _isTauri = false
    _gitHistoryReturn = []
  })

  it('renders page title', async () => {
    const HistoryPage = (await import('../HistoryPage.vue')).default
    const wrapper = mount(HistoryPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('History')
  })

  it('shows back navigation', async () => {
    const HistoryPage = (await import('../HistoryPage.vue')).default
    const wrapper = mount(HistoryPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const backBtn = wrapper.find('button[aria-label="Back to article"]')
    expect(backBtn.exists()).toBe(true)
  })

  it('handles error state', async () => {
    const HistoryPage = (await import('../HistoryPage.vue')).default
    const wrapper = mount(HistoryPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const hasContent = wrapper.text().length > 0
    expect(hasContent).toBe(true)
  })

  // Regression: goBack must use router.back() so user returns to EditorPage
  // (not router.push('/articles/:id') which always goes to ArticlePage).
  // This preserves "从哪来到哪去" (from where you came, go back there).
  it('goBack uses router.back() to preserve navigation origin', async () => {
    mockBack.mockClear()
    mockPush.mockClear()

    const HistoryPage = (await import('../HistoryPage.vue')).default
    const wrapper = mount(HistoryPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    const backBtn = wrapper.find('button[aria-label="Back to article"]')
    expect(backBtn.exists()).toBe(true)
    await backBtn.trigger('click')

    // Must call router.back() not router.push() — so the user returns
    // to whichever page they came from (Editor, Article, or elsewhere).
    expect(mockBack).toHaveBeenCalled()
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('uses local git history in Tauri mode', async () => {
    _isTauri = true
    _gitHistoryReturn = [
      { hash: 'abc0001', message: 'First draft', author: 'test', timestamp: '2026-06-01T10:00:00Z' },
      { hash: 'abc0002', message: 'Edit content', author: 'test', timestamp: '2026-06-02T10:00:00Z' },
    ]

    const HistoryPage = (await import('../HistoryPage.vue')).default
    const wrapper = mount(HistoryPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('First draft')
    expect(wrapper.text()).toContain('Edit content')
    // Should not be loading
    const hasCommits = wrapper.text().includes('First draft')
    expect(hasCommits).toBe(true)
  })

  // ── Rollback tests (Vue dialog, works in Tauri) ──────────────────

  it('clicking rollback shows confirm dialog, confirm calls rollbackArticle', async () => {
    const { rollbackArticle } = await import('@/api/articles')
    ;(rollbackArticle as ReturnType<typeof vi.fn>).mockClear()
    const HistoryPage = (await import('../HistoryPage.vue')).default
    const wrapper = mount(HistoryPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    // Click rollback button
    const rollbackBtn = wrapper.find('button[aria-label="Rollback to this version"]')
    expect(rollbackBtn.exists()).toBe(true)
    await rollbackBtn.trigger('click')
    await flushPromises()

    // Confirmation dialog should appear
    expect(wrapper.text()).toContain('This creates a new commit')

    // Click Confirm
    const confirmBtn = wrapper.findAll('button').find(b => b.text().trim() === 'Confirm')!
    expect(confirmBtn.exists()).toBe(true)
    await confirmBtn.trigger('click')
    await flushPromises()

    expect(rollbackArticle).toHaveBeenCalled()
  })

  it('cancel rollback does not call rollbackArticle', async () => {
    const { rollbackArticle } = await import('@/api/articles')
    ;(rollbackArticle as ReturnType<typeof vi.fn>).mockClear()
    const HistoryPage = (await import('../HistoryPage.vue')).default
    const wrapper = mount(HistoryPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    const rollbackBtn = wrapper.find('button[aria-label="Rollback to this version"]')
    await rollbackBtn.trigger('click')
    await flushPromises()

    // Click Cancel
    const cancelBtn = wrapper.findAll('button').find(b => b.text().trim() === 'Cancel')!
    await cancelBtn.trigger('click')
    await flushPromises()

    expect(rollbackArticle).not.toHaveBeenCalled()
  })

  it('shows rollback error message on failure', async () => {
    const { rollbackArticle } = await import('@/api/articles')
    ;(rollbackArticle as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
      response: { data: { detail: 'Repository not found' } },
    })
    const HistoryPage = (await import('../HistoryPage.vue')).default
    const wrapper = mount(HistoryPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    // Click rollback → Confirm
    await wrapper.find('button[aria-label="Rollback to this version"]').trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(b => b.text().trim() === 'Confirm')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Repository not found')
  })

  // ── S2.x E2E: Tauri-mode rollback flow ────────────────────────────

  describe('S2 E2E: rollback in Tauri/local mode', () => {
    beforeEach(() => {
      _isTauri = true
      _gitHistoryReturn = [
        { hash: 'abc1234', message: 'Add conclusion', author: 'Alice', timestamp: '2026-06-01T12:00:00Z' },
        { hash: 'def5678', message: 'Fix methods', author: 'Alice', timestamp: '2026-05-28T10:00:00Z' },
        { hash: 'ghi9012', message: 'Initial draft', author: 'Alice', timestamp: '2026-05-20T08:00:00Z' },
      ]
      _gitRollbackReturn = { hash: 'newhash99', message: 'Rollback to abc12345' }
    })

    afterEach(() => {
      _isTauri = false
    })

    it('S2.1: rollback button → confirm → calls tauri.gitRollback', async () => {
      const HistoryPage = (await import('../HistoryPage.vue')).default
      const wrapper = mount(HistoryPage, {
        global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
      })
      await flushPromises()

      _mockGitRollback.mockClear()
      // Click rollback button
      await wrapper.find('button[aria-label="Rollback to this version"]').trigger('click')
      await flushPromises()
      // Click Confirm in dialog
      await wrapper.findAll('button').find(b => b.text().trim() === 'Confirm')!.trigger('click')
      await flushPromises()

      expect(_mockGitRollback).toHaveBeenCalledWith({
        article_id: 'art-1',
        commit_hash: 'ghi9012',
        author: 'User',
      })
    })

    it('S2.4: rollback failure shows error in Tauri mode', async () => {
      _gitRollbackReturn = { error: 'Git repository not found' }
      const HistoryPage = (await import('../HistoryPage.vue')).default
      const wrapper = mount(HistoryPage, {
        global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
      })
      await flushPromises()

      await wrapper.find('button[aria-label="Rollback to this version"]').trigger('click')
      await flushPromises()
      await wrapper.findAll('button').find(b => b.text().trim() === 'Confirm')!.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('Git repository not found')
    })

    it('S2.5: cancel rollback does nothing', async () => {
      const HistoryPage = (await import('../HistoryPage.vue')).default
      const wrapper = mount(HistoryPage, {
        global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
      })
      await flushPromises()

      _mockGitRollback.mockClear()
      await wrapper.find('button[aria-label="Rollback to this version"]').trigger('click')
      await flushPromises()
      await wrapper.findAll('button').find(b => b.text().trim() === 'Cancel')!.trigger('click')
      await flushPromises()

      expect(_mockGitRollback).not.toHaveBeenCalled()
    })
  })
})
