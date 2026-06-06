import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const { mockPush } = vi.hoisted(() => ({
  mockPush: vi.fn(),
}))

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({ params: { id: 'test-article-1' } }),
  RouterLink: { template: '<a><slot /></a>' },
}))

const mockCreateMergeProposal = vi.fn().mockResolvedValue({
  id: 'merge-1',
  fork_article_id: 'fork-article-1',
  target_article_id: 'parent-article-1',
  proposer_id: 'u1',
  status: 'open',
  created_at: '2026-06-06T00:00:00Z',
})

const mockGetMergeProposals = vi.fn().mockResolvedValue({ proposals: [] })

vi.mock('../../api/articles', () => ({
  getArticle: vi.fn().mockResolvedValue({
    id: 'test-article-1',
    title: 'A Study on Quantum Error Correction',
    status: 'sedimentation',
    authors: [
      { id: 'u1', name: 'Alice Chen', anonymous_name: 'anon1' },
      { id: 'u2', name: 'Bob Lee', anonymous_name: 'anon2' },
    ],
    fork_count: 2,
    forked_from: null,
    commit_count: 3,
    compiled_format: 'html',
    compiled_output: '<p>Quantum error correction is essential...</p>',
    compiled_pages: 12,
    score: { originality: 4, rigor: 5, completeness: 4, pedagogy: 3, impact: 4 },
    sink_eta: '2026-07-01T00:00:00Z',
    days_remaining: 25,
    sink_duration_days: 30,
    review_count: 3,
    is_bookmarked: false,
    is_own_article: true,
    created_at: '2026-05-01T00:00:00Z',
    updated_at: '2026-06-05T00:00:00Z',
  }),
  getHistory: vi.fn().mockResolvedValue({ commits: [] }),
  forkArticle: vi.fn().mockResolvedValue({ id: 'forked-1' }),
  extendSink: vi.fn().mockResolvedValue({}),
  createMergeProposal: mockCreateMergeProposal,
  getMergeProposals: mockGetMergeProposals,
  acceptMergeProposal: vi.fn().mockResolvedValue({}),
  rejectMergeProposal: vi.fn().mockResolvedValue({}),
}))

describe('ArticlePage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders article title', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    expect(wrapper.text()).toContain('A Study on Quantum Error Correction')
  })

  it('renders authors', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    expect(wrapper.text()).toContain('Alice Chen')
    expect(wrapper.text()).toContain('Bob Lee')
  })

  it('renders status badge', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    expect(wrapper.text()).toMatch(/In Pool|sedimentation/)
  })

  it('has bookmark toggle', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    const bookmarkBtn = wrapper.find('button[aria-label*="bookmark" i]')
    expect(bookmarkBtn.exists()).toBe(true)
  })

  it('has tab switcher for Body and Comments', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    expect(wrapper.text()).toMatch(/body|comments|Body|Comments/i)
  })

  it('renders download source and pdf buttons', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    // Look for download buttons by aria-label
    const sourceBtn = wrapper.find('a[aria-label*="download source" i], button[aria-label*="download source" i]')
    const pdfBtn = wrapper.find('a[aria-label*="download pdf" i], button[aria-label*="download pdf" i]')
    expect(sourceBtn.exists()).toBe(true)
    expect(pdfBtn.exists()).toBe(true)
  })

  it('renders Merge button when article is a fork (has forked_from)', async () => {
    // Override getArticle to return a forked article
    const articlesMod = await import('../../api/articles')
    const getArticle = articlesMod.getArticle as ReturnType<typeof vi.fn>
    getArticle.mockResolvedValueOnce({
      id: 'fork-article-1',
      title: 'My Improvements to Quantum Error Correction',
      status: 'draft',
      authors: [{ id: 'u1', name: 'Alice Chen', anonymous_name: 'anon1' }],
      fork_count: 0,
      forked_from: 'parent-article-1',
      commit_count: 1,
      compiled_format: 'html',
      compiled_output: '<p>Improved version...</p>',
      compiled_pages: 5,
      score: { originality: 4, rigor: 4, completeness: 3, pedagogy: 3, impact: 3 },
      sink_eta: null,
      days_remaining: null,
      sink_duration_days: 30,
      review_count: 0,
      is_bookmarked: false,
      is_own_article: true,
      created_at: '2026-06-05T00:00:00Z',
      updated_at: '2026-06-06T00:00:00Z',
    })
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    // Should show Merge button because article is a fork
    const mergeBtn = wrapper.find('button[aria-label*="merge" i], button span:contains("Merge")')
    expect(wrapper.text()).toMatch(/merge|Merge|Propose/i)
  })

  it('clicking Merge proposes merging the fork back to its parent', async () => {
    const articlesMod = await import('../../api/articles')
    const getArticle = articlesMod.getArticle as ReturnType<typeof vi.fn>
    getArticle.mockResolvedValueOnce({
      id: 'fork-article-1',
      title: 'My Improvements',
      status: 'draft',
      authors: [{ id: 'u1', name: 'Alice Chen', anonymous_name: 'anon1' }],
      fork_count: 0,
      forked_from: 'parent-article-1',
      commit_count: 1,
      compiled_format: 'html',
      compiled_output: '<p>Improved version...</p>',
      compiled_pages: 5,
      score: { originality: 4, rigor: 4, completeness: 3, pedagogy: 3, impact: 3 },
      sink_eta: null,
      days_remaining: null,
      sink_duration_days: 30,
      review_count: 0,
      is_bookmarked: false,
      is_own_article: true,
      created_at: '2026-06-05T00:00:00Z',
      updated_at: '2026-06-06T00:00:00Z',
    })
    mockPush.mockClear()
    mockCreateMergeProposal.mockClear()

    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))

    // Set a viewer so the merge handler proceeds
    const { useUserStore } = await import('../../stores/useUserStore')
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen' } as any

    // Click the Merge button
    const mergeBtn = wrapper.find('button[aria-label="Propose merge"]')
    expect(mergeBtn.exists()).toBe(true)
    await mergeBtn.trigger('click')
    await new Promise(r => setTimeout(r, 50))

    expect(mockCreateMergeProposal).toHaveBeenCalledWith('parent-article-1', {
      fork_article_id: 'fork-article-1',
      proposer_id: 'u1',
    })
  })
})
