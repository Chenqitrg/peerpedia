import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import HomePage from '../HomePage.vue'

// Mock the store to avoid real HTTP calls
vi.mock('../../stores/useArticleStore', () => ({
  useArticleStore: () => ({
    articles: [{ id: '1', title: 'Test Article', status: 'published' }],
    loading: false,
    fetchArticles: vi.fn(),
  }),
}))

describe('HomePage', () => {
  it('renders articles from store', () => {
    setActivePinia(createPinia())
    const wrapper = mount(HomePage)
    expect(wrapper.text()).toContain('PeerPedia')
    expect(wrapper.text()).toContain('Test Article')
  })
})
