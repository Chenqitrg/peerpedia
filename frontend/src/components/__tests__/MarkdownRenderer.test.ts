import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MarkdownRenderer from '../MarkdownRenderer.vue'

describe('MarkdownRenderer', () => {
  it('renders rendered HTML content', () => {
    const wrapper = mount(MarkdownRenderer, { props: { content: '<p>Hello <strong>World</strong></p>' } })
    expect(wrapper.html()).toContain('<strong>World</strong>')
    expect(wrapper.text()).toContain('Hello')
    expect(wrapper.text()).toContain('World')
  })

  it('renders empty content safely', () => {
    const wrapper = mount(MarkdownRenderer, { props: { content: '' } })
    expect(wrapper.text()).toBe('')
  })
})
