import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import NavBar from '../NavBar.vue'

// RouterLink stub that renders slot content
const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

describe('NavBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders PeerPedia brand with home link', () => {
    const wrapper = mount(NavBar, {
      global: {
        stubs: { 'router-link': RouterLinkStub, 'router-view': true },
      },
    })
    expect(wrapper.text()).toContain('PeerPedia')
    // The logo should link to home
    const brandLink = wrapper.find('a[href="/"]')
    expect(brandLink.exists()).toBe(true)
  })

  it('renders Pool navigation link', () => {
    const wrapper = mount(NavBar, {
      global: {
        stubs: { 'router-link': RouterLinkStub, 'router-view': true },
      },
    })
    expect(wrapper.text()).toContain('Pool')
  })

  it('has frosted glass effect (backdrop-blur classes)', () => {
    const wrapper = mount(NavBar, {
      global: {
        stubs: { 'router-link': RouterLinkStub, 'router-view': true },
      },
    })
    const nav = wrapper.find('nav')
    const classes = nav.classes().join(' ')
    expect(classes).toMatch(/backdrop-blur/)
  })

  it('renders a search input', () => {
    const wrapper = mount(NavBar, {
      global: {
        stubs: { 'router-link': RouterLinkStub, 'router-view': true },
      },
    })
    const input = wrapper.find('input')
    expect(input.exists()).toBe(true)
  })

  it('renders action buttons: bookmarks, new article', () => {
    const wrapper = mount(NavBar, {
      global: {
        stubs: { 'router-link': RouterLinkStub, 'router-view': true },
      },
    })
    // Bookmarks link should exist
    const bookmarkLink = wrapper.find('a[href="/bookmarks"]')
    expect(bookmarkLink.exists()).toBe(true)
    // New article link should exist
    const newArticleLink = wrapper.find('a[href="/edit"]')
    expect(newArticleLink.exists()).toBe(true)
  })
})
