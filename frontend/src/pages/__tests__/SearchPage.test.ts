import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SearchPage from '../SearchPage.vue'

describe('SearchPage', () => {
  it('renders search page', () => {
    const wrapper = mount(SearchPage)
    expect(wrapper.text()).toContain('Search')
  })
})
