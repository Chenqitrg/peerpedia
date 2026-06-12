import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import SyncButton from '../SyncButton.vue'

const mockConnect = vi.fn()
const mockDisconnect = vi.fn()
const mockConnectionState = ref<'idle' | 'connecting' | 'synced'>('idle')
const mockFlash = ref(false)

vi.mock('@/composables/useNetworkStatus', () => ({
  useNetworkStatus: () => ({
    connectionState: mockConnectionState,
    flash: mockFlash,
    connect: mockConnect,
    disconnect: mockDisconnect,
  }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

describe('SyncButton', () => {
  beforeEach(() => {
    mockConnectionState.value = 'idle'
    mockFlash.value = false
    mockConnect.mockClear()
    mockDisconnect.mockClear()
  })

  // ── Render: 32x32 icon-only button with corner dot ──────────────

  it('renders idle state: WifiOff icon, gray dot, no text', () => {
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-dot--idle').exists()).toBe(true)
    expect(wrapper.find('svg').exists()).toBe(true) // WifiOff
    expect(wrapper.text()).toBe('') // icon-only, no text label
    expect(wrapper.attributes('title')).toBe('nav.syncConnectAria')
  })

  it('renders connecting state: Wifi icon, white pulsing dot', () => {
    mockConnectionState.value = 'connecting'
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-dot--connecting').exists()).toBe(true)
    expect(wrapper.find('.sync-icon--connecting').exists()).toBe(true)
    expect(wrapper.attributes('title')).toBe('nav.syncConnecting')
  })

  it('renders synced state: Wifi icon, blue dot with glow', () => {
    mockConnectionState.value = 'synced'
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-btn--synced').exists()).toBe(true)
    expect(wrapper.find('.sync-dot--synced').exists()).toBe(true)
    expect(wrapper.find('.sync-icon--synced').exists()).toBe(true)
    expect(wrapper.attributes('title')).toBe('nav.syncDisconnectAria')
  })

  it('shows red flash dot', () => {
    mockConnectionState.value = 'idle'
    mockFlash.value = true
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-dot--flash').exists()).toBe(true)
    expect(wrapper.find('.sync-icon--flash').exists()).toBe(true)
  })

  // ── Fixed size ──────────────────────────────────────────────────

  it('has fixed width/height (32px icon button)', () => {
    const wrapper = mount(SyncButton)
    const btn = wrapper.find('button')
    expect(btn.attributes('style')).toBeFalsy() // no dynamic width
  })

  // ── Click behavior ──────────────────────────────────────────────

  it('calls connect() on click when idle', async () => {
    const wrapper = mount(SyncButton)
    await wrapper.trigger('click')
    expect(mockConnect).toHaveBeenCalledOnce()
  })

  it('calls disconnect() on click when synced', async () => {
    mockConnectionState.value = 'synced'
    const wrapper = mount(SyncButton)
    await wrapper.trigger('click')
    expect(mockDisconnect).toHaveBeenCalledOnce()
  })

  it('calls disconnect() on click when connecting (cancel)', async () => {
    mockConnectionState.value = 'connecting'
    const wrapper = mount(SyncButton)
    await wrapper.trigger('click')
    expect(mockDisconnect).toHaveBeenCalledOnce()
  })
})
