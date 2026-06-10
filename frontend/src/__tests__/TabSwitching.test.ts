/**
 * Tab Switching — Behavior Specification
 *
 * These tests define the EXPECTED BEHAVIOR of tab switching.
 * They are the specification. If code fails these, the code is wrong.
 *
 * Principle (docs/test_requirement.md):
 * - Tests describe what the user sees and does
 * - Tests are locked once written — code must conform
 * - If code errors, assume code is the problem
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, useRoute } from 'vue-router'
import { nextTick } from 'vue'
import { useTabStore } from '../stores/useTabStore'

// ── Mocks (I/O boundary only) ───────────────────────────────────

vi.mock('@/api/articles', () => ({
  getArticle: vi.fn(async () => ({ id: 'x', title: 'Test', status: 'published', authors: [], fork_count: 0, forked_from: null, commit_count: 1, commit_hash: 'abc', compiled_format: 'html', compiled_output: '<p>x</p>', compiled_pages: 1, score: {}, sink_eta: null, days_remaining: null, sink_duration_days: 30, review_count: 0, is_bookmarked: false, is_own_article: false, created_at: '', updated_at: '' })),
  getArticleSource: vi.fn(async () => ({ content: '#', format: 'markdown' })),
  getHistory: vi.fn(async () => ({ commits: [] })), forkArticle: vi.fn(), extendSink: vi.fn(),
  createMergeProposal: vi.fn(), getMergeProposals: vi.fn(async () => ({ proposals: [] })),
  deleteArticle: vi.fn(), compilePreview: vi.fn(async () => '<p>P</p>'),
}))
vi.mock('@/api/reviews', () => ({ getReviews: vi.fn(async () => []), createReview: vi.fn(), postReviewMessage: vi.fn() }))
vi.mock('@/api/compile', () => ({ compilePreview: vi.fn(async () => '<p>P</p>') }))
vi.mock('@/api/auth', () => ({ login: vi.fn(), register: vi.fn(), getMe: vi.fn(async () => ({ user: {} })) }))
vi.mock('@/stores/useUserStore', () => ({
  useUserStore: () => ({ viewer: { id: 'u1', name: 'A' }, token: 'x', showAuthModal: false, intendedRoute: null,
    isTauriMode: false, isBrowserLocal: false, restoreSession: vi.fn(async () => {}), login: vi.fn(), register: vi.fn(), logout: vi.fn() }),
}))
vi.mock('@/composables/useTauri', () => ({
  useTauri: () => ({ isTauri: { value: false }, isBrowserLocal: { value: false }, saveDraft: vi.fn(), getDraft: vi.fn().mockResolvedValue(null), listDrafts: vi.fn().mockResolvedValue([]), deleteDraft: vi.fn(), gitInit: vi.fn(), gitCommit: vi.fn(), gitHistory: vi.fn().mockResolvedValue([]), compileTypst: vi.fn(), getSessionToken: vi.fn(() => null), setSessionToken: vi.fn(), login: vi.fn(), listAccounts: vi.fn().mockResolvedValue([]), isFollowing: vi.fn(), getCachedArticle: vi.fn().mockResolvedValue(null), searchDrafts: vi.fn().mockResolvedValue([]), searchCachedArticles: vi.fn().mockResolvedValue([]), deleteArticle: vi.fn() }),
}))

// ── Simple route components with identifiable content ────────────
// Use /edit routes (which the tab system recognizes) but with simple
// components that render distinct text, avoiding EditorPage complexity.

const PageA = {
  template: '<div class="page-a"><h1>Page A Content</h1><textarea class="cm-editor"></textarea></div>',
  setup() { useTabStore().ensureTab('editor', useRoute().path) },
}
const PageB = {
  template: '<div class="page-b"><h1>Page B Content</h1><textarea class="cm-editor"></textarea></div>',
  setup() { useTabStore().ensureTab('editor', useRoute().path) },
}

// ── Helpers ─────────────────────────────────────────────────────

async function makeRouter() {
  const r = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>Home</div>' } },
      { path: '/edit/a', component: PageA, meta: { requiresAuth: false } },
      { path: '/edit/b', component: PageB, meta: { requiresAuth: false } },
    ],
  })
  await r.push('/')
  await r.isReady()
  return r
}

async function mountApp() {
  localStorage.clear()
  localStorage.setItem('viewer', JSON.stringify({ id: 'u1', name: 'A' }))
  localStorage.setItem('peerpedia_token', 'x')

  const router = await makeRouter()
  const pinia = createPinia()
  setActivePinia(pinia)

  const { default: App } = await import('../App.vue')
  const wrapper = mount(App, {
    global: {
      plugins: [router, pinia],
      stubs: {
        NavBar: { template: '<nav>Nav</nav>' },
        AuthModal: { template: '<div />' },
        CodeEditor: { template: '<textarea class="cm-editor"></textarea>', props: ['modelValue'], emits: ['update:modelValue'] },
      },
    },
  })

  return { wrapper, router }
}

async function settle() {
  await flushPromises()
  await nextTick()
  await new Promise(r => setTimeout(r, 300))
  await flushPromises()
}

/** Get text of all expanded tab titles. */
function tabTitles(w: any): string[] {
  const items = w.findAll('.tab-drawer-item')
  return items.map((i: any) => i.find('.tab-drawer-item-title').text())
}

/** Hover edges to expand drawer. */
async function expand(w: any) {
  await w.find('.tab-drawer-edges').trigger('mouseenter')
  await nextTick()
}

