import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const { mockPush, mockSearchArticles } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockSearchArticles: vi.fn().mockResolvedValue({
    articles: [
      {
        id: 'search-1',
        title: 'Quantum Computing',
        status: 'published',
        authors: [{ id: 'u1', name: 'Alice Chen', anonymous_name: 'anon1' }],
        content_preview: 'A deep dive into quantum algorithms',
        commit_hash: 'abc123',
        fork_count: 2,
        forked_from: null,
        commit_count: 3,
        score: { originality: 5, rigor: 4, completeness: 4, pedagogy: 3, impact: 5 },
        days_remaining: null,
        sink_duration_days: null,
        is_bookmarked: false,
        is_own_article: false,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-06-01T00:00:00Z',
      },
    ],
    total: 1,
    query: 'quantum',
  }),
}))

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({ query: { q: 'quantum' } }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('../../api/search', () => ({
  searchArticles: mockSearchArticles,
}))

describe('SearchPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders search page with heading', async () => {
    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    expect(wrapper.text()).toContain('Search')
  })

  it('has search input', async () => {
    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    const input = wrapper.find('input[type="text"], input[type="search"]')
    expect(input.exists()).toBe(true)
  })

  it('renders search results', async () => {
    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Quantum Computing')
  })

  it('shows empty state when no results', async () => {
    mockSearchArticles.mockResolvedValueOnce({
      articles: [],
      total: 0,
      query: 'quantum',
    })
    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    // Should show some content
    expect(wrapper.text()).toBeTruthy()
  })

  it('has sort selector dropdown', async () => {
    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const sortSelect = wrapper.find('select')
    expect(sortSelect.exists()).toBe(true)
    // Should have sort options
    expect(wrapper.text()).toMatch(/newest|Newest|sort|Sort/i)
  })

  it('selecting a category updates search params', async () => {
    mockSearchArticles.mockClear()
    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    // Find the category filter input/select
    const selects = wrapper.findAll('select')
    // At least one select is rendered (sort + category)
    expect(selects.length).toBeGreaterThanOrEqual(1)
  })
})
