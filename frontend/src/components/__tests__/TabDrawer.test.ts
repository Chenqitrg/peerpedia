import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useTabStore } from '../../stores/useTabStore'
import TabDrawer from '../TabDrawer.vue'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mockPush }) }))

describe('TabDrawer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    mockPush.mockClear()
  })

  it('renders nothing when no tabs', () => {
    expect(mount(TabDrawer).find('.tab-drawer-edges').exists()).toBe(false)
  })

  it('renders stacked edges when tabs open', () => {
    const s = useTabStore()
    s.ensureTab('editor', '/edit/a')
    s.ensureTab('article', '/article/b')
    const wrapper = mount(TabDrawer)
    expect(wrapper.findAll('.tab-drawer-edge')).toHaveLength(2)
  })

  it('expands drawer on mouseenter and shows tab titles', async () => {
    const s = useTabStore()
    const id = s.ensureTab('editor', '/edit/a')
    s.updateTab(id, { title: 'My Draft' })
    const wrapper = mount(TabDrawer)
    await wrapper.find('.tab-drawer-edges').trigger('mouseenter')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.tab-drawer-panel').exists()).toBe(true)
    expect(wrapper.text()).toContain('My Draft')
  })

  it('highlights active tab', async () => {
    const s = useTabStore()
    const idA = s.ensureTab('editor', '/edit/a')
    s.ensureTab('editor', '/edit/b')
    s.activateTab(idA)
    const wrapper = mount(TabDrawer)
    await wrapper.find('.tab-drawer-edges').trigger('mouseenter')
    await wrapper.vm.$nextTick()
    const items = wrapper.findAll('.tab-drawer-item')
    expect(items[0].classes()).toContain('tab-drawer-item--active')
    expect(items[1].classes()).not.toContain('tab-drawer-item--active')
  })

  it('shows dirty dot on dirty editor tab', async () => {
    const s = useTabStore()
    const id = s.ensureTab('editor', '/edit/a')
    s.updateTab(id, { dirty: true })
    const wrapper = mount(TabDrawer)
    await wrapper.find('.tab-drawer-edges').trigger('mouseenter')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.tab-drawer-dirty-dot').exists()).toBe(true)
  })

  it('emits close-tab with UUID when close button clicked', async () => {
    const s = useTabStore()
    const id = s.ensureTab('editor', '/edit/a')
    const wrapper = mount(TabDrawer)
    await wrapper.find('.tab-drawer-edges').trigger('mouseenter')
    await wrapper.vm.$nextTick()
    await wrapper.find('.tab-drawer-close-btn').trigger('click')
    expect(wrapper.emitted('close-tab')![0]).toEqual([id])
  })
})
