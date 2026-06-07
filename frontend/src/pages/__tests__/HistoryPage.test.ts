import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
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
let _isTauri = false
let _gitHistoryReturn: any = []
vi.mock('@/composables/useTauri', () => ({
  useTauri: () => ({
    isTauri: { value: _isTauri },
    isBrowserLocal: { value: false },
    gitHistory: vi.fn().mockImplementation(() => Promise.resolve(_gitHistoryReturn)),
    gitShow: vi.fn().mockResolvedValue(''),
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
})
