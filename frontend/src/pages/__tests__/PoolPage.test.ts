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

vi.mock('../../api/pool', () => ({
  getPool: vi.fn().mockResolvedValue({
    articles: [
      {
        id: 'pool-1',
        title: 'Sinking Article',
        status: 'sedimentation',
        authors: [{ id: 'u1', name: 'Alice', anonymous_name: 'anon1' }],
        content_preview: 'This article is in the pool',
        commit_hash: 'def123',
        fork_count: 0,
        forked_from: null,
        commit_count: 1,
        score: { originality: 4, rigor: 3, completeness: 3, pedagogy: 4, impact: 3 },
        days_remaining: 25,
        sink_duration_days: 30,
        is_bookmarked: false,
        is_own_article: false,
        created_at: '2026-05-01T00:00:00Z',
        updated_at: '2026-06-05T00:00:00Z',
      },
      {
        id: 'pool-2',
        title: 'Almost Out',
        status: 'sedimentation',
        authors: [{ id: 'u2', name: 'Bob', anonymous_name: 'anon2' }],
        content_preview: 'Almost out of the pool',
        commit_hash: 'abc789',
        fork_count: 1,
        forked_from: 'orig-1',
        commit_count: 3,
        score: { originality: 5, rigor: 4, completeness: 5, pedagogy: 4, impact: 5 },
        days_remaining: 3,
        sink_duration_days: 30,
        is_bookmarked: true,
        is_own_article: true,
        created_at: '2026-04-01T00:00:00Z',
        updated_at: '2026-06-05T00:00:00Z',
      },
    ],
    total: 2,
  }),
}))

describe('PoolPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders pool page title', async () => {
    const PoolPage = (await import('../PoolPage.vue')).default
    const wrapper = mount(PoolPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    expect(wrapper.text()).toContain('Pool')
  })

  it('renders pool article titles', async () => {
    const PoolPage = (await import('../PoolPage.vue')).default
    const wrapper = mount(PoolPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    expect(wrapper.text()).toContain('Sinking Article')
    expect(wrapper.text()).toContain('Almost Out')
  })

  it('renders progress bar with remaining days', async () => {
    const PoolPage = (await import('../PoolPage.vue')).default
    const wrapper = mount(PoolPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    expect(wrapper.text()).toContain('25')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('remaining')
  })

  it('renders empty state when no articles', async () => {
    vi.mocked(await import('../../api/pool')).getPool.mockResolvedValueOnce({
      articles: [],
      total: 0,
    })
    const PoolPage = (await import('../PoolPage.vue')).default
    const wrapper = mount(PoolPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    expect(wrapper.text()).toMatch(/empty|no articles|none/i)
  })
})
