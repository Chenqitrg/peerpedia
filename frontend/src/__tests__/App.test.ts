import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRouter: () => ({}),
  useRoute: () => ({}),
  RouterLink: { template: '<a><slot /></a>' },
}))

describe('App shell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders NavBar and router-view', async () => {
    const { default: App } = await import('../App.vue')
    const wrapper = mount(App, { global: { stubs: { 'router-view': true } } })
    expect(wrapper.findComponent({ name: 'NavBar' }).exists()).toBe(true)
  })

  it('has dark page background class', async () => {
    const { default: App } = await import('../App.vue')
    const wrapper = mount(App, { global: { stubs: { 'router-view': true } } })
    // The root element should have a dark background class
    expect(wrapper.classes()).toEqual(
      expect.arrayContaining([expect.stringMatching(/bg-/)]),
    )
  })
})
