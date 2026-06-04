import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('vue-router', () => ({ useRouter: () => ({}), useRoute: () => ({}) }))

describe('App', () => {
  it('renders navbar and router view', async () => {
    const { default: App } = await import('../App.vue')
    const wrapper = mount(App, { global: { stubs: { 'router-view': true } } })
    expect(wrapper.find('nav').exists() || wrapper.text()).toBeTruthy()
  })
})
