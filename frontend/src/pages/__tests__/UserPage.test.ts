import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import UserPage from '../UserPage.vue'

vi.mock('vue-router', () => ({ useRoute: () => ({ params: { id: 'test-user' } }) }))

describe('UserPage', () => {
  it('renders user page', () => {
    const wrapper = mount(UserPage)
    expect(wrapper.text()).toContain('User')
  })
})