// ═════════════════════════════════════════════════════════════════
// SPECIFICATION: Tab Switching Behavior
// ═════════════════════════════════════════════════════════════════

describe('Tab Switching Specification', () => {
  let wrp: any, rou: any
  afterEach(() => { if (wrp) wrp.unmount() })

  // ── Spec 1: Opening a page creates a tab ──────────────────────

  it('SPEC-1: navigating to /edit/a creates a tab in the drawer', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    await rou.push('/edit/a')
    await settle()

    // User sees: left edge has 1 tab
    const edges = wrp.findAll('.tab-drawer-edge')
    expect(edges.length).toBe(1)
  })

  // ── Spec 2: Opening a second page creates a second tab ────────

  it('SPEC-2: navigating to /edit/b adds a second tab', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    await rou.push('/edit/a')
    await settle()
    await rou.push('/edit/b')
    await settle()

    // User sees: 2 tab edges
    expect(wrp.findAll('.tab-drawer-edge').length).toBe(2)
  })

  // ── Spec 3: Clicking a tab switches the view ──────────────────

  it('SPEC-3: clicking tab A in drawer switches view to page A', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    // Open page A then page B (B is now active)
    await rou.push('/edit/a')
    await settle()
    await rou.push('/edit/b')
    await settle()

    // Verify we're on page B
    expect(wrp.html()).toContain('Page B Content')
    expect(wrp.html()).not.toContain('Page A Content')

    // User clicks tab A in the drawer
    await expand(wrp)
    const items = wrp.findAll('.tab-drawer-item')
    expect(items.length).toBe(2)
    // First tab is /edit/a, second is /edit/b
    await items[0].trigger('click')
    await settle()

    // User sees: page A content is visible, page B is not
    expect(wrp.html()).toContain('Page A Content')
    expect(wrp.html()).not.toContain('Page B Content')
  })

  // ── Spec 4: Clicking back to tab B restores page B ────────────

  it('SPEC-4: after switching to A, clicking tab B switches back to B', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    // Open both pages, switch to A
    await rou.push('/edit/a')
    await settle()
    await rou.push('/edit/b')
    await settle()

    // Switch to A
    await expand(wrp)
    let items = wrp.findAll('.tab-drawer-item')
    await items[0].trigger('click')
    await settle()
    expect(wrp.html()).toContain('Page A Content')

    // User clicks tab B
    await expand(wrp)
    items = wrp.findAll('.tab-drawer-item')
    await items[1].trigger('click')
    await settle()

    // User sees: page B content is visible again
    expect(wrp.html()).toContain('Page B Content')
    expect(wrp.html()).not.toContain('Page A Content')
  })

  // ── Spec 5: Active tab is visually highlighted ────────────────

  it('SPEC-5: active tab has active styling, inactive tabs do not', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    await rou.push('/edit/a')
    await settle()
    await rou.push('/edit/b')
    await settle()

    await expand(wrp)
    const items = wrp.findAll('.tab-drawer-item')
    expect(items.length).toBe(2)

    // Tab B is active (last navigated), Tab A is not
    expect(items[0].classes()).not.toContain('tab-drawer-item--active')
    expect(items[1].classes()).toContain('tab-drawer-item--active')

    // Click tab A → A becomes active
    await items[0].trigger('click')
    await settle()
    await expand(wrp)
    const items2 = wrp.findAll('.tab-drawer-item')
    expect(items2[0].classes()).toContain('tab-drawer-item--active')
    expect(items2[1].classes()).not.toContain('tab-drawer-item--active')
  })

  // ── Spec 6: Tab drawer shows correct tab count ────────────────

  it('SPEC-6: drawer header shows the number of open tabs', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    await rou.push('/edit/a')
    await settle()
    await rou.push('/edit/b')
    await settle()

    await expand(wrp)
    // The count badge is in the header
    const header = wrp.find('.tab-drawer-header')
    expect(header.exists()).toBe(true)
    const spans = header.findAll('span')
    // Last span is the count pill
    const count = spans[spans.length - 1].text()
    expect(count).toBe('2')
  })

  // ── Spec 7: Closing active tab → navigates to neighbor ────────

  it('SPEC-7: closing the active tab navigates to the remaining tab', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    await rou.push('/edit/a')
    await settle()
    await rou.push('/edit/b')
    await settle()

    // Two tabs exist, B is active
    expect(wrp.findAll('.tab-drawer-edge').length).toBe(2)
    expect(wrp.html()).toContain('Page B Content')

    // Close tab B (the active one)
    await expand(wrp)
    const closeBtns = wrp.findAll('.tab-drawer-close-btn')
    await closeBtns[1].trigger('click') // Close B
    await settle()

    // User sees: tab B removed, navigated to tab A
    expect(wrp.findAll('.tab-drawer-edge').length).toBe(1)
    expect(wrp.html()).toContain('Page A Content')
  })

  // ── Spec 8: Tabs persist across the drawer collapse/expand ────

  it('SPEC-8: tab titles are correct when drawer is re-expanded', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    await rou.push('/edit/a')
    await settle()
    await rou.push('/edit/b')
    await settle()

    // First expand → check titles
    await expand(wrp)
    const titles1 = tabTitles(wrp)
    expect(titles1.length).toBe(2)

    // Collapse
    await wrp.find('.tab-drawer-panel').trigger('mouseleave')
    await new Promise(r => setTimeout(r, 250))

    // Re-expand → titles should be the same
    await expand(wrp)
    const titles2 = tabTitles(wrp)
    expect(titles2).toEqual(titles1)
  })
})
