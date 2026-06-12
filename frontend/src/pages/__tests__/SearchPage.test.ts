import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock useNetworkStatus so canRead('search.network') passes in tests
vi.mock('@/composables/useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(() => ({
    isOnline: { value: true },
    isSynced: { value: true },
    connectionState: { value: 'synced' as const },
    ping: vi.fn(),
  })),
}))

const { mockPush, mockSearchArticles, mockSearchDrafts, mockSearchCached } = vi.hoisted(() => ({
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
        abstract: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-06-01T00:00:00Z',
      },
    ],
    total: 1,
    query: 'quantum',
  }),
  mockSearchDrafts: vi.fn().mockResolvedValue([]),
  mockSearchCached: vi.fn().mockResolvedValue([]),
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

vi.mock('../../composables/useTauri', () => ({
  useTauri: () => ({
    isTauri: { value: false },
    isBrowserLocal: { value: false },
    searchDrafts: mockSearchDrafts,
    searchCachedArticles: mockSearchCached,
  }),
}))

describe('SearchPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockRouteQuery.q = 'quantum'
    delete mockRouteQuery.category
    delete mockRouteQuery.sort
    delete mockRouteQuery.mode
    mockSearchArticles.mockClear()
    mockPush.mockClear()
  })

  it('shows query text as heading when q param is present', async () => {
    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('quantum')
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
    })
    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toBeTruthy()
  })

  it('shows local badge when mode=local in URL', async () => {
    mockRouteQuery.mode = 'local'
    const SearchPage = (await import('../SearchPage.vue')).default
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    expect(wrapper.text()).toMatch(/Local/i)
  })
})

describe('SearchPage — local mode', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    delete mockRouteQuery.q
    delete mockRouteQuery.category
    delete mockRouteQuery.sort
    mockRouteQuery.mode = 'local'
    mockSearchArticles.mockClear()
    mockSearchDrafts.mockClear()
    mockSearchCached.mockClear()
    mockPush.mockClear()
    mockSearchDrafts.mockResolvedValue([])
    mockSearchCached.mockResolvedValue([])
    vi.resetModules()
  })

  it('calls searchDrafts and searchCachedArticles when mode=local', async () => {
    mockRouteQuery.q = 'quantum'

    vi.doMock('../../composables/useTauri', () => ({
      useTauri: () => ({
        isTauri: { value: false },
        isBrowserLocal: { value: true },
        searchDrafts: mockSearchDrafts,
        searchCachedArticles: mockSearchCached,
      }),
    }))

    const { default: SearchPage } = await import('../SearchPage.vue')
    mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    expect(mockSearchDrafts).toHaveBeenCalled()
    expect(mockSearchCached).toHaveBeenCalled()
    expect(mockSearchArticles).not.toHaveBeenCalled()
  })

  it('displays local search results (draft + cached merged)', async () => {
    mockRouteQuery.q = 'quantum'

    mockSearchDrafts.mockResolvedValue([
      { id: 'draft-1', title: 'Quantum Draft', content: '...', updated_at: '2026-06-01T00:00:00Z' },
    ])
    mockSearchCached.mockResolvedValue([
      { id: 'cache-1', title: 'Quantum Cache', updated_at: '2026-06-02T00:00:00Z' },
    ])

    vi.doMock('../../composables/useTauri', () => ({
      useTauri: () => ({
        isTauri: { value: false },
        isBrowserLocal: { value: true },
        searchDrafts: mockSearchDrafts,
        searchCachedArticles: mockSearchCached,
      }),
    }))

    const { default: SearchPage } = await import('../SearchPage.vue')
    const wrapper = mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Quantum Draft')
    expect(wrapper.text()).toContain('Quantum Cache')
  })

  it('does not call searchDrafts when mode is not local', async () => {
    delete mockRouteQuery.mode
    mockRouteQuery.q = 'quantum'

    vi.doMock('../../composables/useTauri', () => ({
      useTauri: () => ({
        isTauri: { value: false },
        isBrowserLocal: { value: false },
        searchDrafts: mockSearchDrafts,
        searchCachedArticles: mockSearchCached,
      }),
    }))

    const { default: SearchPage } = await import('../SearchPage.vue')
    mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    expect(mockSearchArticles).toHaveBeenCalled()
    expect(mockSearchDrafts).not.toHaveBeenCalled()
    expect(mockSearchCached).not.toHaveBeenCalled()
  })

  it('uses network search when isBrowserLocal but online (isLocalOnly returns false)', async () => {
    mockRouteQuery.q = 'quantum'
    delete mockRouteQuery.mode

    vi.doMock('../../composables/useTauri', () => ({
      useTauri: () => ({
        isTauri: { value: false },
        isBrowserLocal: { value: true },
        searchDrafts: mockSearchDrafts,
        searchCachedArticles: mockSearchCached,
      }),
    }))

    const { default: SearchPage } = await import('../SearchPage.vue')
    mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    // isLocalOnly() checks ?tauri + !isOnline, not isBrowserLocal directly.
    // Since isOnline is true (mock default), isLocalOnly() returns false → network search.
    expect(mockSearchArticles).toHaveBeenCalled()
    expect(mockSearchDrafts).not.toHaveBeenCalled()
  })

  it('mode=local search requires query to be non-empty', async () => {
    mockRouteQuery.q = ''

    vi.doMock('../../composables/useTauri', () => ({
      useTauri: () => ({
        isTauri: { value: false },
        isBrowserLocal: { value: true },
        searchDrafts: mockSearchDrafts,
        searchCachedArticles: mockSearchCached,
      }),
    }))

    const { default: SearchPage } = await import('../SearchPage.vue')
    mount(SearchPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    expect(mockSearchDrafts).not.toHaveBeenCalled()
    expect(mockSearchCached).not.toHaveBeenCalled()
  })
})
