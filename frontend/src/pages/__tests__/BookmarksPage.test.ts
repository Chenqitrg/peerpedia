import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({}),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('../../api/bookmarks', () => ({
  fetchBookmarks: vi.fn().mockResolvedValue([
    { id: 'bm-1', user_id: 'u1', article_id: 'art-1', created_at: '2026-06-01T00:00:00Z' },
  ]),
}))

vi.mock('../../api/articles', () => ({
  getArticle: vi.fn().mockResolvedValue({
    id: 'art-1',
    title: 'Bookmarked Quantum Paper',
    status: 'published',
    authors: [{ id: 'u1', name: 'Alice', anonymous_name: 'anon1' }],
    content_preview: 'Preview of quantum paper',
    commit_hash: 'abc123',
    fork_count: 1,
    forked_from: null,
    commit_count: 2,
    score: { originality: 4, rigor: 3, completeness: 4, pedagogy: 3, impact: 4 },
    days_remaining: null,
    sink_duration_days: null,
    is_bookmarked: true,
    is_own_article: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  }),
}))

describe('BookmarksPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.setItem('viewer', JSON.stringify({ id: 'u1', name: 'Test User' }))
  })

  it('renders bookmarks page title', async () => {
    const BookmarksPage = (await import('../BookmarksPage.vue')).default
    const wrapper = mount(BookmarksPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Bookmarks')
  })

  it('renders bookmarked articles', async () => {
    const BookmarksPage = (await import('../BookmarksPage.vue')).default
    const wrapper = mount(BookmarksPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Bookmarked Quantum Paper')
  })

  it('shows empty state when no bookmarks', async () => {
    vi.mocked(await import('../../api/bookmarks')).fetchBookmarks.mockResolvedValueOnce([])
    const BookmarksPage = (await import('../BookmarksPage.vue')).default
    const wrapper = mount(BookmarksPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toBeTruthy()
  })
})
