/**
 * Tab Identity — Behavior Specification
 *
 * When switching between tabs, each tab must retain its own identity
 * (title, content). Switching must not cause tab titles to merge or
 * overwrite each other.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import { nextTick } from 'vue'

// ── Mocks (I/O boundary only) ───────────────────────────────────

// Use @/ alias — ../../ from src/__tests__/ resolves differently than ../ from src/stores/.
// @/ always resolves to src/, matching the store's import resolution.
vi.mock('@/api/articles', () => ({
  getArticle: vi.fn(async (id: string) => ({ id, title: 'Loaded-'+id, status: 'published', authors: [], fork_count: 0, forked_from: null, commit_count: 1, commit_hash: 'abc', compiled_format: 'html', compiled_output: '<p>'+id+'</p>', compiled_pages: 1, score: {}, sink_eta: null, days_remaining: null, sink_duration_days: 30, review_count: 0, is_bookmarked: false, is_own_article: false, created_at: '', updated_at: '' })),
  getArticles: vi.fn(async () => ({ articles: [], total: 0 })),
  getArticleSource: vi.fn(async () => ({ content: '#', format: 'markdown' })),
  getHistory: vi.fn(async () => ({ commits: [] })), createArticle: vi.fn(), updateArticle: vi.fn(),
  forkArticle: vi.fn(), extendSink: vi.fn(), createMergeProposal: vi.fn(),
  getMergeProposals: vi.fn(async () => ({ proposals: [] })), deleteArticle: vi.fn(),
  compilePreview: vi.fn(async () => '<p>P</p>'), getDiff: vi.fn(), rollbackArticle: vi.fn(),
  getCitations: vi.fn(), acceptMergeProposal: vi.fn(), rejectMergeProposal: vi.fn(),
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

// ── Helpers ─────────────────────────────────────────────────────

async function makeRouter() {
  const r = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>Home</div>' } },
      // Use real EditorPage so useEditorTab composable is active
      { path: '/edit', component: () => import('../pages/EditorPage.vue'), meta: { requiresAuth: false } },
      { path: '/edit/:id', component: () => import('../pages/EditorPage.vue'), meta: { requiresAuth: false } },
      { path: '/article/:id', component: () => import('../pages/ArticlePage.vue') },
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
        CodeEditor: {
          template: '<textarea class="cm-editor" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
          props: ['modelValue', 'format', 'placeholder'],
          emits: ['update:modelValue'],
        },
        DownloadButton: { template: '<button />' },
        SelfReviewPanel: { template: '<div />' },
        ReviewPanel: { template: '<div />' },
        ScoreBadges: { template: '<div />' },
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

function tabTitles(w: any): string[] {
  const items = w.findAll('.tab-drawer-item')
  return items.map((i: any) => i.find('.tab-drawer-item-title').text())
}

function activeTabTitle(w: any): string | null {
  const items = w.findAll('.tab-drawer-item')
  for (const item of items) {
    if (item.classes().includes('tab-drawer-item--active')) {
      return item.find('.tab-drawer-item-title').text()
    }
  }
  return null
}

async function expand(w: any) {
  await w.find('.tab-drawer-edges').trigger('mouseenter')
  await nextTick()
}

// ═════════════════════════════════════════════════════════════════
// SPECIFICATION: Tab Identity
// ═════════════════════════════════════════════════════════════════

describe('Tab Identity Specification', () => {
  let wrp: any, rou: any
  afterEach(() => { if (wrp) wrp.unmount() })

  // ── IDENTITY-1: Two editor tabs get distinct titles ───────────

  it('IDENTITY-1: two editor tabs show distinct titles after loading', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    // Open editor for article-1 (title loaded from mocked article store)
    await rou.push('/edit/article-1')
    await settle()

    // Open editor for article-2
    await rou.push('/edit/article-2')
    await settle()

    // Two tabs exist
    await expand(wrp)
    const titles = tabTitles(wrp)
    expect(titles.length).toBe(2)
    // Titles must be distinct (Loaded-article-1 vs Loaded-article-2)
    expect(titles[0]).not.toBe(titles[1])
  })

  // ── IDENTITY-2: Switch away and back — title persists ──────────

  it('IDENTITY-2: tab title persists after switching away and back', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    await rou.push('/edit/article-1')
    await settle()
    await rou.push('/edit/article-2')
    await settle()

    // Record title of tab A
    await expand(wrp)
    const titleABefore = tabTitles(wrp)[0]

    // Switch to tab A, then back to tab B
    await wrp.findAll('.tab-drawer-item')[0].trigger('click')  // → A
    await settle()
    await expand(wrp)
    await wrp.findAll('.tab-drawer-item')[1].trigger('click')  // → B
    await settle()

    // Tab A must still show its original title
    await expand(wrp)
    expect(tabTitles(wrp)[0]).toBe(titleABefore)
  })

  // ── IDENTITY-3: Both titles survive round-trip switching ──────

  it('IDENTITY-3: round-trip switching preserves both titles', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    await rou.push('/edit/article-1')
    await settle()
    await rou.push('/edit/article-2')
    await settle()

    await expand(wrp)
    const before = tabTitles(wrp)

    // B→A→B→A→B
    for (let i = 0; i < 2; i++) {
      await wrp.findAll('.tab-drawer-item')[0].trigger('click')
      await settle()
      await expand(wrp)
      await wrp.findAll('.tab-drawer-item')[1].trigger('click')
      await settle()
    }

    await expand(wrp)
    const after = tabTitles(wrp)
    expect(after.length).toBe(2)
    expect(after[0]).toBe(before[0])
    expect(after[1]).toBe(before[1])
    expect(after[0]).not.toBe(after[1])
  })

  // ── IDENTITY-4: Content preserved across switches ─────────────

  it('IDENTITY-4: editor content is preserved when switching tabs', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    await rou.push('/edit/article-1')
    await settle()
    await wrp.find('.cm-editor').setValue('Content for A')
    await settle()

    await rou.push('/edit/article-2')
    await settle()
    await wrp.find('.cm-editor').setValue('Content for B')
    await settle()

    // Content is B
    expect((wrp.find('.cm-editor').element as HTMLTextAreaElement).value).toBe('Content for B')

    // Switch to A
    await expand(wrp)
    await wrp.findAll('.tab-drawer-item')[0].trigger('click')
    await settle()

    // Content must be A — NOT B
    expect((wrp.find('.cm-editor').element as HTMLTextAreaElement).value).toBe('Content for A')
  })

  // ── IDENTITY-5: Three editor tabs, switch many times, titles never merge ─

  it('IDENTITY-5: three editor tabs with different titles never merge after multiple switches', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    // Open three editor tabs, each loads a distinct title from API
    await rou.push('/edit/article-1')
    await settle()
    await rou.push('/edit/article-2')
    await settle()
    await rou.push('/edit/article-3')
    await settle()

    // Verify three tabs exist with three distinct titles
    await expand(wrp)
    const t0 = tabTitles(wrp)
    expect(t0.length).toBe(3)
    expect(new Set(t0).size).toBe(3) // all distinct

    // Record the initial titles
    const initial = [...t0]

    // Switch pattern: 3→1→2→3→1→2→3 (many round trips)
    for (const idx of [0, 1, 2, 0, 1, 2]) {
      await expand(wrp)
      const items = wrp.findAll('.tab-drawer-item')
      await items[idx].trigger('click')
      await settle()
    }

    // After all switching, three tabs must still be distinct and correct
    await expand(wrp)
    const final = tabTitles(wrp)
    expect(final.length).toBe(3)
    expect(final).toEqual(initial)       // each tab kept its title
    expect(new Set(final).size).toBe(3)   // all still distinct
  })

  // ── IDENTITY-6: Three ARTICLE tabs, switch, titles never merge ──

  it('IDENTITY-6: three article tabs with different titles never merge after switching', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    // Open three article pages
    await rou.push('/article/art-a')
    await settle()
    await rou.push('/article/art-b')
    await settle()
    await rou.push('/article/art-c')
    await settle()

    await expand(wrp)
    const initial = tabTitles(wrp)
    expect(initial.length).toBe(3)

    // Switch 3→1→2→3 many times
    for (const idx of [0, 1, 2, 0, 1, 2]) {
      await expand(wrp)
      await wrp.findAll('.tab-drawer-item')[idx].trigger('click')
      await settle()
    }

    await expand(wrp)
    const final = tabTitles(wrp)
    expect(final.length).toBe(3)
    // If all titles are distinct, no merge happened
    expect(new Set(final).size).toBe(initial.length)
  })

  // ── IDENTITY-8: Rapid switching before API resolves doesn't mix titles ─

  it('IDENTITY-8: switching tabs rapidly while API is in-flight does not merge titles', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    // Open article A — but switch away BEFORE the settle() completes
    await rou.push('/article/art-a')
    await flushPromises() // let setup + onMounted start, but don't wait for API

    // Rapidly switch to article B
    await rou.push('/article/art-b')
    await flushPromises()

    // Rapidly switch to article C
    await rou.push('/article/art-c')
    await settle() // now wait for everything

    // Then switch back through all of them rapidly
    await expand(wrp)
    const items = wrp.findAll('.tab-drawer-item')
    expect(items.length).toBe(3)

    // Click all three in quick succession (no settle between)
    await items[0].trigger('click')
    await items[1].trigger('click')
    await items[2].trigger('click')
    await items[0].trigger('click')
    await settle()

    // After everything settles, titles must be distinct
    await expand(wrp)
    const final = tabTitles(wrp)
    expect(final.length).toBe(3)
    expect(new Set(final).size).toBe(3)
  })

  // ── IDENTITY-7: Mix editor + article tabs, switch, titles never merge ─

  it('IDENTITY-7: mixing editor and article tabs preserves all titles', async () => {
    const app = await mountApp(); wrp = app.wrapper; rou = app.router

    // Open editor tab
    await rou.push('/edit/article-1')
    await settle()
    // Open article tab
    await rou.push('/article/art-x')
    await settle()
    // Open another editor tab
    await rou.push('/edit/article-2')
    await settle()

    await expand(wrp)
    const initial = tabTitles(wrp)
    expect(initial.length).toBe(3)

    // Switch around 10 times
    for (let i = 0; i < 10; i++) {
      await expand(wrp)
      const items = wrp.findAll('.tab-drawer-item')
      await items[i % 3].trigger('click')
      await settle()
    }

    await expand(wrp)
    const final = tabTitles(wrp)
    // After all switching, every tab must still show its original title
    expect(final).toEqual(initial)
  })
})
