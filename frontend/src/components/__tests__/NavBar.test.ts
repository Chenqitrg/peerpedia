import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import NavBar from '../NavBar.vue'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({ path: '/' }),
}))

// Mock useNetworkStatus — vi.mock is hoisted, so the factory must use vi.hoisted.
const { mockUseNetworkStatus } = vi.hoisted(() => ({
  mockUseNetworkStatus: vi.fn(() => ({
    isSynced: { value: true },
    isSynced: { value: true },
    connectionState: ref('synced'),
    flash: ref(false),
    connect: vi.fn(),
    disconnect: vi.fn(),
    ping: vi.fn(),
  })),
}))
vi.mock('@/composables/useNetworkStatus', () => ({
  useNetworkStatus: mockUseNetworkStatus,
}))

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

describe('NavBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders PeerPedia brand with home link', () => {
    const wrapper = mount(NavBar, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    expect(wrapper.text()).toContain('PeerPedia')
    const brandLink = wrapper.find('a[href="/"]')
    expect(brandLink.exists()).toBe(true)
  })

  it('has frosted glass effect (backdrop-blur classes)', () => {
    const wrapper = mount(NavBar, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    const nav = wrapper.find('nav')
    const classes = nav.classes().join(' ')
    expect(classes).toMatch(/backdrop-blur/)
  })

  it('shows Sign In button when not logged in', () => {
    const wrapper = mount(NavBar, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    expect(wrapper.text()).toContain('Sign In')
    // No search, bookmarks, pool, edit links
    expect(wrapper.find('input').exists()).toBe(false)
  })

  it('New Article link navigates to /edit?new=1 for fresh editor', async () => {
    const user = { id: 'u1', username: 'test', name: 'Test' }
    localStorage.setItem('viewer', JSON.stringify(user))
    localStorage.setItem('token', 'test-token')
    setActivePinia(createPinia())

    const wrapper = mount(NavBar, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    // Find the "New Article" button by aria-label (i18n key: nav.newArticle)
    const newArticleBtn = wrapper.find('button[aria-label="写文章"], button[aria-label="New Article"]')
    expect(newArticleBtn.exists()).toBe(true)
    // Clicking this should open the format picker modal (Teleported to body)
    newArticleBtn.trigger('click')
    await wrapper.vm.$nextTick()
    // Modal is Teleported to body — query document.body
    expect(document.body.textContent).toContain('Choose Format')
    expect(document.body.textContent).toContain('Standard format with math support')
    expect(document.body.textContent).toContain('Academic typesetting')
    // Click the Markdown format card
    const markdownCard = Array.from(document.body.querySelectorAll('button')).find(
      b => b.textContent?.includes('Markdown') && b.textContent?.includes('Standard format')
    )
    expect(markdownCard).toBeTruthy()
    markdownCard!.click()
    expect(mockPush).toHaveBeenCalledWith(expect.stringMatching(/^\/edit\?new=1&_t=\d+&format=markdown$/))
  })

  it('shows nav links when logged in', () => {
    const user = { id: 'u1', username: 'test', name: 'Test' }
    localStorage.setItem('viewer', JSON.stringify(user))
    localStorage.setItem('token', 'test-token')
    setActivePinia(createPinia())  // reset store with localStorage populated

    const wrapper = mount(NavBar, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    // Should show Pool link (icon-only with title tooltip)
    expect(wrapper.find('a[href="/pool"]').exists()).toBe(true)
    // Should show action links
    expect(wrapper.find('a[href="/bookmarks"]').exists()).toBe(true)
    expect(wrapper.find('button[aria-label="写文章"], button[aria-label="New Article"]').exists()).toBe(true)
  })
})

describe('NavBar — search routing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    const user = { id: 'u1', username: 'test', name: 'Test' }
    localStorage.setItem('viewer', JSON.stringify(user))
    localStorage.setItem('token', 'test-token')
    setActivePinia(createPinia())
  })

  it('routes without mode=local when online (even in browser-local mode)', async () => {
    localStorage.setItem('peerpedia_browser_local', '1')

    const wrapper = mount(NavBar, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })

    // Find search input, type, submit the form
    const input = wrapper.find('input')
    expect(input.exists()).toBe(true)
    await input.setValue('quantum physics')
    await wrapper.find('form').trigger('submit')

    // isLocalOnly() checks ?tauri + !isOnline; localStorage alone doesn't trigger it.
    // Since isOnline is true (mock default), no &mode=local is appended.
    expect(mockPush).toHaveBeenCalledWith('/search?q=quantum%20physics')
  })

  it('routes to /search without mode when in web mode', async () => {
    const wrapper = mount(NavBar, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })

    const input = wrapper.find('input')
    expect(input.exists()).toBe(true)
    await input.setValue('general relativity')
    await wrapper.find('form').trigger('submit')

    expect(mockPush).toHaveBeenCalledWith('/search?q=general%20relativity')
  })
})

describe('NavBar — WiFi connectivity icon', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('shows green Wifi icon when server is reachable (isOnline=true)', () => {
    mockUseNetworkStatus.mockReturnValue({
      isSynced: { value: true },
      isSynced: { value: true },
      connectionState: ref('synced'),
      flash: ref(false),
      connect: vi.fn(),
      disconnect: vi.fn(),
      ping: vi.fn(),
    })
    const user = { id: 'u1', username: 'test', name: 'Test' }
    localStorage.setItem('viewer', JSON.stringify(user))
    localStorage.setItem('token', 'test-token')
    setActivePinia(createPinia())

    const wrapper = mount(NavBar, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    // SyncButton in synced state shows green dot
    const syncBtn = wrapper.find('.sync-btn--synced')
    expect(syncBtn.exists()).toBe(true)
  })

  it('shows gray WifiOff icon when server is unreachable in Tauri mode', () => {
    mockUseNetworkStatus.mockReturnValue({
      isSynced: { value: false },
      isSynced: { value: false },
      connectionState: ref('idle'),
      flash: ref(false),
      connect: vi.fn(),
      disconnect: vi.fn(),
      ping: vi.fn(),
    })
    // Simulate Tauri environment
    ;(window as any).__TAURI__ = {}
    const user = { id: 'u1', username: 'test', name: 'Test' }
    localStorage.setItem('viewer', JSON.stringify(user))
    localStorage.setItem('token', 'test-token')
    setActivePinia(createPinia())

    const wrapper = mount(NavBar, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    // SyncButton in idle state — should NOT be in synced state
    expect(wrapper.find('.sync-btn--synced').exists()).toBe(false)
    // Should show a wifi icon (WifiOff when idle)
    expect(wrapper.find('svg').exists()).toBe(true)

    delete (window as any).__TAURI__
  })
})
