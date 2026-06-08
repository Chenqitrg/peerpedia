import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

// Mutable state for controlling mock behavior across test blocks.
const tauriState = vi.hoisted(() => ({
  isTauri: false,
  isBrowserLocal: false,
  mockListDrafts: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../composables/useTauri', () => ({
  useTauri: () => ({
    isTauri: { value: tauriState.isTauri },
    isBrowserLocal: { value: tauriState.isBrowserLocal },
    getSessionToken: vi.fn(() => null),
    setSessionToken: vi.fn(),
    listDrafts: tauriState.mockListDrafts,
    isFollowing: vi.fn().mockResolvedValue({ following: false }),
    listAccounts: vi.fn().mockResolvedValue([]),
    gitHistory: vi.fn().mockResolvedValue([]),
  }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ params: { id: 'test-user' } }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('../../api/users', () => ({
  getUser: vi.fn().mockResolvedValue({
    id: 'test-user',
    name: 'Alice Chen',
    anonymous_name: 'shadow_writer',
    affiliation: 'MIT',
    expertise: ['Quantum Computing', 'Information Theory'],
    avatar_url: null,
    contact: 'alice@mit.edu',
    reputation: { professionalism: 4, objectivity: 3, collaboration: 5, pedagogy: 4 },
    followers_count: 15,
    following_count: 8,
    article_count: 5,
    created_at: '2025-01-01T00:00:00Z',
  }),
  getFollowers: vi.fn().mockResolvedValue([]),
  getFollowing: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../api/articles', () => ({
  getArticles: vi.fn().mockResolvedValue({
    articles: [
      {
        id: 'art-1',
        title: 'User Article',
        status: 'published',
        authors: [{ id: 'test-user', name: 'Alice Chen', anonymous_name: 'shadow_writer' }],
        content_preview: 'Preview text',
        commit_hash: 'abc123',
        fork_count: 0,
        forked_from: null,
        commit_count: 1,
        score: { originality: 4, rigor: 3, completeness: 4, pedagogy: 3, impact: 4 },
        days_remaining: null,
        sink_duration_days: null,
        is_bookmarked: false,
        is_own_article: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-06-01T00:00:00Z',
      },
    ],
    total: 1,
  }),
}))

describe('UserPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders user name', async () => {
    const UserPage = (await import('../UserPage.vue')).default
    const wrapper = mount(UserPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Alice Chen')
  })

  it('renders user affiliation', async () => {
    const UserPage = (await import('../UserPage.vue')).default
    const wrapper = mount(UserPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('MIT')
  })

  it('renders reputation scores', async () => {
    const UserPage = (await import('../UserPage.vue')).default
    const wrapper = mount(UserPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    // Reputation badges now use icons + numbers (no text labels)
    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('5')
  })

  it('renders follower and following counts', async () => {
    const UserPage = (await import('../UserPage.vue')).default
    const wrapper = mount(UserPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('15')
    expect(wrapper.text()).toContain('8')
  })

  it('renders article list', async () => {
    const UserPage = (await import('../UserPage.vue')).default
    const wrapper = mount(UserPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('User Article')
  })

  it('renders expertise tags', async () => {
    const UserPage = (await import('../UserPage.vue')).default
    const wrapper = mount(UserPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Quantum Computing')
    expect(wrapper.text()).toContain('Information Theory')
  })

  it('does not show Follow/Unfollow button on own profile', async () => {
    const { useUserStore } = await import('../../stores/useUserStore')
    const store = useUserStore()
    store.viewer = { id: 'test-user', name: 'Test' } as any

    const UserPage = (await import('../UserPage.vue')).default
    const wrapper = mount(UserPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const btn = wrapper.find('button.btn-sm')
    if (btn.exists()) {
      expect(btn.text()).not.toBe('Follow')
    }
  })

  it('loads Tauri local drafts when in browser-local mode on own profile', async () => {
    // This test reproduces the bug: UserPage should show drafts from local
    // storage in browser-local mode when viewing own profile.
    tauriState.isBrowserLocal = true
    tauriState.isTauri = false
    tauriState.mockListDrafts.mockResolvedValue([
      { id: 'draft-1', title: 'My Local Draft', updated_at: '2026-06-07T00:00:00Z' },
    ])

    const { useUserStore } = await import('../../stores/useUserStore')
    const store = useUserStore()
    store.viewer = { id: 'test-user', name: 'Alice Chen', username: 'alice' } as any
    store.isBrowserLocal = true

    const UserPage = (await import('../UserPage.vue')).default
    const wrapper = mount(UserPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    // The local draft should appear
    expect(tauriState.mockListDrafts).toHaveBeenCalled()
    expect(wrapper.text()).toContain('My Local Draft')
  })
})
