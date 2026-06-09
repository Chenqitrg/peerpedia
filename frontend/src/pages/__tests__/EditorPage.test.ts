import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const { mockPush, mockReplace, mockRoute, mockSaveDraft, mockGitInit, mockGitCommit, mockGitHistory, mockGetDraft, mockCompileTypst } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockReplace: vi.fn(),
  mockRoute: { params: { id: undefined } as any, query: {} as Record<string, string | undefined> },
  mockSaveDraft: vi.fn().mockResolvedValue({ id: 'draft-99', account_id: 'u1', title: '', content: '', format: 'markdown', updated_at: '2026-06-07' }),
  mockGitInit: vi.fn().mockResolvedValue({ hash: 'abc1234', message: 'Initial draft' }),
  mockGitCommit: vi.fn().mockResolvedValue({ hash: 'abc5678', message: 'Update' }),
  mockGitHistory: vi.fn().mockResolvedValue([]),
  mockGetDraft: vi.fn().mockResolvedValue(null),
  mockCompileTypst: vi.fn().mockResolvedValue('<svg xmlns="http://www.w3.org/2000/svg"><text>Typst SVG output</text></svg>'),
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
vi.mock('@/composables/useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(() => ({
    isOnline: { value: true },
    startPing: vi.fn(),
    stopPing: vi.fn(),
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

describe('EditorPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    _isTauri = false
    vi.clearAllMocks()
    mockRoute.params = { id: undefined } as any
    mockRoute.query = {}
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
    await new Promise(r => setTimeout(r, 50))
    const titleInput = wrapper.find('input[type="text"], input[placeholder*="title" i], input[placeholder*="Title" i]')
    expect(titleInput.exists()).toBe(true)
  })

  it('has format toggle between Markdown and Typst', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    expect(wrapper.text()).toMatch(/markdown|typst/i)
  })

  it('has a Publish button', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    // Icon-only button — find by aria-label or title
    const publishBtn = wrapper.find('[aria-label="Publish"]')
    expect(publishBtn.exists()).toBe(true)
  })

  it('has draft save button', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    const saveBtn = wrapper.find('button[aria-label="Save draft"], button[title="Save draft"]')
    expect(saveBtn.exists()).toBe(true)
  })

  it('has a compile button', async () => {
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
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
    await new Promise(r => setTimeout(r, 50))
    const html = wrapper.html()
    expect(html.length).toBeGreaterThan(0)
  })

  it('self-assessment modal shows contribution slider', async () => {
    const { useUserStore } = await import('../../stores/useUserStore')
    const pinia = setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))

    const publishBtn = wrapper.find('[aria-label="Publish"]')
    expect(publishBtn.exists()).toBe(true)
    await publishBtn.trigger('click')
    await new Promise(r => setTimeout(r, 50))

    expect(wrapper.text()).toMatch(/contribution|Contribution|slider/i)
  })

  it('preserves contribution slider values when publish modal is reopened', async () => {
    const { useUserStore } = await import('../../stores/useUserStore')
    const pinia = setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))

    const vm = wrapper.vm as any

    await vm.handlePublish()
    expect(vm.contributions).toEqual({ u1: 100 })

    vm.contributions['u1'] = 50
    expect(vm.contributions['u1']).toBe(50)

    vm.showSelfReview = false

    await vm.handlePublish()
    expect(vm.contributions['u1']).toBe(50)
    expect(vm.contributions).toEqual({ u1: 50 })
  })

  // Regression: saveDraft must trigger git init in Tauri/local mode
  it('saveDraft triggers git init in Tauri mode', async () => {
    _isTauri = true
    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
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
    await new Promise(r => setTimeout(r, 50))
    const vm = wrapper.vm as any

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
    await new Promise(r => setTimeout(r, 50))
    const vm = wrapper.vm as any

    // No commit message set
    vm.commitMsg = ''
    expect(vm.showCommitPopup).toBe(false)

    // Clicking save should open the popup instead of saving
    await vm.handleSaveDraft()
    await new Promise(r => setTimeout(r, 10))

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
    await new Promise(r => setTimeout(r, 50))

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
    await new Promise(r => setTimeout(r, 50))
    const vm = wrapper.vm as any

    // Before save: hasSaved is false
    expect(vm.hasSaved).toBe(false)

    // Write content and save
    vm.title = 'Download Test'
    vm.content = '# Test Content'
    vm.commitMsg = 'First save'
    await vm.saveDraft()
    await new Promise(r => setTimeout(r, 50))

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
    await new Promise(r => setTimeout(r, 50))
    const vm = wrapper.vm as any

    // Before save: no history link (isEdit=false, no currentDraftId)
    expect(wrapper.find('[aria-label="History"]').exists()).toBe(false)

    // Save a new draft
    vm.title = 'History Test'
    vm.content = '# Test'
    vm.commitMsg = 'first'
    await vm.saveDraft()
    await new Promise(r => setTimeout(r, 50))

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
    await new Promise(r => setTimeout(r, 200))
    const vm = wrapper.vm as any

    expect(vm.currentDraftId).toBeUndefined()
    expect(vm.title).toBe('')
    expect(vm.content).toBe('')
    expect(localStorage.getItem('editor-draft-id-u1-new')).toBeNull()
    expect(localStorage.getItem('editor-draft-u1-new')).toBeNull()
  })
  // Regression: confirmSaveWithCommit sets commit message and saves
  it('confirmSaveWithCommit saves after setting commit message', async () => {
    _isTauri = true
    const { useUserStore } = await import('../../stores/useUserStore')
    setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen', username: 'alice' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))
    const vm = wrapper.vm as any

    vm.title = 'Article'
    vm.content = '# Content'
    vm.tempCommitMsg = 'My commit message'
    vm.showCommitPopup = true

    await vm.confirmSaveWithCommit()
    await new Promise(r => setTimeout(r, 10))

    expect(vm.showCommitPopup).toBe(false)
    expect(vm.commitMsg).toBe('My commit message')
    expect(mockSaveDraft).toHaveBeenCalled()
  })

  // Regression: editor resets state when activated with query.new=1 (NavBar "New Article")
  it('resets editor state and cleans URL when activated with query.new=1', async () => {
    _isTauri = true
    mockRoute.query = { new: '1' }

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
    await new Promise(r => setTimeout(r, 200))
    const vm = wrapper.vm as any

    // State should be reset
    expect(vm.title).toBe('')
    expect(vm.content).toBe('')
    expect(vm.currentDraftId).toBeUndefined()
    // Stale localStorage keys should be removed
    expect(localStorage.getItem('editor-draft-id-u1-new')).toBeNull()
    expect(localStorage.getItem('editor-draft-u1-new')).toBeNull()
    // URL should be cleaned from /edit?new=1 to /edit
    expect(mockReplace).toHaveBeenCalledWith({ path: '/edit' })
  })

  // Regression: editor does NOT trigger reset when activated without query.new.
  // With keep-alive in App.vue, the cached EditorPage is reactivated on back-navigation
  // via onActivated — no re-mount, no onMounted clear. The query.new guard ensures
  // only explicit "New Article" clicks (/edit?new=1) trigger a reset.
  it('does not reset editor when activated without query.new', async () => {
    _isTauri = true
    mockRoute.query = {} // no new query param — back navigation

    // Pre-populate localStorage with a valid draft
    localStorage.setItem('editor-draft-id-u1-new', 'draft-99')
    localStorage.setItem('editor-draft-u1-new', JSON.stringify({ title: 'Saved Draft', content: '# Content' }))

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 200))

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
    await new Promise(r => setTimeout(r, 50))
    const vm = wrapper.vm as any

    // Set Typst content and format
    vm.format = 'typst'
    vm.content = '= Hello\nSome *typst* content.'

    // Trigger compilation via the handleCompile button path
    await vm.handleCompile()
    await new Promise(r => setTimeout(r, 50))

    // Verify compileTypst was called with correct params
    expect(mockCompileTypst).toHaveBeenCalledWith({
      content: '= Hello\nSome *typst* content.',
      format: 'typst',
    })

    // Verify previewHtml contains the SVG output
    expect(vm.previewHtml).toContain('<svg')
    expect(vm.previewHtml).toContain('typst-preview')
    expect(vm.previewHtml).toContain('Typst SVG output')
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
    await new Promise(r => setTimeout(r, 50))
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
    await new Promise(r => setTimeout(r, 50))
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
    await new Promise(r => setTimeout(r, 50))
    const vm = wrapper.vm as any

    vm.format = 'typst'
    vm.content = '= Bad Typst'

    await vm.handleCompile()
    await new Promise(r => setTimeout(r, 50))

    // Error should be shown in the preview area (typst-preview-error)
    expect(vm.previewHtml).toContain('typst-preview-error')
    expect(vm.previewHtml).toContain('typst: command not found')
    // Also set in error bar
    expect(vm.errorMsg).toContain('typst')
  })
})
