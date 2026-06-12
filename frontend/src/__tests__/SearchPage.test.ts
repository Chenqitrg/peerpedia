import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref, reactive } from 'vue'

// Mock vue-router — route.query is a plain reactive object in Vue Router
const mockQuery = reactive<Record<string, any>>({})
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), afterEach: vi.fn() }),
  useRoute: () => ({ query: mockQuery }),
  RouterLink: { template: '<a><slot /></a>' },
}))

// Mock useOffline — isLocalOnly is a function, not a ref
const mockIsLocalOnlyValue = ref(false)
const mockIsLocalOnly = vi.fn(() => mockIsLocalOnlyValue.value)
const mockCanRead = vi.fn((feature: string) => {
  if (feature === 'search.network') return !mockIsLocalOnlyValue.value
  return true
})
vi.mock('../composables/useOffline', () => ({
  useOffline: () => ({
    isLocalOnly: mockIsLocalOnly,
    canRead: mockCanRead,
    getFallback: vi.fn(),
  }),
}))

// Mock useTauri
const mockSearchDrafts = vi.fn().mockResolvedValue([])
const mockSearchCachedArticles = vi.fn().mockResolvedValue([])
vi.mock('../composables/useTauri', () => ({
  useTauri: () => ({
    isTauri: ref(false),
    isBrowserLocal: ref(false),
    searchDrafts: mockSearchDrafts,
    searchCachedArticles: mockSearchCachedArticles,
  }),
}))

// Mock useUserStore
vi.mock('../stores/useUserStore', () => ({
  useUserStore: () => ({
    viewer: { id: 'test-user', name: 'Test User' },
  }),
}))

// Mock useNetworkStatus
vi.mock('../composables/useNetworkStatus', () => ({
  useNetworkStatus: () => ({
    isOnline: ref(true),
  }),
}))

// Mock API
const mockSearchArticles = vi.fn().mockResolvedValue({
  articles: [{ id: '1', title: 'Test Article', status: 'published' }],
  total: 1,
})
vi.mock('../api/search', () => ({
  searchArticles: mockSearchArticles,
}))

// Mock useBookmarkToggle
vi.mock('../composables/useBookmarkToggle', () => ({
  useBookmarkToggle: () => ({ toggle: vi.fn() }),
}))

// Mock useAsyncResource — execute the function immediately
vi.mock('../composables/useAsyncResource', () => ({
  useAsyncResource: (fn: any, _default: any, _opts: any) => {
    const result = ref<any>(null)
    const loading = ref(false)
    const error = ref<string | null>(null)
    const execute = async () => {
      loading.value = true
      error.value = null
      try {
        result.value = await fn()
      } catch (e: any) {
        error.value = e?.message || 'Unknown error'
      } finally {
        loading.value = false
      }
    }
    return { data: result, loading, error, execute }
  },
}))

// Stub child components
vi.mock('../components/ArticleCard.vue', () => ({
  default: { template: '<div class="article-card-stub" />', emits: ['toggle-bookmark'] },
}))
vi.mock('../components/SkeletonCard.vue', () => ({
  default: { template: '<div class="skeleton-card-stub" />' },
}))
vi.mock('../components/ErrorState.vue', () => ({
  default: { template: '<div class="error-state-stub" />', emits: ['retry'] },
}))
vi.mock('../components/Pagination.vue', () => ({
  default: { template: '<div class="pagination-stub" />', emits: ['change'] },
}))

describe('SearchPage isLocalMode', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockIsLocalOnlyValue.value = false
    // Clear and reset mockQuery
    for (const k of Object.keys(mockQuery)) delete mockQuery[k]
    mockSearchArticles.mockResolvedValue({
      articles: [{ id: '1', title: 'Test', status: 'published' }],
      total: 1,
    })
    mockSearchDrafts.mockResolvedValue([])
    mockSearchCachedArticles.mockResolvedValue([])
  })

  it('shows Network badge when online and not local mode', async () => {
    mockIsLocalOnlyValue.value = false
    mockQuery.q = 'test'

    const { default: SearchPage } = await import('../pages/SearchPage.vue')
    const wrapper = mount(SearchPage)

    await wrapper.vm.doSearch()
    await wrapper.vm.$nextTick()

    const badge = wrapper.find('span.rounded-full')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('Network')
  })

  it('shows Local badge when isLocalOnly() returns true', async () => {
    mockIsLocalOnlyValue.value = true
    mockQuery.q = 'test'

    const { default: SearchPage } = await import('../pages/SearchPage.vue')
    const wrapper = mount(SearchPage)

    await wrapper.vm.doSearch()
    await wrapper.vm.$nextTick()

    const badge = wrapper.find('span.rounded-full')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('Local')
  })

  it('shows Local badge when mode=local in URL', async () => {
    mockIsLocalOnlyValue.value = false
    mockQuery.q = 'test'
    mockQuery.mode = 'local'

    const { default: SearchPage } = await import('../pages/SearchPage.vue')
    const wrapper = mount(SearchPage)

    await wrapper.vm.doSearch()
    await wrapper.vm.$nextTick()

    const badge = wrapper.find('span.rounded-full')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('Local')
  })

  it('shows degraded Local badge when network search fails', async () => {
    mockIsLocalOnlyValue.value = false
    mockQuery.q = 'test'
    mockSearchArticles.mockRejectedValue(new Error('Server error'))

    const { default: SearchPage } = await import('../pages/SearchPage.vue')
    const wrapper = mount(SearchPage)

    await wrapper.vm.doSearch()
    await wrapper.vm.$nextTick()

    const badge = wrapper.find('span.rounded-full')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('Local (fallback)')
  })

  it('does not search with empty query', async () => {
    mockQuery.q = ''

    const { default: SearchPage } = await import('../pages/SearchPage.vue')
    const wrapper = mount(SearchPage)

    await wrapper.vm.doSearch()
    await wrapper.vm.$nextTick()

    expect(mockSearchArticles).not.toHaveBeenCalled()
    expect(mockSearchDrafts).not.toHaveBeenCalled()
  })
})
