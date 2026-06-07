import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import NetworkStatusBadge from '../NetworkStatusBadge.vue'

describe('NetworkStatusBadge', () => {
  it('renders online state with green dot', () => {
    const wrapper = mount(NetworkStatusBadge)
    expect(wrapper.find('.network-status-badge').exists()).toBe(true)
    const dot = wrapper.find('.status-dot')
    expect(dot.exists()).toBe(true)
    expect(dot.classes()).toContain('online')
  })

  it('renders offline state with gray dot when forceOffline', () => {
    const wrapper = mount(NetworkStatusBadge, {
      props: { forceOffline: true },
    })
    const dot = wrapper.find('.status-dot')
    expect(dot.exists()).toBe(true)
    expect(dot.classes()).toContain('offline')
    expect(dot.classes()).not.toContain('online')
  })
})
