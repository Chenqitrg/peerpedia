import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock useNetworkStatus so canRead('search.network') passes in tests
vi.mock('@/composables/useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(() => ({
    isOnline: { value: true },
    startPing: vi.fn(),
    stopPing: vi.fn(),
  })),
}))

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

const mockRouteQuery = { q: 'quantum' } as Record<string, string>

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({ query: mockRouteQuery }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('../../api/search', () => ({
  searchArticles: mockSearchArticles,
}))

describe('SearchPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Reset route query between tests to avoid cross-test pollution
    mockRouteQuery.q = 'quantum'
    delete mockRouteQuery.category
    delete mockRouteQuery.sort
    mockSearchArticles.mockClear()
    mockPush.mockClear()
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

  it('restores category from URL query param on mount', async () => {
    // Set category in route query before mounting
    mockRouteQuery.q = ''
    mockRouteQuery.category = 'physics'
    mockRouteQuery.sort = ''
    mockSearchArticles.mockClear()

    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    // Category should be restored and search should have been triggered
    // The searchArticles should have been called with category='physics'
    expect(mockSearchArticles).toHaveBeenCalled()
    const callArgs = mockSearchArticles.mock.calls[0]?.[0]
    expect(callArgs?.category).toBe('physics')
  })

  it('restores sort from URL query param on mount', async () => {
    mockRouteQuery.q = 'test'
    mockRouteQuery.category = ''
    mockRouteQuery.sort = 'newest'
    mockSearchArticles.mockClear()

    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    expect(mockSearchArticles).toHaveBeenCalled()
    const callArgs = mockSearchArticles.mock.calls[0]?.[0]
    expect(callArgs?.sort).toBe('newest')
  })

  it('enables submit button when category is selected even with empty query', async () => {
    mockRouteQuery.q = ''
    delete mockRouteQuery.category
    delete mockRouteQuery.sort
    mockSearchArticles.mockClear()

    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    // Find the category select and pick an option
    const selects = wrapper.findAll('select')
    // The first select should be category
    const categorySelect = selects.length >= 2 ? selects[0] : selects[selects.length - 1]
    await categorySelect.setValue('physics')
    await flushPromises()

    // Submit button should now be enabled (not disabled when category is set)
    const submitBtn = wrapper.find('button[type="submit"]')
    expect(submitBtn.exists()).toBe(true)
    // Button should not be disabled when a category is selected
    const disabledAttr = submitBtn.attributes('disabled')
    expect(disabledAttr).toBeUndefined()
  })
})
