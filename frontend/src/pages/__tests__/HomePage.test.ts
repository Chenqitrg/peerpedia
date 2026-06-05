import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('../../api/feed', () => ({
  fetchFeed: vi.fn().mockResolvedValue({
    articles: [
      {
        id: 'feed-1',
        title: 'Feed Article One',
        status: 'sedimentation',
        authors: [{ id: 'u1', name: 'Alice', anonymous_name: 'anon1' }],
        content_preview: 'Preview content',
        commit_hash: 'abc1234',
        fork_count: 0,
        forked_from: null,
        commit_count: 2,
        score: { originality: 4, rigor: 3, completeness: 4, pedagogy: 3, impact: 4 },
        days_remaining: 10,
        sink_duration_days: 30,
        is_bookmarked: false,
        is_own_article: false,
        created_at: '2026-06-01T00:00:00Z',
        updated_at: '2026-06-05T00:00:00Z',
      },
      {
        id: 'feed-2',
        title: 'Feed Article Two',
        status: 'published',
        authors: [{ id: 'u2', name: 'Bob', anonymous_name: 'anon2' }],
        content_preview: 'More preview',
        commit_hash: 'def5678',
        fork_count: 1,
        forked_from: null,
        commit_count: 1,
        score: { originality: 5, rigor: 4, completeness: 5, pedagogy: 4, impact: 5 },
        days_remaining: null,
        sink_duration_days: null,
        is_bookmarked: true,
        is_own_article: true,
        created_at: '2026-05-15T00:00:00Z',
        updated_at: '2026-06-01T00:00:00Z',
      },
    ],
    total: 2,
    page: 1,
    size: 20,
  }),
}))

function setLoggedIn() {
  localStorage.setItem('viewer', JSON.stringify({ id: 'u1', username: 'test', name: 'Test' }))
  localStorage.setItem('token', 'test-token')
}

describe('HomePage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('shows welcome state when not logged in', async () => {
    const HomePage = (await import('../HomePage.vue')).default
    const wrapper = mount(HomePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    expect(wrapper.text()).toContain('PeerPedia')
    expect(wrapper.text()).toContain('Sign In')
  })

  it('renders Feed when logged in', async () => {
    setLoggedIn()
    setActivePinia(createPinia())  // re-init store with viewer
    const HomePage = (await import('../HomePage.vue')).default
    const wrapper = mount(HomePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    expect(wrapper.text()).toContain('Feed')
  })

  it('renders feed article titles when logged in', async () => {
    setLoggedIn()
    setActivePinia(createPinia())
    const HomePage = (await import('../HomePage.vue')).default
    const wrapper = mount(HomePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    expect(wrapper.text()).toContain('Feed Article One')
    expect(wrapper.text()).toContain('Feed Article Two')
  })
})
