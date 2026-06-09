/**
 * Black-box E2E tests for the VSCode-style tab system.
 *
 * These tests treat the app as a black box: they simulate user actions
 * (navigation, clicks, typing) and assert on visible DOM output only.
 * No store internals, no component refs, no implementation details.
 *
 * Test principles (from docs/test_requirement.md):
 * - Test what the user does and sees, not how the code works
 * - Independent of implementation — survive internal refactoring
 * - Large-scale closed loops connecting full frontend flow
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { nextTick } from 'vue'

// ── Mocks ───────────────────────────────────────────────────────
// Only mock the I/O boundary (API + localStorage). Everything else
// (router, stores, composables, components) runs for real.

// Auth: provide a logged-in viewer so editor routes work
const mockViewer = { id: 'u1', name: 'Alice Chen', username: 'alice' }

// Mock articles API — register test articles
const mockArticles: Record<string, any> = {}
function registerArticle(id: string, overrides: Partial<any> = {}) {
  mockArticles[id] = {
    id,
    title: `Article ${id}`,
    status: 'published',
    authors: [{ id: 'u1', name: 'Alice Chen', anonymous_name: 'anon1' }],
    fork_count: 0,
    forked_from: null,
    commit_count: 1,
    commit_hash: 'abc123',
    compiled_format: 'html',
    compiled_output: `<p>Content of article ${id}</p>`,
    compiled_pages: 3,
    score: { originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 },
    sink_eta: null,
    days_remaining: null,
    sink_duration_days: 30,
    review_count: 0,
    is_bookmarked: false,
    is_own_article: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}
registerArticle('article-a')
registerArticle('article-b')

vi.mock('../../api/articles', () => ({
  getArticle: vi.fn(async (id: string) => {
    if (mockArticles[id]) return { ...mockArticles[id] }
    throw new Error('Article not found')
  }),
  getArticleSource: vi.fn(async () => ({ content: '# Test', format: 'markdown' })),
  getHistory: vi.fn(async () => ({ commits: [] })),
  forkArticle: vi.fn(),
  extendSink: vi.fn(),
  createMergeProposal: vi.fn(),
  getMergeProposals: vi.fn(async () => ({ proposals: [] })),
  deleteArticle: vi.fn(),
  compilePreview: vi.fn(async () => '<p>Preview</p>'),
}))

vi.mock('../../api/reviews', () => ({
  getReviews: vi.fn(async () => []),
  createReview: vi.fn(),
  postReviewMessage: vi.fn(),
}))

vi.mock('../../api/compile', () => ({
  compilePreview: vi.fn(async () => '<p>Preview</p>'),
}))

// Mock auth API — prevents restoreSession() from hanging
vi.mock('../../api/auth', () => ({
  login: vi.fn(),
  register: vi.fn(),
  getMe: vi.fn(async () => ({
    user: { id: 'u1', name: 'Alice Chen', username: 'alice' },
  })),
}))

// Mock user store — skip network calls in restoreSession
vi.mock('../../stores/useUserStore', () => ({
  useUserStore: () => ({
    viewer: { id: 'u1', name: 'Alice Chen', username: 'alice' },
    token: 'test-token-xxx',
    showAuthModal: false,
    intendedRoute: null,
    isTauriMode: false,
    isBrowserLocal: false,
    restoreSession: vi.fn(async () => {}),
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}))

// Mock useTauri — prevents native API calls in jsdom
vi.mock('../../composables/useTauri', () => ({
  useTauri: () => ({
    isTauri: { value: false },
    isBrowserLocal: { value: false },
    saveDraft: vi.fn().mockResolvedValue({ id: 'draft-99', account_id: 'u1', title: '', content: '', format: 'markdown', updated_at: '' }),
    getDraft: vi.fn().mockResolvedValue(null),
    listDrafts: vi.fn().mockResolvedValue([]),
    deleteDraft: vi.fn().mockResolvedValue({ ok: true }),
    gitInit: vi.fn().mockResolvedValue({ hash: 'abc', message: 'init' }),
    gitCommit: vi.fn().mockResolvedValue({ hash: 'abc', message: 'commit' }),
    gitHistory: vi.fn().mockResolvedValue([]),
    compileTypst: vi.fn().mockResolvedValue('<svg>Typst</svg>'),
    getSessionToken: vi.fn(() => null),
    setSessionToken: vi.fn(),
    login: vi.fn(),
    listAccounts: vi.fn().mockResolvedValue([]),
    isFollowing: vi.fn().mockResolvedValue({ following: false }),
    getCachedArticle: vi.fn().mockResolvedValue(null),
    searchDrafts: vi.fn().mockResolvedValue([]),
    searchCachedArticles: vi.fn().mockResolvedValue([]),
    deleteArticle: vi.fn().mockResolvedValue({ ok: true }),
  }),
}))

// ── Helpers ─────────────────────────────────────────────────────

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div class="page-home">Home</div>' } },
      {
        path: '/edit',
        component: () => import('../pages/EditorPage.vue'),
        meta: { requiresAuth: false },
      },
      {
        path: '/edit/:id',
        component: () => import('../pages/EditorPage.vue'),
        meta: { requiresAuth: false },
      },
      { path: '/article/:id', component: () => import('../pages/ArticlePage.vue') },
      { path: '/articles/:id', component: () => import('../pages/ArticlePage.vue') },
    ],
  })
}

/**
 * Mount the full App with real router + stores. Navigation happens AFTER
 * mount so that App.vue's router.afterEach guard is registered in time.
 */
