import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

describe('PoolPage', () => {
  it('renders pool page title', async () => {
    setActivePinia(createPinia())
    const PoolPage = (await import('../PoolPage.vue')).default
    const wrapper = mount(PoolPage, {
      global: {
        stubs: { 'router-link': true, 'router-view': true },
      },
    })
    expect(wrapper.text()).toContain('Pool')
  })
})
