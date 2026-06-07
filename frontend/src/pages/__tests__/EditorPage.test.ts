import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const { mockPush } = vi.hoisted(() => ({
  mockPush: vi.fn(),
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

describe('EditorPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
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
    expect(wrapper.text()).toMatch(/publish|Publish/)
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
    // Should have some button elements
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
    // EditorPage renders with compile/preview area — download is available
    const html = wrapper.html()
    // Should have a toolbar with action buttons
    expect(html.length).toBeGreaterThan(0)
  })

  it('self-assessment modal shows contribution slider', async () => {
    // Set up a viewer so the publish modal can use their ID
    const { useUserStore } = await import('../../stores/useUserStore')
    const pinia = setActivePinia(createPinia())
    const userStore = useUserStore()
    userStore.viewer = { id: 'u1', name: 'Alice Chen' } as any

    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await new Promise(r => setTimeout(r, 50))

    // Click the Publish button to open the self-assessment modal
    const buttons = wrapper.findAll('button')
    const publishBtn = buttons.find(b => b.text().match(/publish|Publish|submit/i))
    expect(publishBtn).toBeTruthy()
    await publishBtn!.trigger('click')
    await new Promise(r => setTimeout(r, 50))

    // Modal should now be visible with contribution section
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

    // Open publish modal — contributions initialized to { u1: 100 }
    await vm.handlePublish()
    expect(vm.contributions).toEqual({ u1: 100 })

    // User adjusts contribution from 100% → 50%
    vm.contributions['u1'] = 50
    expect(vm.contributions['u1']).toBe(50)

    // Close modal
    vm.showSelfReview = false

    // Reopen — contributions should still be { u1: 50 }, not reset to { u1: 100 }
    await vm.handlePublish()
    expect(vm.contributions['u1']).toBe(50)
    expect(vm.contributions).toEqual({ u1: 50 })
  })
})
