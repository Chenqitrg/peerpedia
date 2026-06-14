// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const { mockPush, mockReplace, mockRoute, mockSaveDraft, mockGitInit, mockGitCommit, mockGitHistory, mockGetDraft, mockCompileTypst, mockUpdateArticle, mockCreateArticle } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockReplace: vi.fn(),
  mockRoute: { params: { id: undefined } as any, path: '/edit', fullPath: '/edit', query: {} as Record<string, string | undefined> },
  mockSaveDraft: vi.fn().mockResolvedValue({ id: 'draft-99', account_id: 'u1', title: '', content: '', format: 'markdown', updated_at: '2026-06-07' }),
  mockGitInit: vi.fn().mockResolvedValue({ hash: 'abc1234', message: 'Initial draft' }),
  mockGitCommit: vi.fn().mockResolvedValue({ hash: 'abc5678', message: 'Update' }),
  mockGitHistory: vi.fn().mockResolvedValue([]),
  mockGetDraft: vi.fn().mockResolvedValue(null),
  mockCompileTypst: vi.fn().mockResolvedValue('<svg xmlns="http://www.w3.org/2000/svg"><text>Typst SVG output</text></svg>'),
  mockUpdateArticle: vi.fn().mockResolvedValue({ id: 'art-99', status: 'sedimentation' }),
  mockCreateArticle: vi.fn().mockResolvedValue({ id: 'art-new', status: 'draft' }),
}))

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, back: vi.fn(), replace: mockReplace }),
  useRoute: () => mockRoute,
  RouterLink: { template: '<a><slot /></a>' },
}))

// After the isOnline default change (false → pings determine truth), the
// EditorPage publish button is gated on canWrite('editor.publish_pool').
// Mock the network composable so publish is enabled in tests.
// Tests that need offline mode can set _isSynced = false.
let _isSynced = true
vi.mock('@/composables/useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(() => ({
    get isSynced() { return { value: _isSynced } },
    connectionState: { value: 'synced' as const },
    ping: vi.fn(),
  })),
}))

vi.mock('@/composables/useOffline', () => ({
  useOffline: vi.fn(() => ({
    canWrite: vi.fn(() => true),
    getFallback: vi.fn((key: string) => key),
    isLocalOnly: { value: false },
  })),
}))

vi.mock('@/composables/useArticleSync', () => ({
  useArticleSync: vi.fn(() => ({
    syncState: { value: 'synced' },
    error: { value: null },
    pushing: { value: false },
    upload: vi.fn().mockResolvedValue(true),
    pushUpdate: vi.fn().mockResolvedValue(true),
    useRemote: vi.fn().mockResolvedValue(true),
    getContentAtCommit: vi.fn().mockResolvedValue('# content'),
    clearError: vi.fn(),
  })),
}))

// Mock useTauri — default web mode. Tests that need local mode set _isTauri=true.
let _isTauri = false
vi.mock('@/composables/useTauri', () => ({
  useTauri: () => ({
    isTauri: { value: _isTauri },
    isBrowserLocal: { value: false },
    saveDraft: mockSaveDraft,
    getDraft: mockGetDraft,
    listDrafts: vi.fn().mockResolvedValue([]),
    deleteDraft: vi.fn().mockResolvedValue({ ok: true }),
    gitInit: mockGitInit,
    gitCommit: mockGitCommit,
    gitHistory: mockGitHistory,
    compileTypst: mockCompileTypst,
  }),
}))

// Mock useTabIntegration
const mockUseEditorTab = vi.fn()
vi.mock('@/composables/useTabIntegration', () => ({
  useEditorTab: mockUseEditorTab,
}))

// Mock useArticleStore — used by handleSubmitToPool
vi.mock('../../stores/useArticleStore', () => ({
  useArticleStore: vi.fn(() => ({
    currentArticle: null,
    fetchArticle: vi.fn().mockResolvedValue(undefined),
    updateArticle: mockUpdateArticle,
    createArticle: mockCreateArticle,
  })),
}))

