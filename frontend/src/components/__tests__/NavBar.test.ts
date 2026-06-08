import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import NavBar from '../NavBar.vue'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({ path: '/' }),
}))

// Mock useNetworkStatus so canRead('pool')/canRead('schools') pass in tests
vi.mock('@/composables/useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(() => ({
    isOnline: { value: true },
    startPing: vi.fn(),
    stopPing: vi.fn(),
  })),
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

  it('New Article link goes to /edit for fresh editor', () => {
    const user = { id: 'u1', username: 'test', name: 'Test' }
    localStorage.setItem('viewer', JSON.stringify(user))
    localStorage.setItem('token', 'test-token')
    setActivePinia(createPinia())

    const wrapper = mount(NavBar, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    const newArticleLink = wrapper.find('a[href="/edit"]')
    expect(newArticleLink.exists()).toBe(true)
    // Clicking this should navigate to /edit with no ID → fresh editor
    expect(newArticleLink.attributes('href')).toBe('/edit')
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
    expect(wrapper.find('a[href="/edit"]').exists()).toBe(true)
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

  it('routes to /search?mode=local when in browser-local mode', async () => {
    localStorage.setItem('peerpedia_browser_local', '1')

    const wrapper = mount(NavBar, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })

    // Find search input, type, submit the form
    const input = wrapper.find('input')
    expect(input.exists()).toBe(true)
    await input.setValue('quantum physics')
    await wrapper.find('form').trigger('submit')

    expect(mockPush).toHaveBeenCalledWith('/search?q=quantum%20physics&mode=local')
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
