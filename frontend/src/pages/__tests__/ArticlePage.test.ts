import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '123' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

// Mock the article store to avoid HTTP calls
vi.mock('../../stores/useArticleStore', () => ({
  useArticleStore: () => ({
    currentArticle: {
      id: '123',
      title: 'Test Article',
      status: 'published',
      authors: [{ name: 'Author' }],
      review_count: 0,
      fork_count: 0,
      score: null,
    },
    fetchArticle: vi.fn(),
  }),
}))

describe('ArticlePage', () => {
  it('renders article page with id', async () => {
    setActivePinia(createPinia())
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: {
        stubs: { 'router-link': true, 'router-view': true },
      },
    })
    expect(wrapper.text()).toContain('Test Article')
  })
})
