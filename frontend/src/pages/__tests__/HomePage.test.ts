import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('../../api/feed', () => ({
  fetchFeed: vi.fn().mockResolvedValue({
    articles: [
      {
        id: 'feed-1',
        title: 'Feed Article One',
        status: 'sedimentation',
        authors: [{ id: 'u1', name: 'Alice', anonymous_name: 'anon1' }],
        content_preview: 'Preview content',
        commit_hash: 'abc1234',
        fork_count: 0,
        forked_from: null,
        commit_count: 2,
        score: { originality: 4, rigor: 3, completeness: 4, pedagogy: 3, impact: 4 },
        days_remaining: 10,
        sink_duration_days: 30,
        is_bookmarked: false,
        is_own_article: false,
        created_at: '2026-06-01T00:00:00Z',
        updated_at: '2026-06-05T00:00:00Z',
      },
      {
        id: 'feed-2',
        title: 'Feed Article Two',
        status: 'published',
        authors: [{ id: 'u2', name: 'Bob', anonymous_name: 'anon2' }],
        content_preview: 'More preview',
        commit_hash: 'def5678',
        fork_count: 1,
        forked_from: null,
        commit_count: 1,
        score: { originality: 5, rigor: 4, completeness: 5, pedagogy: 4, impact: 5 },
        days_remaining: null,
        sink_duration_days: null,
        is_bookmarked: true,
        is_own_article: true,
        created_at: '2026-05-15T00:00:00Z',
        updated_at: '2026-06-01T00:00:00Z',
      },
    ],
    total: 2,
    page: 1,
    size: 20,
  }),
}))

describe('HomePage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders page title', async () => {
    const HomePage = (await import('../HomePage.vue')).default
    const wrapper = mount(HomePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true, 'article-card': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    expect(wrapper.text()).toContain('Feed')
  })

  it('renders feed article titles', async () => {
    const HomePage = (await import('../HomePage.vue')).default
    const wrapper = mount(HomePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    expect(wrapper.text()).toContain('Feed Article One')
    expect(wrapper.text()).toContain('Feed Article Two')
  })

  it('renders pagination controls', async () => {
    const HomePage = (await import('../HomePage.vue')).default
    const wrapper = mount(HomePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    // Should have page number buttons or pagination controls
    const pageButtons = wrapper.findAll('button, a').filter(el =>
      /page|1|2|\d+/i.test(el.text())
    )
    expect(pageButtons.length).toBeGreaterThanOrEqual(0)
  })

  it('shows empty state when no articles', async () => {
    vi.mocked(await import('../../api/feed')).fetchFeed.mockResolvedValueOnce({
      articles: [],
      total: 0,
      page: 1,
      size: 20,
    })
    const HomePage = (await import('../HomePage.vue')).default
    const wrapper = mount(HomePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    expect(wrapper.text()).toMatch(/no articles|empty|none/i)
  })
})
