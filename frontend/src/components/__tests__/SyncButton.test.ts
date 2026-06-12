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

  // ── Render states ─────────────────────────────────────────────────

  it('renders idle state with WifiOff icon and Sync text', () => {
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-btn--idle').exists()).toBe(true)
    expect(wrapper.find('.sync-label').text()).toBe('nav.syncIdle')
    expect(wrapper.find('svg').exists()).toBe(true) // WifiOff
    expect(wrapper.attributes('aria-label')).toBe('nav.syncConnectAria')
  })

  it('renders connecting state with pulsing dot and Connecting text', () => {
    mockConnectionState.value = 'connecting'
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-btn--connecting').exists()).toBe(true)
    expect(wrapper.find('.sync-dot--connecting').exists()).toBe(true)
    expect(wrapper.find('.sync-label').text()).toBe('nav.syncConnecting')
  })

  it('renders synced state with Wifi icon and Synced text', () => {
    mockConnectionState.value = 'synced'
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-btn--synced').exists()).toBe(true)
    expect(wrapper.find('.sync-dot--synced').exists()).toBe(true)
    expect(wrapper.find('.sync-label').text()).toBe('nav.syncSynced')
    expect(wrapper.attributes('aria-label')).toBe('nav.syncDisconnectAria')
  })

  it('shows red flash dot when flash is true', () => {
    mockConnectionState.value = 'idle'
    mockFlash.value = true
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-btn--flash').exists()).toBe(true)
    expect(wrapper.find('.sync-dot--flash').exists()).toBe(true)
    // When flashing, idle class is suppressed (idle && !flash)
    expect(wrapper.find('.sync-btn--idle').exists()).toBe(false)
  })

  // ── Click behavior ────────────────────────────────────────────────

  it('calls connect() on click when idle', async () => {
    const wrapper = mount(SyncButton)
    await wrapper.trigger('click')
    expect(mockConnect).toHaveBeenCalledOnce()
    expect(mockDisconnect).not.toHaveBeenCalled()
  })

  it('calls disconnect() on click when synced', async () => {
    mockConnectionState.value = 'synced'
    const wrapper = mount(SyncButton)
    await wrapper.trigger('click')
    expect(mockDisconnect).toHaveBeenCalledOnce()
    expect(mockConnect).not.toHaveBeenCalled()
  })

  it('calls disconnect() on click when connecting (cancel)', async () => {
    mockConnectionState.value = 'connecting'
    const wrapper = mount(SyncButton)
    await wrapper.trigger('click')
    expect(mockDisconnect).toHaveBeenCalledOnce()
    expect(mockConnect).not.toHaveBeenCalled()
  })
})
