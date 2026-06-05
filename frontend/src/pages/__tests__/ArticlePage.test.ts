import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ params: { id: 'test-article-1' } }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('../../api/articles', () => ({
  getArticle: vi.fn().mockResolvedValue({
    id: 'test-article-1',
    title: 'A Study on Quantum Error Correction',
    status: 'sedimentation',
    authors: [
      { id: 'u1', name: 'Alice Chen', anonymous_name: 'anon1' },
      { id: 'u2', name: 'Bob Lee', anonymous_name: 'anon2' },
    ],
    fork_count: 2,
    forked_from: null,
    commit_count: 3,
    compiled_format: 'html',
    compiled_output: '<p>Quantum error correction is essential...</p>',
    compiled_pages: 12,
    score: { originality: 4, rigor: 5, completeness: 4, pedagogy: 3, impact: 4 },
    sink_eta: '2026-07-01T00:00:00Z',
    days_remaining: 25,
    sink_duration_days: 30,
    review_count: 3,
    is_bookmarked: false,
    is_own_article: true,
    created_at: '2026-05-01T00:00:00Z',
    updated_at: '2026-06-05T00:00:00Z',
  }),
  getHistory: vi.fn().mockResolvedValue({ commits: [] }),
}))

describe('ArticlePage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders article title', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    expect(wrapper.text()).toContain('A Study on Quantum Error Correction')
  })

  it('renders authors', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    expect(wrapper.text()).toContain('Alice Chen')
    expect(wrapper.text()).toContain('Bob Lee')
  })

  it('renders status badge', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    expect(wrapper.text()).toMatch(/In Pool|sedimentation/)
  })

  it('has bookmark toggle', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    const bookmarkBtn = wrapper.find('button[aria-label*="bookmark" i]')
    expect(bookmarkBtn.exists()).toBe(true)
  })

  it('has tab switcher for Body and Comments', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    expect(wrapper.text()).toMatch(/body|comments|Body|Comments/i)
  })
})