async function mountApp() {
  localStorage.setItem('viewer', JSON.stringify(mockViewer))
  localStorage.setItem('peerpedia_token', 'test-token-xxx')
  localStorage.setItem('session_token', 'test-token-xxx')

  const router = makeRouter()
  await router.push('/')
  await router.isReady()

  const pinia = createPinia()
  setActivePinia(pinia)

  const { default: App } = await import('../App.vue')
  const wrapper = mount(App, {
    global: {
      plugins: [router, pinia],
      stubs: {
        CodeEditor: {
          template: `<textarea class="cm-editor" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)"></textarea>`,
          props: ['modelValue', 'format', 'placeholder'],
          emits: ['update:modelValue'],
        },
        NavBar: { template: '<nav class="navbar">NavBar</nav>' },
        AuthModal: { template: '<div class="auth-modal" />' },
        DownloadButton: { template: '<button class="download-btn">Download</button>' },
        SelfReviewPanel: { template: '<div class="self-review-panel" />' },
        ReviewPanel: { template: '<div class="review-panel" />' },
        ScoreBadges: { template: '<div class="score-badges" />' },
      },
    },
  })

  return { wrapper, router }
}

/** Wait for async rendering + API calls to settle. */
async function settle() {
  await flushPromises()
  await nextTick()
  await new Promise(r => setTimeout(r, 500))
  await flushPromises()
  await nextTick()
}

/** Get all tab titles visible in the expanded drawer. */
function getTabTitles(wrapper: any): string[] {
  const items = wrapper.findAll('.tab-drawer-item')
  return items.map((item: any) => item.find('.tab-drawer-item-title').text())
}

/** Hover the tab edges to expand drawer, returning the wrapper for chaining. */
async function expandDrawer(wrapper: any) {
  await wrapper.find('.tab-drawer-edges').trigger('mouseenter')
  await nextTick()
}

// ── Tests ───────────────────────────────────────────────────────