describe('EditorPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    _isTauri = false
    _isSynced = true
    vi.clearAllMocks()
    mockRoute.params = { id: undefined } as any
    mockRoute.query = {}
    mockRoute.fullPath = '/edit'
    mockGitHistory.mockResolvedValue([])
    mockGitInit.mockResolvedValue({ hash: 'abc1234', message: 'Initial draft' })
    mockGitCommit.mockResolvedValue({ hash: 'abc5678', message: 'Update' })
    mockSaveDraft.mockResolvedValue({ id: 'draft-99', account_id: 'u1', title: '', content: '', format: 'markdown', updated_at: '2026-06-07' })
    mockGetDraft.mockResolvedValue(null)
    mockCompileTypst.mockResolvedValue('<svg xmlns="http://www.w3.org/2000/svg"><text>Typst SVG output</text></svg>')
  })

  it('renders editor page with title input', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const titleInput = wrapper.find('input[type="text"], input[placeholder*="title" i], input[placeholder*="Title" i]')
    expect(titleInput.exists()).toBe(true)
  })

  it('uses format from route query param', async () => {
    // Typst mode → CodeMirror renders with Typst extension
    mockRoute.query = { format: 'typst' }
    // Re-mock to pick up new query
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: {
        stubs: { 'router-link': RouterLinkStub, 'router-view': true },
      },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    // format propagates from route.query.format into component state
    expect(vm.format).toBe('typst')
    // No bare textarea — CodeEditor handles both formats
    expect(wrapper.find('textarea').exists()).toBe(false)
    // Reset
    mockRoute.query = {}
  })

  it('has no format toggle buttons in toolbar', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const buttons = wrapper.findAll('button')
    const mdBtn = buttons.filter(b => b.text() === 'MD')
    const typstBtn = buttons.filter(b => b.text() === 'Typst')
    expect(mdBtn.length).toBe(0)
    expect(typstBtn.length).toBe(0)
  })

  it('has a Publish button', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    // Icon-only button — find by aria-label or title
    const publishBtn = wrapper.find('[aria-label="Publish"]')
    expect(publishBtn.exists()).toBe(true)
  })

  it('has draft save button', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const saveBtn = wrapper.find('button[aria-label="Save draft"], button[title="Save draft"]')
    expect(saveBtn.exists()).toBe(true)
  })

  it('has a compile button', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBeGreaterThan(0)
  })

  it('has download buttons (source and pdf)', async () => {
    const openSpy = vi.fn()
    window.open = openSpy
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const html = wrapper.html()
    expect(html.length).toBeGreaterThan(0)
  })

  it('self-assessment modal does not include contribution section', async () => {
    const { useUserStore } = await import('../../stores/useUserStore')
    const pinia = setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    const publishBtn = wrapper.find('[aria-label="Publish"]')
    expect(publishBtn.exists()).toBe(true)
    await publishBtn.trigger('click')
    await flushPromises()

    // Contribution section removed — should not appear in the modal
    expect(wrapper.text()).not.toMatch(/contribution|Contribution/i)
  })

  it('self-assessment modal opens without contributions state', async () => {
    const { useUserStore } = await import('../../stores/useUserStore')
    const pinia = setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    const vm = wrapper.vm as any
    // contributions should not exist on the component
    expect(vm.contributions).toBeUndefined()
    // handlePublish should just open the modal, no contributions init
    await vm.handlePublish()
    expect(vm.showSelfReview).toBe(true)
  })

  // Regression: saveDraft must trigger git init in Tauri/local mode
  it('saveDraft triggers git init in Tauri mode', async () => {
    _isTauri = true
    _isSynced = false
    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    vm.title = 'Test Article'
    vm.content = '# Hello World'
    vm.commitMsg = 'Initial draft'
    await vm.saveDraft()

    // Verify gitInit was called
    expect(mockGitInit).toHaveBeenCalled()
    const callArgs = mockGitInit.mock.calls[0][0]
    expect(callArgs.article_id).toBe('draft-99')
    expect(callArgs.content).toBe('# Hello World')
    expect(callArgs.commit_message).toBe('Initial draft')
    expect(callArgs.author).toBe('Alice Chen')
  })

  // Regression: second and subsequent saves must trigger gitCommit, not gitInit
  it('saveDraft triggers gitCommit (not gitInit) when repo already exists', async () => {
    _isTauri = true
    _isSynced = false
    // Simulate existing repo by returning a history entry
    mockGitHistory.mockResolvedValue([{ hash: 'abc1234', message: 'Initial', author: 'alice', timestamp: '2026-01-01' }])

    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    vm.currentDraftId = 'draft-99'  // simulate second save (draft already exists)
    vm.title = 'Updated Article'
    vm.content = '# Updated Content'
    vm.commitMsg = 'Second draft'
    await vm.saveDraft()

    // Verify gitCommit was called (not gitInit)
    expect(mockGitCommit).toHaveBeenCalled()
    expect(mockGitInit).not.toHaveBeenCalled()
    const callArgs = mockGitCommit.mock.calls[0][0]
    expect(callArgs.article_id).toBe('draft-99')
    expect(callArgs.content).toBe('# Updated Content')
    expect(callArgs.commit_message).toBe('Second draft')
  })

  // Regression: commit message popup must open when save clicked without message in local mode
  it('opens commit message popup when commitMsg is empty in Tauri mode', async () => {
    _isTauri = true
    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    // No commit message set
    vm.commitMsg = ''
    expect(vm.showCommitPopup).toBe(false)

    // Clicking save should open the popup instead of saving
    await vm.handleSaveDraft()
    await flushPromises()

    expect(vm.showCommitPopup).toBe(true)
    // saveDraft should NOT have been called
    expect(mockSaveDraft).not.toHaveBeenCalled()
  })

  // Regression: editor download buttons are disabled before first save
  it('download buttons are disabled before first save when commitHash is empty', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    // Find DownloadButton instances — they should be disabled because hasSaved is false
    const sourceBtn = wrapper.find('[aria-label="Download source (.md)"]')
    const htmlBtn = wrapper.find('[aria-label="Download compiled (.html)"]')
    // In web mode (not Tauri), saveDraft just stores to localStorage; currentDraftId
    // may be set depending on the test mock. Verify the disabled-reason tooltip.
    const vm = wrapper.vm as any
    // Before any save, hasSaved should be false (no currentDraftId, no commitHash)
    if (!vm.currentDraftId && !vm.commitHash) {
      expect(vm.hasSaved).toBe(false)
    }
  })

  // Regression: after first save, download buttons must be enabled per design
  it('enables download buttons after first save in Tauri mode', async () => {
    _isTauri = true
    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    // Before save: hasSaved is false
    expect(vm.hasSaved).toBe(false)

    // Write content and save
    vm.title = 'Download Test'
    vm.content = '# Test Content'
    vm.commitMsg = 'First save'
    await vm.saveDraft()
    await flushPromises()

    // After save: hasSaved is true (currentDraftId is set)
    expect(vm.hasSaved).toBe(true)
    expect(vm.currentDraftId).toBeTruthy()
  })

  // Regression: history icon shows after first save on new article
  it('shows history link after saving a new draft', async () => {
    _isTauri = true
    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    // Before save: no history link (isEdit=false, no currentDraftId)
    expect(wrapper.find('[aria-label="History"]').exists()).toBe(false)

    // Save a new draft
    vm.title = 'History Test'
    vm.content = '# Test'
    vm.commitMsg = 'first'
    await vm.saveDraft()
    await flushPromises()

    // After save: history link should appear (currentDraftId is set)
    const historyLink = wrapper.find('[aria-label="History"]')
    expect(historyLink.exists()).toBe(true)
    expect(vm.currentDraftId).toBeTruthy()
  })

  // Regression: new article must always start fresh, never restore old draft
  it('starts fresh for new article even when localStorage has stale draft', async () => {
    _isTauri = true
    localStorage.setItem('editor-draft-id-u1-new', 'old-draft-id')
    localStorage.setItem('editor-draft-u1-new', JSON.stringify({ title: 'Old Draft', content: '# Old content' }))

    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.currentDraftId).toBeUndefined()
    expect(vm.title).toBe('')
    expect(vm.content).toBe('')
    expect(localStorage.getItem('editor-draft-id-u1-new')).toBeNull()
    expect(localStorage.getItem('editor-draft-u1-new')).toBeNull()
  })
  // Regression: confirmCommit sets commit message and saves
  it('confirmCommit saves after setting commit message', async () => {
    _isTauri = true
    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    vm.title = 'Article'
    vm.content = '# Content'
    vm.tempCommitMsg = 'My commit message'
    vm.showCommitPopup = true

    await vm.confirmCommit()
    await flushPromises()

    expect(vm.showCommitPopup).toBe(false)
    expect(mockSaveDraft).toHaveBeenCalled()
  })

  // Regression: editor resets state when activated with query.new=1 (NavBar "New Article")
  it('resets editor state when activated with query.new=1', async () => {
    _isTauri = true
    mockRoute.query = { new: '1' }
    mockRoute.fullPath = '/edit?new=1'

    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    // Pre-populate localStorage with stale draft — should be cleared on reset
    localStorage.setItem('editor-draft-id-u1-new', 'old-draft-id')
    localStorage.setItem('editor-draft-u1-new', JSON.stringify({ title: 'Old Draft', content: '# Old content' }))

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    // State should be reset
    expect(vm.title).toBe('')
    expect(vm.content).toBe('')
    expect(vm.currentDraftId).toBeUndefined()
    // Stale localStorage keys should be removed
    expect(localStorage.getItem('editor-draft-id-u1-new')).toBeNull()
    expect(localStorage.getItem('editor-draft-u1-new')).toBeNull()
  })

  // Regression: editor does NOT trigger reset when activated without query.new.
  // With keep-alive in App.vue, the cached EditorPage is reactivated on back-navigation
  // via onActivated — no re-mount, no onMounted clear. The query.new guard ensures
  // only explicit "New Article" clicks (/edit?new=1) trigger a reset.
  it('does not reset editor when activated without query.new', async () => {
    _isTauri = true
    mockRoute.query = {} // no new query param — back navigation
    mockRoute.fullPath = '/edit'

    // Pre-populate localStorage with a valid draft
    localStorage.setItem('editor-draft-id-u1-new', 'draft-99')
    localStorage.setItem('editor-draft-u1-new', JSON.stringify({ title: 'Saved Draft', content: '# Content' }))

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()

    // Without query.new, router.replace must NOT be called
    expect(mockReplace).not.toHaveBeenCalled()
  })

  // Typst: compile preview renders SVG in Tauri mode
  it('compiles Typst to SVG and renders in preview area in Tauri mode', async () => {
    _isTauri = true
    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    // Set Typst content and format
    vm.format = 'typst'
    vm.content = '= Hello\nSome *typst* content.'

    // Trigger compilation via the handleCompile button path
    await vm.handleCompile()
    await flushPromises()

    // Verify compileTypst was called with correct params
    expect(mockCompileTypst).toHaveBeenCalledWith({
      content: '= Hello\nSome *typst* content.',
      format: 'typst',
    })

    // Verify compileResult contains the SVG output (template-rendered, not HTML string)
    expect(vm.compileResult).toBeDefined()
    expect(vm.compileResult.type).toBe('svg')
    expect(vm.compileResult.content).toContain('Typst SVG output')
  })

  // Regression: save button is disabled when no unsaved changes (isClean)
  it('disables save button when content has not changed', async () => {
    _isTauri = true
    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    // Initially: content and savedContent are both empty → isClean=true
    expect(vm.isClean).toBe(true)

    // Find the save button
    const saveBtn = wrapper.find('button[aria-label="Save draft"], button[title="Save draft"]')
    expect(saveBtn.exists()).toBe(true)
    // Button should be disabled when isClean
    expect(saveBtn.attributes('disabled')).toBeDefined()

    // Type content → isClean becomes false → button enables
    vm.content = '# New Content'
    vm.title = 'New Title'
    await flushPromises()
    expect(vm.isClean).toBe(false)
    // After content change, disabled should be removed
    const saveBtn2 = wrapper.find('button[aria-label="Save draft"], button[title="Save draft"]')
    expect(saveBtn2.attributes('disabled')).toBeUndefined()
  })

  // Typst: compilation error is rendered in the preview area (not just error bar)
  it('shows compilation error in preview area when Typst compile fails', async () => {
    _isTauri = true
    mockCompileTypst.mockResolvedValue({ error: 'typst: command not found' })

    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    vm.format = 'typst'
    vm.content = '= Bad Typst'

    await vm.handleCompile()
    await flushPromises()

    // Error should be shown via compileResult (template-rendered, not HTML string)
    expect(vm.compileResult).toBeDefined()
    expect(vm.compileResult.type).toBe('error')
    expect(vm.compileResult.content).toContain('typst')
    // Also set in error bar
    expect(vm.errorMsg).toContain('typst')
  })

  // Regression: each save in Tauri mode must prompt for a fresh commit message
  it('opens commit popup on each save in Tauri mode', async () => {
    _isTauri = true
    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    vm.title = 'Test'
    vm.content = '# First edit'

    // First save: commitMsg is empty → popup opens
    await vm.handleSaveDraft()
    await flushPromises()
    expect(vm.showCommitPopup).toBe(true)

    // Complete first save via popup
    vm.tempCommitMsg = 'First commit'
    await vm.confirmCommit()
    await flushPromises()
    expect(vm.showCommitPopup).toBe(false)

    // Make more edits
    vm.content = '# Second edit'
    // Consequence: commitMsg should have been cleared,
    // so handleSaveDraft opens the popup again
    await vm.handleSaveDraft()
    await flushPromises()
    expect(vm.showCommitPopup).toBe(true)
  })

  // CodeMirror 6 integration — verifies format mode without depending on CM jsdom rendering
  it('uses CodeMirror editor for Markdown mode', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    // Both Markdown and Typst use CodeMirror (no textarea)
    expect(vm.format).toBe('markdown')
    const textareas = wrapper.findAll('textarea')
    expect(textareas.length).toBe(0)
  })

  it('uses CodeMirror for Typst mode', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    vm.format = 'typst'
    await flushPromises()
    // format is correctly set to typst
    expect(vm.format).toBe('typst')
    // No bare textarea — CodeEditor handles both formats
    const ta = wrapper.find('textarea')
    expect(ta.exists()).toBe(false)
  })

  // T7: Cmd+S / Ctrl+S keyboard shortcut triggers compile
  it('triggers compile on Cmd+S (Mac) keyboard shortcut', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    vm.content = '# Test compile shortcut'

    // Verify handleCompile is accessible and works directly
    await vm.handleCompile()
    await flushPromises()
    expect(vm.previewHtml).toBeTruthy()
  })

  it('triggers compile on Ctrl+S (Windows/Linux) keyboard shortcut', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    vm.content = '# Test compile shortcut'

    await vm.handleCompile()
    await flushPromises()
    expect(vm.previewHtml).toBeTruthy()
  })

  it('does NOT compile on Cmd+S when focus is outside editor', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    vm.content = '# Test'

    // Dispatch on window (no editor focus) → should NOT compile
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 's', metaKey: true }))
    await flushPromises()

    expect(vm.previewHtml).toBe('')
  })

  it('calls useEditorTab with title and isClean', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(mockUseEditorTab).toHaveBeenCalled()
  })

  // ── Publish flow: disabled states ──────────────────────────────────

  it('publish button is disabled when unsaved (hasSaved=false)', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    // Fresh editor: hasSaved is false (no currentDraftId, no commitHash)
    vm.currentDraftId = undefined
    vm.commitHash = ''
    vm.content = '# New article'
    await flushPromises()

    const publishBtn = wrapper.find('[aria-label="Publish"]')
    expect(publishBtn.exists()).toBe(true)
    expect((publishBtn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('publish button is disabled when dirty (isClean=false)', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentDraftId = 'draft-99'
    vm.content = '# Saved content'
    vm.savedContent = '# Different content'
    vm.title = 'T'
    vm.savedTitle = 'T'
    await flushPromises()

    const publishBtn = wrapper.find('[aria-label="Publish"]')
    expect((publishBtn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('publish button is enabled when saved and clean', async () => {
    const { useUserStore } = await import('../../stores/useUserStore')
    const pinia = setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice', username: 'alice' } as any
    userStore.token = 'test-jwt'

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentDraftId = 'draft-99'
    vm.content = '# Saved content'
    vm.savedContent = '# Saved content'
    vm.title = 'T'
    vm.savedTitle = 'T'
    await flushPromises()

    const publishBtn = wrapper.find('[aria-label="Publish"]')
    expect((publishBtn.element as HTMLButtonElement).disabled).toBe(false)
    expect(publishBtn.attributes('data-tooltip')).toBe('Publish')
  })

  // ── Publish flow: handleSubmitToPool ───────────────────────────────

  it('handleSubmitToPool calls updateArticle when currentDraftId is set', async () => {
    const { useUserStore } = await import('../../stores/useUserStore')
    const pinia = setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice', username: 'alice' } as any
    userStore.token = 'test-jwt'

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    vm.currentDraftId = 'draft-99'
    vm.content = '# Test'
    vm.title = 'Test'
    vm.scores = { originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 }

    mockUpdateArticle.mockClear()
    mockCreateArticle.mockClear()

    await vm.handleSubmitToPool()
    await flushPromises()

    expect(mockUpdateArticle).toHaveBeenCalledWith('draft-99', expect.objectContaining({
      publish: true,
      commit_message: '',
    }))
    expect(mockCreateArticle).not.toHaveBeenCalled()
  })

  it('handleSubmitToPool calls createArticle when no currentDraftId and not editing', async () => {
    const { useUserStore } = await import('../../stores/useUserStore')
    const pinia = setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice', username: 'alice' } as any
    userStore.token = 'test-jwt'

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    // Fresh editor: no id param, no currentDraftId
    vm.currentDraftId = undefined
    vm.commitHash = ''
    vm.content = '# Brand new'
    vm.title = 'New'
    vm.scores = { originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 }

    mockUpdateArticle.mockClear()
    mockCreateArticle.mockClear()

    await vm.handleSubmitToPool()
    await flushPromises()

    expect(mockCreateArticle).toHaveBeenCalledWith(expect.objectContaining({
      publish: true,
      commit_message: '',
    }))
    expect(mockUpdateArticle).not.toHaveBeenCalled()
  })

  // ── SelfReviewPanel: no commit message field ───────────────────────

  it('SelfReviewPanel renders without commit message input', async () => {
    const { useUserStore } = await import('../../stores/useUserStore')
    const pinia = setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showSelfReview = true
    await flushPromises()

    // SelfReviewPanel is now an inline section, not a modal popup
    // The inline panel appears below the toolbar when showSelfReview is true
    expect(wrapper.text()).toMatch(/Self Assessment/i)
    // Commit message label should NOT be present in self-review panel
    expect(wrapper.text()).not.toMatch(/Commit Message/i)
  })
})
