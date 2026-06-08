import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const { mockPush, mockBack } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockBack: vi.fn(),
}))

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, back: mockBack }),
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
    commit_hash: 'abc123def456',
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
  getArticleSource: vi.fn().mockResolvedValue({ content: '# Test', format: 'markdown' }),
  getHistory: vi.fn().mockResolvedValue({ commits: [{ hash: 'abc123' }] }),
  forkArticle: vi.fn().mockResolvedValue({ id: 'forked-1' }),
  extendSink: vi.fn().mockResolvedValue({}),
  createMergeProposal: mockCreateMergeProposal,
  getMergeProposals: mockGetMergeProposals,
  acceptMergeProposal: vi.fn().mockResolvedValue({}),
  rejectMergeProposal: vi.fn().mockResolvedValue({}),
}))

const mockCreateReview = vi.fn().mockResolvedValue({
  id: 'review-1',
  article_id: 'test-article-1',
  reviewer_id: 'u1',
  commit_hash: 'abc123',
  scope: 'pool',
  scores: { originality: 3, rigor: 4, completeness: 3, pedagogy: 3, impact: 3 },
  is_self_review: false,
  reviewer_name: 'Alice Chen',
  thread: [],
  created_at: '2026-06-01T00:00:00Z',
})

const mockGetReviews = vi.fn().mockResolvedValue([
  {
    id: 'review-1',
    article_id: 'test-article-1',
    reviewer_id: 'u1',
    commit_hash: 'abc123',
    scope: 'pool',
    scores: { originality: 3, rigor: 4, completeness: 3, pedagogy: 3, impact: 3 },
    is_self_review: false,
    reviewer_name: 'Alice Chen',
    reviewer_id_name: 'u1',
    thread: [],
    created_at: '2026-06-01T00:00:00Z',
  },
])

vi.mock('../../api/reviews', () => ({
  getReviews: (...args: any[]) => mockGetReviews(...args),
  createReview: (...args: any[]) => mockCreateReview(...args),
  postReviewMessage: vi.fn().mockResolvedValue({}),
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

  it('renders download source and html buttons', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    const sourceBtn = wrapper.find('[aria-label="Download source (.md)"]')
    const htmlBtn = wrapper.find('[aria-label="Download compiled (.html)"]')
    expect(sourceBtn.exists()).toBe(true)
    expect(htmlBtn.exists()).toBe(true)
  })

  it('shows commit hash in metadata row', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    expect(wrapper.text()).toContain('abc123d')
  })

  it('passes commit hash to DownloadButton', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    // DownloadButton should receive commit-hash prop
    const downloadBtns = wrapper.findAllComponents({ name: 'DownloadButton' })
    expect(downloadBtns.length).toBeGreaterThanOrEqual(2)
    for (const btn of downloadBtns) {
      expect(btn.props('commitHash')).toBe('abc123def456')
    }
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

  it('reverts score to old value when API update fails', async () => {
    mockCreateReview.mockRejectedValueOnce(new Error('Network error'))

    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))

    // Set viewer so the review is recognized as "my review"
    const { useUserStore } = await import('../../stores/useUserStore')
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen' } as any

    // Switch to Comments tab to trigger review load
    const buttons = wrapper.findAll('button')
    for (let i = 0; i < buttons.length; i++) {
      if (buttons[i].text().includes('Comments')) {
        await buttons[i].trigger('click')
        break
      }
    }
    await new Promise(r => setTimeout(r, 50))

    // The mock review has originality: 3
    const vm = wrapper.vm as any
    const store = vm.reviewStore
    expect(store).toBeDefined()
    expect(store.reviews.length).toBeGreaterThan(0)
    const review = store.reviews.find((r: any) => r.reviewer_id === 'u1')
    expect(review).toBeDefined()
    expect(review.scores.originality).toBe(3)

    // Call updateSingleScore to change originality from 3 → 5 (API will reject)
    await vm.updateSingleScore('review-1', 'originality', 5)

    // After API rejection, score should revert to 3, not stay at 5
    expect(review.scores.originality).toBe(3)
  })

  // ── Back button regression tests ─────────────────────────────────────

  it('has a back button', async () => {
    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))
    const backBtn = wrapper.find('button[aria-label="Back"]')
    expect(backBtn.exists()).toBe(true)
  })

  it('back button triggers goBack handler', async () => {
    mockPush.mockClear()
    mockBack.mockClear()

    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))

    // Trigger goBack via button click
    const backBtn = wrapper.find('button[aria-label="Back"]')
    expect(backBtn.exists()).toBe(true)
    await backBtn.trigger('click')
    await new Promise(r => setTimeout(r, 50))

    // Default mode (not Tauri) should use router.back()
    // In test environment, isTauri defaults to false
    expect(mockBack).toHaveBeenCalled()
    expect(mockPush).not.toHaveBeenCalled()
  })

  // Regression: goBack must use router.back() so UserPage → ArticlePage → Back
  // returns to UserPage, not Home. HistoryPage loop was fixed separately.
  it('goBack uses router.back() preserving navigation origin', async () => {
    mockPush.mockClear()
    mockBack.mockClear()

    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))

    const vm = wrapper.vm as any
    vm.goBack()
    await new Promise(r => setTimeout(r, 50))

    // Must use router.back() — must NOT use router.push('/')
    expect(mockBack).toHaveBeenCalled()
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('shows merge error message when merge proposal fails', async () => {
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
    mockCreateMergeProposal.mockRejectedValueOnce(new Error('Merge failed'))

    const ArticlePage = (await import('../ArticlePage.vue')).default
    const wrapper = mount(ArticlePage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 100))

    const { useUserStore } = await import('../../stores/useUserStore')
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen' } as any

    const mergeBtn = wrapper.find('button[aria-label="Propose merge"]')
    expect(mergeBtn.exists()).toBe(true)
    await mergeBtn.trigger('click')
    await new Promise(r => setTimeout(r, 50))

    // Should show error message to user
    expect(wrapper.text()).toMatch(/Merge proposal failed|merge.*failed/i)
  })
})
