import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CommentThread from '../CommentThread.vue'

describe('CommentThread', () => {
  it('renders message list', () => {
    const messages = [
      { author_id: 'u1', content: 'Great paper!', created_at: '2026-01-01' },
      { author_id: 'u2', content: 'I agree', created_at: '2026-01-02' },
    ]
    const wrapper = mount(CommentThread, { props: { messages } })
    expect(wrapper.text()).toContain('Great paper!')
    expect(wrapper.text()).toContain('I agree')
  })

  it('renders empty state when no messages', () => {
    const wrapper = mount(CommentThread, { props: { messages: [] } })
    expect(wrapper.text()).toContain('No comments yet.')
  })
})
