// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'

const mockPendingConflictCount = ref(0)

vi.mock('vue-router', () => ({
  useRouter: () => ({ afterEach: vi.fn(), beforeEach: vi.fn() }),
  useRoute: () => ({ path: '/' }),
  RouterLink: { template: '<a><slot /></a>' },
}))

// Mock router module — App.vue + NavBar.vue import pendingConflictCount from it
vi.mock('../router', () => ({
  pendingConflictCount: mockPendingConflictCount,
  default: [],
}))

// Mock useTabStore
const mockTabStore = {
  tabs: [{ id: '/edit/test', type: 'editor', title: 'Test', dirty: false, icon: 'edit', status: 'draft' }],
  activeTabId: '/edit/test',
  openTab: vi.fn(),
  closeTab: vi.fn().mockReturnValue({ shouldPrompt: false }),
  removeTab: vi.fn(),
  activateTab: vi.fn(),
  updateTab: vi.fn(),
  restoreTabs: vi.fn(),
}
vi.mock('@/stores/useTabStore', () => ({
  useTabStore: () => mockTabStore,
}))

// Stub TabDrawer
vi.mock('@/components/TabDrawer.vue', () => ({
  default: {
    name: 'TabDrawer',
    template: '<div class="tab-drawer-stub"><slot /></div>',
    emits: ['close-tab'],
  },
}))

describe('App shell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockTabStore.closeTab.mockReturnValue({ shouldPrompt: false })
  })

  it('renders NavBar and router-view', async () => {
    const { default: App } = await import('../App.vue')
    const wrapper = mount(App, { global: { stubs: { NavBar: true, AuthModal: true, 'router-view': true } } })
    expect(wrapper.findComponent({ name: 'NavBar' }).exists()).toBe(true)
  })

  it('has dark page background class', async () => {
    const { default: App } = await import('../App.vue')
    const wrapper = mount(App, { global: { stubs: { NavBar: true, AuthModal: true, 'router-view': true } } })
    expect(wrapper.classes()).toEqual(
      expect.arrayContaining([expect.stringMatching(/bg-/)]),
    )
  })

  it('renders TabDrawer when tabs are open', async () => {
    const { default: App } = await import('../App.vue')
    const wrapper = mount(App, { global: { stubs: { NavBar: true, AuthModal: true, 'router-view': true } } })
    expect(wrapper.findComponent({ name: 'TabDrawer' }).exists()).toBe(true)
  })

  it('shows close confirmation dialog when closing dirty tab', async () => {
    mockTabStore.closeTab.mockReturnValue({ shouldPrompt: true })
    const { default: App } = await import('../App.vue')
    const wrapper = mount(App, { global: { stubs: { NavBar: true, AuthModal: true, 'router-view': true } } })

    // Simulate close-tab event from TabDrawer
    await wrapper.findComponent({ name: 'TabDrawer' }).vm.$emit('close-tab', '/edit/test')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Save before closing')
  })
})
