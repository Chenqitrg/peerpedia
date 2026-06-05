import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import NavBar from '../NavBar.vue'

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
    // Should show Pool link
    expect(wrapper.text()).toContain('Pool')
    // Should show action links
    expect(wrapper.find('a[href="/bookmarks"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/edit"]').exists()).toBe(true)
  })
})