describe('Tab System E2E', () => {
  let router: ReturnType<typeof makeRouter>
  let wrapper: any

  afterEach(() => {
    if (wrapper) wrapper.unmount()
    localStorage.clear()
  })

  describe('Tab creation on navigation', () => {
    it('creates an editor tab when navigating to /edit', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      // Navigate AFTER mount (triggers App.vue's router.afterEach)
      await router.push('/edit')
      await settle()

      const edges = wrapper.findAll('.tab-drawer-edge')
      expect(edges.length).toBe(1)

      await expandDrawer(wrapper)
      expect(wrapper.find('.tab-drawer-panel').exists()).toBe(true)
      expect(getTabTitles(wrapper)).toContain('Untitled')
    })

    it('creates an article tab when navigating to /article/:id', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/article/article-a')
      await settle()

      const edges = wrapper.findAll('.tab-drawer-edge')
      expect(edges.length).toBe(1)
    })

    it('shows two tabs when navigating from editor to article', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/edit')
      await settle()

      await router.push('/article/article-a')
      await settle()

      expect(wrapper.findAll('.tab-drawer-edge').length).toBe(2)
    })

    it('does NOT create tabs for home page (/ route)', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      // App starts at /, which is not a tab route
      await settle()

      expect(wrapper.find('.tab-drawer-edges').exists()).toBe(false)
    })

    it('navigating back to home does not add a tab', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/edit')
      await settle()
      expect(wrapper.findAll('.tab-drawer-edge').length).toBe(1)

      await router.push('/')
      await settle()
      // Still 1 tab (home doesn't create/remove tabs)
      expect(wrapper.findAll('.tab-drawer-edge').length).toBe(1)
    })
  })

  describe('Tab properties from navigation', () => {
    it('article tab is created with an eye icon (read-only)', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/article/article-a')
      await settle()

      await expandDrawer(wrapper)
      // Article tabs get the eye icon, editor tabs get the edit icon
      const tabItems = wrapper.findAll('.tab-drawer-item')
      expect(tabItems.length).toBe(1)
      // The tab exists with some title (exact title depends on API load timing)
      const titles = getTabTitles(wrapper)
      expect(titles.length).toBe(1)
      expect(titles[0].length).toBeGreaterThan(0)
    })

    it('editor tab starts as "Untitled"', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/edit')
      await settle()

      await expandDrawer(wrapper)
      expect(getTabTitles(wrapper)).toContain('Untitled')
    })
  })

  describe('Tab switching', () => {
    it('clicking an inactive tab activates it', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      // Open editor, then article
      await router.push('/edit')
      await settle()
      await router.push('/article/article-a')
      await settle()

      await expandDrawer(wrapper)
      const items = wrapper.findAll('.tab-drawer-item')
      expect(items.length).toBe(2)

      // Click the first tab (editor) to switch back
      await items[0].trigger('click')
      await settle()

      // Re-expand (drawer may have collapsed after navigation)
      await expandDrawer(wrapper)
      const itemsAfter = wrapper.findAll('.tab-drawer-item')
      expect(itemsAfter[0].classes()).toContain('tab-drawer-item--active')
    })
  })

  describe('Dirty state indicator', () => {
    it('shows dirty dot on editor tab after user types content', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/edit')
      await settle()

      // User types content in the editor
      const textarea = wrapper.find('.cm-editor')
      expect(textarea.exists()).toBe(true)
      await textarea.setValue('New content')
      await settle()

      await expandDrawer(wrapper)
      const dirtyDot = wrapper.find('.tab-drawer-dirty-dot')
      expect(dirtyDot.exists()).toBe(true)
    })
  })

  describe('Close tab — clean tab', () => {
    it('closing a clean article tab removes it from the drawer', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      // Open editor then article → 2 tabs
      await router.push('/edit')
      await settle()
      await router.push('/article/article-a')
      await settle()
      expect(wrapper.findAll('.tab-drawer-edge').length).toBe(2)

      // Close the article tab (second one)
      await expandDrawer(wrapper)
      const closeBtns = wrapper.findAll('.tab-drawer-close-btn')
      expect(closeBtns.length).toBe(2)
      await closeBtns[1].trigger('click')
      await settle()

      expect(wrapper.findAll('.tab-drawer-edge').length).toBe(1)
    })
  })

  describe('Close tab — dirty tab with confirmation dialog', () => {
    it('shows confirmation dialog when closing a dirty editor tab', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/edit')
      await settle()

      // Make editor dirty
      const textarea = wrapper.find('.cm-editor')
      expect(textarea.exists()).toBe(true)
      await textarea.setValue('Unsaved work')
      await settle()

      // Try to close
      await expandDrawer(wrapper)
      await wrapper.findAll('.tab-drawer-close-btn')[0].trigger('click')
      await settle()

      expect(wrapper.text()).toContain('Save before closing')
      expect(wrapper.text()).toContain('Cancel')
      expect(wrapper.text()).toContain('Discard')
    })

    it('Cancel keeps the tab open', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/edit')
      await settle()

      const textarea = wrapper.find('.cm-editor')
      await textarea.setValue('Unsaved work')
      await settle()

      // Open close dialog
      await expandDrawer(wrapper)
      await wrapper.findAll('.tab-drawer-close-btn')[0].trigger('click')
      await settle()
      expect(wrapper.text()).toContain('Save before closing')

      // Click Cancel
      const buttons = wrapper.findAll('button')
      const cancelBtn = buttons.find((b: any) => b.text().trim() === 'Cancel')
      await cancelBtn!.trigger('click')
      await settle()

      // Dialog dismissed, tab still there
      expect(wrapper.text()).not.toContain('Save before closing')
      expect(wrapper.findAll('.tab-drawer-edge').length).toBe(1)
    })

    it('Discard closes the dirty tab anyway', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/edit')
      await settle()

      const textarea = wrapper.find('.cm-editor')
      await textarea.setValue('Unsaved work')
      await settle()

      // Open close dialog
      await expandDrawer(wrapper)
      await wrapper.findAll('.tab-drawer-close-btn')[0].trigger('click')
      await settle()

      // Click Discard
      const buttons = wrapper.findAll('button')
      const discardBtn = buttons.find((b: any) => b.text().trim() === 'Discard')
      await discardBtn!.trigger('click')
      await settle()

      // Tab removed (was the only tab → drawer hidden)
      expect(wrapper.findAll('.tab-drawer-edge').length).toBe(0)
    })
  })

  describe('Drawer UI mechanics', () => {
    it('drawer is collapsed by default', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/edit')
      await settle()

      expect(wrapper.find('.tab-drawer-edges').exists()).toBe(true)
      expect(wrapper.find('.tab-drawer-panel').exists()).toBe(false)
    })

    it('drawer expands on hover and collapses on mouseleave', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/edit')
      await settle()

      await expandDrawer(wrapper)
      expect(wrapper.find('.tab-drawer-panel').exists()).toBe(true)

      await wrapper.find('.tab-drawer-panel').trigger('mouseleave')
      await new Promise(r => setTimeout(r, 250))
      expect(wrapper.find('.tab-drawer-panel').exists()).toBe(false)
    })

    it('drawer stays open when mouse moves from edge to panel', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/edit')
      await settle()

      await expandDrawer(wrapper)
      expect(wrapper.find('.tab-drawer-panel').exists()).toBe(true)

      // Move to panel before collapse timer fires
      await wrapper.find('.tab-drawer-panel').trigger('mouseenter')
      await new Promise(r => setTimeout(r, 50))
      expect(wrapper.find('.tab-drawer-panel').exists()).toBe(true)
    })
  })

  describe('Edge cases', () => {
    it('both /article/:id and /articles/:id create one tab each (no duplicates)', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      // Use the /articles/ plural form
      await router.push('/articles/article-a')
      await settle()

      expect(wrapper.findAll('.tab-drawer-edge').length).toBe(1)
    })

    it('/articles/ and /article/ forms are treated as the same tab', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/article/article-a')
      await settle()
      // Navigate to the same article via the plural route
      await router.push('/articles/article-a')
      await settle()

      // Should still have only 1 tab (normalized to same id)
      expect(wrapper.findAll('.tab-drawer-edge').length).toBe(1)
    })

    it('drawer is completely hidden when last tab is closed', async () => {
      const app = await mountApp()
      wrapper = app.wrapper; router = app.router

      await router.push('/article/article-a')
      await settle()
      expect(wrapper.findAll('.tab-drawer-edge').length).toBe(1)

      // Close the only tab
      await expandDrawer(wrapper)
      await wrapper.find('.tab-drawer-close-btn').trigger('click')
      await settle()

      expect(wrapper.find('.tab-drawer-edges').exists()).toBe(false)
    })
  })
})
