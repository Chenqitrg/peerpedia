import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import NavBar from '../NavBar.vue'

describe('NavBar', () => {
  it('renders app name', () => {
    const wrapper = mount(NavBar)
    expect(wrapper.text()).toContain('PeerPedia')
  })
})
