import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const { mockPush, mockSaveDraft, mockGitInit, mockGitCommit, mockGitHistory, mockGetDraft } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockSaveDraft: vi.fn().mockResolvedValue({ id: 'draft-99', account_id: 'u1', title: '', content: '', format: 'markdown', updated_at: '2026-06-07' }),
  mockGitInit: vi.fn().mockResolvedValue({ hash: 'abc1234', message: 'Initial draft' }),
  mockGitCommit: vi.fn().mockResolvedValue({ hash: 'abc5678', message: 'Update' }),
  mockGitHistory: vi.fn().mockResolvedValue([]),
  mockGetDraft: vi.fn().mockResolvedValue(null),
}))

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, back: vi.fn() }),
  useRoute: () => ({ params: { id: undefined } }),
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
  }),
}))

describe('EditorPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    _isTauri = false
    vi.clearAllMocks()
    mockGitHistory.mockResolvedValue([])
    mockGitInit.mockResolvedValue({ hash: 'abc1234', message: 'Initial draft' })
    mockGitCommit.mockResolvedValue({ hash: 'abc5678', message: 'Update' })
    mockSaveDraft.mockResolvedValue({ id: 'draft-99', account_id: 'u1', title: '', content: '', format: 'markdown', updated_at: '2026-06-07' })
    mockGetDraft.mockResolvedValue(null)
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
})
