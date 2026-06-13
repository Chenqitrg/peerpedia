import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'

// Mock vue-router
const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, afterEach: vi.fn() }),
  useRoute: () => ({ path: '/' }),
  RouterLink: { template: '<a><slot /></a>' },
}))

// Mock useOffline
const mockIsLocalOnlyValue = ref(false)
const mockIsLocalOnly = vi.fn(() => mockIsLocalOnlyValue.value)
const mockCanRead = vi.fn(() => true)
vi.mock('../composables/useOffline', () => ({
  useOffline: () => ({
    isLocalOnly: mockIsLocalOnly,
    canRead: mockCanRead,
  }),
}))

// Mock useTauri
vi.mock('../composables/useTauri', () => ({
  useTauri: () => ({
    isTauri: ref(false),
    isBrowserLocal: ref(false),
    searchDrafts: vi.fn(),
    searchCachedArticles: vi.fn(),
  }),
}))

// Mock useUserStore — logged in
vi.mock('../stores/useUserStore', () => ({
  useUserStore: () => ({
    viewer: { id: 'test-user', username: 'test', name: 'Test User' },
    showAuthModal: false,
    logout: vi.fn(),
  }),
}))

// Mock useNetworkStatus
vi.mock('../composables/useNetworkStatus', () => ({
  useNetworkStatus: () => ({
    isSynced: ref(true),
    isSynced: ref(true),
    connectionState: ref('synced'),
  }),
}))

// Mock useLocalStorage
vi.mock('../composables/useLocalStorage', () => ({
  saveString: vi.fn(),
}))

describe('NavBar handleSearch URL construction', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockIsLocalOnlyValue.value = false
    mockPush.mockClear()
  })

  it('does not append mode=local when isLocalOnly() is false', async () => {
    mockIsLocalOnlyValue.value = false

    const { default: NavBar } = await import('../components/NavBar.vue')
    const wrapper = mount(NavBar)

    // Set search query and submit
    const input = wrapper.find('input[type="text"]')
    await input.setValue('quantum physics')
    const form = wrapper.find('form')
    await form.trigger('submit')

    expect(mockPush).toHaveBeenCalledWith('/search?q=quantum%20physics')
  })

  it('appends mode=local when isLocalOnly() is true', async () => {
    mockIsLocalOnlyValue.value = true

    const { default: NavBar } = await import('../components/NavBar.vue')
    const wrapper = mount(NavBar)

    const input = wrapper.find('input[type="text"]')
    await input.setValue('draft title')
    const form = wrapper.find('form')
    await form.trigger('submit')

    expect(mockPush).toHaveBeenCalledWith('/search?q=draft%20title&mode=local')
  })

  it('does not navigate with empty search query', async () => {
    const { default: NavBar } = await import('../components/NavBar.vue')
    const wrapper = mount(NavBar)

    const form = wrapper.find('form')
    await form.trigger('submit')

    expect(mockPush).not.toHaveBeenCalled()
  })
})
