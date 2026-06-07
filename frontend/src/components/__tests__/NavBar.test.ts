import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import NavBar from '../NavBar.vue'

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
